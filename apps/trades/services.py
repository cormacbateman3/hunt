from datetime import timedelta
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.notifications.models import Notification
from apps.orders.models import AddressSnapshot
from .models import Trade, TradeOffer, TradeOfferItem, TradeShipment


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
    if offer.trade_listing.trade:
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
