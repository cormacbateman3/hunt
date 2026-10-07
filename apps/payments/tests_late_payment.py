"""W1.5 — a payment that arrives too late must not complete a sale.

Before: a payment landing after the order had been released (the buy-now pay
window, or an unpaid auction win) was recorded as paid, marked the listing
sold and told the seller "payment received" — while the order stayed
cancelled, and a cancelled buy-now order can be reused for the next buyer.
"""

from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction
from apps.payments.views import handle_payment_intent_succeeded


class LatePaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('lp_seller', password='pw')
        cls.buyer = User.objects.create_user('lp_buyer', password='pw')
        cls.next_buyer = User.objects.create_user('lp_next', password='pw')
        cls.staff = User.objects.create_user('lp_staff', password='pw', is_staff=True)

    def _order(self, *, status, buyer=None, listing_status='active'):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1931 Clinton',
            description='x', condition_grade='good', buy_now_price=40, status=listing_status,
        )
        return Order.objects.create(
            listing=listing, buyer=buyer or self.buyer, seller=self.seller,
            order_type='buy_now', item_amount=Decimal('40.00'),
            total_amount=Decimal('45.00'), status=status,
        )

    def _intent(self, order, payer):
        return {'id': 'pi_late', 'amount_received': 4500,
                'metadata': {'order_id': str(order.pk), 'buyer_id': str(payer.pk)}}

    def _types(self, user):
        return set(Notification.objects.filter(user=user).values_list('notification_type', flat=True))

    def test_a_payment_after_cancellation_sells_nothing_and_asks_for_a_refund(self):
        order = self._order(status='cancelled')
        handle_payment_intent_succeeded(self._intent(order, self.buyer))

        order.refresh_from_db()
        order.listing.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.listing.status, 'active')
        self.assertFalse(PaymentTransaction.objects.filter(order=order, status='paid').exists())
        self.assertIn('payment_needs_refund', self._types(self.staff))
        self.assertIn('payment_after_cancel', self._types(self.buyer))
        self.assertEqual(self._types(self.seller), set())

    def test_a_previous_buyers_payment_never_lands_on_the_next_buyers_order(self):
        order = self._order(status='pending_payment', buyer=self.next_buyer)
        handle_payment_intent_succeeded(self._intent(order, self.buyer))

        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')
        self.assertIn('payment_after_cancel', self._types(self.buyer))
        self.assertNotIn('payment_after_cancel', self._types(self.next_buyer))
        self.assertIn('payment_needs_refund', self._types(self.staff))

    def test_a_replayed_late_payment_doesnt_repeat_the_alerts(self):
        order = self._order(status='cancelled')
        handle_payment_intent_succeeded(self._intent(order, self.buyer))
        handle_payment_intent_succeeded(self._intent(order, self.buyer))
        self.assertEqual(
            Notification.objects.filter(user=self.staff, notification_type='payment_needs_refund').count(), 1,
        )

    def test_an_on_time_payment_still_completes_the_sale(self):
        order = self._order(status='pending_payment', listing_status='pending')
        handle_payment_intent_succeeded(self._intent(order, self.buyer))

        order.refresh_from_db()
        order.listing.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.listing.status, 'sold')
        self.assertIn('order_paid', self._types(self.seller))

    def test_an_older_session_without_buyer_metadata_still_completes(self):
        order = self._order(status='pending_payment', listing_status='pending')
        handle_payment_intent_succeeded({'id': 'pi_old', 'metadata': {'order_id': str(order.pk)}})
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
