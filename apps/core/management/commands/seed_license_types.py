import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import LicenseType, State


class Command(BaseCommand):
    help = 'Seed license types from utilities/cleaned/license_types.csv'

    def handle(self, *args, **options):
        csv_path = Path('utilities/cleaned/license_types.csv')
        if not csv_path.exists():
            raise CommandError(f'Missing cleaned license type data: {csv_path}')

        federal_state, _ = State.objects.get_or_create(
            code='FD',
            defaults={
                'name': 'Federal',
                'slug': 'federal',
                'issuance_unit_type': 'Statewide',
                'issuance_unit_label': 'Statewide',
            },
        )

        created = 0
        updated = 0
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                state_code = row['state_abbrev'].strip()
                state = None
                if state_code == 'FD':
                    state = federal_state
                elif state_code:
                    state = State.objects.filter(code=state_code).first()
                    if state is None:
                        raise CommandError(f'Unknown state code in license type seed: {state_code}')

                _, is_created = LicenseType.objects.update_or_create(
                    state=state,
                    name=row['name'].strip(),
                    category=row['category'].strip(),
                    defaults={
                        'slug': row['slug'].strip(),
                        'is_system_value': row.get('is_system_value', 'True').strip().lower() == 'true',
                    },
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
