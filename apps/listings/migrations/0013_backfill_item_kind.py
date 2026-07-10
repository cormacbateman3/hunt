from django.db import migrations

BASE_DIMENSIONS = {'residency', 'holder_eligibility', 'activity_scope', 'duration'}


def backfill_item_kind(apps, schema_editor):
    """license if any base dimension is present; addon if only addon_type;
    everything else stays license and is logged for manual review."""
    Listing = apps.get_model('listings', 'Listing')
    addon_pks, ambiguous_pks = [], []
    for item in Listing.objects.prefetch_related('license_types'):
        categories = {lt.category for lt in item.license_types.all()}
        if categories & BASE_DIMENSIONS:
            continue  # license — the field default already says so
        if 'addon_type' in categories:
            addon_pks.append(item.pk)
        else:
            ambiguous_pks.append(item.pk)
    if addon_pks:
        Listing.objects.filter(pk__in=addon_pks).update(item_kind='addon')
    if ambiguous_pks:
        print(
            f'\n[item_kind backfill] {len(ambiguous_pks)} listing(s) had no base or '
            f'addon taxonomy; defaulted to license — review pks: {ambiguous_pks}'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0012_listing_addons_attached_listing_category_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_item_kind, migrations.RunPython.noop),
    ]
