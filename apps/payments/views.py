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
    """Create a Stripe Checkout session for payment"""
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
            success_url=request.build_absolute_uri(f'/payments/success/{transaction.pk}/'),
            cancel_url=request.build_absolute_uri(f'/payments/cancel/{transaction.pk}/'),
            metadata={
                'transaction_id': transaction.pk,
            }
        )

        # Save the session ID
        transaction.stripe_session_id = checkout_session.id
        transaction.save()

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

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session_completed(session)

    return HttpResponse(status=200)


def handle_checkout_session_completed(session):
    """Handle successful payment"""
    transaction_id = session['metadata']['transaction_id']

    try:
        transaction = Transaction.objects.get(pk=transaction_id)
        transaction.status = 'paid'
        transaction.stripe_payment_id = session['payment_intent']
        transaction.save()

        # Notify seller
        Notification.objects.create(
            user=transaction.seller,
            notification_type='payment_received',
            message=f'Payment received for "{transaction.listing.title}"! Amount: ${transaction.sale_amount:.2f}'
        )

        # Notify buyer
        Notification.objects.create(
            user=transaction.buyer,
            notification_type='payment_confirmed',
            message=f'Payment confirmed for "{transaction.listing.title}"! The seller will ship your item soon.'
        )

    except Transaction.DoesNotExist:
        pass  # Log this error
