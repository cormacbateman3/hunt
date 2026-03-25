import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import GeographicUnit, State


class Command(BaseCommand):
    help = 'Seed geographic units from utilities/cleaned/geographic_units.csv'

    def handle(self, *args, **options):
        csv_path = Path('utilities/cleaned/geographic_units.csv')
        if not csv_path.exists():
            raise CommandError(f'Missing cleaned geographic unit data: {csv_path}')

        states = {state.code: state for state in State.objects.all()}
        created = 0
        updated = 0
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                state = states.get(row['state_abbrev'].strip())
                if state is None:
                    raise CommandError(f'Unknown state code in geographic unit seed: {row["state_abbrev"]}')

                _, is_created = GeographicUnit.objects.update_or_create(
                    state=state,
                    name=row['name'].strip(),
                    defaults={
                        'unit_type': row.get('unit_type', '').strip() or state.issuance_unit_type,
                        'fips_code': row.get('fips_code', '').strip(),
                        'slug': row['slug'].strip(),
                        'sort_order': int(row.get('sort_order', '0') or 0),
                        'unit_number': row.get('unit_number', '').strip(),
                        'is_statewide': row.get('is_statewide', 'False').strip().lower() == 'true',
                        'geo_data_complete': row.get('geo_data_complete', 'True').strip().lower() == 'true',
                        'notes': row.get('notes', '').strip(),
                    },
                )
                if is_created:
                    created += 1
                else:
                    updated += 1

        statewide_created = 0
        for state in State.objects.all():
            _, is_created = GeographicUnit.objects.get_or_create(
                state=state,
                name='Statewide',
                defaults={
                    'unit_type': 'Statewide',
                    'slug': f'{state.slug}-statewide',
                    'sort_order': 0,
                    'is_statewide': True,
                    'geo_data_complete': True,
                },
            )
            if is_created:
                statewide_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                'Geographic unit seed complete. '
                f'created={created} updated={updated} statewide_added={statewide_created} '
                f'total={GeographicUnit.objects.count()}'
            )
        )
