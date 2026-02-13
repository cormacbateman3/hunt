from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse


class Listing(models.Model):
    """Auction listing for an antique Pennsylvania hunting license"""

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('sold', 'Sold'),
        ('expired', 'Expired'),
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

    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    license_year = models.IntegerField(help_text="Year the license was issued")
    county = models.CharField(max_length=50, help_text="Pennsylvania county")
    license_type = models.CharField(max_length=50, help_text="e.g., Resident, Non-resident, etc.")
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES)

    # Pricing
    starting_price = models.DecimalField(max_digits=10, decimal_places=2)
    current_bid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Auction Details
    auction_end = models.DateTimeField()
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
        ]

    def __str__(self):
        return f"{self.title} ({self.license_year})"

    def get_absolute_url(self):
        return reverse('listings:detail', kwargs={'pk': self.pk})

    def is_active(self):
        """Check if auction is still active"""
        return self.status == 'active' and self.auction_end > timezone.now()

    def time_remaining(self):
        """Get time remaining in auction"""
        if self.is_active():
            return self.auction_end - timezone.now()
        return None

    def current_price(self):
        """Get current price (highest bid or starting price)"""
        return self.current_bid if self.current_bid else self.starting_price


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
