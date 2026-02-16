import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.orders.models import Order
from .services import (
    ShippoError,
    attach_manual_tracking,
    buy_label_for_order,
    handle_tracking_webhook,
    quote_order_shipping,
)


def _get_order_for_shipping_action(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.user.id not in {order.buyer_id, order.seller_id}:
        return None
    return order


@login_required
@require_POST
def quote_order_shipping_view(request, pk):
    order = _get_order_for_shipping_action(request, pk)
    if not order:
        return HttpResponseForbidden('Not allowed.')
    if request.user.id != order.seller_id:
        return HttpResponseForbidden('Only the seller can quote shipping.')
    if order.status != 'pending_payment':
        messages.error(request, 'Shipping quote can only be updated before payment.')
        return redirect('orders:detail', pk=order.pk)

    try:
        parcel = {
            'weight_oz': Decimal(request.POST.get('weight_oz', '0')),
            'length_in': Decimal(request.POST.get('length_in', '0')),
            'width_in': Decimal(request.POST.get('width_in', '0')),
            'height_in': Decimal(request.POST.get('height_in', '0')),
        }
        if any(v <= 0 for v in parcel.values()):
            raise ShippoError('All package fields must be greater than zero.')
        quote_order_shipping(order, parcel)
        messages.success(request, 'Shipping quoted and order totals updated.')
    except (ArithmeticError, ValueError):
        messages.error(request, 'Invalid package dimensions/weight.')
    except ShippoError as exc:
        messages.error(request, str(exc))
    return redirect('orders:detail', pk=order.pk)


@login_required
@require_POST
def buy_label_view(request, pk):
    order = _get_order_for_shipping_action(request, pk)
    if not order:
        return HttpResponseForbidden('Not allowed.')
    if request.user.id != order.seller_id:
        return HttpResponseForbidden('Only the seller can buy labels.')
    if order.status not in {'paid', 'label_created', 'in_transit'}:
        messages.error(request, 'Order must be paid before label purchase.')
        return redirect('orders:detail', pk=order.pk)

    try:
        buy_label_for_order(order)
        messages.success(request, 'Shipping label created.')
    except ShippoError as exc:
        messages.error(request, str(exc))
    return redirect('orders:detail', pk=order.pk)


@login_required
@require_POST
def manual_tracking_view(request, pk):
    order = _get_order_for_shipping_action(request, pk)
    if not order:
        return HttpResponseForbidden('Not allowed.')
    if request.user.id != order.seller_id:
        return HttpResponseForbidden('Only the seller can enter tracking.')
    if order.status not in {'paid', 'label_created', 'in_transit'}:
        messages.error(request, 'Order must be paid before tracking can be entered.')
        return redirect('orders:detail', pk=order.pk)

    carrier = request.POST.get('carrier', '').strip()
    tracking_number = request.POST.get('tracking_number', '').strip()
    if not carrier or not tracking_number:
        messages.error(request, 'Carrier and tracking number are required.')
        return redirect('orders:detail', pk=order.pk)
    try:
        attach_manual_tracking(order, carrier=carrier, tracking_number=tracking_number)
        messages.success(request, 'Manual tracking saved.')
    except ShippoError as exc:
        messages.error(request, str(exc))
    return redirect('orders:detail', pk=order.pk)


@csrf_exempt
@require_POST
def shippo_webhook(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return HttpResponse(status=400)
    processed = handle_tracking_webhook(payload)
    return HttpResponse(f'processed={processed}', status=200)
