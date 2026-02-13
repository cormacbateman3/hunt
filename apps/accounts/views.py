from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from .forms import UserRegistrationForm, UserLoginForm, UserProfileForm
from .models import UserProfile


def register(request):
    """User registration view with email verification"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True  # Change to False when email verification is implemented
            user.save()

            # Send verification email (simplified for MVP)
            # TODO: Implement email verification with token

            messages.success(request, 'Account created successfully! Please log in.')
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def user_login(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {username}!')
                next_url = request.GET.get('next', 'dashboard')
                return redirect(next_url)
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


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
            messages.success(request, 'Email verified successfully!')
        else:
            messages.info(request, 'Email already verified.')
        return redirect('accounts:login')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('home')
