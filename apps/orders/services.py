from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.core.models import MarketplaceSettings


ORDER_TRANSITIONS = {
    'pending_payment': {'paid', 'cancelled'},
    'paid': {'label_created', 'in_transit', 'delivered', 'completed', 'refunded', 'cancelled'},
    'label_created': {'in_transit', 'delivered', 'completed', 'refunded', 'cancelled'},
    'in_transit': {'delivered', 'completed', 'refunded'},
    'delivered': {'completed', 'refunded'},
    'completed': set(),
    'cancelled': set(),
    'refunded': set(),
}


def can_transition(order, target_status):
    return target_status in ORDER_TRANSITIONS.get(order.status, set())


def transition_order(order, target_status, *, actor=None):
    if not can_transition(order, target_status):
        return False, f'Cannot transition from {order.status} to {target_status}.'

    if actor and target_status in {'label_created', 'in_transit', 'delivered'}:
        if actor.id != order.seller_id:
            return False, 'Only the seller can update shipping-related statuses.'

    if actor and target_status == 'completed':
        if actor.id not in {order.buyer_id, order.seller_id}:
            return False, 'Only order participants can complete the order.'

    order.status = target_status
    order.save(update_fields=['status', 'updated_at'])
    return True, 'Order updated.'


def auto_complete_delivered_orders(grace_days=3, limit=200):
    threshold = timezone.now() - timedelta(days=grace_days)
    # Keep queryset simple and explicit for command-level control.
    from apps.enforcement.handshakes import order_has_handshake
    from .models import Order
    queryset = (
        Order.objects.filter(status='delivered', updated_at__lte=threshold)
        .order_by('updated_at')[:limit]
    )
    completed_count = 0
    for order in queryset:
        # If the two of them agreed to hold this one open — a parcel gone
        # astray, a buyer away from home — assuming receipt would decide it
        # against the buyer on their behalf.
        if order_has_handshake(order.pk, 'receipt'):
            continue
        ok, _ = transition_order(order, 'completed')
        if ok:
            completed_count += 1
    return completed_count, threshold


def get_platform_fee_percent():
    settings_obj = MarketplaceSettings.objects.order_by('id').first()
    if not settings_obj:
        return Decimal('0.00')
    return settings_obj.platform_fee_percent


def calculate_platform_fee(item_amount):
    percent = get_platform_fee_percent()
    fee = (item_amount * percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return fee


def build_order_amounts(item_amount):
    """(item, platform_fee, total) for a purchase at `item_amount`.

    Single source of truth for order pricing. Both purchase paths must use it:
    close_auctions previously hardcoded platform_fee_amount=0 and
    total=item, so the platform fee was silently lost on every auction sale
    (shipping is added later by apply_shipping_to_order, which rebuilds the
    total from item + platform_fee, so a zero fee stayed zero all the way to
    the Stripe charge).
    """
    item_amount = Decimal(item_amount)
    platform_fee = calculate_platform_fee(item_amount)
    return item_amount, platform_fee, item_amount + platform_fee


def release_stale_pending_buy_now_orders(timeout_minutes=30, limit=200):
    from .models import Order
    threshold = timezone.now() - timedelta(minutes=timeout_minutes)
    queryset = (
        Order.objects.select_related('listing')
        .filter(order_type='buy_now', status='pending_payment', created_at__lte=threshold)
        .order_by('created_at')[:limit]
    )
    released_count = 0
    for order in queryset:
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().select_related('listing').get(pk=order.pk)
            listing = locked_order.listing
            if locked_order.status != 'pending_payment' or listing.listing_type != 'buy_now':
                continue
            if listing.status == 'pending':
                listing.status = 'active'
                listing.save(update_fields=['status', 'updated_at'])
            payment = getattr(locked_order, 'payment', None)
            if payment and payment.status in {'pending', 'processing'}:
                payment.status = 'failed'
                payment.save(update_fields=['status', 'updated_at'])
            locked_order.status = 'cancelled'
            locked_order.save(update_fields=['status', 'updated_at'])
            released_count += 1
    return released_count, threshold


def release_unpaid_auction_wins(grace_hours=24, limit=200):
    """Release auctions whose winner never paid.

    Needed because 10.9 stopped close_auctions from delisting at close: the
    listing now sits at 'pending' until the paid webhook, so without a release
    an unpaid win would hold the listing in 'pending' forever (the buy-now
    sweeper is scoped to order_type='buy_now' and cannot help).

    The listing goes to 'expired', not 'active' — the auction genuinely ended,
    so relisting is the seller's decision. Second-chance offers to the
    next-highest bidder are deliberately out of scope; that is a product policy
    call, not part of 10.9.
    """
    from apps.notifications.services import create_notification

    from .models import Order

    threshold = timezone.now() - timedelta(hours=grace_hours)
    queryset = (
        Order.objects.select_related('listing')
        .filter(order_type='auction', status='pending_payment', created_at__lte=threshold)
        .order_by('created_at')[:limit]
    )
    released = []
    for order in queryset:
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().select_related('listing').get(pk=order.pk)
            listing = locked_order.listing
            if locked_order.status != 'pending_payment' or listing.listing_type != 'auction':
                continue
            if listing.status == 'pending':
                listing.status = 'expired'
                listing.save(update_fields=['status', 'updated_at'])
            payment = getattr(locked_order, 'payment', None)
            if payment and payment.status in {'pending', 'processing'}:
                payment.status = 'failed'
                payment.save(update_fields=['status', 'updated_at'])
            locked_order.status = 'cancelled'
            locked_order.save(update_fields=['status', 'updated_at'])
            released.append(locked_order)

    for released_order in released:
        create_notification(
            user=released_order.seller,
            notification_type='auction_expired',
            message=(
                f'The winning bidder on "{released_order.listing.title}" did not pay '
                f'within {grace_hours} hours. The sale was cancelled and the listing '
                'is no longer marked sold — you can relist it.'
            ),
            link_url=f'/listings/{released_order.listing_id}/',
            dedupe_window_hours=24,
        )
    return len(released), threshold
