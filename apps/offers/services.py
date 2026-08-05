"""Offer business rules.

Idiom matches apps/trades/services.py: every entry point returns
`(result, error_message)` and never raises for a business-rule failure —
views translate the tuple into `messages.*`.
"""

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification
from apps.offers.models import (
    ACCEPTED_PAYMENT_WINDOW_HOURS,
    DEFAULT_EXPIRES_DAYS,
    Offer,
)
from apps.orders.models import Order

# Order statuses that mean the listing is genuinely sold — an offer can no
# longer be made or accepted against it.
PAID_ORDER_STATUSES = {'paid', 'label_created', 'in_transit', 'delivered', 'completed'}

ACCEPTED_WINDOW_LABEL = f'{ACCEPTED_PAYMENT_WINDOW_HOURS} hours'


def _offer_url(offer):
    return f'/offers/{offer.pk}/'


def active_offers(listing):
    """Offers still awaiting a response, newest first."""
    return listing.offers.filter(status='pending').order_by('-created_at')


def reserving_offer(listing):
    """The accepted offer holding this listing, if any and not lapsed."""
    for offer in listing.offers.filter(status='accepted').order_by('-accepted_at'):
        if offer.reserves_listing:
            return offer
    return None


def accepted_offer_for(listing, user):
    """The accepted offer entitling `user` to buy `listing` at a agreed price."""
    if not user or not user.is_authenticated:
        return None
    offer = reserving_offer(listing)
    if offer and offer.buyer.id == user.id:
        return offer
    return None


def offer_price_for(listing, user):
    """Item price `user` should be charged: agreed offer price, else list price."""
    offer = accepted_offer_for(listing, user)
    if offer:
        return offer.amount, offer
    return listing.buy_now_price, None


def can_offer_on(listing):
    """Whether the listing is structurally open to offers."""
    if listing.listing_type != 'buy_now' or not listing.allow_offers:
        return False, 'This listing is not accepting offers.'
    if listing.status != 'active':
        return False, 'This listing is not currently available.'
    if not listing.buy_now_price:
        return False, 'This listing has no price to negotiate against.'
    order = Order.objects.filter(listing=listing).first()
    if order and order.status in PAID_ORDER_STATUSES:
        return False, 'This listing has already been purchased.'
    return True, ''


def create_offer(*, listing, from_user, amount, message='',
                 expires_days=DEFAULT_EXPIRES_DAYS, counter_to=None):
    """Create a buyer offer, or a seller counter when `counter_to` is given."""
    open_for_offers, reason = can_offer_on(listing)
    if not open_for_offers:
        return None, reason

    is_seller = from_user.id == listing.seller_id

    # Sellers may only respond, never originate — this is the anti-spam rule
    # in the 10.9 spec ("Sellers cannot originate an offer").
    if is_seller and counter_to is None:
        return None, 'Sellers cannot make offers on their own listing. You can only counter a buyer offer.'
    if not is_seller:
        allowed, capability_reason = enforce_capability(from_user, 'buy_now')
        if not allowed:
            return None, capability_reason

    amount = Decimal(amount)
    if amount <= 0:
        return None, 'Enter an offer above $0.'
    if is_seller:
        # A counter is the seller naming their price: it may sit anywhere up to
        # list price, but at list price the buyer should just buy it outright.
        if amount >= listing.buy_now_price:
            return None, 'A counter must be below the list price.'
    elif amount >= listing.buy_now_price:
        return None, 'Your offer must be below the list price — use Buy now to pay the asking price.'
    elif listing.minimum_offer and amount < listing.minimum_offer:
        # The seller's floor, applied here rather than silently. Telling the
        # buyer the number is the point: an offer turned away without one is
        # a guessing game, and the seller wanted to save both of them the
        # round trip, not hide the price.
        return None, (
            f'The seller is not taking offers below ${listing.minimum_offer:,.2f} '
            f'on this one. Offer that or more and it will reach them.'
        )

    if counter_to is not None:
        if counter_to.listing_id != listing.id:
            return None, 'That offer belongs to a different listing.'
        if counter_to.status != 'pending':
            return None, 'That offer is no longer open to a counter.'
        if counter_to.is_expired:
            _mark_expired(counter_to)
            return None, 'That offer has already expired.'
        if counter_to.to_user_id != from_user.id:
            return None, 'You can only counter an offer made to you.'
        to_user = counter_to.from_user
    else:
        to_user = listing.seller

    if not is_seller and listing.offers.filter(
        from_user=from_user, status='pending'
    ).exists():
        return None, 'You already have an offer pending on this listing. Withdraw it first.'

    expires_at = timezone.now() + timedelta(days=expires_days or DEFAULT_EXPIRES_DAYS)

    with transaction.atomic():
        offer = Offer.objects.create(
            listing=listing,
            from_user=from_user,
            to_user=to_user,
            amount=amount,
            message=message,
            counter_to=counter_to,
            expires_at=expires_at,
        )
        if counter_to is not None:
            Offer.objects.filter(pk=counter_to.pk, status='pending').update(
                status='countered', updated_at=timezone.now()
            )

    create_notification(
        user=to_user,
        notification_type='offer_countered' if counter_to else 'offer_received',
        message=(
            f'{from_user.username} countered at ${amount} on "{listing.title}".'
            if counter_to
            else f'{from_user.username} offered ${amount} on "{listing.title}".'
        ),
        link_url=_offer_url(offer),
    )
    return offer, ''


def _mark_expired(offer):
    Offer.objects.filter(pk=offer.pk, status='pending').update(
        status='expired', updated_at=timezone.now()
    )
    offer.status = 'expired'


def accept_offer(offer, actor):
    """Accept an offer. Binding — the buyer then owes payment at `amount`."""
    if offer.status != 'pending':
        return None, 'Only pending offers can be accepted.'
    if offer.is_expired:
        _mark_expired(offer)
        return None, 'That offer has already expired.'
    if actor.id != offer.to_user_id:
        return None, 'Only the recipient can accept this offer.'

    listing = offer.listing
    open_for_offers, reason = can_offer_on(listing)
    if not open_for_offers:
        return None, reason

    held = reserving_offer(listing)
    if held and held.pk != offer.pk:
        return None, 'Another accepted offer already holds this listing.'

    # The buyer must still be able to transact at accept time.
    allowed, capability_reason = enforce_capability(offer.buyer, 'buy_now')
    if not allowed:
        return None, f'The buyer cannot currently complete a purchase: {capability_reason}'

    with transaction.atomic():
        locked = Offer.objects.select_for_update().get(pk=offer.pk)
        if locked.status != 'pending':
            return None, 'Only pending offers can be accepted.'
        locked.status = 'accepted'
        locked.accepted_at = timezone.now()
        locked.save(update_fields=['status', 'accepted_at', 'updated_at'])

        # One winner per listing: everything else still open is now moot.
        Offer.objects.filter(listing=listing, status='pending').exclude(
            pk=locked.pk
        ).update(status='declined', updated_at=timezone.now())

    offer.refresh_from_db()
    buyer, seller = offer.buyer, listing.seller
    create_notification(
        user=buyer,
        notification_type='offer_accepted',
        message=(
            f'Your ${offer.amount} offer on "{listing.title}" was accepted. '
            f'Complete payment within {ACCEPTED_WINDOW_LABEL} to secure it.'
        ),
        link_url=f'/listings/{listing.pk}/buy-now/review/',
    )
    create_notification(
        user=seller,
        notification_type='offer_accepted',
        message=f'You accepted a ${offer.amount} offer on "{listing.title}".',
        link_url=_offer_url(offer),
    )
    return offer, ''


def decline_offer(offer, actor):
    if offer.status != 'pending':
        return None, 'Only pending offers can be declined.'
    if offer.is_expired:
        _mark_expired(offer)
        return None, 'That offer has already expired.'
    if actor.id != offer.to_user_id:
        return None, 'Only the recipient can decline this offer.'

    offer.status = 'declined'
    offer.save(update_fields=['status', 'updated_at'])
    create_notification(
        user=offer.from_user,
        notification_type='offer_declined',
        message=f'Your ${offer.amount} offer on "{offer.listing.title}" was declined.',
        link_url=_offer_url(offer),
    )
    return True, ''


def withdraw_offer(offer, actor):
    if offer.status != 'pending':
        return None, 'Only pending offers can be withdrawn.'
    if actor.id != offer.from_user_id:
        return None, 'Only the sender can withdraw this offer.'

    offer.status = 'withdrawn'
    offer.save(update_fields=['status', 'updated_at'])
    return True, ''


def expire_offers(limit=500):
    """Sweep both kinds of staleness. Returns (pending_expired, reservations_lapsed)."""
    now = timezone.now()

    stale_pending = list(
        Offer.objects.filter(status='pending', expires_at__lte=now)[:limit]
    )
    for offer in stale_pending:
        updated = Offer.objects.filter(pk=offer.pk, status='pending').update(
            status='expired', updated_at=now
        )
        if updated:
            create_notification(
                user=offer.from_user,
                notification_type='offer_expired',
                message=f'Your ${offer.amount} offer on "{offer.listing.title}" expired.',
                link_url=_offer_url(offer),
                dedupe_window_hours=24,
            )

    # Accepted but unpaid past the window. Only lapse when no order has been
    # paid — a paid order means the offer did its job.
    lapsed = 0
    for offer in Offer.objects.filter(status='accepted', accepted_at__isnull=False)[:limit]:
        if not offer.reservation_lapsed:
            continue
        order = Order.objects.filter(listing=offer.listing).first()
        if order and order.status in PAID_ORDER_STATUSES:
            continue
        updated = Offer.objects.filter(pk=offer.pk, status='accepted').update(
            status='expired', updated_at=now
        )
        if updated:
            lapsed += 1
            create_notification(
                user=offer.buyer,
                notification_type='offer_expired',
                message=(
                    f'Your accepted offer on "{offer.listing.title}" lapsed — '
                    'payment was not completed in time.'
                ),
                link_url=_offer_url(offer),
                dedupe_window_hours=24,
            )
    return len(stale_pending), lapsed
