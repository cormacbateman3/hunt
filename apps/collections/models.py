from django.db import models
from django.contrib.auth.models import User
from apps.core.models import GeographicUnit, LicenseType
from apps.core.constants import COLOR_CHOICES, FORM_LICENSE_TYPE_CATEGORIES, RESIDENT_STATUS_CHOICES, SHAPE_CHOICES


class CollectionItem(models.Model):
    """An item in a user's personal collection"""

    CONDITION_CHOICES = [
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('very_good', 'Very Good'),
        ('excellent', 'Excellent'),
        ('mint', 'Mint'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collection_items')
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
    shape = models.CharField(max_length=30, choices=SHAPE_CHOICES, blank=True)
    colors = models.JSONField(default=list, blank=True)
    condition_grade = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    is_public = models.BooleanField(default=True, help_text="Visible on public profile")
    trade_eligible = models.BooleanField(default=True, help_text="Available for trade offers")
    featured = models.BooleanField(default=False, help_text="Pin to the top of your public profile (max 6)")
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
    """Image for a collection item"""
    collection_item = models.ForeignKey(
        CollectionItem, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='collections/')
    sort_order = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Collection Item Image'
        verbose_name_plural = 'Collection Item Images'
        ordering = ['sort_order', 'uploaded_at']

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
