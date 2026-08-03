from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

User = get_user_model()

# How long a buyer has to pay once the seller accepts. Without this an accepted
# offer would reserve the listing forever if the buyer walked away — there is no
# Order yet at acceptance time, so the 30-minute stale-order sweeper cannot help.
ACCEPTED_PAYMENT_WINDOW_HOURS = 48

# Default life of a pending offer. Shorter than the 4-day trade default: a price
# offer holds nothing, so a stale one costs the seller only attention.
DEFAULT_EXPIRES_DAYS = 2


class Offer(models.Model):
    """A price negotiation on a buy-now listing.

    Buyers originate; sellers may only counter (`counter_to` set). A buyer's
    offer is binding — acceptance commits them to buy at `amount`, which is
    what `Order.item_amount` is priced from instead of `Listing.buy_now_price`.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('countered', 'Countered'),
        ('withdrawn', 'Withdrawn'),
        ('expired', 'Expired'),
    ]

    # Statuses that are done and cannot transition again.
    TERMINAL_STATUSES = {'declined', 'countered', 'withdrawn', 'expired'}

    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.CASCADE, related_name='offers'
    )
    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='offers_sent'
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='offers_received'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('1'))],
        help_text='Offered item price, excluding platform fee and shipping.',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    counter_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counteroffers',
        help_text='Set when this offer is a response to another. Sellers may only counter.',
    )
    message = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['listing', '-created_at']),
            models.Index(fields=['from_user', '-created_at']),
            models.Index(fields=['to_user', '-created_at']),
            models.Index(fields=['status']),
        ]
        constraints = [
            # An offer always has two distinct parties. Backstop for the
            # service-layer rule that a seller cannot negotiate with themselves.
            models.CheckConstraint(
                check=~models.Q(from_user=models.F('to_user')),
                name='offer_parties_are_distinct',
            ),
        ]

    def __str__(self):
        return f'Offer #{self.pk} — ${self.amount} on {self.listing_id} ({self.status})'

    @property
    def is_from_seller(self):
        """True for seller counters. Sellers can never originate (see services)."""
        return self.from_user_id == self.listing.seller_id

    @property
    def is_expired(self):
        return bool(
            self.status == 'pending'
            and self.expires_at
            and self.expires_at <= timezone.now()
        )

    @property
    def payment_deadline(self):
        if not self.accepted_at:
            return None
        return self.accepted_at + timedelta(hours=ACCEPTED_PAYMENT_WINDOW_HOURS)

    @property
    def reservation_lapsed(self):
        """Accepted but the buyer never paid inside the window.

        Kept as a property rather than a status write so a lapsed reservation
        stops blocking other buyers the moment it lapses, even if the sweeper
        has not run yet.
        """
        deadline = self.payment_deadline
        return bool(self.status == 'accepted' and deadline and deadline <= timezone.now())

    @property
    def reserves_listing(self):
        """An accepted, unlapsed offer holds the listing for its buyer."""
        return self.status == 'accepted' and not self.reservation_lapsed

    @property
    def buyer(self):
        """The party who would pay — the non-seller side of the negotiation."""
        return self.to_user if self.is_from_seller else self.from_user
