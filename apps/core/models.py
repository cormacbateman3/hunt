from django.db import models


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
