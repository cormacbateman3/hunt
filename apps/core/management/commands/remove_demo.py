"""
remove_demo — safely wipes all demo seed data.

Safety guards (both must be true to delete anything):
  1. Record is owned by __keystonebid_demo__
  2. Record title starts with [DEMO]

Usage:
    python manage.py remove_demo            # dry-run, shows what would be deleted
    python manage.py remove_demo --yes      # actually delete
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from apps.collections.models import CollectionItem
from apps.listings.models import Listing

DEMO_USERNAME = '__keystonebid_demo__'
DEMO_PREFIX = '[DEMO] '


class Command(BaseCommand):
    help = 'Remove demo seed data (dry-run by default; pass --yes to commit).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Actually delete the records (without this flag the command only reports).',
        )

    def handle(self, *args, **options):
        commit = options['yes']

        try:
            demo_user = User.objects.get(username=DEMO_USERNAME)
        except User.DoesNotExist:
            self.stdout.write('Demo user __keystonebid_demo__ not found — nothing to remove.')
            return

        listing_qs = Listing.objects.filter(
            seller=demo_user,
            title__startswith=DEMO_PREFIX,
        )
        item_qs = CollectionItem.objects.filter(
            owner=demo_user,
            title__startswith=DEMO_PREFIX,
        )

        n_listings = listing_qs.count()
        n_items = item_qs.count()

        self.stdout.write(f'Found {n_listings} demo listing(s) and {n_items} demo collection item(s).')

        if not commit:
            self.stdout.write(
                self.style.WARNING(
                    'Dry-run — nothing deleted. Re-run with --yes to commit.'
                )
            )
            return

        listing_qs.delete()
        item_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Deleted {n_listings} listing(s) and {n_items} collection item(s). '
                f'(Demo user account retained.)'
            )
        )
