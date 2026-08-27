"""The soft close, and the room's one payload.

A bid inside the final two minutes resets the clock to two minutes —
sniping buys nothing but everyone else a fair answer. Effectively
unbounded (each reset demands new money, so a war converges on its own);
SOFT_CLOSE_CAP is only a backstop against pathology.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.bids.services import SOFT_CLOSE_CAP, SOFT_CLOSE_WINDOW, place_bid
from apps.listings.models import Listing


class SoftCloseBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.seller = verified('sc_seller')
        cls.ann = verified('sc_ann')
        cls.bob = verified('sc_bob')

    def _auction(self, ends_in, **overrides):
        fields = dict(
            seller=self.seller, listing_type='auction', title='A lot',
            description='d', condition_grade='good', status='active',
            starting_price=Decimal('20'), bid_increment=Decimal('5'),
            auction_end=timezone.now() + ends_in,
        )
        fields.update(overrides)
        return Listing.objects.create(**fields)


class TheSoftCloseTests(SoftCloseBase):
    def test_a_bid_in_the_window_resets_the_clock(self):
        listing = self._auction(timedelta(seconds=45))
        ok, msg, _ = place_bid(listing, self.ann, Decimal('50'))
        self.assertTrue(ok)
        self.assertIn('The clock reset', msg)
        listing.refresh_from_db()
        left = listing.auction_end - timezone.now()
        self.assertGreater(left, timedelta(seconds=110))
        self.assertLessEqual(left, SOFT_CLOSE_WINDOW)
        self.assertEqual(listing.auction_extensions, 1)

    def test_a_bid_outside_the_window_changes_nothing(self):
        listing = self._auction(timedelta(hours=3))
        original_end = listing.auction_end
        place_bid(listing, self.ann, Decimal('50'))
        listing.refresh_from_db()
        self.assertEqual(listing.auction_end, original_end)
        self.assertEqual(listing.auction_extensions, 0)

    def test_a_losing_bid_in_the_window_still_buys_the_room_time(self):
        """The answer to a proxy volley deserves the same fair window."""
        listing = self._auction(timedelta(hours=3))
        place_bid(listing, self.ann, Decimal('500'))
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() + timedelta(seconds=45))
        listing.refresh_from_db()
        ok, msg, level = place_bid(listing, self.bob, Decimal('100'))
        self.assertEqual(level, 'warning')
        self.assertIn('The clock reset', msg)
        listing.refresh_from_db()
        self.assertEqual(listing.auction_extensions, 1)

    def test_the_cap_holds(self):
        listing = self._auction(timedelta(seconds=45),
                                auction_extensions=SOFT_CLOSE_CAP)
        end_before = listing.auction_end
        place_bid(listing, self.ann, Decimal('50'))
        listing.refresh_from_db()
        self.assertEqual(listing.auction_end, end_before)
        self.assertEqual(listing.auction_extensions, SOFT_CLOSE_CAP)


class TheRoomPayloadTests(SoftCloseBase):
    def _status(self, listing, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(
            reverse('listings:bid_status', args=[listing.pk])).json()

    def test_the_payload_carries_the_room(self):
        listing = self._auction(timedelta(minutes=4))
        place_bid(listing, self.ann, Decimal('500'))
        place_bid(listing, self.bob, Decimal('100'))

        payload = self._status(listing, self.bob)
        self.assertIn('server_time', payload)
        self.assertEqual(payload['extensions'], 0)
        self.assertTrue(payload['reserve_met'])
        self.assertFalse(payload['is_leading'])
        self.assertEqual(payload['your_max'], '100.00')
        # Newest first; the proxy answer is marked.
        self.assertEqual(payload['feed'][0]['bidder'], 'sc_ann')
        self.assertTrue(payload['feed'][0]['auto'])
        self.assertEqual(payload['feed'][1]['bidder'], 'sc_bob')

    def test_the_outcome_rides_along_after_the_close(self):
        listing = self._auction(timedelta(seconds=1))
        place_bid(listing, self.ann, Decimal('50'))
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() - timedelta(minutes=1))
        payload = self._status(listing)
        self.assertFalse(payload['is_active'])
        self.assertEqual(payload['outcome']['status'], 'pending')
        self.assertEqual(payload['outcome']['winner'], 'sc_ann')

    def test_an_anonymous_watcher_gets_no_private_fields(self):
        listing = self._auction(timedelta(minutes=4))
        place_bid(listing, self.ann, Decimal('500'))
        payload = self._status(listing)
        self.assertNotIn('your_max', payload)
        self.assertNotIn('is_leading', payload)
