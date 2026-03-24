"""
Migration 0004: Reference data architecture — Task 9.2

Operations (in order):
  1.  CreateModel State
  2.  RenameModel County → GeographicUnit (renames DB table)
  3.  RenameField geographicunit.state (old CharField) → state_code_legacy
  4.  AlterModelOptions geographicunit (new verbose names + ordering)
  5.  AlterField geographicunit.name  (remove unique=True, max_length 50→100)
  6.  AlterField geographicunit.slug  (remove unique=True, explicit max_length=100)
  7.  AddField geographicunit.state   (FK → State, null=True)
  8.  AddField geographicunit.unit_type
  9.  AddField geographicunit.sort_order
  10. RemoveField geographicunit.state_code_legacy
  11. RunPython backfill_pa_state      (create PA State row; assign to existing units)
  12. AlterUniqueTogether geographicunit  (state, name)
  13. AddIndex x2 geographicunit
  14. AddField licensetype.state       (FK → State, null=True)
  15. AddField licensetype.category
  16. AlterField licensetype.name      (remove unique=True)
  17. AlterField licensetype.slug      (remove unique=True, max_length 100→150)
  18. AlterModelOptions licensetype    (new ordering)
  19. AlterUniqueTogether licensetype  (name, state, category)
  20. AddIndex licensetype
"""

import django.db.models.deletion
from django.db import migrations, models


# ---------------------------------------------------------------------------
# Data migration helper
# ---------------------------------------------------------------------------

def backfill_pa_state(apps, schema_editor):
    """Create the Pennsylvania State record and assign it to all existing GeographicUnits."""
    State = apps.get_model('core', 'State')
    GeographicUnit = apps.get_model('core', 'GeographicUnit')

    pa_state, _ = State.objects.get_or_create(
        code='PA',
        defaults={
            'name': 'Pennsylvania',
            'fips_code': 42,
            'min_license_year': 1913,
            'min_year_confidence': 'high',
            'issuance_unit_type': 'County',
            'issuance_unit_label': 'County (historical); Wildlife Management Unit (WMU since 2003)',
            'is_primary_default': True,
            'slug': 'pennsylvania',
        },
    )

    # All previously seeded county rows were Pennsylvania — assign the FK.
    GeographicUnit.objects.filter(state__isnull=True).update(state=pa_state)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_marketplacesettings_trade_label_fee_amount'),
    ]

    operations = [

        # ------------------------------------------------------------------
        # 1. Create State model
        # ------------------------------------------------------------------
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(help_text='Two-letter abbreviation, e.g. PA', max_length=2, unique=True)),
                ('name', models.CharField(max_length=50, unique=True)),
                ('fips_code', models.IntegerField(blank=True, null=True)),
                ('min_license_year', models.IntegerField(blank=True, help_text='Earliest known license year for this state', null=True)),
                ('min_year_confidence', models.CharField(blank=True, help_text='Confidence level of min_license_year: high/medium/low', max_length=20)),
                ('issuance_unit_type', models.CharField(default='County', help_text='e.g. County, GMU, WMD, DPA, Hunt Area', max_length=30)),
                ('issuance_unit_label', models.CharField(default='County', help_text='Human-readable label for the issuance unit type', max_length=60)),
                ('is_primary_default', models.BooleanField(default=False, help_text='True only for Pennsylvania \u2014 the default state in all forms')),
                ('slug', models.SlugField(max_length=50, unique=True)),
            ],
            options={
                'verbose_name': 'State',
                'verbose_name_plural': 'States',
                'ordering': ['-is_primary_default', 'name'],
            },
        ),

        # ------------------------------------------------------------------
        # 2. Rename County → GeographicUnit (renames core_county → core_geographicunit)
        # ------------------------------------------------------------------
        migrations.RenameModel(
            old_name='County',
            new_name='GeographicUnit',
        ),

        # ------------------------------------------------------------------
        # 3. Rename the old state CharField to free up the name for the new FK
        # ------------------------------------------------------------------
        migrations.RenameField(
            model_name='geographicunit',
            old_name='state',
            new_name='state_code_legacy',
        ),

        # ------------------------------------------------------------------
        # 4. Update verbose names and ordering on GeographicUnit
        # ------------------------------------------------------------------
        migrations.AlterModelOptions(
            name='geographicunit',
            options={
                'ordering': ['sort_order', 'name'],
                'verbose_name': 'Geographic Unit',
                'verbose_name_plural': 'Geographic Units',
            },
        ),

        # ------------------------------------------------------------------
        # 5. Remove unique=True from name and increase max_length (50 → 100)
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name='geographicunit',
            name='name',
            field=models.CharField(max_length=100),
        ),

        # ------------------------------------------------------------------
        # 6. Remove unique=True from slug and add explicit max_length
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name='geographicunit',
            name='slug',
            field=models.SlugField(max_length=100),
        ),

        # ------------------------------------------------------------------
        # 7. Add state FK (null=True — existing rows start with no state)
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='geographicunit',
            name='state',
            field=models.ForeignKey(
                blank=True,
                help_text='State this unit belongs to',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='geographic_units',
                to='core.state',
            ),
        ),

        # ------------------------------------------------------------------
        # 8. Add unit_type field
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='geographicunit',
            name='unit_type',
            field=models.CharField(
                default='County',
                help_text='e.g. County, GMU, WMD, DPA, Hunt Area',
                max_length=30,
            ),
        ),

        # ------------------------------------------------------------------
        # 9. Add sort_order field
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='geographicunit',
            name='sort_order',
            field=models.IntegerField(default=0),
        ),

        # ------------------------------------------------------------------
        # 10. Drop the legacy state_code_legacy CharField (was 'PA' for all rows)
        # ------------------------------------------------------------------
        migrations.RemoveField(
            model_name='geographicunit',
            name='state_code_legacy',
        ),

        # ------------------------------------------------------------------
        # 11. Data migration — must run before adding unique_together
        # ------------------------------------------------------------------
        migrations.RunPython(backfill_pa_state, reverse_code=migrations.RunPython.noop),

        # ------------------------------------------------------------------
        # 12. Add unique_together (safe now that all rows have state assigned)
        # ------------------------------------------------------------------
        migrations.AlterUniqueTogether(
            name='geographicunit',
            unique_together={('state', 'name')},
        ),

        # ------------------------------------------------------------------
        # 13. Indexes on GeographicUnit
        # ------------------------------------------------------------------
        migrations.AddIndex(
            model_name='geographicunit',
            index=models.Index(fields=['state', 'name'], name='core_gu_state_name_idx'),
        ),
        migrations.AddIndex(
            model_name='geographicunit',
            index=models.Index(fields=['state', 'unit_type'], name='core_gu_state_utype_idx'),
        ),

        # ------------------------------------------------------------------
        # 14. Add state FK to LicenseType (null=True — existing types are PA by default)
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='licensetype',
            name='state',
            field=models.ForeignKey(
                blank=True,
                help_text='State this type belongs to; null = universal/cross-state',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='license_types',
                to='core.state',
            ),
        ),

        # ------------------------------------------------------------------
        # 15. Add category field to LicenseType
        # ------------------------------------------------------------------
        migrations.AddField(
            model_name='licensetype',
            name='category',
            field=models.CharField(
                choices=[
                    ('residency', 'Residency'),
                    ('duration', 'Duration'),
                    ('eligibility', 'Eligibility'),
                    ('activity_scope', 'Activity Scope'),
                    ('addon', 'Add-on / Tag / Permit'),
                ],
                default='residency',
                max_length=30,
            ),
        ),

        # ------------------------------------------------------------------
        # 16. Remove unique=True from LicenseType.name
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name='licensetype',
            name='name',
            field=models.CharField(max_length=100),
        ),

        # ------------------------------------------------------------------
        # 17. Remove unique=True from LicenseType.slug and increase max_length
        # ------------------------------------------------------------------
        migrations.AlterField(
            model_name='licensetype',
            name='slug',
            field=models.SlugField(max_length=150),
        ),

        # ------------------------------------------------------------------
        # 18. Update ordering on LicenseType
        # ------------------------------------------------------------------
        migrations.AlterModelOptions(
            name='licensetype',
            options={
                'ordering': ['category', 'name'],
                'verbose_name': 'License Type',
                'verbose_name_plural': 'License Types',
            },
        ),

        # ------------------------------------------------------------------
        # 19. Add unique_together on LicenseType
        # ------------------------------------------------------------------
        migrations.AlterUniqueTogether(
            name='licensetype',
            unique_together={('name', 'state', 'category')},
        ),

        # ------------------------------------------------------------------
        # 20. Add index to LicenseType
        # ------------------------------------------------------------------
        migrations.AddIndex(
            model_name='licensetype',
            index=models.Index(fields=['state', 'category'], name='core_lt_state_cat_idx'),
        ),
    ]
