"""Every lot that has ever been public gets a "Listed" date (10.25).

created_at is the best record we have for existing rows — for anything
published straight through it is the same moment, and for old drafts
published later it is at worst early, never the shelf record's date.
Drafts and scheduled lots stay null; their stamp arrives when they go up.
"""

from django.db import migrations
from django.db.models import F


def backfill(apps, schema_editor):
    Listing = apps.get_model('listings', 'Listing')
    Listing.objects.exclude(status__in=('draft', 'scheduled')).update(
        published_at=F('created_at'))


def unfill(apps, schema_editor):
    Listing = apps.get_model('listings', 'Listing')
    Listing.objects.update(published_at=None)


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0024_listing_published_at_listing_view_count'),
    ]

    operations = [
        migrations.RunPython(backfill, unfill),
    ]
