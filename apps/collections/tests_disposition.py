"""A piece that has left the collection stops being offered — Pass 8b.

Two facts were being conflated before ``disposition`` existed: the owner's
standing answer on trade (tradeability) and whether the object is still
physically theirs. ``_close_traded_pieces`` papered over the second by
flipping the first, which told the wrong story and stole the owner's answer.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from apps.collections.forms import CollectionItemForm
from apps.collections.models import CollectionItem
from apps.collections.tradeability import (
    is_open_to_trade,
    open_to_trade,
    trade_block_label,
    trade_block_reason,
    would_trade,
)
from apps.core.models import State


class DispositionBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('disp_owner')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )

    def _item(self, **kwargs):
        defaults = dict(
            owner=self.owner, title='1949 Tioga', description='d',
            state=self.pa, license_year=1949, condition_grade='good',
        )
        defaults.update(kwargs)
        return CollectionItem.objects.create(**defaults)


class DepartedPieceTests(DispositionBase):
    def test_a_held_piece_is_open_as_before(self):
        item = self._item()
        self.assertEqual(item.disposition, 'held')
        self.assertTrue(is_open_to_trade(item))

    def test_a_departed_piece_cannot_take_an_offer(self):
        for gone in ('sold_elsewhere', 'given_away', 'lost', 'traded'):
            item = self._item(title=gone, disposition=gone)
            self.assertFalse(is_open_to_trade(item), gone)
            self.assertIn('no longer in the collection', trade_block_reason(item))

    def test_departure_outranks_the_owners_open_answer(self):
        """tradeability stays 'open' — the piece left, the answer didn't change."""
        item = self._item(disposition='sold_elsewhere', tradeability='open')
        self.assertFalse(is_open_to_trade(item))

    def test_the_label_says_where_it_went(self):
        self.assertEqual(
            trade_block_label(self._item(disposition='sold_elsewhere')),
            'Sold elsewhere',
        )
        self.assertEqual(
            trade_block_label(self._item(title='x2', disposition='lost'), mine=True),
            'Lost',
        )

    def test_querysets_exclude_departed_pieces_both_ways(self):
        kept = self._item(title='kept')
        self._item(title='gone', disposition='given_away')
        rows = CollectionItem.objects.filter(owner=self.owner)
        self.assertEqual([i.pk for i in open_to_trade(rows)], [kept.pk])
        # would_trade asks about the person, but not about pieces that left.
        self.assertEqual([i.pk for i in would_trade(rows)], [kept.pk])


class TradeLifecycleTests(DispositionBase):
    def test_close_traded_pieces_records_the_departure_not_a_changed_mind(self):
        from apps.listings.models import Listing
        from apps.trades.models import Trade, TradeOffer, TradeOfferItem
        from apps.trades.services import _close_traded_pieces

        suitor = User.objects.create_user('disp_suitor')
        mine = self._item(title='Mine')
        theirs = self._item(title='Theirs', owner=suitor)
        listing = Listing.objects.create(
            seller=self.owner, title='Lot', description='d', state=self.pa,
            condition_grade='good', status='sold', listing_type='trade')
        offer = TradeOffer.objects.create(
            subject_item=mine, trade_listing=listing,
            from_user=suitor, to_user=self.owner, status='accepted')
        TradeOfferItem.objects.create(offer=offer, collection_item=theirs, direction='offered')
        TradeOfferItem.objects.create(offer=offer, collection_item=mine, direction='requested')
        trade = Trade.objects.create(
            offer=offer, listing=listing, initiator=suitor,
            counterparty=self.owner, status='delivered_both')

        _close_traded_pieces(trade)
        mine.refresh_from_db()
        theirs.refresh_from_db()
        self.assertEqual(mine.disposition, 'traded')
        self.assertEqual(theirs.disposition, 'traded')
        # The owner's standing answer is untouched — that's the point.
        self.assertEqual(mine.tradeability, 'open')
        self.assertFalse(is_open_to_trade(mine))


class SaleLifecycleTests(DispositionBase):
    """The missing half of 8b: a KeystoneBid sale writes the departure the
    moment the money lands, and a refund hands the piece back. Before
    this, a sold piece sat in its seller's collection forever — on the
    profile, in the runs, offered to want-matchers."""

    def _sale(self):
        from decimal import Decimal

        from apps.listings.models import Listing
        from apps.orders.models import Order

        buyer = User.objects.create_user(f'disp_buyer_{Order.objects.count()}')
        item = self._item(title='On the block')
        listing = Listing.objects.create(
            seller=self.owner, source_collection_item=item, title='Lot',
            description='d', state=self.pa, condition_grade='good',
            status='pending', listing_type='buy_now', buy_now_price=Decimal('40'))
        order = Order.objects.create(
            listing=listing, buyer=buyer, seller=self.owner,
            order_type='buy_now', status='pending_payment',
            item_amount=Decimal('40'), total_amount=Decimal('40'))
        return item, order

    def test_paid_marks_the_piece_sold(self):
        from apps.orders.services import transition_order

        item, order = self._sale()
        ok, _ = transition_order(order, 'paid')
        self.assertTrue(ok)
        item.refresh_from_db()
        self.assertEqual(item.disposition, 'sold')
        self.assertFalse(is_open_to_trade(item))

    def test_a_refund_hands_it_back(self):
        from apps.orders.services import transition_order

        item, order = self._sale()
        transition_order(order, 'paid')
        transition_order(order, 'refunded')
        item.refresh_from_db()
        self.assertEqual(item.disposition, 'held')

    def test_an_order_event_never_overwrites_another_story(self):
        from apps.orders.services import transition_order

        item, order = self._sale()
        item.disposition = 'given_away'
        item.save(update_fields=['disposition'])
        transition_order(order, 'paid')
        item.refresh_from_db()
        self.assertEqual(item.disposition, 'given_away')
        # And a cancel does not "return" what a sale never took.
        transition_order(order, 'cancelled')
        item.refresh_from_db()
        self.assertEqual(item.disposition, 'given_away')

    def test_the_webhook_path_writes_it_too(self):
        from apps.collections.disposition import piece_sold

        item, order = self._sale()
        self.assertTrue(piece_sold(order.listing))
        item.refresh_from_db()
        self.assertEqual(item.disposition, 'sold')
        # Idempotent — the webhook retries.
        self.assertFalse(piece_sold(order.listing))

    def test_a_sold_piece_leaves_the_matchers(self):
        from apps.collections.matching import holdings

        item, order = self._sale()
        self.assertIn(item.pk, {row['id'] for row in holdings(self.owner)})
        from apps.orders.services import transition_order

        transition_order(order, 'paid')
        self.assertNotIn(item.pk, {row['id'] for row in holdings(self.owner)})


class DispositionOnTheFormTests(DispositionBase):
    def _post(self, item=None, **extra):
        data = {
            'item_kind': 'license', 'title': 'T', 'description': '',
            'state': str(self.pa.pk), 'license_year': '1949',
            'resident_status': 'unknown', 'condition_grade': 'good',
            'shape': 'rectangle',
        }
        data.update(extra)
        return CollectionItemForm(data=data, instance=item, user=self.owner)

    def test_a_form_without_the_control_keeps_the_recorded_departure(self):
        """The add-from-order form never renders disposition; saving through
        it must not quietly mark a departed piece held again."""
        item = self._item(disposition='sold_elsewhere')
        form = self._post(item=item)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().disposition, 'sold_elsewhere')

    def test_the_owner_can_record_a_departure(self):
        item = self._item()
        form = self._post(item=item, disposition='given_away')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().disposition, 'given_away')

    def test_traded_is_not_a_choice_anybody_can_pick(self):
        form = self._post(disposition='traded')
        self.assertFalse(form.is_valid())
        self.assertIn('disposition', form.errors)

    def test_traded_survives_an_edit_of_a_traded_piece(self):
        item = self._item(disposition='traded')
        form = self._post(item=item, disposition='traded')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().disposition, 'traded')

    def test_sold_is_the_sale_lifecycles_word_not_a_form_choice(self):
        form = self._post(disposition='sold')
        self.assertFalse(form.is_valid())
        self.assertIn('disposition', form.errors)

    def test_sold_survives_an_edit_of_a_sold_piece(self):
        item = self._item(disposition='sold')
        form = self._post(item=item, disposition='sold')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().disposition, 'sold')

    def test_a_traded_piece_is_never_offered_sold(self):
        form = self._post(item=self._item(disposition='traded'), disposition='sold')
        self.assertFalse(form.is_valid())
