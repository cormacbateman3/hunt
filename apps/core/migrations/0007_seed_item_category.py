from django.db import migrations


def seed_item_category(apps, schema_editor):
    ItemCategory = apps.get_model('core', 'ItemCategory')
    ItemCategory.objects.get_or_create(
        slug='licenses-permits',
        defaults={
            'department': 'Sporting Antiques',
            'name': 'Licenses & Permits',
            'sort_order': 1,
            'is_active': True,
        },
    )


def remove_item_category(apps, schema_editor):
    ItemCategory = apps.get_model('core', 'ItemCategory')
    ItemCategory.objects.filter(slug='licenses-permits').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_itemcategory_licensetype_first_year_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_item_category, remove_item_category),
    ]
