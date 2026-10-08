"""W1.14 — an auction winner hears again before the pay window closes.

Between "it's yours" and the non-payment strike 24 hours later, nothing
reminded them.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.bench import AUCTION_PAY_GRACE_HOURS
from apps.listings.models import Listing
from apps.notifications import letters
from apps.notifications.models import Notification
from apps.orders.models import Order


class PaymentDueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('pd_seller', password='pw')
        cls.winner = User.objects.create_user('pd_winner', password='pw')

    def _win(self, hours_ago, status='pending_payment'):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='auction', title='1931 Clinton',
            description='x', condition_grade='good', starting_price=10, status='pending')
        order = Order.objects.create(
            listing=listing, buyer=self.winner, seller=self.seller, order_type='auction',
            item_amount=Decimal('40'), total_amount=Decimal('45'), status=status)
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(hours=hours_ago))
        order.refresh_from_db()
        return order

    def _reminders(self):
        return Notification.objects.filter(user=self.winner, notification_type='payment_due')

    def test_halfway_through_the_window_the_winner_is_reminded_once(self):
        self._win(hours_ago=AUCTION_PAY_GRACE_HOURS * 0.6)
        call_command('enqueue_operational_notifications', verbosity=0)
        call_command('enqueue_operational_notifications', verbosity=0)
        self.assertEqual(self._reminders().count(), 1)

    def test_not_too_early_not_after_the_window_and_not_once_paid(self):
        self._win(hours_ago=1)
        self._win(hours_ago=AUCTION_PAY_GRACE_HOURS + 1)
        self._win(hours_ago=AUCTION_PAY_GRACE_HOURS * 0.6, status='paid')
        call_command('enqueue_operational_notifications', verbosity=0)
        self.assertFalse(self._reminders().exists())

    def test_the_letter_names_the_money_and_the_deadline(self):
        self._win(hours_ago=AUCTION_PAY_GRACE_HOURS * 0.6)
        call_command('enqueue_operational_notifications', verbosity=0)
        letter = letters.build(self._reminders().get())
        self.assertIn('Still to pay', letter['subject'])
        self.assertEqual(letter['action']['label'], 'Pay $45.00')
        self.assertTrue(any('Due by' in fact for fact in letter['item']['facts']))
        self.assertFalse(self._reminders().get().sent_email)  # queued for the send job
