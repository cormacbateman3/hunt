"""W1.1 — tracking we can trust.

Before: the Shippo webhook was unauthenticated and applied whatever status it
was posted, and a seller's typed-in tracking number moved the order to "in
transit" on their word. Anyone who knew a tracking number could post
DELIVERED and have the order auto-complete three days later.
"""

import json
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import Address
from apps.listings.models import Listing
from apps.orders.models import Order
from apps.shipping.models import Shipment
from apps.shipping.providers.shippo import ShippoError
from apps.shipping.services import attach_manual_tracking
from apps.trades.models import Trade, TradeShipment
from apps.trades.services import add_trade_manual_tracking

SHIPPO = 'apps.shipping.tracking.ShippoClient'


def shippo_says(code, details='Carrier update'):
    """A patched ShippoClient whose tracking lookup reports ``code``."""
    client = mock.Mock()
    client.return_value.get_tracking_status.return_value = {
        'tracking_status': {'status': code, 'status_details': details} if code else None,
    }
    return client


def _with_address(user):
    address = Address.objects.create(
        user=user, full_name=user.username, line1='1 Main St', city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True,
    )
    user.profile.shipping_address = address
    user.profile.save(update_fields=['shipping_address'])


class TrackingBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('trk_seller', password='pw')
        cls.buyer = User.objects.create_user('trk_buyer', password='pw')
        _with_address(cls.seller)
        _with_address(cls.buyer)

    def _order(self, status='paid'):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='1934 Clinton',
            description='x', condition_grade='good', buy_now_price=40, status='sold',
        )
        return Order.objects.create(
            listing=listing, buyer=self.buyer, seller=self.seller, order_type='buy_now',
            item_amount=Decimal('40.00'), total_amount=Decimal('45.00'), status=status,
        )


@override_settings(SHIPPO_WEBHOOK_TOKEN='s3cret')
class WebhookTests(TrackingBase):
    def _shipped_order(self):
        order = self._order(status='label_created')
        shipment = Shipment.objects.create(
            order=order, carrier='USPS', tracking_number='9400111', status='label_created',
        )
        return order, shipment

    def _post(self, body, token='s3cret'):
        url = reverse('shipping:shippo_webhook')
        if token is not None:
            url += f'?token={token}'
        return self.client.post(url, data=json.dumps(body), content_type='application/json')

    def _delivered_claim(self):
        return {'data': {'tracking_number': '9400111', 'carrier': 'usps',
                         'tracking_status': {'status': 'DELIVERED'}}}

    def test_a_post_without_the_token_is_refused(self):
        order, shipment = self._shipped_order()
        self.assertEqual(self._post(self._delivered_claim(), token=None).status_code, 403)
        shipment.refresh_from_db()
        self.assertEqual(shipment.status, 'label_created')

    def test_a_post_with_the_wrong_token_is_refused(self):
        self._shipped_order()
        self.assertEqual(self._post(self._delivered_claim(), token='guess').status_code, 403)

    @override_settings(SHIPPO_WEBHOOK_TOKEN='')
    def test_no_configured_token_refuses_every_post(self):
        self._shipped_order()
        self.assertEqual(self._post(self._delivered_claim(), token='').status_code, 403)

    def test_a_delivered_claim_is_checked_with_shippo_not_believed(self):
        order, shipment = self._shipped_order()
        with mock.patch(SHIPPO, shippo_says('TRANSIT')) as client:
            self.assertEqual(self._post(self._delivered_claim()).status_code, 200)
        client.return_value.get_tracking_status.assert_called_once_with(
            carrier='usps', tracking_number='9400111',
        )
        shipment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(shipment.status, 'in_transit')
        self.assertEqual(order.status, 'in_transit')

    def test_a_status_the_carrier_never_reported_moves_nothing(self):
        order, shipment = self._shipped_order()
        with mock.patch(SHIPPO, shippo_says('UNKNOWN')):
            self._post(self._delivered_claim())
        shipment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(shipment.status, 'label_created')
        self.assertEqual(order.status, 'label_created')

    def test_a_trade_parcel_is_rechecked_the_same_way(self):
        trade = Trade.objects.create(
            initiator=self.seller, counterparty=self.buyer, status='shipped_one',
        )
        parcel = TradeShipment.objects.create(
            trade=trade, sender=self.seller, recipient=self.buyer, carrier='USPS',
            tracking_number='9400222', status='label_created',
        )
        claim = {'data': {'tracking_number': '9400222', 'tracking_status': {'status': 'DELIVERED'}}}
        with mock.patch(SHIPPO, shippo_says('TRANSIT')):
            self._post(claim)
        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'in_transit')


class MemberTrackingTests(TrackingBase):
    def test_a_number_the_carrier_doesnt_know_is_refused(self):
        order = self._order()
        with mock.patch(SHIPPO, shippo_says('UNKNOWN')):
            with self.assertRaisesMessage(ShippoError, "doesn't recognise"):
                attach_manual_tracking(order, carrier='USPS', tracking_number='MADEUP')
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')
        self.assertFalse(Shipment.objects.filter(order=order).exists())

    def test_an_unsupported_carrier_is_refused_plainly(self):
        with self.assertRaisesMessage(ShippoError, 'USPS, UPS, FedEx and DHL'):
            attach_manual_tracking(self._order(), carrier='Pony Express', tracking_number='1')

    def test_the_order_moves_to_what_the_carrier_says(self):
        for code, expected in (('PRE_TRANSIT', 'label_created'), ('TRANSIT', 'in_transit')):
            with self.subTest(code=code):
                order = self._order()
                with mock.patch(SHIPPO, shippo_says(code)):
                    attach_manual_tracking(order, carrier='USPS', tracking_number=f'9400{code}')
                order.refresh_from_db()
                self.assertEqual(order.status, expected)

    def test_a_trader_cannot_invent_a_number_either(self):
        trade = Trade.objects.create(
            initiator=self.seller, counterparty=self.buyer, status='awaiting_shipments',
        )
        parcel = TradeShipment.objects.create(
            trade=trade, sender=self.seller, recipient=self.buyer,
        )
        with mock.patch(SHIPPO, shippo_says(None)):
            shipment, err = add_trade_manual_tracking(
                shipment=parcel, actor=self.seller, carrier='USPS', tracking_number='MADEUP',
            )
        self.assertIsNone(shipment)
        self.assertIn("doesn't recognise", err)
        parcel.refresh_from_db()
        self.assertEqual(parcel.status, 'pending')
        self.assertEqual(parcel.tracking_number, '')
