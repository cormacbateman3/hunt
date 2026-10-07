"""Shipping status is the carrier's to report, not a member's.

`orders:update_status` let a seller POST "delivered" to their own order with
no tracking at all. That escaped the non-shipment strike (which only looks at
paid orders) and handed the order to auto-complete three days later. The
endpoint is gone, and the service refuses the move from any member.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.core.models import State
from apps.listings.models import Listing
from apps.orders.models import Order
from apps.orders.services import transition_order

User = get_user_model()


class ShippingStatusGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('sg_seller', password='pw')
        cls.buyer = User.objects.create_user('sg_buyer', password='pw')
        cls.staff = User.objects.create_user('sg_staff', password='pw', is_staff=True)
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania'},
        )

    def _paid_order(self):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1934 Clinton',
            description='x', condition_grade='good', status='sold', state=self.pa,
            buy_now_price=Decimal('40.00'),
        )
        return Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller,
            order_type='buy_now', item_amount=Decimal('40.00'),
            total_amount=Decimal('45.00'), status='paid',
        )

    def test_the_self_service_endpoint_is_gone(self):
        order = self._paid_order()
        self.client.force_login(self.seller)
        resp = self.client.post(
            f'/orders/{order.pk}/update-status/', {'target_status': 'delivered'},
        )
        self.assertEqual(resp.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_a_seller_cannot_mark_their_own_order_moving(self):
        order = self._paid_order()
        for target in ('label_created', 'in_transit', 'delivered'):
            with self.subTest(target=target):
                ok, _ = transition_order(order, target, actor=self.seller)
                self.assertFalse(ok)
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_a_buyer_cannot_either(self):
        ok, _ = transition_order(self._paid_order(), 'delivered', actor=self.buyer)
        self.assertFalse(ok)

    def test_carrier_tracking_and_staff_still_can(self):
        order = self._paid_order()
        ok, _ = transition_order(order, 'in_transit')  # carrier event, no actor
        self.assertTrue(ok)
        ok, _ = transition_order(order, 'delivered', actor=self.staff)
        self.assertTrue(ok)
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
