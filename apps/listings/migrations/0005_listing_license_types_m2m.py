"""
Migration 0005: Replace license_type_ref FK with license_types M2M — Task 9.2

Operations:
  1. AddField listing.license_types (M2M → core.LicenseType)
  2. RunPython: copy existing license_type_ref → license_types M2M
  3. RemoveField listing.license_type_ref
"""

from django.db import migrations, models


def copy_license_type_ref_to_m2m(apps, schema_editor):
    """Copy the existing license_type_ref FK value into the new license_types M2M set."""
    Listing = apps.get_model('listings', 'Listing')
    for listing in Listing.objects.filter(license_type_ref__isnull=False).iterator():
        listing.license_types.add(listing.license_type_ref)


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_listing_resident_status_listingquestion'),
        ('core', '0004_state_geographicunit_licensetype_enrich'),
    ]

    operations = [

        # 1. Add the new M2M field (blank=True so existing rows are fine)
        migrations.AddField(
            model_name='listing',
            name='license_types',
            field=models.ManyToManyField(
                blank=True,
                help_text='License type(s) for this listing',
                related_name='listings',
                to='core.licensetype',
            ),
        ),

        # 2. Backfill: copy license_type_ref → license_types for all existing listings
        migrations.RunPython(copy_license_type_ref_to_m2m, reverse_code=migrations.RunPython.noop),

        # 3. Remove the old FK (data already copied above)
        migrations.RemoveField(
            model_name='listing',
            name='license_type_ref',
        ),
    ]
