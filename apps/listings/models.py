from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from apps.core.constants import COLOR_CHOICES, FORM_LICENSE_TYPE_CATEGORIES, RESIDENT_STATUS_CHOICES, SHAPE_CHOICES


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
        ('scheduled', 'Scheduled'),
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
    state = models.ForeignKey(
        'core.State', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='listings', help_text='Issuing state for this item'
    )
    county = models.CharField(max_length=50, help_text="Pennsylvania county")
    county_ref = models.ForeignKey(
        'core.GeographicUnit', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='listings', help_text="Geographic unit reference"
    )
    is_statewide = models.BooleanField(default=False)
    license_type = models.CharField(max_length=50, help_text="Legacy type snapshot", blank=True)
    license_types = models.ManyToManyField(
        'core.LicenseType', blank=True, related_name='listings',
        help_text="License type(s) for this listing",
    )
    shape = models.CharField(max_length=30, choices=SHAPE_CHOICES, blank=True)
    colors = models.JSONField(default=list, blank=True)
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

    # Scheduled go-live (4a)
    scheduled_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Schedule when this listing goes live (leave blank to publish immediately)"
    )

    # Auto-relist (4b)
    auto_relist = models.BooleanField(
        default=True,
        help_text="Automatically relist this auction if it ends without a winner (up to 3 times)"
    )
    relist_count = models.IntegerField(default=0, help_text="How many times this listing has been relisted")
    original_listing = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='relisted_copies',
        help_text="Original listing if this is a relist"
    )

    # Local pickup (4c)
    local_pickup_available = models.BooleanField(
        default=False,
        help_text="Offer local pickup as an alternative to shipping"
    )
    local_pickup_location = models.CharField(
        max_length=100, blank=True,
        help_text="City or region where pickup is available (e.g. 'Lancaster, PA')"
    )

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

    @property
    def listing_completeness_score(self):
        checks = [
            bool(self.county_ref or self.is_statewide),
            self.license_types.filter(category='activity_scope').exists(),
            self.license_types.filter(category='material').exists(),
            bool(self.description.strip()),
            bool(self.shape),
            bool(self.colors),
            self.license_types.filter(category='residency').exists(),
            self.license_types.filter(category='duration').exists(),
            self.license_types.filter(category='holder_eligibility').exists(),
            self.license_types.filter(category='addon_type').exists(),
        ]
        return int((sum(1 for item in checks if item) / len(checks)) * 100)

    def license_types_for_category(self, category):
        return list(self.license_types.filter(category=category).order_by('name'))

    def primary_license_type_name(self, category):
        item = self.license_types.filter(category=category).order_by('name').first()
        return item.name if item else ''

    def display_license_type_summary(self):
        parts = []
        for category in FORM_LICENSE_TYPE_CATEGORIES:
            label = self.primary_license_type_name(category)
            if label:
                parts.append(label)
        return ', '.join(parts)

    def display_colors(self):
        labels = dict(COLOR_CHOICES)
        return ', '.join(labels.get(value, value) for value in self.colors)

    def get_shape_display_label(self):
        labels = dict(SHAPE_CHOICES)
        return labels.get(self.shape, '')


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

    MODERATION_CHOICES = [
        ('ok', 'OK'),
        ('flagged', 'Flagged'),
        ('hidden', 'Hidden'),
    ]

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='questions')
    asker = models.ForeignKey(User, on_delete=models.CASCADE, related_name='listing_questions')
    question = models.TextField()
    seller_answer = models.TextField(blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    moderation_state = models.CharField(
        max_length=10, choices=MODERATION_CHOICES, default='ok',
        help_text='ok = visible; flagged = visible but under review; hidden = removed from public view',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Listing Question'
        verbose_name_plural = 'Listing Questions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Q on {self.listing.title} by {self.asker.username}"
