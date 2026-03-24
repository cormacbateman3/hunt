from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class State(models.Model):
    """US state reference data for the license marketplace."""

    code = models.CharField(max_length=2, unique=True, help_text='Two-letter abbreviation, e.g. PA')
    name = models.CharField(max_length=50, unique=True)
    fips_code = models.IntegerField(null=True, blank=True)
    min_license_year = models.IntegerField(
        null=True, blank=True,
        help_text='Earliest known license year for this state',
    )
    min_year_confidence = models.CharField(
        max_length=20, blank=True,
        help_text='Confidence level of min_license_year: high/medium/low',
    )
    issuance_unit_type = models.CharField(
        max_length=30, default='County',
        help_text='e.g. County, GMU, WMD, DPA, Hunt Area',
    )
    issuance_unit_label = models.CharField(
        max_length=60, default='County',
        help_text='Human-readable label for the issuance unit type',
    )
    is_primary_default = models.BooleanField(
        default=False,
        help_text='True only for Pennsylvania — the default state in all forms',
    )
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        verbose_name = 'State'
        verbose_name_plural = 'States'
        ordering = ['-is_primary_default', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class GeographicUnit(models.Model):
    """
    Geographic issuance unit — replaces the old County model.

    Pennsylvania uses Counties; other states use GMUs, WMDs, DPAs, Hunt Areas, etc.
    The unit_type field captures the heterogeneity.
    """

    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='geographic_units',
        help_text='State this unit belongs to',
    )
    name = models.CharField(max_length=100)
    unit_type = models.CharField(
        max_length=30, default='County',
        help_text='e.g. County, GMU, WMD, DPA, Hunt Area',
    )
    fips_code = models.CharField(max_length=5, blank=True)
    slug = models.SlugField(max_length=100)
    sort_order = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Geographic Unit'
        verbose_name_plural = 'Geographic Units'
        ordering = ['sort_order', 'name']
        unique_together = [('state', 'name')]
        indexes = [
            models.Index(fields=['state', 'name']),
            models.Index(fields=['state', 'unit_type']),
        ]

    def __str__(self):
        return self.name


class LicenseType(models.Model):
    """
    License type taxonomy.

    Has a category dimension (residency/duration/eligibility/activity_scope/addon)
    and an optional state FK (null = universal/cross-state).
    Listings and CollectionItems use a ManyToMany to express multiple type dimensions,
    e.g. Resident (residency) + Annual (duration) + Hunting (activity_scope).
    """

    CATEGORY_CHOICES = [
        ('residency', 'Residency'),
        ('duration', 'Duration'),
        ('eligibility', 'Eligibility'),
        ('activity_scope', 'Activity Scope'),
        ('addon', 'Add-on / Tag / Permit'),
    ]

    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='license_types',
        help_text='State this type belongs to; null = universal/cross-state',
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='residency')
    slug = models.SlugField(max_length=150)

    class Meta:
        verbose_name = 'License Type'
        verbose_name_plural = 'License Types'
        ordering = ['category', 'name']
        unique_together = [('name', 'state', 'category')]
        indexes = [
            models.Index(fields=['state', 'category']),
        ]

    def __str__(self):
        state_label = f' ({self.state.code})' if self.state_id else ' (universal)'
        return f'{self.name}{state_label}'


class MarketplaceSettings(models.Model):
    """Singleton settings for marketplace-wide tunables."""
    platform_fee_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text='Platform fee percentage applied to order item amount.',
    )
    trade_label_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default='1.00',
        validators=[MinValueValidator(0)],
        help_text='Flat fee charged per trader when using in-app trade label purchase.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Marketplace Settings'
        verbose_name_plural = 'Marketplace Settings'

    def __str__(self):
        return f'Marketplace Settings (fee {self.platform_fee_percent}%)'
