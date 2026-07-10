from django.db import migrations

BASE_DIMENSIONS = {'residency', 'holder_eligibility', 'activity_scope', 'duration'}


def backfill_item_kind(apps, schema_editor):
    """license if any base dimension is present; addon if only addon_type;
    everything else stays license and is logged for manual review."""
    CollectionItem = apps.get_model('collections', 'CollectionItem')
    addon_pks, ambiguous_pks = [], []
    for item in CollectionItem.objects.prefetch_related('license_types'):
        categories = {lt.category for lt in item.license_types.all()}
        if categories & BASE_DIMENSIONS:
            continue  # license — the field default already says so
        if 'addon_type' in categories:
            addon_pks.append(item.pk)
        else:
            ambiguous_pks.append(item.pk)
    if addon_pks:
        CollectionItem.objects.filter(pk__in=addon_pks).update(item_kind='addon')
    if ambiguous_pks:
        print(
            f'\n[item_kind backfill] {len(ambiguous_pks)} collection item(s) had no base '
            f'or addon taxonomy; defaulted to license — review pks: {ambiguous_pks}'
        )


class Migration(migrations.Migration):

    dependencies = [
        ('collections', '0007_collectionitem_addons_attached_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_item_kind, migrations.RunPython.noop),
    ]
