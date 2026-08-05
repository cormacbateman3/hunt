"""Orders — one ledger, and an order page that says what to do.

The statuses are engine words; what gets tested is the translation. Every
row promises a consequence, and a row that promised a deadline the
background job does not keep would be worse than no row at all — so the
deadlines are asserted against the same constants the jobs use.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.bench import (
    AUCTION_PAY_GRACE_HOURS,
    RECEIPT_GRACE_DAYS,
    ship_by_days,
)
from apps.core.models import MarketplaceSettings, State
from apps.enforcement import handshakes
from apps.enforcement.models import OrderHandshake, Strike
from apps.listings.models import Listing
from apps.orders import ledger
from apps.orders.models import Order


class OrderLedgerBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('ol_seller', password='pw')
        cls.buyer = User.objects.create_user('ol_buyer', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'is_primary_default': True},
        )

    def _order(self, **kwargs):
        listing = Listing.objects.create(
            seller=self.seller, title=kwargs.pop('title', '1938 Warren Resident'),
            description='d', state=self.pa, condition_grade='good',
            status='sold', listing_type='buy_now', buy_now_price=Decimal('200'))
        defaults = {
            'listing': listing, 'buyer': self.buyer, 'seller': self.seller,
            'order_type': 'buy_now', 'status': 'pending_payment',
            'item_amount': Decimal('200'), 'shipping_amount': Decimal('8.40'),
            'platform_fee_amount': Decimal('16.00'),
            'total_amount': Decimal('208.40'),
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)


class PlainEnglishTests(OrderLedgerBase):
    def test_pending_payment_says_the_consequence_to_the_buyer(self):
        self._order(order_type='auction')
        row = ledger.rows(self.buyer)['rows'][0]
        self.assertEqual(row['headline'], 'Waiting on your payment')
        self.assertIn('the sale is cancelled', row['note'])
        self.assertEqual(row['tone'], 'rust')
        self.assertEqual(row['action']['label'], 'Pay now')

    def test_pay_now_goes_where_payment_actually_starts(self):
        order = self._order(order_type='auction')
        row = ledger.rows(self.buyer)['rows'][0]
        self.assertEqual(
            row['action']['url'],
            reverse('listings:auction_win_review', args=[order.listing_id]))

    def test_the_same_order_reads_differently_to_the_seller(self):
        self._order()
        row = ledger.rows(self.seller)['rows'][0]
        self.assertEqual(row['headline'], 'Waiting on their payment')
        self.assertFalse(row['needs_you'])

    def test_paid_tells_the_seller_when_to_ship(self):
        self._order(status='paid')
        row = ledger.rows(self.seller)['rows'][0]
        self.assertEqual(row['headline'], 'Paid — waiting on you to ship')
        self.assertIn('Ship by', row['note'])
        self.assertEqual(row['tone'], 'brass')

    def test_delivered_tells_the_buyer_what_happens_if_they_say_nothing(self):
        self._order(status='delivered')
        row = ledger.rows(self.buyer)['rows'][0]
        self.assertIn('we’ll assume so on', row['note'])
        self.assertEqual(row['action']['label'], 'It arrived')

    def test_no_engine_words_reach_the_page(self):
        for status in ('pending_payment', 'paid', 'label_created', 'in_transit',
                       'delivered', 'completed'):
            with self.subTest(status=status):
                Order.objects.all().delete()
                self._order(status=status)
                row = ledger.rows(self.buyer)['rows'][0]
                self.assertNotIn('_', row['headline'])

    def test_the_ship_by_date_matches_the_marketplace_setting(self):
        MarketplaceSettings.objects.create(ship_by_days=9)
        order = self._order(status='paid')
        expected = order.updated_at + timedelta(days=9)
        self.assertIn(ledger._on(expected), ledger.rows(self.seller)['rows'][0]['note'])
        self.assertEqual(ship_by_days(), 9)


class SortAndFilterTests(OrderLedgerBase):
    def test_what_needs_you_floats_above_what_does_not(self):
        self._order(status='in_transit', title='Moving')
        self._order(status='delivered', title='Needs a word')
        headlines = [row['headline'] for row in ledger.rows(self.buyer)['rows']]
        self.assertTrue(headlines[0].startswith('Delivered'))

    def test_buying_and_selling_are_one_click_away(self):
        self._order()
        other = User.objects.create_user('ol_third')
        listing = Listing.objects.create(
            seller=other, title='Theirs', description='d', state=self.pa,
            condition_grade='good', status='sold', listing_type='buy_now',
            buy_now_price=Decimal('50'))
        Order.objects.create(
            listing=listing, buyer=self.seller, seller=other, order_type='buy_now',
            status='paid', item_amount=Decimal('50'), shipping_amount=Decimal('5'),
            total_amount=Decimal('55'))

        page = ledger.rows(self.seller)
        counts = {row['key']: row['count'] for row in page['filters']}
        self.assertEqual(counts['selling'], 1)
        self.assertEqual(counts['buying'], 1)
        self.assertEqual(counts[''], 2)

    def test_finished_orders_are_marked_and_filterable(self):
        self._order(status='completed')
        page = ledger.rows(self.buyer, 'finished')
        self.assertEqual(len(page['rows']), 1)
        self.assertTrue(page['rows'][0]['finished'])


class OrderPageTests(OrderLedgerBase):
    def test_the_rail_marks_where_it_is(self):
        order = self._order(status='paid')
        stops = {stop['key']: stop['state'] for stop in ledger.stops(order)}
        self.assertEqual(stops['paid'], 'done')
        self.assertEqual(stops['ship'], 'here')
        self.assertEqual(stops['delivered'], 'ahead')

    def test_your_turn_is_absent_when_it_is_not_your_turn(self):
        order = self._order(status='paid')
        self.assertIsNone(ledger.your_turn(order, self.buyer))
        self.assertIsNotNone(ledger.your_turn(order, self.seller))

    def test_your_turn_carries_the_clock_the_job_uses(self):
        order = self._order(status='delivered')
        turn = ledger.your_turn(order, self.buyer)
        expected = order.updated_at + timedelta(days=RECEIPT_GRACE_DAYS)
        self.assertEqual(turn['due'], expected)

    def test_the_auction_payment_clock_matches_its_own_grace_window(self):
        order = self._order(order_type='auction')
        turn = ledger.your_turn(order, self.buyer)
        self.assertEqual(
            turn['due'], order.created_at + timedelta(hours=AUCTION_PAY_GRACE_HOURS))

    def test_the_seller_sees_what_they_keep_and_the_buyer_does_not(self):
        order = self._order(status='paid')
        selling = ledger.money(order, selling=True)
        self.assertEqual(selling['total_label'], 'You keep')
        self.assertEqual(selling['total'], Decimal('184.00'))

        buying = ledger.money(order, selling=False)
        self.assertEqual(buying['total_label'], 'You paid')
        self.assertEqual(buying['deductions'], [])

    def test_the_record_reads_as_sentences(self):
        order = self._order(status='paid')
        texts = [line['text'] for line in ledger.record(order)]
        self.assertTrue(any('Order opened' in text for text in texts))
        self.assertTrue(any('told to ship by' in text for text in texts))

    def test_the_page_renders_for_both_sides(self):
        order = self._order(status='paid')
        for user in (self.seller, self.buyer):
            self.client.force_login(user)
            resp = self.client.get(reverse('orders:detail', args=[order.pk]))
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, 'The record')
            self.assertNotContains(resp, 'label_created')

    def test_a_stranger_cannot_read_the_order(self):
        order = self._order()
        self.client.force_login(User.objects.create_user('ol_nosy'))
        resp = self.client.get(reverse('orders:detail', args=[order.pk]))
        self.assertEqual(resp.status_code, 403)


class HandshakeTests(OrderLedgerBase):
    def _propose(self, actor=None, covers='shipping', reason='local_pickup'):
        return handshakes.propose(
            order=self.order, actor=actor or self.seller,
            covers=covers, reason=reason, note='At the Bloomsburg show')

    def setUp(self):
        self.order = self._order(status='paid')

    def test_a_proposal_alone_settles_nothing(self):
        handshake, error = self._propose()
        self.assertEqual(error, '')
        self.assertFalse(handshake.is_confirmed)
        self.assertIsNone(handshakes.active_for(self.order, 'shipping'))

    def test_the_other_party_confirms_and_only_then_does_it_hold(self):
        handshake, _ = self._propose()
        ok, error = handshakes.confirm(handshake=handshake, actor=self.buyer)
        self.assertTrue(ok, error)
        self.assertIsNotNone(handshakes.active_for(self.order, 'shipping'))

    def test_you_cannot_confirm_your_own(self):
        handshake, _ = self._propose()
        ok, error = handshakes.confirm(handshake=handshake, actor=self.seller)
        self.assertFalse(ok)
        self.assertIn('other person', error)

    def test_a_stranger_is_not_a_party_to_it(self):
        outsider = User.objects.create_user('ol_outsider')
        handshake, error = self._propose(actor=outsider)
        self.assertIsNone(handshake)
        self.assertIn('buyer and the seller', error)

    def test_a_lapsed_offer_cannot_be_confirmed(self):
        handshake, _ = self._propose()
        OrderHandshake.objects.filter(pk=handshake.pk).update(
            expires_at=timezone.now() - timedelta(hours=1))
        handshake.refresh_from_db()
        ok, error = handshakes.confirm(handshake=handshake, actor=self.buyer)
        self.assertFalse(ok)
        self.assertIn('lapsed', error)

    def test_a_shipping_handshake_does_not_excuse_a_missed_receipt(self):
        """Whoever agreed to wait for the parcel did not agree to that."""
        handshake, _ = self._propose(covers='shipping')
        handshakes.confirm(handshake=handshake, actor=self.buyer)
        self.assertIsNone(handshakes.active_for(self.order, 'receipt'))

    # ── The sweeps have to honour it, or the button is a lie ─────────────
    def test_a_confirmed_handshake_stops_the_non_shipment_strike(self):
        from apps.enforcement.services import enforce_deterministic_policies

        Order.objects.filter(pk=self.order.pk).update(
            updated_at=timezone.now() - timedelta(days=30))

        handshake, _ = self._propose()
        handshakes.confirm(handshake=handshake, actor=self.buyer)

        enforce_deterministic_policies()
        self.assertFalse(
            Strike.objects.filter(related_order=self.order, reason='non_shipment').exists())

    def test_without_one_the_strike_still_lands(self):
        from apps.enforcement.services import enforce_deterministic_policies

        Order.objects.filter(pk=self.order.pk).update(
            updated_at=timezone.now() - timedelta(days=30))
        enforce_deterministic_policies()
        self.assertTrue(
            Strike.objects.filter(related_order=self.order, reason='non_shipment').exists())

    def test_an_unconfirmed_proposal_does_not_stop_the_strike(self):
        from apps.enforcement.services import enforce_deterministic_policies

        Order.objects.filter(pk=self.order.pk).update(
            updated_at=timezone.now() - timedelta(days=30))
        self._propose()

        enforce_deterministic_policies()
        self.assertTrue(
            Strike.objects.filter(related_order=self.order, reason='non_shipment').exists())

    def test_a_receipt_handshake_stops_the_order_auto_completing(self):
        from apps.orders.services import auto_complete_delivered_orders

        Order.objects.filter(pk=self.order.pk).update(status='delivered')
        self.order.refresh_from_db()
        handshake, _ = handshakes.propose(
            order=self.order, actor=self.buyer, covers='receipt',
            reason='alternative_delivery')
        handshakes.confirm(handshake=handshake, actor=self.seller)
        Order.objects.filter(pk=self.order.pk).update(
            updated_at=timezone.now() - timedelta(days=30))

        auto_complete_delivered_orders()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

    # ── Through the views ────────────────────────────────────────────────
    def test_offering_and_agreeing_through_the_page(self):
        self.client.force_login(self.seller)
        self.client.post(reverse('orders:offer_handshake', args=[self.order.pk]),
                         {'covers': 'shipping', 'reason': 'local_pickup',
                          'note': 'At the show'})
        handshake = OrderHandshake.objects.get(order=self.order)

        self.client.force_login(self.buyer)
        page = self.client.get(reverse('orders:detail', args=[self.order.pk]))
        self.assertContains(page, 'offered a handshake')

        self.client.post(reverse('orders:confirm_handshake',
                                 args=[self.order.pk, handshake.pk]))
        handshake.refresh_from_db()
        self.assertTrue(handshake.is_confirmed)

    def test_the_offer_is_beside_the_deadline_with_no_strike_in_sight(self):
        """The whole point: it is available before anybody is penalised."""
        self.assertFalse(Strike.objects.filter(related_order=self.order).exists())
        self.client.force_login(self.seller)
        html = self.client.get(
            reverse('orders:detail', args=[self.order.pk])).content.decode()
        self.assertIn('Offer a handshake', html)
