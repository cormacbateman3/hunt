from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.enforcement.models import Strike
from apps.enforcement.services import confirm_excuse_handshake, initiate_excuse_handshake
from apps.notifications.services import create_notification
from .models import Order
from .services import transition_order


STATUS_FLOW = [
    'pending_payment',
    'paid',
    'label_created',
    'in_transit',
    'delivered',
    'completed',
]


def _get_order_for_user(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('listing', 'buyer', 'seller', 'payment', 'shipment'),
        pk=pk,
    )
    if request.user.id not in {order.buyer_id, order.seller_id}:
        return None
    return order


@login_required
def my_orders(request):
    purchases = (
        Order.objects.filter(buyer=request.user)
        .select_related('listing', 'seller')
        .order_by('-created_at')[:12]
    )
    sales = (
        Order.objects.filter(seller=request.user)
        .select_related('listing', 'buyer')
        .order_by('-created_at')[:12]
    )
    return render(request, 'orders/my_orders.html', {
        'purchases': purchases,
        'sales': sales,
    })


@login_required
def order_detail(request, pk):
    order = _get_order_for_user(request, pk)
    if not order:
        return HttpResponseForbidden('You do not have access to this order.')

    try:
        payment = order.payment
    except Exception:
        payment = None

    try:
        shipment = order.shipment
    except Exception:
        shipment = None
    shipment_events = shipment.events.order_by('-event_time')[:10] if shipment else []
    strikes = Strike.objects.filter(related_order=order).select_related(
        'user', 'excuse_initiated_by', 'excuse_confirmed_by'
    )

    current_index = STATUS_FLOW.index(order.status) if order.status in STATUS_FLOW else -1
    timeline = []
    for index, status in enumerate(STATUS_FLOW):
        timeline.append({
            'code': status,
            'label': dict(Order.STATUS_CHOICES).get(status, status),
            'is_current': index == current_index,
            'is_done': index < current_index,
        })

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'timeline': timeline,
        'is_buyer': request.user.id == order.buyer_id,
        'is_seller': request.user.id == order.seller_id,
        'payment': payment,
        'shipment': shipment,
        'shipment_events': shipment_events,
        'strikes': strikes,
        'excuse_reason_choices': Strike.EXCUSE_REASON_CHOICES,
    })


@login_required
@require_POST
def confirm_receipt(request, pk):
    order = _get_order_for_user(request, pk)
    if not order:
        return HttpResponseForbidden('You do not have access to this order.')
    if request.user.id != order.buyer_id:
        return HttpResponseForbidden('Only the buyer can confirm receipt.')
    if order.status not in {'paid', 'label_created', 'in_transit', 'delivered'}:
        messages.error(request, 'Order cannot be completed from its current status.')
        return redirect('orders:detail', pk=order.pk)

    ok, message = transition_order(order, 'completed', actor=request.user)
    if ok:
        create_notification(
            user=order.seller,
            notification_type='order_completed',
            message=f'Buyer confirmed receipt for order #{order.pk} ({order.listing.title}).',
            link_url=f'/orders/{order.pk}/',
        )
        messages.success(request, 'Receipt confirmed. Order marked as completed.')
    else:
        messages.error(request, message)
    return redirect('orders:detail', pk=order.pk)


@login_required
@require_POST
def update_status(request, pk):
    order = _get_order_for_user(request, pk)
    if not order:
        return HttpResponseForbidden('You do not have access to this order.')

    target = request.POST.get('target_status', '').strip()
    allowed_targets = {'label_created', 'in_transit', 'delivered'}
    if target not in allowed_targets:
        messages.error(request, 'Invalid status transition request.')
        return redirect('orders:detail', pk=order.pk)

    ok, message = transition_order(order, target, actor=request.user)
    if ok:
        note_type = 'order_shipped' if target in {'label_created', 'in_transit'} else 'order_delivered'
        create_notification(
            user=order.buyer,
            notification_type=note_type,
            message=f'Order #{order.pk} status updated to {order.get_status_display()}.',
            link_url=f'/orders/{order.pk}/',
        )
        messages.success(request, 'Order status updated.')
    else:
        messages.error(request, message)
    return redirect('orders:detail', pk=order.pk)


@login_required
@require_POST
def initiate_excuse(request, pk, strike_id):
    order = _get_order_for_user(request, pk)
    if not order:
        return HttpResponseForbidden('You do not have access to this order.')

    strike = get_object_or_404(Strike, pk=strike_id, related_order=order)
    excuse_reason = request.POST.get('excuse_reason', '').strip()
    excuse_note = request.POST.get('excuse_note', '').strip()
    if excuse_reason not in dict(Strike.EXCUSE_REASON_CHOICES):
        messages.error(request, 'Invalid handshake reason.')
        return redirect('orders:detail', pk=order.pk)

    ok, error = initiate_excuse_handshake(
        strike=strike,
        actor=request.user,
        excuse_reason=excuse_reason,
        excuse_note=excuse_note,
    )
    if ok:
        messages.success(request, 'Handshake initiated. Waiting for counterparty confirmation.')
    else:
        messages.error(request, error)
    return redirect('orders:detail', pk=order.pk)


@login_required
@require_POST
def confirm_excuse(request, pk, strike_id):
    order = _get_order_for_user(request, pk)
    if not order:
        return HttpResponseForbidden('You do not have access to this order.')
    strike = get_object_or_404(Strike, pk=strike_id, related_order=order)
    ok, error = confirm_excuse_handshake(strike=strike, actor=request.user)
    if ok:
        messages.success(request, 'Handshake confirmed. Strike marked excused.')
    else:
        messages.error(request, error)
    return redirect('orders:detail', pk=order.pk)
