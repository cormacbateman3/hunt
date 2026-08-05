from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.constants import (
    INSTRUMENT_CHOICES,
    LICENSE_TYPE_CATEGORY_CHOICES,
    SUGGESTION_STATUS_CHOICES,
    SUGGESTION_TARGET_MODEL_CHOICES,
    SUGGESTION_TYPE_CHOICES,
)


class ItemCategory(models.Model):
    """
    Top of the item hierarchy: department -> category.

    One seeded row for now (Sporting Antiques -> Licenses & Permits). The
    department stays a label field on this table until a second department
    actually exists. Not exposed on forms or browse while there is only one
    category — items are stamped via the FK default.
    """

    department = models.CharField(max_length=60, default='Sporting Antiques')
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Item Category'
        verbose_name_plural = 'Item Categories'
        ordering = ['sort_order', 'name']

    def __str__(self):
        return f'{self.department} — {self.name}'


def get_default_item_category():
    """Default pk for item category FKs — the single seeded category."""
    category, _ = ItemCategory.objects.get_or_create(
        slug='licenses-permits',
        defaults={
            'department': 'Sporting Antiques',
            'name': 'Licenses & Permits',
            'sort_order': 1,
        },
    )
    return category.pk


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
    min_year_source = models.URLField(blank=True)
    issuance_scope = models.CharField(max_length=30, blank=True)
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
    agency_name = models.CharField(max_length=150, blank=True)
    agency_name_historical = models.CharField(max_length=150, blank=True)
    licensing_start_year = models.IntegerField(null=True, blank=True)
    licensing_start_source = models.URLField(blank=True)
    notes = models.TextField(blank=True)
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
    unit_number = models.CharField(max_length=30, blank=True)
    is_statewide = models.BooleanField(default=False)
    geo_data_complete = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

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

    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='license_types',
        help_text='State this type belongs to; null = universal/cross-state',
    )
    name = models.CharField(max_length=100)
    category = models.CharField(
        max_length=30,
        choices=LICENSE_TYPE_CATEGORY_CHOICES,
        default='residency',
    )
    slug = models.SlugField(max_length=150)
    is_system_value = models.BooleanField(default=True)

    # Facets — populated only where category='addon_type'
    target_species = models.CharField(
        max_length=50, blank=True,
        help_text='e.g. Deer, Antlerless Deer, Turkey, Waterfowl (addon rows only)',
    )
    hunting_method = models.CharField(
        max_length=30, blank=True,
        help_text='Only methods visible on the artifact: Archery, Muzzleloader, Firearm',
    )
    instrument = models.CharField(
        max_length=20, choices=INSTRUMENT_CHOICES, blank=True,
        help_text='What the artifact physically is (addon rows only)',
    )

    # Product year span — soft bounds: they gate suggestions, ordering, and
    # prefill matching, never validity. Null = unbounded/unknown.
    first_year = models.IntegerField(
        null=True, blank=True,
        help_text='First year this product existed under this name/form',
    )
    last_year = models.IntegerField(
        null=True, blank=True,
        help_text='Last year issued (blank = still issued or unknown)',
    )

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


class ReferenceDataSuggestion(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reference_data_suggestions',
    )
    suggestion_type = models.CharField(
        max_length=20,
        choices=SUGGESTION_TYPE_CHOICES,
        default='new_value',
    )
    target_model = models.CharField(
        max_length=30,
        choices=SUGGESTION_TARGET_MODEL_CHOICES,
        default='other',
    )
    target_id = models.IntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    current_value = models.TextField(blank=True)
    proposed_value = models.TextField()
    source_or_evidence = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=SUGGESTION_STATUS_CHOICES,
        default='pending',
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_reference_data_suggestions',
    )

    class Meta:
        ordering = ['status', '-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['target_model', 'target_id']),
        ]

    def __str__(self):
        return f'{self.get_target_model_display()} suggestion #{self.pk}'


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
    ship_by_days = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text=(
            'Days a seller has to dispatch after payment clears. Quoted to '
            'buyers on the listing page and printed as a date on the order. '
            'No background job enforces it yet, so it is a promise rather '
            'than a constraint — do not shorten it without one.'
        ),
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Marketplace Settings'
        verbose_name_plural = 'Marketplace Settings'

    def __str__(self):
        return f'Marketplace Settings (fee {self.platform_fee_percent}%)'
