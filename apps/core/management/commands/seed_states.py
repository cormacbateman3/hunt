import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import State


class Command(BaseCommand):
    help = 'Seed states from utilities/cleaned/states.csv'

    def handle(self, *args, **options):
        csv_path = Path('utilities/cleaned/states.csv')
        if not csv_path.exists():
            raise CommandError(f'Missing cleaned state data: {csv_path}')

        created = 0
        updated = 0
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                _, is_created = State.objects.update_or_create(
                    code=row['state_abbrev'].strip(),
                    defaults={
                        'name': row['state_name'].strip(),
                        'fips_code': int(row['state_fips']) if row['state_fips'].strip() else None,
                        'min_license_year': int(row['min_license_year']) if row['min_license_year'].strip() else None,
                        'min_year_confidence': row.get('min_year_confidence', '').strip(),
                        'min_year_source': row.get('min_year_source', '').strip(),
                        'issuance_scope': row.get('issuance_scope', '').strip(),
                        'issuance_unit_type': row.get('issuance_unit_type', '').strip() or 'County',
                        'issuance_unit_label': row.get('issuance_unit_label', '').strip() or 'County',
                        'is_primary_default': row.get('is_primary_default', 'False').strip().lower() == 'true',
                        'agency_name': row.get('agency_name', '').strip(),
                        'agency_name_historical': row.get('agency_name_historical', '').strip(),
                        'licensing_start_year': int(row['licensing_start_year']) if row.get('licensing_start_year', '').strip() else None,
                        'licensing_start_source': row.get('licensing_start_source', '').strip(),
                        'notes': row.get('notes', '').strip(),
                        'slug': row['slug'].strip(),
                    },
                )
                if is_created:
                    created += 1
                else:
                    updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'State seed complete. created={created} updated={updated} total={State.objects.count()}'
            )
        )
