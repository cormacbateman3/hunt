"""W1.15 — one clock for every order deadline.

Deadlines used to count from ``updated_at``, which moves on any save, and
the non-shipment strike carried its own five calendar days while every
screen quoted MarketplaceSettings.ship_by_days.
"""

from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.enforcement.models import Strike
from apps.enforcement.services import enforce_deterministic_policies
from apps.listings.models import Listing
from apps.orders import clock
from apps.orders.models import Order
from apps.orders.services import auto_complete_delivered_orders, transition_order


def _aware(*args):
    return timezone.make_aware(datetime(*args))


class BusinessDayTests(TestCase):
    def test_a_friday_payment_skips_the_weekend(self):
        friday = _aware(2026, 10, 9, 10, 0)            # a Friday
        self.assertEqual(clock.add_business_days(friday, 1).weekday(), 0)   # Monday
        self.assertEqual(clock.add_business_days(friday, 5), _aware(2026, 10, 16, 10, 0))


class OrderClockTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('clk_seller', password='pw')
        cls.buyer = User.objects.create_user('clk_buyer', password='pw')

    def _order(self, status='pending_payment', **kwargs):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1934 Clinton', description='x',
            condition_grade='good', buy_now_price=Decimal('40'), status='sold')
        return Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller, order_type='buy_now',
            item_amount=Decimal('40'), total_amount=Decimal('45'), status=status, **kwargs)

    def test_each_stage_stamps_its_moment_once(self):
        order = self._order()
        transition_order(order, 'paid')
        transition_order(order, 'in_transit')
        transition_order(order, 'delivered')
        transition_order(order, 'completed')
        order.refresh_from_db()
        for field in ('paid_at', 'shipped_at', 'delivered_at', 'completed_at'):
            self.assertIsNotNone(getattr(order, field), field)

    def test_a_later_save_doesnt_move_the_posting_deadline(self):
        paid = timezone.now() - timedelta(days=2)
        order = self._order(status='paid', paid_at=paid)
        before = clock.ship_by(order)
        order.shipping_amount = Decimal('6')
        order.save()   # moves updated_at
        order.refresh_from_db()
        self.assertEqual(clock.ship_by(order), before)

    def test_the_strike_waits_for_the_deadline_the_seller_was_shown(self):
        # Paid six calendar days ago, but the window is five *business* days:
        # if those six days held a weekend, the deadline hasn't passed.
        paid = timezone.now() - timedelta(days=6)
        order = self._order(status='paid', paid_at=paid)
        enforce_deterministic_policies()
        struck = Strike.objects.filter(related_order=order, reason='non_shipment').exists()
        self.assertEqual(struck, clock.ship_by(order) <= timezone.now())

    def test_well_past_the_deadline_the_strike_lands(self):
        order = self._order(status='paid', paid_at=timezone.now() - timedelta(days=14))
        enforce_deterministic_policies()
        self.assertTrue(Strike.objects.filter(related_order=order, reason='non_shipment').exists())

    def test_auto_complete_counts_from_delivery_not_the_last_save(self):
        fresh = self._order(status='delivered', delivered_at=timezone.now() - timedelta(hours=2))
        stale = self._order(status='delivered',
                            delivered_at=timezone.now() - timedelta(days=clock.RECEIPT_GRACE_DAYS + 1))
        auto_complete_delivered_orders()
        fresh.refresh_from_db()
        stale.refresh_from_db()
        self.assertEqual(fresh.status, 'delivered')
        self.assertEqual(stale.status, 'completed')
