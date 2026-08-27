"""Proxy bidding — the one mechanic, resolved the eBay way.

The number a bidder enters is their maximum. The visible price moves only
when somebody pushes it; the standing maximum answers one increment at a
time and never past itself; ties keep the earlier hand; the winner pays
the standing price at the close, not their maximum.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.bids.models import Bid, ProxyMax
from apps.bids.services import close_auction, place_bid
from apps.listings.models import Listing
from apps.orders.models import Order


class ProxyBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name):
            user = User.objects.create_user(name, password='pw')
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.seller = verified('px_seller')
        cls.ann = verified('px_ann')
        cls.bob = verified('px_bob')

    def _auction(self, **overrides):
        fields = dict(
            seller=self.seller, listing_type='auction', title='A lot',
            description='d', condition_grade='good', status='active',
            starting_price=Decimal('20'), bid_increment=Decimal('5'),
            auction_end=timezone.now() + timedelta(days=3),
        )
        fields.update(overrides)
        return Listing.objects.create(**fields)

    def _price(self, listing):
        listing.refresh_from_db()
        return listing.current_bid

    def _leader(self, listing):
        bid = Bid.objects.filter(listing=listing, is_winning=True).first()
        return bid.bidder if bid else None


class TheOpeningBidTests(ProxyBase):
    def test_the_first_bid_stands_at_the_starting_price(self):
        listing = self._auction()
        ok, msg, level = place_bid(listing, self.ann, Decimal('100'))
        self.assertTrue(ok, msg)
        self.assertEqual(level, 'success')
        self.assertEqual(self._price(listing), Decimal('20'))
        self.assertEqual(self._leader(listing), self.ann)
        self.assertEqual(
            ProxyMax.objects.get(listing=listing, bidder=self.ann).max_amount,
            Decimal('100'))

    def test_a_maximum_covering_the_reserve_moves_the_price_to_it(self):
        listing = self._auction(reserve_price=Decimal('60'))
        place_bid(listing, self.ann, Decimal('100'))
        self.assertEqual(self._price(listing), Decimal('60'))


class TheDuelTests(ProxyBase):
    def test_a_higher_maximum_takes_the_lead_one_increment_up(self):
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))     # price 20
        ok, msg, level = place_bid(listing, self.bob, Decimal('150'))
        self.assertTrue(ok)
        self.assertEqual(level, 'success')
        self.assertEqual(self._leader(listing), self.bob)
        self.assertEqual(self._price(listing), Decimal('105'))   # ann's max + inc

    def test_a_lower_maximum_is_answered_instantly(self):
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))
        ok, msg, level = place_bid(listing, self.bob, Decimal('40'))
        self.assertTrue(ok)                # the bid was recorded
        self.assertEqual(level, 'warning')  # but it is not good news
        self.assertEqual(self._leader(listing), self.ann)
        self.assertEqual(self._price(listing), Decimal('45'))    # bob + inc, ≤ ann's max
        answer = Bid.objects.filter(listing=listing, is_winning=True).first()
        self.assertTrue(answer.is_proxy)

    def test_the_answer_never_passes_the_maximum(self):
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))
        place_bid(listing, self.bob, Decimal('98'))
        # 98 + 5 would be 103 — the proxy stops at ann's 100.
        self.assertEqual(self._price(listing), Decimal('100'))
        self.assertEqual(self._leader(listing), self.ann)

    def test_a_tie_keeps_the_earlier_hand(self):
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))
        ok, msg, level = place_bid(listing, self.bob, Decimal('100'))
        self.assertEqual(level, 'warning')
        self.assertEqual(self._leader(listing), self.ann)
        self.assertEqual(self._price(listing), Decimal('100'))


class TheLeaderTests(ProxyBase):
    def test_the_leader_raising_moves_the_ceiling_not_the_price(self):
        """The end of outbidding yourself: a higher number from the leader
        is a maximum change, invisible to the room."""
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))
        visible_before = Bid.objects.filter(listing=listing).count()
        ok, msg, level = place_bid(listing, self.ann, Decimal('300'))
        self.assertTrue(ok)
        self.assertIn('Maximum raised', msg)
        self.assertEqual(self._price(listing), Decimal('20'))    # unmoved
        self.assertEqual(Bid.objects.filter(listing=listing).count(), visible_before)
        self.assertEqual(
            ProxyMax.objects.get(listing=listing, bidder=self.ann).max_amount,
            Decimal('300'))

    def test_the_leader_cannot_lower_their_maximum(self):
        listing = self._auction()
        place_bid(listing, self.ann, Decimal('100'))
        ok, msg, level = place_bid(listing, self.ann, Decimal('80'))
        self.assertFalse(ok)
        self.assertIn('already', msg)

    def test_a_raise_that_meets_the_reserve_shows_it(self):
        listing = self._auction(reserve_price=Decimal('200'))
        place_bid(listing, self.ann, Decimal('100'))    # under reserve: price 20
        self.assertEqual(self._price(listing), Decimal('20'))
        ok, msg, level = place_bid(listing, self.ann, Decimal('250'))
        self.assertTrue(ok)
        self.assertEqual(self._price(listing), Decimal('200'))   # jumped to reserve


class TheSettlementTests(ProxyBase):
    def test_the_winner_pays_the_standing_price_not_their_maximum(self):
        listing = self._auction(auction_end=timezone.now() + timedelta(seconds=1))
        place_bid(listing, self.ann, Decimal('500'))
        place_bid(listing, self.bob, Decimal('100'))
        # price now 105 (bob + inc), ann leads with a 500 ceiling nobody hit
        Listing.objects.filter(pk=listing.pk).update(
            auction_end=timezone.now() - timedelta(minutes=1))
        listing.refresh_from_db()
        self.assertEqual(close_auction(listing), 'sold')
        order = Order.objects.get(listing=listing)
        self.assertEqual(order.buyer, self.ann)
        self.assertEqual(order.item_amount, Decimal('105'))
