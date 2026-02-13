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
    """User dashboard showing active bids and listings"""
    # This will be enhanced with actual bid and listing data
    context = {
        'user': request.user,
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
