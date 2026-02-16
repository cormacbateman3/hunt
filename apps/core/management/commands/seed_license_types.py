from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.core.models import LicenseType


LICENSE_TYPES = [
    'Resident',
    'Non-Resident',
    'Junior Resident',
    'Junior Non-Resident',
    'Senior Resident',
    'Sportsman',
    'Furtaker',
]


class Command(BaseCommand):
    help = 'Seed license type reference data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing license types before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            deleted, _ = LicenseType.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing license type records.'))

        created = 0
        updated = 0
        for name in LICENSE_TYPES:
            _, is_created = LicenseType.objects.update_or_create(
                name=name,
                defaults={'slug': slugify(name)},
            )
            if is_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'License type seed complete. created={created} updated={updated} total={LicenseType.objects.count()}'
            )
        )
