from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.orders.models import Order
from apps.trades.models import Trade

from .forms import ReviewForm
from .models import Review


@login_required
@require_POST
def submit_order_review(request, order_id):
    """Submit a review tied to a completed order."""
    order = get_object_or_404(Order, pk=order_id)
    if request.user.id not in {order.buyer_id, order.seller_id}:
        return HttpResponseForbidden()
    if order.status != 'completed':
        messages.error(request, 'Reviews are only available for completed orders.')
        return redirect('orders:detail', pk=order_id)

    # Determine who is being reviewed
    reviewed_user = order.seller if request.user.id == order.buyer_id else order.buyer

    # Block duplicate
    if Review.objects.filter(reviewer=request.user, order=order).exists():
        messages.info(request, 'You have already left a review for this transaction.')
        return redirect('orders:detail', pk=order_id)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.reviewer = request.user
        review.reviewed_user = reviewed_user
        review.order = order
        review.save()
        messages.success(request, 'Review submitted. Thank you.')
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
    return redirect('orders:detail', pk=order_id)


@login_required
@require_POST
def submit_trade_review(request, trade_id):
    """Submit a review tied to a completed trade."""
    trade = get_object_or_404(Trade, pk=trade_id)
    if request.user.id not in {trade.initiator_id, trade.counterparty_id}:
        return HttpResponseForbidden()
    if trade.status != 'completed':
        messages.error(request, 'Reviews are only available for completed trades.')
        return redirect('trades:trade_detail', pk=trade_id)

    reviewed_user = trade.counterparty if request.user.id == trade.initiator_id else trade.initiator

    if Review.objects.filter(reviewer=request.user, trade=trade).exists():
        messages.info(request, 'You have already left a review for this trade.')
        return redirect('trades:trade_detail', pk=trade_id)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review = form.save(commit=False)
        review.reviewer = request.user
        review.reviewed_user = reviewed_user
        review.trade = trade
        review.save()
        messages.success(request, 'Review submitted. Thank you.')
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                messages.error(request, err)
    return redirect('trades:trade_detail', pk=trade_id)
