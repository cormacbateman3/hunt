from django.db import models
from django.contrib.auth.models import User
from apps.core.models import GeographicUnit, LicenseType, get_default_item_category
from apps.core.constants import COLOR_CHOICES, CONDITION_CHOICES, FORM_LICENSE_TYPE_CATEGORIES, ITEM_KIND_CHOICES, RESIDENT_STATUS_CHOICES, SHAPE_CHOICES
from apps.listings.models import ERA_LABEL_CHOICES, IMAGE_ROLE_CHOICES, _year_to_era


class CollectionItem(models.Model):
    """An item in a user's personal collection"""

    CONDITION_CHOICES = CONDITION_CHOICES

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection_items')
    category = models.ForeignKey(
        'core.ItemCategory', on_delete=models.PROTECT,
        default=get_default_item_category, related_name='collection_items',
    )
    item_kind = models.CharField(
        max_length=20, choices=ITEM_KIND_CHOICES, default='license',
        help_text='Base license vs. standalone stamp/tag/permit',
    )
    addons_attached = models.BooleanField(
        null=True, blank=True,
        help_text='For licenses with add-ons: True = tags/stamps still physically attached; False = detached/used; null = unknown',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    license_year = models.IntegerField(null=True, blank=True, help_text="Year the license was issued")
    state = models.ForeignKey(
        'core.State', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='collection_items', help_text='Issuing state for this item'
    )
    county = models.ForeignKey(
        GeographicUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='collection_items'
    )
    license_types = models.ManyToManyField(
        LicenseType, blank=True, related_name='collection_items',
        help_text="License type(s) for this collection item",
    )
    resident_status = models.CharField(
        max_length=20, choices=RESIDENT_STATUS_CHOICES, default='unknown'
    )
    serial_number = models.CharField(
        max_length=100, blank=True,
        help_text="License serial or stub number, if visible"
    )
    era_label = models.CharField(
        max_length=10, choices=ERA_LABEL_CHOICES, null=True, blank=True,
        help_text="Decade era — set automatically when license_year is known; required when year is unknown"
    )
    shape = models.CharField(max_length=30, choices=SHAPE_CHOICES, blank=True)
    colors = models.JSONField(default=list, blank=True)
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    is_public = models.BooleanField(default=True, help_text="Visible on public profile")
    # DEFERRED — `default=True` opts every item into trading, so any UI reading
    # this flag says the same thing about everybody and carries no signal.
    # Blocked on: 10.10 trade re-architecture, which replaces this with an
    # explicit item-level `is_tradeable` choice.
    # Register: docs/internal/plan_design.md
    trade_eligible = models.BooleanField(default=True, help_text="Available for trade offers")
    featured = models.BooleanField(default=False, help_text="Pin to the top of your public profile (max 6)")

    # ── Only the owner ever sees these ───────────────────────────────────
    #
    # What you paid, where you got it, and a note to yourself. This block is
    # what makes cataloguing worth doing rather than a chore — and it is
    # never public, never shown to a buyer, and never price history. Price
    # history is what *listings* sold for; this is what you spent.
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Private. What you paid, for your own records and an '
                  'insurance export. Never shown to anybody else.',
    )
    acquired_note = models.CharField(
        max_length=120, blank=True,
        help_text='Private. When and where — "Mar 2026, Bloomsburg".',
    )
    private_note = models.TextField(
        blank=True, max_length=1000,
        help_text='Private. A note to yourself about this piece.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Collection Item'
        verbose_name_plural = 'Collection Items'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['owner', '-created_at']),
            models.Index(fields=['is_public', 'trade_eligible']),
        ]

    def __str__(self):
        return f"{self.title} ({self.license_year}) - {self.owner.username}"

    @property
    def effective_era(self):
        """Canonical era — derived from license_year if known, else falls back to era_label."""
        if self.license_year:
            return _year_to_era(self.license_year)
        return self.era_label or ''

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


class CollectionItemImage(models.Model):
    """Image for a collection item.

    ``image_role`` matches ``ListingImage`` so a photograph keeps its meaning
    when an item is listed for sale — the front stays the front.
    """

    collection_item = models.ForeignKey(
        CollectionItem, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='collections/')
    image_role = models.CharField(
        max_length=10, choices=IMAGE_ROLE_CHOICES, default='detail',
        help_text='What this photograph is of.',
    )
    sort_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Collection Item Image'
        verbose_name_plural = 'Collection Item Images'
        ordering = ['sort_order', 'uploaded_at']
        constraints = [
            models.UniqueConstraint(
                fields=['collection_item', 'image_role'],
                condition=models.Q(image_role__in=('front', 'back')),
                name='one_item_photograph_per_named_slot',
            ),
        ]

    def __str__(self):
        return f"Image for {self.collection_item.title}"


class WantedItem(models.Model):
    """Item a user is looking for"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wanted_items')
    state = models.ForeignKey(
        'core.State', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='wanted_items'
    )
    county = models.ForeignKey(
        GeographicUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='wanted_items'
    )
    year_min = models.IntegerField(null=True, blank=True)
    year_max = models.IntegerField(null=True, blank=True)
    license_type = models.ForeignKey(
        LicenseType, on_delete=models.SET_NULL, null=True, blank=True, related_name='wanted_items'
    )
    notes = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Wanted Item'
        verbose_name_plural = 'Wanted Items'
        ordering = ['-created_at']

    def __str__(self):
        parts = []
        if self.county:
            parts.append(str(self.county))
        if self.year_min and self.year_max:
            parts.append(f"{self.year_min}-{self.year_max}")
        elif self.year_min:
            parts.append(f"from {self.year_min}")
        elif self.year_max:
            parts.append(f"to {self.year_max}")
        return f"Wanted: {', '.join(parts) or 'Any'} - {self.user.username}"
