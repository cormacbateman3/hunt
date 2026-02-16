from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from apps.core.constants import RESIDENT_STATUS_CHOICES


class Listing(models.Model):
    """Auction listing for an antique Pennsylvania hunting license"""

    LISTING_TYPE_CHOICES = [
        ('auction', 'Auction House'),
        ('buy_now', 'General Store'),
        ('trade', 'Trading Block'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('sold', 'Sold'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    CONDITION_CHOICES = [
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('very_good', 'Very Good'),
        ('excellent', 'Excellent'),
        ('mint', 'Mint'),
    ]

    # Relationships
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listings')
    source_collection_item = models.ForeignKey(
        'collections.CollectionItem', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='listings',
        help_text="Collection item this listing was created from"
    )

    # Listing type
    listing_type = models.CharField(
        max_length=20, choices=LISTING_TYPE_CHOICES, default='auction'
    )

    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    license_year = models.IntegerField(help_text="Year the license was issued")
    county = models.CharField(max_length=50, help_text="Pennsylvania county")
    county_ref = models.ForeignKey(
        'core.County', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='listings', help_text="County reference"
    )
    license_type = models.CharField(max_length=50, help_text="e.g., Resident, Non-resident, etc.")
    license_type_ref = models.ForeignKey(
        'core.LicenseType', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='listings', help_text="License type reference"
    )
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    resident_status = models.CharField(
        max_length=20, choices=RESIDENT_STATUS_CHOICES, default='unknown'
    )

    # Auction pricing
    starting_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    current_bid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    reserve_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Minimum price to sell (auction only)"
    )

    # Buy-now pricing
    buy_now_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Fixed price for buy-now listings"
    )

    # Trade fields
    trade_notes = models.TextField(blank=True, help_text="What the seller is looking for in trade")
    allow_cash = models.BooleanField(
        default=False, help_text="Allow cash component in trade offers"
    )

    # Auction Details
    auction_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Images
    featured_image = models.ImageField(upload_to='listings/', help_text="Main listing image")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Listing'
        verbose_name_plural = 'Listings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-auction_end']),
            models.Index(fields=['county', 'license_year']),
            models.Index(fields=['listing_type', 'status']),
        ]

    def __str__(self):
        return f"{self.title} ({self.license_year})"

    def get_absolute_url(self):
        return reverse('listings:detail', kwargs={'pk': self.pk})

    def is_active(self):
        """Check if auction is still active"""
        if self.listing_type == 'auction':
            return self.status == 'active' and self.auction_end and self.auction_end > timezone.now()
        return self.status == 'active'

    def time_remaining(self):
        """Get time remaining in auction"""
        if self.listing_type == 'auction' and self.is_active():
            return self.auction_end - timezone.now()
        return None

    def current_price(self):
        """Get current price (highest bid or starting price)"""
        if self.listing_type == 'buy_now':
            return self.buy_now_price
        if self.listing_type == 'auction':
            return self.current_bid if self.current_bid else self.starting_price
        return None


class ListingImage(models.Model):
    """Additional images for a listing"""
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='additional_images')
    image = models.ImageField(upload_to='listings/')
    sort_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Listing Image'
        verbose_name_plural = 'Listing Images'
        ordering = ['sort_order', 'uploaded_at']

    def __str__(self):
        return f"Image for {self.listing.title}"


class ListingQuestion(models.Model):
    """Simple listing Q&A for buyer questions and seller answers."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='questions')
    asker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listing_questions')
    question = models.TextField()
    seller_answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Listing Question'
        verbose_name_plural = 'Listing Questions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Q on {self.listing.title} by {self.asker.username}"
