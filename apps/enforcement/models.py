from django.db import models
from django.contrib.auth.models import User


class Strike(models.Model):
    """Strike against a user for policy violations"""

    REASON_CHOICES = [
        ('non_shipment', 'Non Shipment'),
        ('non_payment', 'Non Payment'),
        ('cancellation_abuse', 'Cancellation Abuse'),
        ('other', 'Other'),
    ]
    EXCUSE_REASON_CHOICES = [
        ('local_pickup', 'Local Pickup'),
        ('agreed_delay', 'Agreed Delay'),
        ('combined_shipment', 'Combined Shipment'),
        ('alternative_delivery', 'Alternative Delivery'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='strikes')
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    related_order = models.ForeignKey(
        'orders.Order', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='strikes'
    )
    related_trade = models.ForeignKey(
        'trades.Trade', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='strikes'
    )
    notes = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_excused = models.BooleanField(default=False)
    excuse_reason = models.CharField(max_length=50, choices=EXCUSE_REASON_CHOICES, blank=True)
    excuse_note = models.CharField(max_length=250, blank=True)
    excuse_initiated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='excuses_initiated'
    )
    excuse_expires_at = models.DateTimeField(null=True, blank=True)
    excuse_confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='excuses_confirmed'
    )
    excuse_confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Strike'
        verbose_name_plural = 'Strikes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_excused']),
        ]

    def __str__(self):
        return f"Strike for {self.user.username}: {self.get_reason_display()}"


class AccountRestriction(models.Model):
    """Restrictions applied to a user account based on strikes"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='restriction')
    can_bid = models.BooleanField(default=True)
    can_sell = models.BooleanField(default=True)
    can_trade = models.BooleanField(default=True)
    suspended_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Account Restriction'
        verbose_name_plural = 'Account Restrictions'

    def __str__(self):
        restrictions = []
        if not self.can_bid:
            restrictions.append('no-bid')
        if not self.can_sell:
            restrictions.append('no-sell')
        if not self.can_trade:
            restrictions.append('no-trade')
        return f"{self.user.username}: {', '.join(restrictions) or 'no restrictions'}"
