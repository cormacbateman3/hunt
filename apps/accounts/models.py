from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
import uuid


class Address(models.Model):
    """Shipping/billing address for a user"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name = models.CharField(max_length=200)
    line1 = models.CharField(max_length=200)
    line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2)
    postal_code = models.CharField(max_length=10)
    country = models.CharField(max_length=2, default='US')
    phone = models.CharField(max_length=20, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Address'
        verbose_name_plural = 'Addresses'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.full_name}, {self.line1}, {self.city}, {self.state} {self.postal_code}"


class UserProfile(models.Model):
    """
    Extended user profile for KeystoneBid collectors.
    Extends Django's built-in User model via OneToOne relationship.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    county = models.CharField(
        max_length=50,
        blank=True,
        help_text="User's home Pennsylvania county"
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=uuid.uuid4, editable=False)
    phone_verified = models.BooleanField(default=False)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    shipping_address = models.ForeignKey(
        Address,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_for_profile',
        help_text="Default shipping address"
    )
    # Messaging gate fields — set by admin only
    messaging_disabled = models.BooleanField(default=False)
    messaging_disabled_reason = models.TextField(blank=True)
    messaging_disabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s profile"

    def get_display_name(self):
        """Return display name if set, otherwise username"""
        return self.display_name or self.user.username

    @property
    def account_readiness(self):
        """
        Returns a list of dicts describing readiness items.
        Each dict: {label, complete, fix_url_name, fix_label}
        fix_url_name is a named URL (no args) or None if not applicable.
        """
        from django.urls import reverse
        return [
            {
                'label': 'Email verified',
                'complete': self.email_verified,
                'fix_url': reverse('accounts:resend_verification'),
                'fix_label': 'Resend verification email',
            },
            {
                'label': 'Shipping address saved',
                'complete': bool(self.shipping_address_id),
                'fix_url': reverse('accounts:address_add'),
                'fix_label': 'Add address',
            },
            {
                # No phone-verification flow exists yet — no fix link until one
                # ships (10.6: the old link pointed at a page with no phone UI).
                'label': 'Phone verified',
                'complete': self.phone_verified,
                'fix_url': None,
                'fix_label': '',
            },
        ]


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create UserProfile when User is created"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save UserProfile when User is saved"""
    instance.profile.save()
