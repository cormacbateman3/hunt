from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import stripe
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.shipping.services import ShippoError, ensure_checkout_shipping_ready
from .models import PaymentTransaction, Transaction

stripe.api_key = settings.STRIPE_SECRET_KEY


def _get_or_create_order_from_transaction(transaction):
    order, _ = Order.objects.get_or_create(
        listing=transaction.listing,
        defaults={
            'buyer': transaction.buyer,
            'seller': transaction.seller,
            'order_type': 'auction',
            'item_amount': transaction.sale_amount,
            'shipping_amount': 0,
            'platform_fee_amount': 0,
            'total_amount': transaction.sale_amount,
            'status': 'paid' if transaction.status == 'paid' else 'pending_payment',
        },
    )
    PaymentTransaction.objects.get_or_create(
        order=order,
        defaults={
            'stripe_payment_intent_id': transaction.stripe_payment_id,
            'stripe_checkout_session_id': transaction.stripe_session_id,
            'status': 'paid' if transaction.status == 'paid' else 'pending',
        },
    )
    return order


@login_required
def create_checkout_session(request, order_id):
    """Create a Stripe Checkout session for an order."""
    order = get_object_or_404(
        Order.objects.select_related('listing'),
        pk=order_id,
        buyer=request.user,
    )
    if order.status != 'pending_payment':
        messages.error(request, 'This order is not in a payable state.')
        return redirect('orders:detail', pk=order.pk)

    payment, _ = PaymentTransaction.objects.get_or_create(
        order=order,
        defaults={'status': 'pending'},
    )
    try:
        ensure_checkout_shipping_ready(order)
    except ShippoError as exc:
        messages.error(request, f'Shipping setup required before payment: {exc}')
        return redirect('orders:detail', pk=order.pk)

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': order.listing.title,
                        'description': (
                            f'{order.listing.license_year} '
                            f'{order.listing.county} County '
                            f'({order.get_order_type_display()})'
                        ),
                        'images': [request.build_absolute_uri(order.listing.featured_image.url)]
                        if order.listing.featured_image else [],
                    },
                    'unit_amount': int(order.total_amount * 100),
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.SITE_URL.rstrip('/')}/payments/success/{order.pk}/",
            cancel_url=f"{settings.SITE_URL.rstrip('/')}/payments/cancel/{order.pk}/",
            metadata={'order_id': str(order.pk)},
            payment_intent_data={'metadata': {'order_id': str(order.pk)}},
        )

        payment.stripe_checkout_session_id = checkout_session.id
        payment.status = 'processing'
        payment.save(update_fields=['stripe_checkout_session_id', 'status', 'updated_at'])
        return redirect(checkout_session.url)
    except Exception as exc:
        messages.error(request, f'Payment error: {exc}')
        return redirect('orders:detail', pk=order.pk)


@login_required
def payment_success(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('listing', 'payment'),
        pk=order_id,
        buyer=request.user,
    )
    return render(request, 'payments/success.html', {'order': order})


@login_required
def payment_cancel(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    messages.warning(request, 'Payment was cancelled. You can try again from the order page.')
    return redirect('orders:detail', pk=order.pk)


@login_required
def legacy_checkout_redirect(request, transaction_id):
    transaction = get_object_or_404(Transaction, pk=transaction_id, buyer=request.user)
    order = _get_or_create_order_from_transaction(transaction)
    return redirect('payments:checkout', order_id=order.pk)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        handle_checkout_session_completed(event['data']['object'])
    elif event['type'] == 'payment_intent.succeeded':
        handle_payment_intent_succeeded(event['data']['object'])

    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    metadata = session.get('metadata') or {}
    order_id = metadata.get('order_id')
    transaction_id = metadata.get('transaction_id')
    payment_intent_id = session.get('payment_intent')
    order = None
    if order_id:
        order = Order.objects.filter(pk=order_id).first()
    elif transaction_id:
        transaction = Transaction.objects.filter(pk=transaction_id).first()
        if transaction:
            order = _get_or_create_order_from_transaction(transaction)
    if not order:
        return

    payment, _ = PaymentTransaction.objects.get_or_create(order=order)
    if payment_intent_id and not payment.stripe_payment_intent_id:
        payment.stripe_payment_intent_id = payment_intent_id
    if session.get('id') and not payment.stripe_checkout_session_id:
        payment.stripe_checkout_session_id = session.get('id')
    payment.status = 'processing'
    payment.save(update_fields=['stripe_payment_intent_id', 'stripe_checkout_session_id', 'status', 'updated_at'])


def handle_payment_intent_succeeded(payment_intent):
    metadata = payment_intent.get('metadata') or {}
    order_id = metadata.get('order_id')
    transaction_id = metadata.get('transaction_id')
    if order_id:
        order = Order.objects.filter(pk=order_id).first()
    elif transaction_id:
        transaction = Transaction.objects.filter(pk=transaction_id).first()
        order = _get_or_create_order_from_transaction(transaction) if transaction else None
    else:
        payment = PaymentTransaction.objects.filter(
            stripe_payment_intent_id=payment_intent.get('id')
        ).select_related('order').first()
        order = payment.order if payment else None

    if not order:
        return

    payment, _ = PaymentTransaction.objects.get_or_create(order=order)
    was_paid = order.status == 'paid'

    payment.status = 'paid'
    payment.stripe_payment_intent_id = payment_intent.get('id', '')
    payment.save(update_fields=['status', 'stripe_payment_intent_id', 'updated_at'])

    if order.status == 'pending_payment':
        order.status = 'paid'
        order.save(update_fields=['status', 'updated_at'])
    if order.order_type == 'buy_now' and order.listing.status != 'sold':
        order.listing.status = 'sold'
        order.listing.save(update_fields=['status', 'updated_at'])

    if not was_paid:
        Notification.objects.create(
            user=order.seller,
            notification_type='order_paid',
            message=(
                f'Payment received for order #{order.pk} ({order.listing.title}) '
                f'from {order.buyer.username}.'
            ),
            link_url=f'/orders/{order.pk}/',
        )
        Notification.objects.create(
            user=order.buyer,
            notification_type='payment_confirmed',
            message=f'Payment confirmed for order #{order.pk}.',
            link_url=f'/orders/{order.pk}/',
        )
