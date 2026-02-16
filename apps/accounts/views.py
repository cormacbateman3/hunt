from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from .forms import UserRegistrationForm, UserProfileForm
from .models import UserProfile
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.orders.models import Order
from apps.notifications.models import Notification


def register(request):
    """User registration view with email verification"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = False
            user.save()

            verification_url = request.build_absolute_uri(
                reverse(
                    'accounts:verify_email',
                    kwargs={'token': user.profile.email_verification_token},
                )
            )
            email_context = {
                'user': user,
                'verification_url': verification_url,
            }
            subject = 'Verify your KeystoneBid account'
            text_body = render_to_string(
                'accounts/emails/verify_email.txt',
                email_context,
            )
            html_body = render_to_string(
                'accounts/emails/verify_email.html',
                email_context,
            )
            send_mail(
                subject=subject,
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_body,
                fail_silently=False,
            )

            messages.success(
                request,
                'Account created. Check your email for a verification link before logging in.',
            )
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def user_logout(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def profile_edit(request):
    """Edit user profile"""
    profile = request.user.profile

    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile', username=request.user.username)
    else:
        form = UserProfileForm(instance=profile)

    return render(request, 'accounts/profile_edit.html', {'form': form})


def profile_view(request, username):
    """Public profile view"""
    user = get_object_or_404(User, username=username)
    profile = user.profile

    context = {
        'profile_user': user,
        'profile': profile,
    }

    return render(request, 'accounts/profile.html', context)


@login_required
def dashboard(request):
    """User dashboard with listings, bids, payments, and notifications."""
    my_listings = Listing.objects.filter(seller=request.user).order_by('-created_at')[:8]
    active_listings = Listing.objects.filter(seller=request.user, status='active').count()

    my_bids = Bid.objects.filter(bidder=request.user).select_related('listing').order_by('-placed_at')[:8]
    winning_bids = Bid.objects.filter(bidder=request.user, is_winning=True, listing__status='active').count()

    pending_payments = Order.objects.filter(
        buyer=request.user,
        status='pending_payment'
    ).select_related('listing').order_by('-created_at')
    recent_purchases = Order.objects.filter(
        buyer=request.user
    ).select_related('listing').order_by('-created_at')[:6]
    recent_sales = Order.objects.filter(
        seller=request.user
    ).select_related('listing').order_by('-created_at')[:6]

    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]

    context = {
        'active_listings_count': active_listings,
        'my_listings': my_listings,
        'my_bids': my_bids,
        'winning_bids_count': winning_bids,
        'pending_payments': pending_payments,
        'recent_purchases': recent_purchases,
        'recent_sales': recent_sales,
        'recent_notifications': recent_notifications,
    }
    return render(request, 'accounts/dashboard.html', context)


def verify_email(request, token):
    """Email verification view"""
    try:
        profile = UserProfile.objects.get(email_verification_token=token)
        if not profile.email_verified:
            profile.email_verified = True
            profile.save()
            profile.user.is_active = True
            profile.user.save(update_fields=['is_active'])
            messages.success(request, 'Email verified successfully!')
        else:
            messages.info(request, 'Email already verified.')
        return redirect('accounts:login')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('home')
