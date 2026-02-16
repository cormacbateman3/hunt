from django.db import models
from django.contrib.auth.models import User
from apps.listings.models import Listing


class Bid(models.Model):
    """Bid placed on an auction listing"""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_winning = models.BooleanField(default=False)
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
