from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from apps.notifications.models import Notification
from apps.orders.models import AddressSnapshot
from apps.orders.services import transition_order
from .models import Shipment, ShipmentEvent
from .providers.shippo import ShippoClient, ShippoError


TERMINAL_SHIPMENT_STATUSES = {'delivered', 'failed', 'returned'}
TRACKING_TO_SHIPMENT_STATUS = {
    'PRE_TRANSIT': 'label_created',
    'TRANSIT': 'in_transit',
    'OUT_FOR_DELIVERY': 'out_for_delivery',
    'DELIVERED': 'delivered',
    'RETURNED': 'returned',
    'FAILURE': 'failed',
}


def _to_decimal(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _address_to_shippo_payload(address):
    return {
        'name': address.full_name,
        'street1': address.line1,
        'street2': address.line2,
        'city': address.city,
        'state': address.state,
        'zip': address.postal_code,
        'country': address.country,
        'phone': address.phone or '',
    }


def _snapshot_from_address(address):
    return AddressSnapshot.objects.create(
        full_name=address.full_name,
        line1=address.line1,
        line2=address.line2,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country,
        phone=address.phone,
    )


def ensure_order_snapshots(order):
    seller_address = getattr(order.seller.profile, 'shipping_address', None)
    buyer_address = getattr(order.buyer.profile, 'shipping_address', None)
    if not seller_address or not buyer_address:
        raise ShippoError('Buyer and seller must both have default shipping addresses configured.')

    updated = False
    if not order.ship_from_snapshot:
        order.ship_from_snapshot = _snapshot_from_address(seller_address)
        updated = True
    if not order.ship_to_snapshot:
        order.ship_to_snapshot = _snapshot_from_address(buyer_address)
        updated = True
    if updated:
        order.save(update_fields=['ship_from_snapshot', 'ship_to_snapshot', 'updated_at'])
    return order.ship_from_snapshot, order.ship_to_snapshot


def default_parcel():
    return {
        'weight_oz': _to_decimal(getattr(settings, 'SHIPPO_DEFAULT_WEIGHT_OZ', '8.0')),
        'length_in': _to_decimal(getattr(settings, 'SHIPPO_DEFAULT_LENGTH_IN', '10.0')),
        'width_in': _to_decimal(getattr(settings, 'SHIPPO_DEFAULT_WIDTH_IN', '7.0')),
        'height_in': _to_decimal(getattr(settings, 'SHIPPO_DEFAULT_HEIGHT_IN', '1.0')),
    }


def _parcel_to_shippo(parcel):
    return {
        'length': str(parcel['length_in']),
        'width': str(parcel['width_in']),
        'height': str(parcel['height_in']),
        'distance_unit': 'in',
        'weight': str(parcel['weight_oz']),
        'mass_unit': 'oz',
    }


def quote_order_shipping(order, parcel_data=None):
    ship_from, ship_to = ensure_order_snapshots(order)
    parcel = parcel_data or default_parcel()
    client = ShippoClient()
    shipment_payload = client.create_shipment(
        address_from=_address_to_shippo_payload(ship_from),
        address_to=_address_to_shippo_payload(ship_to),
        parcel=_parcel_to_shippo(parcel),
    )
    rates = shipment_payload.get('rates') or []
    if not rates:
        raise ShippoError('No shipping rates were returned by Shippo.')

    selected = min(rates, key=lambda r: Decimal(str(r.get('amount', '0'))))
    rate_amount = _to_decimal(selected['amount'])

    shipment, _ = Shipment.objects.get_or_create(order=order)
    shipment.provider = 'shippo'
    shipment.external_shipment_id = shipment_payload.get('object_id', '') or ''
    shipment.carrier = selected.get('provider', '') or selected.get('provider_image_200', '') or ''
    service = selected.get('servicelevel') or {}
    shipment.service_level = service.get('name', '') if isinstance(service, dict) else ''
    shipment.rate_id = selected.get('object_id', '') or ''
    shipment.rate_amount = rate_amount
    shipment.package_weight_oz = parcel['weight_oz']
    shipment.package_length_in = parcel['length_in']
    shipment.package_width_in = parcel['width_in']
    shipment.package_height_in = parcel['height_in']
    shipment.save()

    order.shipping_amount = rate_amount
    order.total_amount = order.item_amount + order.platform_fee_amount + order.shipping_amount
    order.save(update_fields=['shipping_amount', 'total_amount', 'updated_at'])
    return shipment


def ensure_checkout_shipping_ready(order):
    shipment = Shipment.objects.filter(order=order).first()
    if shipment and shipment.rate_id and shipment.rate_amount is not None:
        order.shipping_amount = shipment.rate_amount
        order.total_amount = order.item_amount + order.platform_fee_amount + order.shipping_amount
        order.save(update_fields=['shipping_amount', 'total_amount', 'updated_at'])
        ensure_order_snapshots(order)
        return shipment
    return quote_order_shipping(order)


def _normalize_tracking_state(code):
    code = (code or '').upper()
    return TRACKING_TO_SHIPMENT_STATUS.get(code, 'in_transit')


def _shipment_status_to_order_status(status):
    if status == 'label_created':
        return 'label_created'
    if status in {'in_transit', 'out_for_delivery'}:
        return 'in_transit'
    if status == 'delivered':
        return 'delivered'
    return None


def _record_event(shipment, *, status, description, event_time, raw_payload):
    ShipmentEvent.objects.get_or_create(
        shipment=shipment,
        status=status,
        description=description[:500],
        event_time=event_time,
        defaults={'raw_payload': raw_payload or {}},
    )


def _apply_shipment_status(shipment, status, *, description='', raw_payload=None, notify=True):
    shipment.status = status
    shipment.last_event_at = timezone.now()
    shipment.save(update_fields=['status', 'last_event_at', 'updated_at'])
    _record_event(
        shipment,
        status=status,
        description=description or f'Shipment updated to {status}.',
        event_time=shipment.last_event_at,
        raw_payload=raw_payload or {},
    )

    order_status = _shipment_status_to_order_status(status)
    if order_status:
        ok, _ = transition_order(shipment.order, order_status)
        if ok and notify:
            note_type = 'order_delivered' if order_status == 'delivered' else 'order_shipped'
            Notification.objects.create(
                user=shipment.order.buyer,
                notification_type=note_type,
                message=f'Order #{shipment.order_id} shipment status: {shipment.get_status_display()}.',
                link_url=f'/orders/{shipment.order_id}/',
            )


def buy_label_for_order(order):
    shipment = Shipment.objects.filter(order=order).first()
    if not shipment or not shipment.rate_id:
        raise ShippoError('No quoted shipping rate found. Quote shipping before buying label.')
    ensure_order_snapshots(order)
    client = ShippoClient()
    transaction_payload = client.create_transaction(rate_id=shipment.rate_id)
    if (transaction_payload.get('status') or '').upper() not in {'SUCCESS', 'QUEUED'}:
        raise ShippoError(f'Label purchase failed: {transaction_payload}')

    tracking = transaction_payload.get('tracking_number', '') or ''
    shipment.tracking_number = tracking
    shipment.label_url = transaction_payload.get('label_url', '') or ''
    shipment.carrier = transaction_payload.get('tracking_status', {}).get('carrier', shipment.carrier) or shipment.carrier
    shipment.save(update_fields=['tracking_number', 'label_url', 'carrier', 'updated_at'])
    _apply_shipment_status(
        shipment,
        'label_created',
        description='Shipping label purchased.',
        raw_payload=transaction_payload,
    )
    return shipment


def attach_manual_tracking(order, *, carrier, tracking_number):
    ensure_order_snapshots(order)
    shipment, _ = Shipment.objects.get_or_create(order=order, defaults={'provider': 'manual'})
    shipment.provider = shipment.provider or 'manual'
    shipment.carrier = carrier
    shipment.tracking_number = tracking_number
    shipment.save(update_fields=['provider', 'carrier', 'tracking_number', 'updated_at'])
    _apply_shipment_status(
        shipment,
        'in_transit',
        description='Seller entered manual tracking.',
        raw_payload={'carrier': carrier, 'tracking_number': tracking_number},
    )
    return shipment


def refresh_tracking(shipment):
    if not shipment.tracking_number or not shipment.carrier:
        return False
    client = ShippoClient()
    payload = client.get_tracking_status(carrier=shipment.carrier, tracking_number=shipment.tracking_number)
    tracking_status = payload.get('tracking_status') or {}
    status = _normalize_tracking_state(tracking_status.get('status'))
    description = tracking_status.get('status_details') or 'Tracking status updated.'
    _apply_shipment_status(shipment, status, description=description, raw_payload=payload, notify=False)

    history = payload.get('tracking_history') or []
    for item in history:
        code = _normalize_tracking_state(item.get('status'))
        details = item.get('status_details', '') or ''
        event_time_raw = item.get('status_date') or item.get('object_created')
        if event_time_raw:
            try:
                event_time = datetime.fromisoformat(event_time_raw.replace('Z', '+00:00'))
                if timezone.is_naive(event_time):
                    event_time = timezone.make_aware(event_time, timezone.get_current_timezone())
            except ValueError:
                event_time = timezone.now()
        else:
            event_time = timezone.now()
        _record_event(
            shipment,
            status=code,
            description=details,
            event_time=event_time,
            raw_payload=item,
        )
    return True


def handle_tracking_webhook(payload):
    data = payload.get('data') if isinstance(payload, dict) else None
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = [data]
    else:
        events = [payload] if isinstance(payload, dict) else []

    processed = 0
    for event in events:
        tracking_number = event.get('tracking_number') or event.get('tracking')
        carrier = event.get('carrier') or event.get('carrier_code')
        if not tracking_number:
            continue
        shipment = Shipment.objects.filter(tracking_number=tracking_number).first()
        if not shipment and carrier:
            shipment = Shipment.objects.filter(tracking_number=tracking_number, carrier=carrier).first()
        if not shipment:
            continue
        status_code = (
            event.get('tracking_status', {}).get('status')
            if isinstance(event.get('tracking_status'), dict)
            else event.get('status')
        )
        status = _normalize_tracking_state(status_code)
        details = ''
        if isinstance(event.get('tracking_status'), dict):
            details = event['tracking_status'].get('status_details', '')
        _apply_shipment_status(shipment, status, description=details or 'Tracking webhook update.', raw_payload=event)
        processed += 1
    return processed
