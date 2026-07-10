import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.management.seed_utils import upsert_row
from apps.core.models import State


class Command(BaseCommand):
    help = (
        'Seed states from utilities/cleaned/states.csv. Default mode creates '
        'missing rows and reports drift without touching existing rows; use '
        '--overwrite to force CSV -> DB.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Update existing rows from the CSV (overwrites admin edits).',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
        csv_path = Path('utilities/cleaned/states.csv')
        if not csv_path.exists():
            raise CommandError(f'Missing cleaned state data: {csv_path}')

        counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'drift': 0}
        drift_lines = []
        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                values = {
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
                }
                outcome, drift_line = upsert_row(
                    State, {'code': row['state_abbrev'].strip()}, values, overwrite,
                )
                counts[outcome] += 1
                if drift_line:
                    drift_lines.append(drift_line)

        if drift_lines:
            self.stdout.write(self.style.WARNING(
                f'Drift (DB differs from CSV on {len(drift_lines)} row(s); re-run with --overwrite to apply):'
            ))
            for line in drift_lines:
                self.stdout.write(self.style.WARNING(line))

        self.stdout.write(
            self.style.SUCCESS(
                f'State seed complete. created={counts["created"]} updated={counts["updated"]} '
                f'drift={counts["drift"]} total={State.objects.count()}'
            )
        )
