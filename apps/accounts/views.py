from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from .forms import UserRegistrationForm, UserProfileForm, AddressForm
from .models import UserProfile, Address
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.orders.models import Order
from apps.notifications.models import Notification
from apps.collections.models import CollectionItem, WantedItem
from apps.favorites.models import Favorite


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

    addresses = request.user.addresses.all()
    return render(request, 'accounts/profile_edit.html', {
        'form': form,
        'addresses': addresses,
        'readiness': profile.account_readiness,
    })


def profile_view(request, username):
    """Public profile view"""
    user = get_object_or_404(User, username=username)
    profile = user.profile
    is_owner = request.user.is_authenticated and request.user.id == user.id

    collection_items = (
        CollectionItem.objects.filter(owner=user)
        .select_related('state', 'county')
        .prefetch_related('images', 'license_types')
        .order_by('-created_at')
    )
    if not is_owner:
        collection_items = collection_items.filter(is_public=True)

    wanted_items = (
        WantedItem.objects.filter(user=user)
        .select_related('state', 'county', 'license_type')
        .order_by('-created_at')[:8]
    )
    favorite_collection_ids = set()
    if request.user.is_authenticated:
        favorite_collection_ids = set(
            Favorite.objects.filter(user=request.user, collection_item__isnull=False)
            .values_list('collection_item_id', flat=True)
        )

    context = {
        'profile_user': user,
        'profile': profile,
        'collection_items': collection_items,
        'wanted_items': wanted_items,
        'is_owner': is_owner,
        'favorite_collection_ids': favorite_collection_ids,
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
    recent_favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related('listing', 'collection_item', 'collection_item__owner')
        .order_by('-created_at')[:8]
    )

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
        'recent_favorites': recent_favorites,
        'readiness': request.user.profile.account_readiness,
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


@login_required
def resend_verification_email(request):
    """Resend email verification link. Rate-limited to 3 per hour."""
    if request.method != 'POST':
        return redirect('accounts:profile_edit')

    profile = request.user.profile
    if profile.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('accounts:profile_edit')

    cache_key = f'resend_verify_{request.user.pk}'
    sent_times = cache.get(cache_key, [])
    now = timezone.now().timestamp()
    # Keep only timestamps within the last hour
    sent_times = [t for t in sent_times if now - t < 3600]
    if len(sent_times) >= 3:
        messages.error(request, 'You have requested too many verification emails. Please wait before trying again.')
        return redirect('accounts:profile_edit')

    sent_times.append(now)
    cache.set(cache_key, sent_times, 3600)

    verification_url = request.build_absolute_uri(
        reverse('accounts:verify_email', kwargs={'token': profile.email_verification_token})
    )
    email_context = {'user': request.user, 'verification_url': verification_url}
    send_mail(
        subject='Verify your KeystoneBid account',
        message=render_to_string('accounts/emails/verify_email.txt', email_context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.user.email],
        html_message=render_to_string('accounts/emails/verify_email.html', email_context),
        fail_silently=False,
    )
    messages.success(request, 'Verification email sent. Check your inbox.')
    return redirect('accounts:profile_edit')


@login_required
def address_add(request):
    """Add a new shipping address."""
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            # Make default if this is the user's first address
            profile = request.user.profile
            if not profile.shipping_address_id:
                profile.shipping_address = address
                profile.save(update_fields=['shipping_address'])
                address.is_default = True
                address.save(update_fields=['is_default'])
            messages.success(request, 'Address saved.')
            return redirect('accounts:profile_edit')
    else:
        form = AddressForm()

    return render(request, 'accounts/address_form.html', {'form': form, 'action': 'Add'})


@login_required
def address_edit(request, pk):
    """Edit an existing shipping address."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated.')
            return redirect('accounts:profile_edit')
    else:
        form = AddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {'form': form, 'action': 'Edit', 'address': address})


@login_required
def address_delete(request, pk):
    """Delete an address. POST only."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        profile = request.user.profile
        if profile.shipping_address_id == address.pk:
            # Clear default; auto-assign another if available
            profile.shipping_address = None
            profile.save(update_fields=['shipping_address'])
            remaining = request.user.addresses.exclude(pk=address.pk).first()
            if remaining:
                profile.shipping_address = remaining
                profile.save(update_fields=['shipping_address'])
                remaining.is_default = True
                remaining.save(update_fields=['is_default'])
        address.delete()
        messages.success(request, 'Address removed.')
        return redirect('accounts:profile_edit')

    return render(request, 'accounts/address_confirm_delete.html', {'address': address})


@login_required
def address_set_default(request, pk):
    """Set an address as the default. POST only."""
    if request.method != 'POST':
        return redirect('accounts:profile_edit')
    address = get_object_or_404(Address, pk=pk, user=request.user)
    profile = request.user.profile
    # Clear old default flag
    request.user.addresses.filter(is_default=True).update(is_default=False)
    address.is_default = True
    address.save(update_fields=['is_default'])
    profile.shipping_address = address
    profile.save(update_fields=['shipping_address'])
    messages.success(request, 'Default address updated.')
    return redirect('accounts:profile_edit')
