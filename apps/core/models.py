from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator


class County(models.Model):
    """Pennsylvania county reference data"""
    name = models.CharField(max_length=50, unique=True)
    state = models.CharField(max_length=2, default='PA')
    fips_code = models.CharField(max_length=5, blank=True)
    slug = models.SlugField(max_length=50, unique=True)

    class Meta:
        verbose_name = 'County'
        verbose_name_plural = 'Counties'
        ordering = ['name']

    def __str__(self):
        return self.name


class LicenseType(models.Model):
    """License type reference data (e.g., Resident, Non-resident)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'License Type'
        verbose_name_plural = 'License Types'
        ordering = ['name']

    def __str__(self):
        return self.name


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
