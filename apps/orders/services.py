from datetime import timedelta
from django.utils import timezone


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
