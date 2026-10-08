"""W1.16 — the Stripe webhook, exercised end to end.

Before this, no test anywhere called the webhook, and replays were only
safe by accident of the order's status.
"""

from decimal import Decimal
from unittest import mock

import stripe
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.payments.models import PaymentTransaction, StripeEvent

CONSTRUCT = 'apps.payments.views.stripe.Webhook.construct_event'


class StripeWebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('sw_seller', password='pw')
        cls.buyer = User.objects.create_user('sw_buyer', password='pw')

    def _order(self):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1931 Clinton', description='x',
            condition_grade='good', buy_now_price=Decimal('40'), status='pending')
        return Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller, order_type='buy_now',
            item_amount=Decimal('40'), total_amount=Decimal('45'), status='pending_payment')

    def _post(self, event):
        with mock.patch(CONSTRUCT, return_value=event):
            return self.client.post(reverse('payments:webhook'), data=b'{}',
                                    content_type='application/json', HTTP_STRIPE_SIGNATURE='t=1,v1=x')

    def _paid_event(self, order, event_id='evt_paid'):
        return {'id': event_id, 'type': 'payment_intent.succeeded', 'data': {'object': {
            'id': 'pi_1', 'metadata': {'order_id': str(order.pk), 'buyer_id': str(self.buyer.pk)}}}}

    def test_a_bad_signature_is_refused(self):
        order = self._order()
        error = stripe.error.SignatureVerificationError('bad', 'sig')
        with mock.patch(CONSTRUCT, side_effect=error):
            resp = self.client.post(reverse('payments:webhook'), data=b'{}',
                                    content_type='application/json')
        self.assertEqual(resp.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending_payment')

    def test_checkout_completed_records_the_session(self):
        order = self._order()
        self._post({'id': 'evt_cs', 'type': 'checkout.session.completed', 'data': {'object': {
            'id': 'cs_1', 'payment_intent': 'pi_1', 'metadata': {'order_id': str(order.pk)}}}})
        payment = PaymentTransaction.objects.get(order=order)
        self.assertEqual(payment.status, 'processing')
        self.assertEqual(payment.stripe_checkout_session_id, 'cs_1')

    def test_payment_succeeded_sells_and_stamps_the_moment(self):
        order = self._order()
        self.assertEqual(self._post(self._paid_event(order)).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertIsNotNone(order.paid_at)
        self.assertEqual(order.listing.status, 'sold')

    def test_a_replayed_event_is_acted_on_once(self):
        order = self._order()
        self._post(self._paid_event(order))
        self._post(self._paid_event(order))
        self.assertEqual(StripeEvent.objects.filter(event_id='evt_paid').count(), 1)
        self.assertEqual(
            Notification.objects.filter(user=self.seller, notification_type='order_paid').count(), 1)

    def test_a_failure_lets_stripe_retry(self):
        order = self._order()
        with mock.patch('apps.payments.views.handle_payment_intent_succeeded',
                        side_effect=RuntimeError('db hiccup')):
            with self.assertRaises(RuntimeError):
                self._post(self._paid_event(order))
        self.assertFalse(StripeEvent.objects.filter(event_id='evt_paid').exists())
        self._post(self._paid_event(order))   # Stripe's retry
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
