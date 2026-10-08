"""W1.22 — the Market's sort and filter, as a buyer would expect them.

- The state rail opened on the 10.21 default while the results ignored it.
- "Price" sorted on starting_price alone, so every Store listing sat at one end.
- NULLs sorted first on SQLite and last on Postgres ("Ending soonest").
- "Newly listed" used created_at, not the listed date.
- A typed year that wasn't a number crashed the page.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.core.models import State
from apps.listings.models import Listing


class MarketSortAndFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('ms_seller', password='pw')
        cls.bidder = User.objects.create_user('ms_bidder', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'is_primary_default': True})
        cls.md, _ = State.objects.get_or_create(
            code='MD', defaults={'name': 'Maryland', 'slug': 'maryland'})
        common = {'seller': cls.seller, 'description': 'd', 'condition_grade': 'good',
                  'status': 'active', 'license_year': 1934}
        now = timezone.now()
        cls.store_cheap = Listing.objects.create(
            title='Store at 15', listing_type='buy_now', buy_now_price=Decimal('15'),
            state=cls.pa, published_at=now - timedelta(days=3), **common)
        cls.store_dear = Listing.objects.create(
            title='Store at 90', listing_type='buy_now', buy_now_price=Decimal('90'),
            state=cls.pa, published_at=now - timedelta(days=1), **common)
        cls.lot = Listing.objects.create(
            title='Lot bid to 50', listing_type='auction', starting_price=Decimal('10'),
            auction_end=now + timedelta(days=2), state=cls.pa,
            published_at=now - timedelta(days=2), **common)
        Bid.objects.create(listing=cls.lot, bidder=cls.bidder, amount=Decimal('50'))
        cls.maryland = Listing.objects.create(
            title='Maryland piece', listing_type='buy_now', buy_now_price=Decimal('30'),
            state=cls.md, **common)

    def _titles(self, **params):
        resp = self.client.get(reverse('hunt'), params)
        return [listing.title for listing in resp.context['listings']]

    def test_price_sorts_by_what_a_buyer_faces(self):
        titles = self._titles(state_id=self.pa.pk, sort='price_asc')
        self.assertEqual(titles, ['Store at 15', 'Lot bid to 50', 'Store at 90'])
        titles = self._titles(state_id=self.pa.pk, sort='price_desc')
        self.assertEqual(titles, ['Store at 90', 'Lot bid to 50', 'Store at 15'])

    def test_ending_soonest_puts_lots_with_a_clock_first(self):
        titles = self._titles(state_id=self.pa.pk, sort='ending')
        self.assertEqual(titles[0], 'Lot bid to 50')

    def test_newly_listed_uses_the_listed_date(self):
        titles = self._titles(state_id=self.pa.pk, sort='new')
        self.assertEqual(titles, ['Store at 90', 'Lot bid to 50', 'Store at 15'])

    def test_the_rail_and_the_results_agree_on_the_state(self):
        resp = self.client.get(reverse('hunt'))
        self.assertEqual(resp.context['selected_state'], self.pa)   # the 10.21 default
        titles = [listing.title for listing in resp.context['listings']]
        self.assertNotIn('Maryland piece', titles)
        self.assertContains(resp, 'Every state')

    def test_every_state_widens_it(self):
        self.assertIn('Maryland piece', self._titles(state_id=''))

    def test_a_year_that_isnt_a_number_is_ignored_not_a_crash(self):
        resp = self.client.get(reverse('hunt'), {'year_min': 'abc', 'year_max': '19x0'})
        self.assertEqual(resp.status_code, 200)
