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
            models.Index(fields=['bidder', '-placed_at']),
        ]

    def __str__(self):
        return f"${self.amount} bid on {self.listing.title} by {self.bidder.username}"

    def save(self, *args, **kwargs):
        """Update listing current_bid and outbid notifications"""
        super().save(*args, **kwargs)

        # Update listing's current bid
        if self.is_winning:
            self.listing.current_bid = self.amount
            self.listing.save(update_fields=['current_bid'])

            # Mark all other bids on this listing as not winning
            Bid.objects.filter(listing=self.listing).exclude(pk=self.pk).update(is_winning=False)
