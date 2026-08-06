from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.accounts.bench import ship_by_days
from apps.collections.tradeability import trade_block_reason
from apps.notifications.services import create_notification
from apps.enforcement.services import enforce_capability
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
    allowed, reason = enforce_capability(user, 'trade')
    if not allowed:
        return False, reason
    profile = user.profile
    if not profile.email_verified:
        return False, (
            'To trade, your email must be verified. '
            f'<a href="{reverse("accounts:resend_verification")}">Resend verification email &rarr;</a>'
        )
    if not profile.shipping_address:
        return False, (
            'To trade, you need a saved shipping address. '
            f'<a href="{reverse("accounts:address_add")}">Add address &rarr;</a>'
        )
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
        create_notification(
            user=user,
            notification_type=note_type,
            message=message,
            link_url=f'/trades/{trade.pk}/',
        )


def _close_traded_pieces(trade):
    """Record that the traded licences have physically changed hands.

    Ownership does not transfer. Nothing anywhere moves a CollectionItem
    between owners, and doing that properly belongs with the collection work
    — but leaving both sides' pieces advertised is worse than the gap
    itself. A second collector proposes for a licence that left months ago,
    the owner accepts, cannot ship it because it is in somebody else's
    drawer, and takes a non-shipment strike for something that was never
    theirs to give.

    This used to write ``tradeability='closed'``, which stopped the offers
    but told the wrong story — the owner's standing answer is not what
    changed; the piece *left*. ``disposition`` is the honest record, it
    blocks trade availability the same way, and it leaves the owner's
    tradeability answer alone for whenever ownership transfer exists.
    """
    from apps.collections.models import CollectionItem

    # The accepted offer is the trade's own record now, so this no longer
    # has to go looking for it through the lot — which was never possible
    # for a trade struck without one.
    accepted = trade.offer
    if accepted is None:
        return

    # Both directions: each side's piece has left its owner.
    item_ids = [
        item.collection_item_id for item in accepted.items.all()
        if item.collection_item_id
    ]
    if item_ids:
        CollectionItem.objects.filter(pk__in=item_ids).update(
            disposition='traded')


def sync_trade_status(trade, *, notify=True):
    shipments = list(trade.shipments.all())
    if len(shipments) < 2:
        return trade.status

    next_status = _derive_trade_status(shipments)
    previous = trade.status
    if next_status != previous:
        trade.status = next_status
        trade.save(update_fields=['status', 'updated_at'])
        if next_status == 'completed':
            _close_traded_pieces(trade)
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


# A trade can be proposed against a Trading Block lot or a General Store
# shelf. It cannot be proposed against an auction: an auction is a binding
# commitment to sell to the highest bidder, and a trade struck mid-lot takes
# the goods out from under them.
TRADEABLE_LISTING_TYPES = ('trade', 'buy_now')


def open_trade_on(item):
    """The live trade already committing this piece, or None.

    Uniqueness used to hang off `Trade.listing`, so the question could only
    be asked about a lot. It is really a question about the **piece**: you
    cannot promise the same licence to two people, whether or not either
    negotiation went through a listing.
    """
    return (
        Trade.objects
        .filter(offer__items__collection_item=item, status__in=Trade.OPEN_STATUSES)
        .first()
    )


def create_trade_offer(
    *,
    subject_item=None,
    listing=None,
    from_user,
    to_user,
    offered_items,
    requested_items=None,
    message='',
    cash_amount=Decimal('0.00'),
    cash_direction='from_proposer',
    expires_days=4,
    counter_to=None,
):
    """Open or continue a negotiation about one piece.

    Either a `subject_item` (somebody's licence, listed or not) or a
    `listing` whose source item becomes the subject. A listing is no longer
    required — that requirement is what made "propose a trade" a walk to
    somebody's shelf rather than a button.
    """
    if listing is not None:
        if listing.listing_type not in TRADEABLE_LISTING_TYPES:
            return None, 'This listing cannot take trade offers.'
        if listing.status != 'active':
            return None, 'This listing is not currently active.'
        if subject_item is None:
            subject_item = listing.source_collection_item

    if subject_item is None:
        return None, 'A trade has to be about something.'
    # The subject is the anchor of the whole negotiation and does not change
    # hands as it goes back and forth — but which *side* of the table it sits
    # on does. Rae asks Walt for his 1916; Walt counters, and the same 1916
    # is now the thing Walt is giving. So the owner has to be one of the two,
    # not specifically the recipient.
    if subject_item.owner_id not in {from_user.id, to_user.id}:
        return None, 'That piece belongs to neither of you.'
    blocked = trade_block_reason(subject_item)
    if blocked:
        return None, f'"{subject_item.title}" cannot be traded: {blocked}'
    if open_trade_on(subject_item):
        return None, 'That piece is already committed to a trade.'
    if from_user.id == to_user.id:
        return None, 'Cannot create a trade offer to yourself.'

    ok, reason = validate_trade_gate(from_user)
    if not ok:
        return None, reason

    offered_items = list(offered_items)
    for item in offered_items:
        if item.owner_id != from_user.id:
            return None, 'All offered items must belong to the proposer.'
        blocked = trade_block_reason(item)
        if blocked:
            return None, f'"{item.title}" cannot be traded: {blocked}'

    # The design's right-hand roster is a real control: you pick what you
    # want off their shelf, not just what you arrived asking about. The
    # subject piece is always on the table — it is what you came for.
    requested = list(requested_items or [])
    for item in requested:
        if item.owner_id != to_user.id:
            return None, 'All requested items must belong to the other trader.'
        if not item.is_public:
            return None, f'"{item.title}" is not on public show.'
        blocked = trade_block_reason(item)
        if blocked:
            return None, f'"{item.title}" cannot be traded: {blocked}'

    # `subject_item` is what the negotiation is **filed under**, not a piece
    # nailed to the table. Swapping it out is an ordinary move — the design's
    # own second round is "asked for the 1944 Fulton instead" — so every
    # licence here has an ×, including the one you arrived about. The subject
    # keeps the thread together; the table is free.
    if not offered_items:
        return None, 'Put at least one of your licences on the table.'
    if not requested:
        return None, 'Ask for at least one of theirs.'

    # A lot's owner decides whether cash is welcome. A piece that was never
    # listed has nobody's answer on file, so cash is allowed — evening a swap
    # up is the ordinary case, and refusing by default would be inventing a
    # preference nobody expressed.
    if cash_amount and listing is not None and not listing.allow_cash:
        return None, 'This listing does not allow cash add-ons.'
    if cash_amount and cash_amount < 0:
        return None, 'Cash cannot be negative — pick a direction instead.'
    if cash_direction not in dict(TradeOffer.CASH_DIRECTION_CHOICES):
        return None, 'Unknown cash direction.'

    expires_at = timezone.now() + timedelta(days=expires_days or 4)
    with transaction.atomic():
        offer = TradeOffer.objects.create(
            subject_item=subject_item,
            trade_listing=listing,
            from_user=from_user,
            to_user=to_user,
            status='pending',
            expires_at=expires_at,
            message=message,
            cash_amount=cash_amount or Decimal('0.00'),
            cash_direction=cash_direction,
            counter_to=counter_to,
        )

        for item in offered_items:
            TradeOfferItem.objects.create(
                offer=offer,
                collection_item=item,
                direction='offered',
            )

        for item in requested:
            TradeOfferItem.objects.create(
                offer=offer,
                collection_item=item,
                direction='requested',
            )

        if counter_to and counter_to.status == 'pending':
            counter_to.status = 'countered'
            counter_to.save(update_fields=['status', 'updated_at'])
            # Only when it came from the other chair. Revising your own offer
            # supersedes it just the same, but telling somebody their offer
            # was countered by themselves is noise.
            if counter_to.from_user_id != from_user.id:
                create_notification(
                    user=counter_to.from_user,
                    notification_type='trade_offer_countered',
                    message=f'Your trade offer on "{subject_item.title}" was countered.',
                    link_url=f'/trades/offers/{offer.pk}/',
                )

        create_notification(
            user=to_user,
            notification_type='trade_offer_countered' if counter_to else 'trade_offer_received',
            message=(
                f'New counteroffer on "{subject_item.title}".'
                if counter_to else
                f'{from_user.username} has offered a trade for your '
                f'"{subject_item.title}".'
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
    # The question is about the **piece**, not the lot: you cannot promise
    # the same licence to two people, listed or not.
    if offer.subject_item_id and open_trade_on(offer.subject_item):
        return None, 'That piece is already committed to a trade.'

    ok, reason = validate_trade_gate(actor)
    if not ok:
        return None, reason

    with transaction.atomic():
        locked_offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if locked_offer.status != 'pending':
            return None, 'Offer is no longer pending.'
        if Trade.objects.filter(offer=locked_offer).exists():
            return None, 'This offer has already been accepted.'
        listing = locked_offer.trade_listing

        trade = Trade.objects.create(
            offer=locked_offer,
            listing=listing,
            initiator=locked_offer.from_user,
            counterparty=locked_offer.to_user,
            status='awaiting_shipments',
            ship_by_deadline=timezone.now() + timedelta(days=ship_by_days()),
        )
        _create_trade_shipments(trade)

        locked_offer.status = 'accepted'
        locked_offer.save(update_fields=['status', 'updated_at'])

        # Every other live negotiation about the same piece is over — the
        # licence has gone. Scoped to the piece rather than the lot, because
        # a piece can now be asked about without one.
        rivals = TradeOffer.objects.filter(status='pending').exclude(pk=locked_offer.pk)
        if locked_offer.subject_item_id:
            rivals = rivals.filter(subject_item_id=locked_offer.subject_item_id)
        elif listing:
            rivals = rivals.filter(trade_listing=listing)
        else:
            rivals = TradeOffer.objects.none()
        rivals.update(status='declined')

        if listing:
            listing.status = 'sold'
            listing.save(update_fields=['status', 'updated_at'])

        subject = locked_offer.subject_item.title if locked_offer.subject_item_id else 'your licence'
        create_notification(
            user=trade.initiator,
            notification_type='trade_offer_accepted',
            message=f'Your trade offer for "{subject}" was accepted.',
            link_url=f'/trades/{trade.pk}/',
        )
        create_notification(
            user=trade.counterparty,
            notification_type='trade_offer_accepted',
            message=f'You accepted the trade for "{subject}". Both sides ship next.',
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
    create_notification(
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
        create_notification(
            user=offer.from_user,
            notification_type='trade_offer_expired',
            message=f'Trade offer #{offer.pk} expired without response.',
            link_url=f'/trades/offers/{offer.pk}/',
            dedupe_window_hours=24,
        )
        expired += 1
    return expired
