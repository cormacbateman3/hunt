"""My listings — the Interest column, and the honest observations beside it.

The column exists so a seller can tell how a listing is *doing*, not just
what state it is in. What matters most is that anything waiting on them wins
the row: an unanswered offer or question takes the edge marker and the only
filled button, whatever else is going on.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.core.models import GeographicUnit, State
from apps.favorites.models import Favorite
from apps.listings import seller_desk
from apps.listings.models import Listing, ListingQuestion
from apps.offers.models import Offer


class DeskBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('sd_seller', password='pw')
        cls.buyer = User.objects.create_user('sd_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        cls.unit = GeographicUnit.objects.create(
            state=cls.pa, name='Lycoming', slug='sd-lycoming')

    def _listing(self, **kwargs):
        defaults = {
            'seller': self.seller, 'title': 'A licence', 'description': 'd',
            'state': self.pa, 'county_ref': self.unit, 'condition_grade': 'good',
            'status': 'active', 'listing_type': 'buy_now',
            'buy_now_price': Decimal('200'), 'license_year': 1934,
        }
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def _offer(self, listing, **kwargs):
        return Offer.objects.create(
            listing=listing, from_user=self.buyer, to_user=self.seller,
            amount=Decimal('150'), status=kwargs.pop('status', 'pending'), **kwargs)

    def _rows(self, status_key=''):
        return seller_desk.rows(self.seller, status_key)


class SellerDeskTests(DeskBase):
    # ── Interest ─────────────────────────────────────────────────────────
    def test_interest_counts_offers_questions_and_bids(self):
        listing = self._listing(listing_type='auction', starting_price=Decimal('40'),
                                buy_now_price=None,
                                auction_end=timezone.now() + timedelta(days=3))
        Bid.objects.create(listing=listing, bidder=self.buyer, amount=Decimal('50'))
        ListingQuestion.objects.create(listing=listing, asker=self.buyer, question='?')
        Favorite.objects.create(user=self.buyer, listing=listing)

        row = self._rows()['rows'][0]
        labels = [chip['label'] for chip in row['interest']]
        self.assertIn('1 question', labels)
        self.assertIn('1 bid', labels)
        self.assertEqual(row['watchers'], '1 watching')

    def test_an_answered_question_stops_counting(self):
        listing = self._listing()
        question = ListingQuestion.objects.create(
            listing=listing, asker=self.buyer, question='?')
        self.assertEqual(self._rows()['rows'][0]['interest'][0]['label'], '1 question')

        question.seller_answer = 'Yes.'
        question.answered_at = timezone.now()
        question.save()
        self.assertEqual(self._rows()['rows'][0]['interest'], [])

    def test_a_hidden_question_never_counts(self):
        listing = self._listing()
        ListingQuestion.objects.create(
            listing=listing, asker=self.buyer, question='?', moderation_state='hidden')
        self.assertEqual(self._rows()['rows'][0]['interest'], [])

    def test_a_settled_offer_stops_counting(self):
        listing = self._listing(allow_offers=True)
        offer = self._offer(listing)
        self.assertTrue(self._rows()['rows'][0]['needs_you'])

        offer.status = 'declined'
        offer.save()
        self.assertFalse(self._rows()['rows'][0]['needs_you'])

    # ── Anything waiting on the seller wins the row ──────────────────────
    def test_an_open_offer_takes_the_edge_and_the_filled_button(self):
        listing = self._listing(allow_offers=True)
        self._offer(listing)
        row = self._rows()['rows'][0]
        self.assertTrue(row['needs_you'])
        self.assertEqual(row['action']['style'], 'primary')
        self.assertEqual(row['action']['label'], 'See offers')
        self.assertEqual(row['headline'], 'People waiting on you')

    def test_waiting_beats_a_closing_auction(self):
        """A lot closing in minutes still loses to somebody waiting on a
        reply — the reply is the only thing that can lose the sale."""
        listing = self._listing(
            listing_type='auction', starting_price=Decimal('40'), buy_now_price=None,
            auction_end=timezone.now() + timedelta(minutes=20))
        ListingQuestion.objects.create(listing=listing, asker=self.buyer, question='?')
        row = self._rows()['rows'][0]
        self.assertEqual(row['action']['label'], 'Answer')
        self.assertEqual(row['headline'], 'People waiting on you')

    def test_a_quiet_row_gets_a_text_action_not_a_button(self):
        self._listing(listing_type='auction', starting_price=Decimal('40'),
                      buy_now_price=None,
                      auction_end=timezone.now() + timedelta(days=5))
        row = self._rows()['rows'][0]
        self.assertFalse(row['needs_you'])
        self.assertEqual(row['action']['style'], 'text')

    # ── Honest observations ──────────────────────────────────────────────
    def test_a_quiet_listing_suggests_a_price(self):
        listing = self._listing(buy_now_price=Decimal('200'))
        Listing.objects.filter(pk=listing.pk).update(
            created_at=timezone.now() - timedelta(days=19))
        for name in ('w1', 'w2', 'w3'):
            Favorite.objects.create(
                user=User.objects.create_user(name), listing=listing)

        row = self._rows()['rows'][0]
        self.assertEqual(row['note'], 'Quiet — try $170?')

    def test_nothing_is_suggested_before_there_is_evidence(self):
        listing = self._listing()
        Listing.objects.filter(pk=listing.pk).update(
            created_at=timezone.now() - timedelta(days=19))
        # Watched by nobody: "the price is wrong" is not a supportable reading.
        self.assertEqual(self._rows()['rows'][0]['note'], 'Nobody has looked yet')

    def test_a_young_listing_is_left_alone(self):
        self._listing()
        self.assertEqual(self._rows()['rows'][0]['note'], '')

    def test_an_unsold_listing_counts_its_relists_down(self):
        self._listing(status='expired', relist_count=2)
        self.assertEqual(self._rows()['rows'][0]['note'], '1 relist left of 3')

    def test_a_spent_listing_says_so(self):
        self._listing(status='expired', relist_count=3)
        row = self._rows()['rows'][0]
        self.assertEqual(row['note'], 'No relists left')
        self.assertNotEqual(row['action']['label'], 'List it again')

    def test_reserve_is_reported_both_ways(self):
        listing = self._listing(
            listing_type='auction', starting_price=Decimal('40'), buy_now_price=None,
            reserve_price=Decimal('150'),
            auction_end=timezone.now() + timedelta(minutes=30))
        self.assertIn('Reserve not met', self._rows()['rows'][0]['note'])

        Bid.objects.create(listing=listing, bidder=self.buyer, amount=Decimal('160'))
        Listing.objects.filter(pk=listing.pk).update(current_bid=Decimal('160'))
        self.assertIn('Reserve met', self._rows()['rows'][0]['note'])

    # ── Filters ──────────────────────────────────────────────────────────
    def test_filters_count_every_state_even_when_one_is_showing(self):
        self._listing()
        self._listing(status='sold')
        self._listing(status='expired')
        self._listing(status='draft')

        page = self._rows('sold')
        counts = {row['key']: row['count'] for row in page['filters']}
        self.assertEqual(counts, {'live': 1, 'drafts': 1, 'scheduled': 0,
                                  'sold': 1, 'unsold': 1})
        self.assertEqual(len(page['rows']), 1)

    def test_a_draft_row_points_at_the_terms(self):
        draft = self._listing(status='draft')
        row = self._rows('drafts')['rows'][0]
        self.assertEqual(row['headline'], 'Still a draft')
        self.assertEqual(row['action']['label'], 'Finish the terms')
        self.assertIn(f'/listings/{draft.pk}/terms/', row['action']['url'])

    def test_an_unknown_filter_shows_everything(self):
        self._listing()
        self.assertEqual(len(self._rows('nonsense')['rows']), 1)

    def test_only_your_own_listings_appear(self):
        Listing.objects.create(
            seller=self.buyer, title='Theirs', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='buy_now',
            buy_now_price=Decimal('10'))
        self.assertEqual(self._rows()['rows'], [])


class MyListingsPageTests(DeskBase):
    def test_the_page_renders_the_interest_column(self):
        listing = self._listing(allow_offers=True)
        self._offer(listing)

        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:my_listings'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Interest')
        self.assertContains(resp, '1 offer')
        self.assertContains(resp, 'People waiting on you')

    def test_the_page_needs_a_login(self):
        resp = self.client.get(reverse('listings:my_listings'))
        self.assertEqual(resp.status_code, 302)

    def test_an_empty_desk_offers_the_way_in(self):
        self.client.force_login(self.seller)
        resp = self.client.get(reverse('listings:my_listings'))
        self.assertContains(resp, 'haven&rsquo;t listed anything yet')
