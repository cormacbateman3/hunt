"""UX revamp: Hunt as one catalog, and the listing-detail decision panel."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.collections.models import CollectionItem
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing


class HuntCatalogTests(TestCase):
    """Format is a filter, not a destination."""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('hunt_seller', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        common = {
            'seller': cls.seller, 'description': 'd', 'state': cls.pa,
            'condition_grade': 'good', 'status': 'active', 'license_year': 1934,
        }
        cls.auction = Listing.objects.create(
            title='Auction item', listing_type='auction',
            starting_price=Decimal('10'),
            auction_end=timezone.now() + timedelta(days=2), **common)
        cls.store = Listing.objects.create(
            title='Store item', listing_type='buy_now',
            buy_now_price=Decimal('50'), local_pickup_available=True, **common)
        cls.swap = Listing.objects.create(
            title='Trade item', listing_type='trade',
            trade_notes='Wants Cameron', **common)

    def test_pillar_urls_redirect_permanently_into_hunt(self):
        for name, fmt in [('listings:auction_house', 'auction'),
                          ('listings:general_store', 'buy_now'),
                          ('listings:trading_block', 'trade')]:
            with self.subTest(name=name):
                resp = self.client.get(reverse(name))
                self.assertEqual(resp.status_code, 301)
                self.assertTrue(resp.headers['Location'].startswith(reverse('hunt')))
                self.assertIn('format=' + fmt, resp.headers['Location'])

    def test_pillar_redirect_keeps_existing_filters(self):
        resp = self.client.get(reverse('listings:general_store') + '?year_min=1930')
        self.assertEqual(resp.status_code, 301)
        self.assertIn('year_min=1930', resp.headers['Location'])

    def test_unfiltered_hunt_holds_every_format_in_one_grid(self):
        resp = self.client.get(reverse('hunt'))
        self.assertEqual(resp.status_code, 200)
        for listing in (self.auction, self.store, self.swap):
            self.assertContains(resp, listing.title)

    def test_format_filter_narrows_the_catalog(self):
        resp = self.client.get(reverse('hunt'), {'format': 'trade'})
        self.assertContains(resp, self.swap.title)
        self.assertNotContains(resp, self.auction.title)

    def test_facets_count_every_format_not_only_the_selected_one(self):
        """Counts are measured with the format filter removed, so the rail
        still says how much widening would give back."""
        resp = self.client.get(reverse('hunt'), {'format': 'trade'})
        counts = {f['key']: f['count'] for f in resp.context['hunt_formats']}
        self.assertEqual(counts, {'auction': 1, 'buy_now': 1, 'trade': 1})
        checked = {f['key'] for f in resp.context['hunt_formats'] if f['checked']}
        self.assertEqual(checked, {'trade'})

    def test_pickup_facet_counts_within_the_current_filters(self):
        self.assertEqual(self.client.get(reverse('hunt')).context['pickup_count'], 1)
        narrowed = self.client.get(reverse('hunt'), {'format': 'trade'})
        self.assertEqual(narrowed.context['pickup_count'], 0)

    def test_topbar_q_drives_the_same_query_as_the_in_page_search(self):
        resp = self.client.get(reverse('hunt'), {'q': 'Trade item'})
        self.assertContains(resp, self.swap.title)
        self.assertNotContains(resp, self.store.title)

    def test_a_filter_chip_removes_only_its_own_filter(self):
        resp = self.client.get(reverse('hunt'), {'format': ['trade', 'auction']})
        chips = resp.context['applied_filters']
        trade_chip = next(c for c in chips if c['label'] == 'Open to trade')
        self.assertNotIn('format=trade', trade_chip['url'])
        self.assertIn('format=auction', trade_chip['url'])

    def test_wants_tab_is_empty_for_a_collector_with_no_wants(self):
        buyer = User.objects.create_user('wants_buyer', password='pw')
        self.client.force_login(buyer)
        resp = self.client.get(reverse('hunt'), {'tab': 'wants'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(list(resp.context['listings']), [])


class ListingDetailDecisionPanelTests(TestCase):
    """The bid panel is the only reason the page exists.

    The old grid was `2fr 1fr` with three children, so the seller card took
    the top-right cell and the bid panel wrapped into the wide left column
    below the image — under the fold.
    """

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('detail_seller', password='pw')
        cls.buyer = User.objects.create_user('detail_buyer', password='pw')
        cls.buyer.profile.email_verified = True
        cls.buyer.profile.save()
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'},
        )
        cls.listing = Listing.objects.create(
            seller=cls.seller, title='1934 Lycoming Resident', description='d',
            state=cls.pa, condition_grade='good', status='active',
            listing_type='auction', starting_price=Decimal('100'),
            license_year=1934, auction_end=timezone.now() + timedelta(days=2),
        )

    def _get(self, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(reverse('listings:detail', args=[self.listing.pk]))

    def test_the_grid_has_exactly_two_children(self):
        html = self._get(self.buyer).content.decode()
        self.assertEqual(html.count('class="lst-main"'), 1)
        self.assertEqual(html.count('class="lst-rail"'), 1)

    def test_the_bid_form_is_inside_the_decision_rail(self):
        html = self._get(self.buyer).content.decode()
        rail_at = html.index('class="lst-rail"')
        form_at = html.index('data-bid-form')
        self.assertGreater(form_at, rail_at)

    def test_quick_bid_amounts_all_clear_the_minimum(self):
        resp = self._get(self.buyer)
        minimum = Decimal(resp.context['minimum_bid'])
        quick = resp.context['quick_bids']
        self.assertTrue(quick)
        self.assertEqual(quick[0], minimum)
        for amount in quick[1:]:
            self.assertGreater(amount, minimum)
        self.assertEqual(len(quick), len(set(quick)))

    def test_gap_panel_says_whether_the_collector_already_owns_it(self):
        unit = GeographicUnit.objects.create(
            state=self.pa, name='Lycoming', slug='pa-lycoming')
        self.listing.county_ref = unit
        self.listing.save(update_fields=['county_ref'])

        gap = self._get(self.buyer).context['viewer_gap']
        self.assertFalse(gap['have'])
        self.assertTrue(gap['new_unit'])

        CollectionItem.objects.create(
            owner=self.buyer, title='mine', state=self.pa, county=unit,
            license_year=1934, condition_grade='good')
        self.assertTrue(self._get(self.buyer).context['viewer_gap']['have'])

    def test_no_gap_panel_on_your_own_listing(self):
        self.assertIsNone(self._get(self.seller).context['viewer_gap'])

    def test_anonymous_visitor_is_offered_sign_in_rather_than_a_bid_form(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Sign in to bid')
        self.assertNotContains(resp, 'data-bid-form')
