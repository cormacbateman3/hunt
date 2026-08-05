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


class OrderHandshake(models.Model):
    """An agreement between two people that a deadline no longer applies.

    The excuse flow on Strike only exists once a strike has been issued —
    after the damage. Nearly every late shipment is a misunderstanding about
    timing, a show pickup, or a buyer who said "no rush": all of them are
    settled between the two parties, and none of them should cost anybody a
    strike first.

    So this is the same agreement offered *before* the deadline bites. One
    party proposes, the other confirms, and the enforcement sweep skips the
    deadline it covers. Unconfirmed proposals do nothing at all — an
    agreement one person made with themselves is not an agreement.

    Scoped deliberately: a handshake about shipping does not excuse a missed
    payment. Whoever agreed to wait for the parcel did not agree to that.
    """

    COVERS_CHOICES = [
        ('shipping', 'The shipping deadline'),
        ('receipt', 'Confirming it arrived'),
    ]

    REASON_CHOICES = Strike.EXCUSE_REASON_CHOICES

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='handshakes')
    covers = models.CharField(max_length=20, choices=COVERS_CHOICES)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    note = models.CharField(max_length=250, blank=True)

    proposed_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='handshakes_proposed')
    proposed_at = models.DateTimeField(auto_now_add=True)

    confirmed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='handshakes_confirmed')
    confirmed_at = models.DateTimeField(null=True, blank=True)

    # A proposal nobody answers has to stop mattering, or a seller could park
    # one against every order and never ship again.
    expires_at = models.DateTimeField()

    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Order Handshake'
        verbose_name_plural = 'Order Handshakes'
        ordering = ['-proposed_at']
        indexes = [models.Index(fields=['order', 'covers', '-proposed_at'])]
        constraints = [
            # The audit trail cannot be half-written: either nobody has
            # confirmed, or we can say who did and when.
            models.CheckConstraint(
                check=(
                    models.Q(confirmed_by__isnull=True, confirmed_at__isnull=True)
                    | models.Q(confirmed_by__isnull=False, confirmed_at__isnull=False)
                ),
                name='handshake_confirmation_is_whole',
            ),
            models.CheckConstraint(
                check=~models.Q(confirmed_by=models.F('proposed_by')),
                name='handshake_needs_two_people',
            ),
        ]

    def __str__(self):
        state = 'confirmed' if self.is_confirmed else 'proposed'
        return f'Handshake on order {self.order_id} ({self.covers}, {state})'

    @property
    def is_confirmed(self):
        return bool(self.confirmed_by_id and self.confirmed_at)

    @property
    def is_open(self):
        """Proposed, unanswered, and still inside its window."""
        from django.utils import timezone
        return (
            not self.is_confirmed
            and not self.withdrawn_at
            and self.expires_at > timezone.now()
        )
