"""10.7 shipping-wiring tests: parcel config, rate selection, who-pays, snapshots."""
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Address
from apps.listings.models import Listing
from apps.orders.models import Order
from apps.shipping.services import (
    apply_shipping_to_order,
    ensure_order_snapshots,
    listing_parcel,
    select_rate,
)


def make_address(user, line1='1 Main St', is_default=False):
    return Address.objects.create(
        user=user, full_name=user.username, line1=line1, city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=is_default,
    )


class ShippingConfigTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('seller', password='pw')
        cls.buyer = User.objects.create_user('buyer', password='pw')
        cls.listing = Listing.objects.create(
            seller=cls.seller, listing_type='buy_now', title='1942 License',
            description='x', county='Adams', condition_grade='good',
            buy_now_price=50, status='active',
        )

    def _order(self, **kwargs):
        defaults = {
            'listing': self.listing, 'buyer': self.buyer, 'seller': self.seller,
            'order_type': 'buy_now', 'item_amount': Decimal('50.00'),
            'platform_fee_amount': Decimal('0.00'), 'total_amount': Decimal('50.00'),
            'status': 'pending_payment',
        }
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def test_listing_parcel_uses_seller_config_with_default_fallback(self):
        self.listing.package_weight_oz = Decimal('12.0')
        self.listing.package_length_in = Decimal('11.0')
        parcel = listing_parcel(self.listing)
        self.assertEqual(parcel['weight_oz'], Decimal('12.0'))
        self.assertEqual(parcel['length_in'], Decimal('11.0'))
        # unset fields fall back to the defaults
        self.assertEqual(parcel['width_in'], Decimal('7.0'))
        self.assertEqual(parcel['height_in'], Decimal('1.0'))

    def test_select_rate_honors_service_choice_and_falls_back(self):
        rates = [
            {'amount': '4.50', 'servicelevel': {'token': 'usps_ground_advantage'}},
            {'amount': '9.10', 'servicelevel': {'token': 'fedex_2_day'}},
            {'amount': '8.20', 'servicelevel': {'token': 'fedex_2_day'}},
        ]
        self.assertEqual(select_rate(rates, 'fedex_2_day')['amount'], '8.20')
        self.assertEqual(select_rate(rates, 'cheapest')['amount'], '4.50')
        # chosen service returned no rates -> cheapest overall
        self.assertEqual(select_rate(rates, 'ups_ground')['amount'], '4.50')

    def test_who_pays_controls_buyer_total(self):
        order = self._order()
        apply_shipping_to_order(order, Decimal('6.40'))
        self.assertEqual(order.shipping_amount, Decimal('6.40'))
        self.assertEqual(order.total_amount, Decimal('56.40'))

        seller_pays = self._order(
            listing=Listing.objects.create(
                seller=self.seller, listing_type='buy_now', title='Another',
                description='x', county='Adams', condition_grade='good',
                buy_now_price=50, status='active', shipping_payer='seller',
            ),
            shipping_payer='seller',
        )
        apply_shipping_to_order(seller_pays, Decimal('6.40'))
        self.assertEqual(seller_pays.shipping_amount, Decimal('0.00'))
        self.assertEqual(seller_pays.total_amount, Decimal('50.00'))

    def test_ship_from_prefers_listing_address_over_profile_default(self):
        default_addr = make_address(self.seller, line1='9 Default Rd', is_default=True)
        profile = self.seller.profile
        profile.shipping_address = default_addr
        profile.save(update_fields=['shipping_address'])
        buyer_addr = make_address(self.buyer, line1='2 Buyer Ln', is_default=True)
        buyer_profile = self.buyer.profile
        buyer_profile.shipping_address = buyer_addr
        buyer_profile.save(update_fields=['shipping_address'])

        listing_addr = make_address(self.seller, line1='77 Listing Way')
        self.listing.ship_from_address = listing_addr
        self.listing.save(update_fields=['ship_from_address'])

        order = self._order()
        ship_from, ship_to = ensure_order_snapshots(order)
        self.assertEqual(ship_from.line1, '77 Listing Way')
        self.assertEqual(ship_to.line1, '2 Buyer Ln')
