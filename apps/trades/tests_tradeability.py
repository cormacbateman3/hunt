"""Two bugs that were live in shipped code, and the rule that replaces them.

`apps/trades` had no test module at all before this file.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Address
from apps.collections.models import CollectionItem
from apps.collections.tradeability import (
    is_open_to_trade,
    open_to_trade,
    trade_block_reason,
    would_trade,
)
from apps.core.models import State
from apps.listings.models import Listing
from apps.trades.models import TradeOffer


class TradeabilityBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('td_owner', password='pw')
        cls.suitor = User.objects.create_user('td_suitor', password='pw')
        cls.rival = User.objects.create_user('td_rival', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )
        # Trading is gated on a verified email; these tests are about what
        # happens after that gate, not the gate itself.
        for member in (cls.owner, cls.suitor, cls.rival):
            address = Address.objects.create(
                user=member, full_name=member.username, line1='1 Main St',
                city='Williamsport', state='PA', postal_code='17701')
            member.profile.email_verified = True
            member.profile.shipping_address = address
            member.profile.save(
                update_fields=['email_verified', 'shipping_address'])

    def _item(self, owner=None, **kwargs):
        defaults = {
            'owner': owner or self.owner, 'title': '1931 Cameron',
            'state': self.pa, 'condition_grade': 'good', 'is_public': True,
        }
        defaults.update(kwargs)
        return CollectionItem.objects.create(**defaults)

    def _lot(self, item, status='active'):
        return Listing.objects.create(
            seller=item.owner, source_collection_item=item, title=item.title,
            description='d', state=self.pa, condition_grade='good',
            status=status, listing_type='auction', starting_price=Decimal('40'),
            auction_end=timezone.now() + timedelta(days=3))


class TheRatchetTests(TradeabilityBase):
    """Listing a piece used to mark it un-tradeable forever.

    Two places wrote `trade_eligible = False` when a lot went live and nothing
    anywhere wrote it back — while four separate paths can close a listing. A
    lot that expired unsold left the piece un-tradeable for good, silently.
    """

    def test_a_live_lot_blocks_a_trade_offer(self):
        item = self._item()
        self.assertTrue(is_open_to_trade(item))

        self._lot(item)
        self.assertFalse(is_open_to_trade(item))
        self.assertIn('live lot', trade_block_reason(item))

    def test_a_lot_that_ends_gives_the_piece_back(self):
        """This is the bug. The old code never restored the flag."""
        item = self._item()
        lot = self._lot(item)
        self.assertFalse(is_open_to_trade(item))

        lot.status = 'expired'
        lot.save(update_fields=['status'])
        self.assertTrue(is_open_to_trade(item))

    def test_every_way_a_lot_can_end_gives_it_back(self):
        """Four paths close a listing. Deriving means none of them can forget."""
        for ending in ('expired', 'sold', 'closed', 'cancelled'):
            with self.subTest(ending=ending):
                CollectionItem.objects.all().delete()
                item = self._item()
                lot = self._lot(item)
                lot.status = ending
                lot.save(update_fields=['status'])
                self.assertTrue(is_open_to_trade(item))

    def test_the_owners_own_answer_still_wins(self):
        item = self._item(trade_eligible=False)
        self.assertFalse(is_open_to_trade(item))
        self.assertIn('not offering', trade_block_reason(item))

    def test_the_queryset_and_the_predicate_agree(self):
        open_item = self._item(title='Open')
        listed = self._item(title='Listed')
        self._lot(listed)
        closed = self._item(title='Closed', trade_eligible=False)

        available = set(open_to_trade(CollectionItem.objects.all()))
        self.assertEqual(available, {open_item})
        for item in (open_item, listed, closed):
            self.assertEqual(item in available, is_open_to_trade(item))

    def test_a_person_does_not_stop_trading_because_one_piece_is_at_auction(self):
        """The person-level question and the piece-level one are different."""
        item = self._item()
        self._lot(item)
        self.assertIn(item, would_trade(CollectionItem.objects.all()))
        self.assertNotIn(item, open_to_trade(CollectionItem.objects.all()))


class OfferPrivacyTests(TradeabilityBase):
    """One proposer could read every rival proposer's offer.

    `offer_detail` built its history by filtering on the listing alone, so
    whatever somebody was willing to give up was shown to everybody else
    bidding against them.
    """

    def _trade_listing(self):
        return Listing.objects.create(
            seller=self.owner, title='Up for trade', description='d',
            state=self.pa, condition_grade='good', status='active',
            listing_type='trade')

    def _offer(self, listing, proposer):
        return TradeOffer.objects.create(
            trade_listing=listing, from_user=proposer, to_user=self.owner,
            status='pending')

    def test_a_proposer_never_sees_a_rivals_offer(self):
        listing = self._trade_listing()
        mine = self._offer(listing, self.suitor)
        theirs = self._offer(listing, self.rival)

        self.client.force_login(self.suitor)
        resp = self.client.get(reverse('trades:offer_detail', args=[mine.pk]))
        self.assertEqual(resp.status_code, 200)

        shown = list(resp.context['history'])
        self.assertIn(mine, shown)
        self.assertNotIn(theirs, shown)

    def test_the_owner_sees_each_negotiation_separately(self):
        listing = self._trade_listing()
        first = self._offer(listing, self.suitor)
        second = self._offer(listing, self.rival)

        self.client.force_login(self.owner)
        shown = list(self.client.get(
            reverse('trades:offer_detail', args=[first.pk])).context['history'])
        self.assertIn(first, shown)
        self.assertNotIn(second, shown)

    def test_a_counter_stays_in_its_own_thread(self):
        listing = self._trade_listing()
        opening = self._offer(listing, self.suitor)
        counter = TradeOffer.objects.create(
            trade_listing=listing, from_user=self.owner, to_user=self.suitor,
            status='pending', counter_to=opening)
        rival = self._offer(listing, self.rival)

        self.client.force_login(self.suitor)
        shown = list(self.client.get(
            reverse('trades:offer_detail', args=[opening.pk])).context['history'])
        self.assertIn(opening, shown)
        self.assertIn(counter, shown)
        self.assertNotIn(rival, shown)

    def test_a_stranger_is_refused_outright(self):
        listing = self._trade_listing()
        offer = self._offer(listing, self.suitor)
        self.client.force_login(User.objects.create_user('td_nosy'))
        resp = self.client.get(reverse('trades:offer_detail', args=[offer.pk]))
        self.assertEqual(resp.status_code, 403)


class CompletedTradeTests(TradeabilityBase):
    """A completed trade used to leave both pieces advertised.

    Ownership does not transfer, so the licence stayed in the old owner's
    collection marked tradeable. A second collector could propose for
    something that left months ago; the owner accepts, cannot ship, and takes
    a non-shipment strike for a piece that was never theirs to give.
    """

    def _completed_trade(self):
        from apps.trades.models import Trade, TradeOffer, TradeOfferItem
        from apps.trades.services import _close_traded_pieces

        listing = Listing.objects.create(
            seller=self.owner, title='Up for trade', description='d',
            state=self.pa, condition_grade='good', status='sold',
            listing_type='trade')
        mine = self._item(owner=self.owner, title='Mine')
        theirs = self._item(owner=self.suitor, title='Theirs')

        offer = TradeOffer.objects.create(
            trade_listing=listing, from_user=self.suitor, to_user=self.owner,
            status='accepted')
        TradeOfferItem.objects.create(
            offer=offer, collection_item=theirs, direction='offered')
        TradeOfferItem.objects.create(
            offer=offer, collection_item=mine, direction='requested')

        trade = Trade.objects.create(
            listing=listing, initiator=self.suitor, counterparty=self.owner,
            status='delivered_both')
        return trade, mine, theirs, _close_traded_pieces

    def test_completion_stops_advertising_both_pieces(self):
        trade, mine, theirs, close = self._completed_trade()
        self.assertTrue(is_open_to_trade(mine))
        self.assertTrue(is_open_to_trade(theirs))

        close(trade)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertFalse(is_open_to_trade(mine))
        self.assertFalse(is_open_to_trade(theirs))

    def test_a_piece_that_has_gone_cannot_be_offered_again(self):
        """The strike this prevents is the whole point."""
        from apps.trades.services import create_trade_offer

        trade, mine, theirs, close = self._completed_trade()
        close(trade)
        mine.refresh_from_db()

        second = Listing.objects.create(
            seller=self.rival, title='Another', description='d', state=self.pa,
            condition_grade='good', status='active', listing_type='trade')
        offer, error = create_trade_offer(
            listing=second, from_user=self.owner, to_user=self.rival,
            offered_items=[mine])
        self.assertIsNone(offer)
        self.assertIn('cannot be traded', error)
