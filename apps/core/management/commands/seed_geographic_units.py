import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.management.seed_utils import upsert_row
from apps.core.models import GeographicUnit, State


class Command(BaseCommand):
    help = (
        'Seed geographic units from utilities/cleaned/geographic_units.csv. '
        'Default mode creates missing rows and reports drift without touching '
        'existing rows; use --overwrite to force CSV -> DB.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Update existing rows from the CSV (overwrites admin edits).',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        csv_path = Path('utilities/cleaned/geographic_units.csv')
        if not csv_path.exists():
            raise CommandError(f'Missing cleaned geographic unit data: {csv_path}')

        states = {state.code: state for state in State.objects.all()}
        counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'drift': 0}
        drift_lines = []
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                state = states.get(row['state_abbrev'].strip())
                if state is None:
                    raise CommandError(f'Unknown state code in geographic unit seed: {row["state_abbrev"]}')

                values = {
                    'unit_type': row.get('unit_type', '').strip() or state.issuance_unit_type,
                    'fips_code': row.get('fips_code', '').strip(),
                    'slug': row['slug'].strip(),
                    'sort_order': int(row.get('sort_order', '0') or 0),
                    'unit_number': row.get('unit_number', '').strip(),
                    'is_statewide': row.get('is_statewide', 'False').strip().lower() == 'true',
                    'geo_data_complete': row.get('geo_data_complete', 'True').strip().lower() == 'true',
                    'notes': row.get('notes', '').strip(),
                }
                outcome, drift_line = upsert_row(
                    GeographicUnit,
                    {'state': state, 'name': row['name'].strip()},
                    values,
                    overwrite,
                )
                counts[outcome] += 1
                if drift_line:
                    drift_lines.append(drift_line)

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

        if drift_lines:
            self.stdout.write(self.style.WARNING(
                f'Drift (DB differs from CSV on {len(drift_lines)} row(s); re-run with --overwrite to apply):'
            ))
            for line in drift_lines:
                self.stdout.write(self.style.WARNING(line))

        self.stdout.write(
            self.style.SUCCESS(
                'Geographic unit seed complete. '
                f'created={counts["created"]} updated={counts["updated"]} drift={counts["drift"]} '
                f'statewide_added={statewide_created} total={GeographicUnit.objects.count()}'
            )
        )
