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
    from .models import Order
    queryset = (
        Order.objects.filter(status='delivered', updated_at__lte=threshold)
        .order_by('updated_at')[:limit]
    )
    completed_count = 0
    for order in queryset:
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
