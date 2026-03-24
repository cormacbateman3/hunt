"""
Migration 0003: Replace license_type FK with license_types M2M on CollectionItem — Task 9.2

Operations:
  1. AddField collectionitem.license_types (M2M → core.LicenseType)
  2. RunPython: copy existing license_type FK → license_types M2M
  3. RemoveField collectionitem.license_type
"""

from django.db import migrations, models


def copy_license_type_to_m2m(apps, schema_editor):
    """Copy the existing license_type FK value into the new license_types M2M set."""
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    for item in CollectionItem.objects.filter(license_type__isnull=False).iterator():
        item.license_types.add(item.license_type)


class Migration(migrations.Migration):

    dependencies = [
        ('collections', '0002_alter_collectionitem_is_public_and_more'),
        ('core', '0004_state_geographicunit_licensetype_enrich'),
    ]

    operations = [

        # 1. Add the new M2M field (blank=True so existing rows are fine)
        migrations.AddField(
            model_name='collectionitem',
            name='license_types',
            field=models.ManyToManyField(
                blank=True,
                help_text='License type(s) for this collection item',
                related_name='collection_items',
                to='core.licensetype',
            ),
        ),

        # 2. Backfill: copy license_type → license_types for all existing items
        migrations.RunPython(copy_license_type_to_m2m, reverse_code=migrations.RunPython.noop),

        # 3. Remove the old FK (data already copied above)
        migrations.RemoveField(
            model_name='collectionitem',
            name='license_type',
        ),
    ]
