from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.notifications.models import Notification
from apps.orders.models import AddressSnapshot
from apps.shipping.providers.shippo import ShippoClient, ShippoError
from .models import Trade, TradeOffer, TradeOfferItem, TradeShipment


TRADE_TRACKING_TO_SHIPMENT_STATUS = {
    'PRE_TRANSIT': 'label_created',
    'TRANSIT': 'in_transit',
    'OUT_FOR_DELIVERY': 'in_transit',
    'DELIVERED': 'delivered',
}
TRADE_SHIPPED_STATES = {'label_created', 'in_transit', 'delivered', 'confirmed'}
TRADE_DELIVERED_STATES = {'delivered', 'confirmed'}
TRADE_TERMINAL_TRACKING_STATES = {'delivered', 'confirmed'}


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


def validate_trade_gate(user):
    profile = user.profile
    if not profile.email_verified:
        return False, 'Email verification is required before trading.'
    if not profile.shipping_address:
        return False, 'A default shipping address is required before trading.'
    return True, ''


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


def _parcel_to_shippo(parcel):
    return {
        'length': str(parcel['length_in']),
        'width': str(parcel['width_in']),
        'height': str(parcel['height_in']),
        'distance_unit': 'in',
        'weight': str(parcel['weight_oz']),
        'mass_unit': 'oz',
    }


def _normalize_tracking_state(code):
    return TRADE_TRACKING_TO_SHIPMENT_STATUS.get((code or '').upper(), 'in_transit')


def _derive_trade_status(shipments):
    shipped_count = sum(1 for s in shipments if s.status in TRADE_SHIPPED_STATES)
    delivered_count = sum(1 for s in shipments if s.status in TRADE_DELIVERED_STATES)
    confirmed_count = sum(1 for s in shipments if s.status == 'confirmed')

    if confirmed_count >= 2:
        return 'completed'
    if delivered_count >= 2:
        return 'delivered_both'
    if delivered_count == 1:
        return 'delivered_one'
    if shipped_count >= 2:
        return 'shipped_both'
    if shipped_count == 1:
        return 'shipped_one'
    return 'awaiting_shipments'


def _notify_trade_state_change(trade, old_status, new_status):
    if new_status == old_status:
        return

    if new_status in {'shipped_one', 'shipped_both'}:
        note_type = 'trade_shipped'
        message = f'Trade #{trade.pk} shipment progress updated ({trade.get_status_display()}).'
    elif new_status in {'delivered_one', 'delivered_both'}:
        note_type = 'trade_delivered'
        message = f'Trade #{trade.pk} delivery progress updated ({trade.get_status_display()}).'
    elif new_status == 'completed':
        note_type = 'trade_completed'
        message = f'Trade #{trade.pk} is now completed.'
    else:
        return

    for user in {trade.initiator, trade.counterparty}:
        Notification.objects.create(
            user=user,
            notification_type=note_type,
            message=message,
            link_url=f'/trades/{trade.pk}/',
        )


def sync_trade_status(trade, *, notify=True):
    shipments = list(trade.shipments.all())
    if len(shipments) < 2:
        return trade.status

    next_status = _derive_trade_status(shipments)
    previous = trade.status
    if next_status != previous:
        trade.status = next_status
        trade.save(update_fields=['status', 'updated_at'])
        if notify:
            _notify_trade_state_change(trade, previous, next_status)
    return trade.status


def _ensure_trade_shipment_snapshots(shipment):
    sender_address = getattr(shipment.sender.profile, 'shipping_address', None)
    recipient_address = getattr(shipment.recipient.profile, 'shipping_address', None)
    if not sender_address or not recipient_address:
        raise ShippoError('Both traders need default shipping addresses configured.')

    updated = False
    if not shipment.ship_from_snapshot:
        shipment.ship_from_snapshot = _snapshot_from_address(sender_address)
        updated = True
    if not shipment.ship_to_snapshot:
        shipment.ship_to_snapshot = _snapshot_from_address(recipient_address)
        updated = True
    if updated:
        shipment.save(update_fields=['ship_from_snapshot', 'ship_to_snapshot', 'updated_at'])


def apply_trade_shipment_status(shipment, status, *, notify=True):
    status = status or shipment.status
    updates = []
    if shipment.status != status:
        shipment.status = status
        updates.append('status')
    now = timezone.now()
    shipment.last_event_at = now
    updates.append('last_event_at')
    if status == 'delivered' and not shipment.delivered_at:
        shipment.delivered_at = now
        updates.append('delivered_at')
    if updates:
        updates.append('updated_at')
        shipment.save(update_fields=updates)
    sync_trade_status(shipment.trade, notify=notify)
    return shipment


def add_trade_manual_tracking(*, shipment, actor, carrier, tracking_number):
    if actor.id != shipment.sender_id:
        return None, 'Only the sending trader can enter tracking.'
    carrier = (carrier or '').strip()
    tracking_number = (tracking_number or '').strip()
    if not carrier or not tracking_number:
        return None, 'Carrier and tracking number are required.'

    _ensure_trade_shipment_snapshots(shipment)
    shipment.provider = shipment.provider or 'manual'
    shipment.carrier = carrier
    shipment.tracking_number = tracking_number
    shipment.save(update_fields=['provider', 'carrier', 'tracking_number', 'updated_at'])
    apply_trade_shipment_status(shipment, 'in_transit')
    return shipment, ''


def buy_trade_label(*, shipment, actor, parcel):
    if actor.id != shipment.sender_id:
        return None, 'Only the sending trader can buy labels.'
    _ensure_trade_shipment_snapshots(shipment)

    client = ShippoClient()
    shipment_payload = client.create_shipment(
        address_from=_address_to_shippo_payload(shipment.ship_from_snapshot),
        address_to=_address_to_shippo_payload(shipment.ship_to_snapshot),
        parcel=_parcel_to_shippo(parcel),
    )
    rates = shipment_payload.get('rates') or []
    if not rates:
        return None, 'No shipping rates returned by Shippo.'
    selected = min(rates, key=lambda r: Decimal(str(r.get('amount', '0'))))
    rate_id = selected.get('object_id')
    if not rate_id:
        return None, 'Shippo did not return a purchasable rate.'

    transaction_payload = client.create_transaction(rate_id=rate_id)
    if (transaction_payload.get('status') or '').upper() not in {'SUCCESS', 'QUEUED'}:
        return None, 'Shippo label purchase failed.'

    shipment.provider = 'shippo'
    shipment.carrier = (
        transaction_payload.get('tracking_status', {}).get('carrier')
        or selected.get('provider')
        or shipment.carrier
    )
    shipment.tracking_number = transaction_payload.get('tracking_number', '') or ''
    shipment.label_url = transaction_payload.get('label_url', '') or ''
    shipment.save(update_fields=['provider', 'carrier', 'tracking_number', 'label_url', 'updated_at'])
    apply_trade_shipment_status(shipment, 'label_created')
    return shipment, ''


def refresh_trade_tracking(shipment):
    if not shipment.tracking_number or not shipment.carrier:
        return False
    client = ShippoClient()
    payload = client.get_tracking_status(carrier=shipment.carrier, tracking_number=shipment.tracking_number)
    tracking_status = payload.get('tracking_status') or {}
    status = _normalize_tracking_state(tracking_status.get('status'))
    apply_trade_shipment_status(shipment, status, notify=False)
    return True


def handle_trade_tracking_webhook(payload):
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
        shipment = TradeShipment.objects.filter(tracking_number=tracking_number).first()
        if not shipment and carrier:
            shipment = TradeShipment.objects.filter(
                tracking_number=tracking_number,
                carrier=carrier,
            ).first()
        if not shipment:
            continue
        status_code = (
            event.get('tracking_status', {}).get('status')
            if isinstance(event.get('tracking_status'), dict)
            else event.get('status')
        )
        status = _normalize_tracking_state(status_code)
        apply_trade_shipment_status(shipment, status)
        processed += 1
    return processed


def confirm_trade_receipt(*, shipment, actor):
    if actor.id != shipment.recipient_id:
        return None, 'Only the receiving trader can confirm receipt.'
    if shipment.status not in {'delivered', 'confirmed'}:
        return None, 'Shipment must be delivered before confirmation.'

    shipment.status = 'confirmed'
    if not shipment.recipient_confirmed_at:
        shipment.recipient_confirmed_at = timezone.now()
    shipment.save(update_fields=['status', 'recipient_confirmed_at', 'updated_at'])
    sync_trade_status(shipment.trade)
    return shipment, ''


def auto_complete_delivered_trades(*, grace_days=3, limit=200):
    threshold = timezone.now() - timedelta(days=grace_days)
    candidates = (
        Trade.objects.filter(status='delivered_both')
        .select_related('listing')
        .prefetch_related('shipments')
        .order_by('updated_at')[:limit]
    )

    completed = 0
    for trade in candidates:
        shipments = list(trade.shipments.all())
        if len(shipments) < 2:
            continue
        if any(s.status not in TRADE_DELIVERED_STATES for s in shipments):
            continue
        if any(not s.delivered_at or s.delivered_at > threshold for s in shipments):
            continue
        for shipment in shipments:
            if shipment.status != 'confirmed':
                shipment.status = 'confirmed'
                if not shipment.recipient_confirmed_at:
                    shipment.recipient_confirmed_at = timezone.now()
                shipment.save(update_fields=['status', 'recipient_confirmed_at', 'updated_at'])
        sync_trade_status(trade)
        completed += 1
    return completed, threshold


def create_trade_offer(
    *,
    listing,
    from_user,
    to_user,
    offered_items,
    message='',
    cash_amount=Decimal('0.00'),
    expires_days=4,
    counter_to=None,
):
    if listing.listing_type != 'trade':
        return None, 'This listing is not a trade listing.'
    if listing.status != 'active':
        return None, 'Trade listing is not currently active.'
    if Trade.objects.filter(listing=listing).exists():
        return None, 'This trade listing already has an accepted trade.'
    if from_user.id == to_user.id:
        return None, 'Cannot create a trade offer to yourself.'

    ok, reason = validate_trade_gate(from_user)
    if not ok:
        return None, reason

    offered_items = list(offered_items)
    if not offered_items:
        return None, 'At least one offered item is required.'
    for item in offered_items:
        if item.owner_id != from_user.id:
            return None, 'All offered items must belong to the proposer.'
        if not item.trade_eligible:
            return None, f'"{item.title}" is not trade-eligible.'
    if cash_amount and not listing.allow_cash:
        return None, 'This listing does not allow cash add-ons.'

    expires_at = timezone.now() + timedelta(days=expires_days or 4)
    with transaction.atomic():
        offer = TradeOffer.objects.create(
            trade_listing=listing,
            from_user=from_user,
            to_user=to_user,
            status='pending',
            expires_at=expires_at,
            message=message,
            cash_amount=cash_amount or Decimal('0.00'),
            counter_to=counter_to,
        )

        for item in offered_items:
            TradeOfferItem.objects.create(
                offer=offer,
                collection_item=item,
                direction='offered',
            )

        requested_item = listing.source_collection_item
        if requested_item:
            TradeOfferItem.objects.create(
                offer=offer,
                collection_item=requested_item,
                direction='requested',
            )

        if counter_to and counter_to.status == 'pending':
            counter_to.status = 'countered'
            counter_to.save(update_fields=['status', 'updated_at'])
            Notification.objects.create(
                user=counter_to.from_user,
                notification_type='trade_offer_countered',
                message=f'Your trade offer #{counter_to.pk} received a counteroffer.',
                link_url=f'/trades/offers/{offer.pk}/',
            )

        Notification.objects.create(
            user=to_user,
            notification_type='trade_offer_countered' if counter_to else 'trade_offer_received',
            message=(
                f'New counteroffer #{offer.pk} on "{listing.title}".'
                if counter_to else
                f'New trade offer #{offer.pk} on "{listing.title}".'
            ),
            link_url=f'/trades/offers/{offer.pk}/',
        )

    return offer, ''


def _create_trade_shipments(trade):
    initiator_address = getattr(trade.initiator.profile, 'shipping_address', None)
    counterparty_address = getattr(trade.counterparty.profile, 'shipping_address', None)

    TradeShipment.objects.get_or_create(
        trade=trade,
        sender=trade.initiator,
        recipient=trade.counterparty,
        defaults={
            'provider': 'manual',
            'status': 'pending',
            'ship_from_snapshot': _snapshot_from_address(initiator_address) if initiator_address else None,
            'ship_to_snapshot': _snapshot_from_address(counterparty_address) if counterparty_address else None,
        },
    )
    TradeShipment.objects.get_or_create(
        trade=trade,
        sender=trade.counterparty,
        recipient=trade.initiator,
        defaults={
            'provider': 'manual',
            'status': 'pending',
            'ship_from_snapshot': _snapshot_from_address(counterparty_address) if counterparty_address else None,
            'ship_to_snapshot': _snapshot_from_address(initiator_address) if initiator_address else None,
        },
    )


def accept_trade_offer(offer, actor):
    if offer.status != 'pending':
        return None, 'Only pending offers can be accepted.'
    if offer.expires_at and offer.expires_at <= timezone.now():
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])
        return None, 'Offer has already expired.'
    if actor.id != offer.to_user_id:
        return None, 'Only the recipient can accept this offer.'
    if Trade.objects.filter(listing=offer.trade_listing).exists():
        return None, 'This listing already has an accepted trade.'

    ok, reason = validate_trade_gate(actor)
    if not ok:
        return None, reason

    with transaction.atomic():
        locked_offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if locked_offer.status != 'pending':
            return None, 'Offer is no longer pending.'
        listing = locked_offer.trade_listing
        if Trade.objects.filter(listing=listing).exists():
            return None, 'This listing already has an accepted trade.'

        trade = Trade.objects.create(
            listing=listing,
            initiator=locked_offer.from_user,
            counterparty=locked_offer.to_user,
            status='awaiting_shipments',
            ship_by_deadline=timezone.now() + timedelta(days=5),
        )
        _create_trade_shipments(trade)

        locked_offer.status = 'accepted'
        locked_offer.save(update_fields=['status', 'updated_at'])
        TradeOffer.objects.filter(
            trade_listing=listing,
            status='pending',
        ).exclude(pk=locked_offer.pk).update(status='declined')
        listing.status = 'sold'
        listing.save(update_fields=['status', 'updated_at'])

        Notification.objects.create(
            user=trade.initiator,
            notification_type='trade_offer_accepted',
            message=f'Your trade offer #{locked_offer.pk} was accepted.',
            link_url=f'/trades/{trade.pk}/',
        )
        Notification.objects.create(
            user=trade.counterparty,
            notification_type='trade_offer_accepted',
            message=f'You accepted trade offer #{locked_offer.pk}. Trade #{trade.pk} created.',
            link_url=f'/trades/{trade.pk}/',
        )
    return trade, ''


def decline_trade_offer(offer, actor):
    if offer.status != 'pending':
        return False, 'Only pending offers can be declined.'
    if offer.expires_at and offer.expires_at <= timezone.now():
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])
        return False, 'Offer has already expired.'
    if actor.id != offer.to_user_id:
        return False, 'Only the recipient can decline this offer.'
    offer.status = 'declined'
    offer.save(update_fields=['status', 'updated_at'])
    Notification.objects.create(
        user=offer.from_user,
        notification_type='trade_offer_declined',
        message=f'Your trade offer #{offer.pk} was declined.',
        link_url=f'/trades/offers/{offer.pk}/',
    )
    return True, ''


def withdraw_trade_offer(offer, actor):
    if offer.status != 'pending':
        return False, 'Only pending offers can be withdrawn.'
    if offer.expires_at and offer.expires_at <= timezone.now():
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])
        return False, 'Offer has already expired.'
    if actor.id != offer.from_user_id:
        return False, 'Only the proposer can withdraw this offer.'
    offer.status = 'withdrawn'
    offer.save(update_fields=['status', 'updated_at'])
    return True, ''


def expire_offers(limit=500):
    now = timezone.now()
    pending = TradeOffer.objects.filter(status='pending', expires_at__lte=now).order_by('expires_at')[:limit]
    expired = 0
    for offer in pending:
        offer.status = 'expired'
        offer.save(update_fields=['status', 'updated_at'])
        expired += 1
    return expired
