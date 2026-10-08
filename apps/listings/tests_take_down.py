"""W1.6 — a seller can take a listing down.

The terms page promised "take it down whenever" and "you can cancel a lot
until the first bid is in", but nothing ended a live listing.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.models import Bid
from apps.collections.models import CollectionItem
from apps.collections.tradeability import is_open_to_trade
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.offers.models import Offer


class TakeDownTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('td_seller', password='pw')
        cls.buyer = User.objects.create_user('td_buyer', password='pw')

    def setUp(self):
        self.client.force_login(self.seller)

    def _store(self, **kwargs):
        piece = CollectionItem.objects.create(
            owner=self.seller, title='1931 Clinton', license_year=1931, condition_grade='good')
        defaults = dict(seller=self.seller, listing_type='buy_now', title='1931 Clinton',
                        description='x', condition_grade='good', buy_now_price=Decimal('40'),
                        status='active', allow_offers=True, source_collection_item=piece)
        defaults.update(kwargs)
        return Listing.objects.create(**defaults)

    def _auction(self, **kwargs):
        return self._store(listing_type='auction', buy_now_price=None,
                           starting_price=Decimal('10'), bid_increment=Decimal('1'),
                           auction_end=timezone.now() + timedelta(days=3), **kwargs)

    def _take_down(self, listing):
        return self.client.post(reverse('listings:take_down', args=[listing.pk]))

    def test_a_store_listing_comes_down_and_its_offers_close_with_a_note(self):
        listing = self._store()
        offer = Offer.objects.create(listing=listing, from_user=self.buyer, to_user=self.seller,
                                     amount=Decimal('30'), status='pending')
        self.assertRedirects(self._take_down(listing), reverse('listings:my_listings'),
                             fetch_redirect_response=False)
        listing.refresh_from_db()
        offer.refresh_from_db()
        self.assertEqual(listing.status, 'cancelled')
        self.assertEqual(offer.status, 'declined')
        note = Notification.objects.get(user=self.buyer)
        self.assertIn('taken off the market', note.message)
        # The piece is back on the shelf, open to trade again.
        self.assertTrue(is_open_to_trade(listing.source_collection_item))

    def test_a_lot_comes_down_until_the_first_bid(self):
        quiet = self._auction()
        self._take_down(quiet)
        quiet.refresh_from_db()
        self.assertEqual(quiet.status, 'cancelled')

        bid_on = self._auction()
        Bid.objects.create(listing=bid_on, bidder=self.buyer, amount=Decimal('12'))
        self._take_down(bid_on)
        bid_on.refresh_from_db()
        self.assertEqual(bid_on.status, 'active')

    def test_not_while_someone_is_paying(self):
        listing = self._store(status='pending')
        self._take_down(listing)
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')

    def test_only_the_seller(self):
        listing = self._store()
        self.client.force_login(self.buyer)
        self.assertEqual(self._take_down(listing).status_code, 404)

    def test_without_javascript_it_asks_first(self):
        listing = self._store()
        resp = self.client.get(reverse('listings:take_down', args=[listing.pk]))
        self.assertContains(resp, 'off the market?')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')

    def test_the_edit_page_offers_it_or_says_why_not(self):
        listing = self._store()
        resp = self.client.get(reverse('listings:edit', args=[listing.pk]))
        self.assertContains(resp, 'data-kb-confirm-ok="Take it down"')

        lot = self._auction()
        Bid.objects.create(listing=lot, bidder=self.buyer, amount=Decimal('12'))
        resp = self.client.get(reverse('listings:edit', args=[lot.pk]))
        self.assertContains(resp, 'bids stand')
        self.assertNotContains(resp, 'data-kb-confirm-ok="Take it down"')
