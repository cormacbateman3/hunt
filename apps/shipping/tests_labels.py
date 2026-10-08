"""W1.23 — buying a label and quoting the postage.

A label purchase spends real money at Shippo and moves the order into the
post; a quote sets what the buyer pays. Neither had a test. Shippo is always
mocked here (``apps.shipping.services.ShippoClient``) — nothing touches the
network.

``tests.py`` already covers ``select_rate`` and ``apply_shipping_to_order``
on their own; these go through ``quote_order_shipping`` and
``buy_label_for_order`` end to end.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Address
from apps.listings.models import Listing
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.shipping.models import Shipment, ShipmentEvent
from apps.shipping.providers.shippo import ShippoError
from apps.shipping.services import (
    buy_label_for_order,
    ensure_checkout_shipping_ready,
    quote_order_shipping,
)

CLIENT = 'apps.shipping.services.ShippoClient'

LABEL_URL = 'https://shippo-delivery.example/label_9400111.pdf'


def _with_address(user, line1='1 Main St'):
    address = Address.objects.create(
        user=user, full_name=user.username, line1=line1, city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True,
    )
    user.profile.shipping_address = address
    user.profile.save(update_fields=['shipping_address'])
    return address


def shippo_rates(*rates, object_id='shp_1'):
    """A patched ShippoClient whose shipment call returns ``rates``."""
    client = mock.Mock()
    client.return_value.create_shipment.return_value = {
        'object_id': object_id, 'rates': list(rates)}
    return client


def rate(amount, token, object_id, provider='USPS', name='Ground Advantage'):
    return {'amount': amount, 'object_id': object_id, 'provider': provider,
            'servicelevel': {'token': token, 'name': name}}


class LabelBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('lbl_seller', password='pw')
        cls.buyer = User.objects.create_user('lbl_buyer', password='pw')
        _with_address(cls.seller, line1='9 Seller Rd')
        cls.buyer_address = _with_address(cls.buyer, line1='2 Buyer Ln')

    def _order(self, status='paid', seller=None, **listing_kwargs):
        seller = seller or self.seller
        listing = Listing.objects.create(
            seller=seller, listing_type='buy_now', title='1941 Tioga Resident',
            description='x', condition_grade='good', buy_now_price=Decimal('40'),
            status='sold', **listing_kwargs)
        return Order.objects.create(
            listing=listing, buyer=self.buyer, seller=seller, order_type='buy_now',
            status=status, item_amount=Decimal('40.00'),
            platform_fee_amount=Decimal('2.00'), total_amount=Decimal('42.00'))


# ── buy_label_for_order ──────────────────────────────────────────────────

class BuyLabelTests(LabelBase):
    def setUp(self):
        self.order = self._order()
        self.shipment = Shipment.objects.create(
            order=self.order, rate_id='rate_ground', rate_amount=Decimal('6.40'),
            carrier='USPS', service_level='Ground Advantage')

    def _shippo_transaction(self, payload=None, side_effect=None):
        client = mock.Mock()
        if side_effect:
            client.return_value.create_transaction.side_effect = side_effect
        else:
            client.return_value.create_transaction.return_value = payload
        return client

    def _success(self, **extra):
        payload = {'status': 'SUCCESS', 'tracking_number': '9400111',
                   'label_url': LABEL_URL}
        payload.update(extra)
        return payload

    def assertNothingChanged(self):
        self.shipment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.shipment.tracking_number, '')
        self.assertEqual(self.shipment.label_url, '')
        self.assertEqual(self.shipment.status, 'pending')
        self.assertEqual(self.order.status, 'paid')
        self.assertIsNone(self.order.shipped_at)
        self.assertFalse(ShipmentEvent.objects.filter(shipment=self.shipment).exists())
        self.assertFalse(Notification.objects.filter(
            user=self.buyer, notification_type='order_shipped').exists())

    def test_a_bought_label_records_the_tracking_and_the_label(self):
        client = self._shippo_transaction(self._success())
        with mock.patch(CLIENT, client):
            buy_label_for_order(self.order)

        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.tracking_number, '9400111')
        self.assertEqual(self.shipment.label_url, LABEL_URL)
        self.assertEqual(self.shipment.carrier, 'USPS')
        self.assertEqual(self.shipment.status, 'label_created')

    def test_the_label_is_bought_at_the_quoted_rate(self):
        client = self._shippo_transaction(self._success())
        with mock.patch(CLIENT, client):
            buy_label_for_order(self.order)
        client.return_value.create_transaction.assert_called_once_with(rate_id='rate_ground')

    def test_the_order_moves_into_the_post_and_the_buyer_hears(self):
        with mock.patch(CLIENT, self._shippo_transaction(self._success())):
            buy_label_for_order(self.order)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'label_created')
        self.assertIsNotNone(self.order.shipped_at)
        event = ShipmentEvent.objects.get(shipment=self.shipment)
        self.assertEqual(event.status, 'label_created')
        self.assertEqual(event.description, 'Shipping label purchased.')
        note = Notification.objects.get(user=self.buyer, notification_type='order_shipped')
        self.assertEqual(note.link_url, f'/orders/{self.order.pk}/')

    def test_the_addresses_are_snapshotted_and_a_later_edit_does_not_rewrite_them(self):
        with mock.patch(CLIENT, self._shippo_transaction(self._success())):
            buy_label_for_order(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.ship_from_snapshot.line1, '9 Seller Rd')
        self.assertEqual(self.order.ship_to_snapshot.line1, '2 Buyer Ln')

        Address.objects.filter(pk=self.buyer_address.pk).update(line1='5 New Home Ct')
        self.order.refresh_from_db()
        self.assertEqual(self.order.ship_to_snapshot.line1, '2 Buyer Ln')

    def test_a_failed_purchase_raises_and_changes_nothing(self):
        failed = {'status': 'ERROR', 'messages': [{'text': 'Rate expired'}]}
        with mock.patch(CLIENT, self._shippo_transaction(failed)):
            with self.assertRaisesMessage(ShippoError, 'Label purchase failed'):
                buy_label_for_order(self.order)
        self.assertNothingChanged()

    def test_shippo_being_unreachable_changes_nothing(self):
        down = self._shippo_transaction(side_effect=ShippoError('Shippo took too long to answer.'))
        with mock.patch(CLIENT, down):
            with self.assertRaises(ShippoError):
                buy_label_for_order(self.order)
        self.assertNothingChanged()

    def test_buying_without_a_quote_is_refused_before_shippo_is_asked(self):
        order = self._order()
        client = mock.Mock()
        with mock.patch(CLIENT, client):
            with self.assertRaisesMessage(ShippoError, 'No quoted shipping rate found'):
                buy_label_for_order(order)
        client.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.status, 'paid')

    def test_a_quote_without_a_rate_to_buy_is_refused(self):
        Shipment.objects.filter(pk=self.shipment.pk).update(rate_id='')
        client = mock.Mock()
        with mock.patch(CLIENT, client):
            with self.assertRaises(ShippoError):
                buy_label_for_order(self.order)
        client.assert_not_called()
        self.assertNothingChanged()

    def test_a_label_shippo_reports_as_unknown_to_tracking_is_still_recorded(self):
        # A real Shippo transaction carries "tracking_status": "UNKNOWN" until
        # the carrier first scans the parcel; the code calls .get() on it.
        with mock.patch(CLIENT, self._shippo_transaction(self._success(tracking_status='UNKNOWN'))):
            buy_label_for_order(self.order)
        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.tracking_number, '9400111')


    # W1.27: a double click paid twice, and a QUEUED purchase moved the order
    # with nothing to print.

    def test_a_second_purchase_is_refused_before_shippo_is_called(self):
        with mock.patch(CLIENT, self._shippo_transaction(self._success())):
            buy_label_for_order(self.order)
        with mock.patch(CLIENT) as client:
            with self.assertRaisesMessage(ShippoError, 'already been bought'):
                buy_label_for_order(self.order)
        client.return_value.create_transaction.assert_not_called()

    def test_a_queued_label_moves_nothing_and_blocks_a_repeat(self):
        queued = {'status': 'QUEUED', 'object_id': 'tx_1'}
        with mock.patch(CLIENT, self._shippo_transaction(queued)):
            with self.assertRaisesMessage(ShippoError, "Please don't buy another"):
                buy_label_for_order(self.order)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        with mock.patch(CLIENT) as client:
            with self.assertRaises(ShippoError):
                buy_label_for_order(self.order)
        client.return_value.create_transaction.assert_not_called()


# ── quote_order_shipping ─────────────────────────────────────────────────

RATES = (
    rate('4.50', 'usps_ground_advantage', 'rate_ground'),
    rate('9.85', 'usps_priority', 'rate_priority_dear', name='Priority Mail'),
    rate('8.70', 'usps_priority', 'rate_priority', name='Priority Mail'),
    rate('7.10', 'ups_ground', 'rate_ups', provider='UPS', name='Ground'),
)


class QuoteTests(LabelBase):
    def test_the_quote_takes_the_cheapest_rate_of_the_sellers_service(self):
        order = self._order(status='pending_payment', shipping_service='usps_priority')
        with mock.patch(CLIENT, shippo_rates(*RATES)):
            shipment = quote_order_shipping(order)

        self.assertEqual(shipment.rate_id, 'rate_priority')
        self.assertEqual(shipment.rate_amount, Decimal('8.70'))
        self.assertEqual(shipment.carrier, 'USPS')
        self.assertEqual(shipment.service_level, 'Priority Mail')
        self.assertEqual(shipment.external_shipment_id, 'shp_1')

        order.refresh_from_db()
        self.assertEqual(order.shipping_amount, Decimal('8.70'))
        self.assertEqual(order.total_amount, Decimal('50.70'))   # 40 + 2 fee + 8.70

    def test_best_available_takes_the_cheapest_rate_of_all(self):
        order = self._order(status='pending_payment')   # shipping_service='cheapest'
        with mock.patch(CLIENT, shippo_rates(*RATES)):
            shipment = quote_order_shipping(order)
        self.assertEqual(shipment.rate_id, 'rate_ground')
        order.refresh_from_db()
        self.assertEqual(order.shipping_amount, Decimal('4.50'))

    def test_when_the_seller_pays_the_buyer_pays_no_shipping(self):
        order = self._order(status='pending_payment', shipping_payer='seller')
        self.assertEqual(order.shipping_payer, 'buyer')   # not yet snapshotted
        with mock.patch(CLIENT, shippo_rates(*RATES)):
            shipment = quote_order_shipping(order)

        order.refresh_from_db()
        self.assertEqual(order.shipping_payer, 'seller')
        self.assertEqual(order.shipping_amount, Decimal('0.00'))
        self.assertEqual(order.total_amount, Decimal('42.00'))
        # The real cost stays on the shipment, for the seller's books.
        self.assertEqual(shipment.rate_amount, Decimal('4.50'))

    def test_shippo_is_sent_the_listings_parcel_and_the_snapshotted_addresses(self):
        order = self._order(status='pending_payment', package_weight_oz=Decimal('12'))
        client = shippo_rates(*RATES)
        with mock.patch(CLIENT, client):
            quote_order_shipping(order)

        kwargs = client.return_value.create_shipment.call_args.kwargs
        self.assertEqual(kwargs['parcel']['weight'], '12.00')
        self.assertEqual(kwargs['parcel']['mass_unit'], 'oz')
        self.assertEqual(kwargs['address_from']['street1'], '9 Seller Rd')
        self.assertEqual(kwargs['address_to']['street1'], '2 Buyer Ln')

    def test_a_requote_updates_the_one_shipment(self):
        order = self._order(status='pending_payment')
        with mock.patch(CLIENT, shippo_rates(*RATES)):
            quote_order_shipping(order)
        with mock.patch(CLIENT, shippo_rates(rate('5.05', 'usps_ground_advantage', 'rate_new'))):
            quote_order_shipping(order)

        self.assertEqual(Shipment.objects.filter(order=order).count(), 1)
        self.assertEqual(Shipment.objects.get(order=order).rate_id, 'rate_new')
        order.refresh_from_db()
        self.assertEqual(order.shipping_amount, Decimal('5.05'))

    def test_no_rates_is_a_plain_error_and_the_total_is_untouched(self):
        order = self._order(status='pending_payment')
        with mock.patch(CLIENT, shippo_rates()):
            with self.assertRaisesMessage(ShippoError, 'No shipping rates'):
                quote_order_shipping(order)
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal('42.00'))
        self.assertFalse(Shipment.objects.filter(order=order).exists())

    def test_a_seller_without_an_address_is_named_as_the_gap_not_the_buyer(self):
        homeless = User.objects.create_user('lbl_no_address', password='pw')
        order = self._order(status='pending_payment', seller=homeless)
        client = mock.Mock()
        with mock.patch(CLIENT, client):
            with self.assertRaisesMessage(ShippoError, "seller hasn't set up a shipping address"):
                quote_order_shipping(order)
        client.assert_not_called()

    def test_checkout_reuses_a_standing_quote_without_asking_shippo_again(self):
        order = self._order(status='pending_payment')
        with mock.patch(CLIENT, shippo_rates(*RATES)):
            quote_order_shipping(order)

        client = mock.Mock()
        with mock.patch(CLIENT, client):
            shipment = ensure_checkout_shipping_ready(order)
        client.assert_not_called()
        self.assertEqual(shipment.rate_id, 'rate_ground')
        order.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal('46.50'))

    def test_checkout_quotes_when_there_is_no_quote_yet(self):
        order = self._order(status='pending_payment')
        client = shippo_rates(*RATES)
        with mock.patch(CLIENT, client):
            shipment = ensure_checkout_shipping_ready(order)
        client.return_value.create_shipment.assert_called_once()
        self.assertEqual(shipment.rate_id, 'rate_ground')

