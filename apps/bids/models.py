from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.contrib.auth.models import User
from apps.listings.models import Listing


class Bid(models.Model):
    """One visible price movement — what the room heard.

    ``amount`` is the standing price after this bid, never anybody's
    maximum; maximums live privately on :class:`ProxyMax`. ``is_proxy``
    marks the automatic answers ("their maximum covers you"), so the
    history can say which bids a hand placed.
    """
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2,
                                 validators=[MinValueValidator(Decimal('0.01'))])
    is_winning = models.BooleanField(default=False)
    is_proxy = models.BooleanField(
        default=False,
        help_text='Placed automatically on the bidder’s behalf by their standing maximum.',
    )
    placed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Bid'
        verbose_name_plural = 'Bids'
        ordering = ['-placed_at']
        indexes = [
            models.Index(fields=['listing', '-amount']),
            models.Index(fields=['listing', '-amount', 'placed_at']),
            models.Index(fields=['bidder', '-placed_at']),
        ]

    def __str__(self):
        return f"${self.amount} bid on {self.listing.title} by {self.bidder.username}"

    def clean(self):
        super().clean()
        if self.bidder_id and self.listing_id and self.bidder_id == self.listing.seller_id:
            raise ValidationError('You cannot bid on your own listing.')

    def save(self, *args, **kwargs):
        # A seller must never end up holding a bid on their own auction: such a
        # bid can win at close and mint a self-purchase Order. The form and
        # place_bid both refuse it; this closes the shell/admin/import paths
        # too. Cannot be a DB CheckConstraint — the seller lives on Listing,
        # and a check constraint cannot reach across a foreign key.
        if self.bidder_id and self.listing_id and self.bidder_id == self.listing.seller_id:
            raise ValidationError('You cannot bid on your own listing.')
        return super().save(*args, **kwargs)


class ProxyMax(models.Model):
    """A bidder's standing maximum on one auction — the private half of
    proxy bidding (the eBay mechanic, and the site's only mechanic).

    The visible ``Bid`` rows are what the room heard; this is the
    instruction behind them: "bid for me, one increment at a time, up to
    here and never past it." Never shown to anyone but its owner.
    """
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='proxy_maxes')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='proxy_maxes')
    max_amount = models.DecimalField(max_digits=10, decimal_places=2,
                                     validators=[MinValueValidator(Decimal('0.01'))])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Proxy maximum'
        verbose_name_plural = 'Proxy maximums'
        constraints = [
            models.UniqueConstraint(fields=['listing', 'bidder'],
                                    name='one_standing_max_per_bidder'),
        ]

    def __str__(self):
        return f"max ${self.max_amount} on {self.listing_id} by {self.bidder.username}"
