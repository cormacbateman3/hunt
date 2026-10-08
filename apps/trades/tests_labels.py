"""W1.27 on the trade side: one label per side, and a queued label blocks a repeat."""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from apps.accounts.models import Address
from apps.trades.models import Trade, TradeShipment
from apps.trades.services import QUEUED_PROVIDER, buy_trade_label

CLIENT = 'apps.trades.services.ShippoClient'
PARCEL = {'weight_oz': Decimal('4'), 'length_in': Decimal('9'),
          'width_in': Decimal('6'), 'height_in': Decimal('1')}


def _with_address(user):
    address = Address.objects.create(
        user=user, full_name=user.username, line1='1 Main St', city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True)
    user.profile.shipping_address = address
    user.profile.save(update_fields=['shipping_address'])


def _shippo(transaction):
    client = mock.Mock()
    client.return_value.create_shipment.return_value = {
        'rates': [{'amount': '5.10', 'object_id': 'rate_1', 'provider': 'USPS'}]}
    client.return_value.create_transaction.return_value = transaction
    return client


class TradeLabelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sender = User.objects.create_user('tl_sender', password='pw')
        cls.recipient = User.objects.create_user('tl_recipient', password='pw')
        _with_address(cls.sender)
        _with_address(cls.recipient)

    def setUp(self):
        trade = Trade.objects.create(initiator=self.sender, counterparty=self.recipient,
                                     status='awaiting_shipments')
        self.side = TradeShipment.objects.create(trade=trade, sender=self.sender,
                                                 recipient=self.recipient)

    def test_one_label_per_side(self):
        ok = {'status': 'SUCCESS', 'tracking_number': '9400', 'label_url': 'https://x/l.pdf',
              'tracking_status': 'UNKNOWN'}
        with mock.patch(CLIENT, _shippo(ok)):
            shipment, err = buy_trade_label(shipment=self.side, actor=self.sender, parcel=PARCEL)
        self.assertEqual(err, '')
        self.assertEqual(shipment.carrier, 'USPS')
        with mock.patch(CLIENT) as client:
            _, err = buy_trade_label(shipment=self.side, actor=self.sender, parcel=PARCEL)
        self.assertIn('already been bought', err)
        client.return_value.create_transaction.assert_not_called()

    def test_a_queued_label_moves_nothing_and_blocks_a_repeat(self):
        with mock.patch(CLIENT, _shippo({'status': 'QUEUED'})):
            shipment, err = buy_trade_label(shipment=self.side, actor=self.sender, parcel=PARCEL)
        self.assertIsNone(shipment)
        self.side.refresh_from_db()
        self.assertEqual(self.side.provider, QUEUED_PROVIDER)
        self.assertEqual(self.side.status, 'pending')
        with mock.patch(CLIENT) as client:
            _, err = buy_trade_label(shipment=self.side, actor=self.sender, parcel=PARCEL)
        self.assertIn("Please don't buy another", err)
        client.return_value.create_transaction.assert_not_called()
