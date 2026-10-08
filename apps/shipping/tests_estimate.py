"""W1.20 — the review page's shipping estimate never hangs on Shippo.

It called Shippo synchronously with a 30-second timeout on every page view.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from apps.accounts.models import Address
from apps.listings.models import Listing
from apps.shipping.providers.shippo import ShippoError
from apps.shipping.services import ESTIMATE_TIMEOUT_SECONDS, estimate_listing_shipping

CLIENT = 'apps.shipping.services.ShippoClient'


def _with_address(user):
    address = Address.objects.create(
        user=user, full_name=user.username, line1='1 Main St', city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True)
    user.profile.shipping_address = address
    user.profile.save(update_fields=['shipping_address'])


class EstimateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('est_seller', password='pw')
        cls.buyer = User.objects.create_user('est_buyer', password='pw')
        _with_address(cls.seller)
        _with_address(cls.buyer)
        cls.listing = Listing.objects.create(
            seller=cls.seller, listing_type='buy_now', title='1931 Clinton', description='x',
            condition_grade='good', buy_now_price=Decimal('40'), status='active',
            shipping_payer='buyer')

    def setUp(self):
        cache.clear()

    def test_a_short_timeout_and_a_cached_answer(self):
        with mock.patch(CLIENT) as client:
            client.return_value.create_shipment.return_value = {'rates': [{'amount': '5.25'}]}
            first = estimate_listing_shipping(self.listing, self.buyer)
            second = estimate_listing_shipping(self.listing, self.buyer)
        self.assertEqual(first, (Decimal('5.25'), 'Estimated'))
        self.assertEqual(second, (Decimal('5.25'), 'Estimated'))
        client.assert_called_once_with(timeout=ESTIMATE_TIMEOUT_SECONDS)
        self.assertLess(ESTIMATE_TIMEOUT_SECONDS, 10)

    def test_a_slow_or_failing_shippo_falls_back_plainly(self):
        with mock.patch(CLIENT) as client:
            client.return_value.create_shipment.side_effect = ShippoError('Shippo took too long to answer.')
            self.assertEqual(estimate_listing_shipping(self.listing, self.buyer),
                             (None, 'Calculated at payment'))
