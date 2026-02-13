from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.conf import settings
import stripe
from .models import Transaction
from apps.notifications.models import Notification

stripe.api_key = settings.STRIPE_SECRET_KEY


@login_required
def create_checkout_session(request, transaction_id):
    """Create a Stripe Checkout session for the winning buyer."""
    transaction = get_object_or_404(
        Transaction,
        pk=transaction_id,
        buyer=request.user,
        status='pending'
    )

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': transaction.listing.title,
                        'description': f'{transaction.listing.license_year} {transaction.listing.county} County',
                        'images': [request.build_absolute_uri(transaction.listing.featured_image.url)]
                            if transaction.listing.featured_image else [],
                    },
                    'unit_amount': int(transaction.sale_amount * 100),  # Convert to cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.SITE_URL.rstrip('/')}/payments/success/{transaction.pk}/",
            cancel_url=f"{settings.SITE_URL.rstrip('/')}/payments/cancel/{transaction.pk}/",
            metadata={
                'transaction_id': str(transaction.pk),
            },
            payment_intent_data={
                'metadata': {
                    'transaction_id': str(transaction.pk),
                }
            },
        )

        # Save the session ID
        transaction.stripe_session_id = checkout_session.id
        transaction.save(update_fields=['stripe_session_id', 'updated_at'])

        return redirect(checkout_session.url)

    except Exception as e:
        messages.error(request, f'Payment error: {str(e)}')
        return redirect('accounts:dashboard')


@login_required
def payment_success(request, transaction_id):
    """Payment success page"""
    transaction = get_object_or_404(
        Transaction,
        pk=transaction_id,
        buyer=request.user
    )

    context = {
        'transaction': transaction,
    }

    return render(request, 'payments/success.html', context)


@login_required
def payment_cancel(request, transaction_id):
    """Payment cancelled page"""
    transaction = get_object_or_404(
        Transaction,
        pk=transaction_id,
        buyer=request.user
    )

    messages.warning(request, 'Payment was cancelled. You can try again from your dashboard.')
    return redirect('accounts:dashboard')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhooks"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session_completed(session)
    elif event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_payment_intent_succeeded(payment_intent)

    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    """Persist payment intent id from checkout completion when available."""
    metadata = session.get('metadata') or {}
    transaction_id = metadata.get('transaction_id')
    payment_intent_id = session.get('payment_intent')

    if not transaction_id or not payment_intent_id:
        return

    try:
        transaction = Transaction.objects.get(pk=transaction_id)
        if not transaction.stripe_payment_id:
            transaction.stripe_payment_id = payment_intent_id
            transaction.save(update_fields=['stripe_payment_id', 'updated_at'])
    except Transaction.DoesNotExist:
        return


def handle_payment_intent_succeeded(payment_intent):
    """Mark transaction as paid and notify seller when Stripe confirms payment."""
    metadata = payment_intent.get('metadata') or {}
    transaction_id = metadata.get('transaction_id')

    if transaction_id:
        transaction = Transaction.objects.filter(pk=transaction_id).first()
    else:
        transaction = Transaction.objects.filter(stripe_payment_id=payment_intent.get('id')).first()

    if not transaction:
        return

    already_paid = transaction.status == 'paid'
    transaction.status = 'paid'
    transaction.stripe_payment_id = payment_intent.get('id', '')
    transaction.save(update_fields=['status', 'stripe_payment_id', 'updated_at'])

    if not already_paid:
        Notification.objects.create(
            user=transaction.seller,
            notification_type='payment_received',
            message=(
                f'Payment received for "{transaction.listing.title}" '
                f'from {transaction.buyer.username}. Amount: ${transaction.sale_amount:.2f}.'
            )
        )
