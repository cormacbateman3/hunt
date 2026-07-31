import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import LicenseType, State

# Rows renamed/merged in ref_data (T5). Old DB rows are repointed onto the new
# row (M2M references preserved) and then deleted. Keyed (state_code, category, old_name).
RENAMES = {
    ('CO', 'addon_type', 'Deer Tag (Over-the-Counter)'): 'Deer Tag',
    ('CO', 'addon_type', 'Deer Tag (Limited Draw)'): 'Deer Tag',
    ('CO', 'addon_type', 'Elk Tag (Over-the-Counter)'): 'Elk Tag',
    ('CO', 'addon_type', 'Elk Tag (Limited Draw)'): 'Elk Tag',
    ('CO', 'addon_type', 'Pronghorn Tag (Draw)'): 'Pronghorn Tag',
    ('CO', 'addon_type', 'Bear Tag (Over-the-Counter)'): 'Bear Tag',
    ('CO', 'addon_type', 'Bear Tag (Draw)'): 'Bear Tag',
    ('CO', 'addon_type', 'Moose Tag (Draw)'): 'Moose Tag',
    ('CO', 'addon_type', 'Mountain Goat Tag (Draw)'): 'Mountain Goat Tag',
    ('CO', 'addon_type', 'Bighorn Sheep Tag (Draw)'): 'Bighorn Sheep Tag',
    ('CO', 'addon_type', 'Turkey Tag (Over-the-Counter)'): 'Turkey Tag',
    ('CO', 'addon_type', 'Turkey Tag (Draw)'): 'Turkey Tag',
    ('CO', 'addon_type', 'Mountain Lion Tag (Over-the-Counter)'): 'Mountain Lion Tag',
    ('CO', 'addon_type', 'Bison Tag (Draw)'): 'Bison Tag',
    ('KS', 'addon_type', 'Deer Firearm Tag (Draw)'): 'Deer Firearm Tag',
    ('KS', 'addon_type', 'Mule Deer Stamp (Draw)'): 'Mule Deer Stamp',
    ('KS', 'addon_type', 'Antelope Tag (Draw)'): 'Antelope Tag',
    ('KS', 'addon_type', 'Elk Tag (Draw)'): 'Elk Tag',
    ('MO', 'addon_type', 'Black Bear Permit (Draw)'): 'Black Bear Permit',
    ('MO', 'addon_type', 'Elk Permit (Draw)'): 'Elk Permit',
    ('MT', 'addon_type', 'Moose License (Draw)'): 'Moose License',
    ('MT', 'addon_type', 'Bighorn Sheep License (Draw)'): 'Bighorn Sheep License',
    ('MT', 'addon_type', 'Mountain Goat License (Draw)'): 'Mountain Goat License',
    ('MT', 'addon_type', 'Bison License (Draw)'): 'Bison License',
    ('WY', 'addon_type', 'Moose License (Draw)'): 'Moose License',
    ('WY', 'addon_type', 'Bighorn Sheep License (Draw)'): 'Bighorn Sheep License',
    ('WY', 'addon_type', 'Mountain Goat License (Draw)'): 'Mountain Goat License',
    ('WY', 'addon_type', 'Wild Bison License (Draw)'): 'Wild Bison License',
    ('WY', 'addon_type', 'Turkey License (Draw)'): 'Turkey License',
}

# Rows removed from ref_data with no replacement (T5/R5). Deleted only when
# nothing references them; otherwise reported and left in place.
DELETIONS = [
    ('IN', 'addon_type', 'Deer License Bundle'),
]

# Categories that no longer exist as taxonomy rows (form vocab lives in
# constants.py). Swept when unreferenced.
RETIRED_CATEGORIES = ['shape', 'colors']

SYNCED_FIELDS = [
    'slug', 'is_system_value', 'target_species', 'hunting_method',
    'instrument', 'first_year', 'last_year',
]


def _int_or_none(value):
    value = (value or '').strip()
    return int(value) if value else None


class Command(BaseCommand):
    help = (
        'Seed license types from utilities/cleaned/license_types.csv. '
        'Default mode creates missing rows and reports drift without touching '
        'existing rows (protects admin edits); use --overwrite to force CSV -> DB.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--overwrite', action='store_true',
            help='Update existing rows from the CSV (overwrites admin edits).',
        )

    def handle(self, *args, **options):
        overwrite = options['overwrite']
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
        states = {state.code: state for state in State.objects.all()}

        created = 0
        updated = 0
        drift: list[str] = []

        with csv_path.open(newline='', encoding='utf-8-sig') as handle:
            for row in csv.DictReader(handle):
                state_code = row['state_abbrev'].strip()
                state = None
                if state_code == 'FD':
                    state = federal_state
                elif state_code:
                    state = states.get(state_code)
                    if state is None:
                        raise CommandError(f'Unknown state code in license type seed: {state_code}')

                values = {
                    'slug': row['slug'].strip(),
                    'is_system_value': row.get('is_system_value', 'True').strip().lower() == 'true',
                    'target_species': row.get('target_species', '').strip(),
                    'hunting_method': row.get('hunting_method', '').strip(),
                    'instrument': row.get('instrument', '').strip(),
                    'first_year': _int_or_none(row.get('first_year')),
                    'last_year': _int_or_none(row.get('last_year')),
                }

                obj = LicenseType.objects.filter(
                    state=state, name=row['name'].strip(), category=row['category'].strip(),
                ).first()
                if obj is None:
                    LicenseType.objects.create(
                        state=state, name=row['name'].strip(), category=row['category'].strip(),
                        **values,
                    )
                    created += 1
                    continue

                changed = {
                    field: (getattr(obj, field), value)
                    for field, value in values.items()
                    if getattr(obj, field) != value
                }
                if not changed:
                    continue
                if overwrite:
                    for field, value in values.items():
                        setattr(obj, field, value)
                    obj.save()
                    updated += 1
                else:
                    drift.append(f'  {obj} [{obj.category}]: ' + ', '.join(
                        f'{field} db={db_value!r} csv={csv_value!r}'
                        for field, (db_value, csv_value) in changed.items()
                    ))

        renamed = self._apply_renames(states, federal_state)
        deleted = self._apply_deletions(states, federal_state)
        swept = self._sweep_retired_categories()

        # Federal is a pseudo-state with no base license, so its year floor is
        # simply the earliest federal item on record — derive it from the seeded
        # rows rather than hardcoding (real states' floors come from states.csv).
        self._sync_federal_floor(federal_state)

        if drift:
            self.stdout.write(self.style.WARNING(
                f'Drift (DB differs from CSV on {len(drift)} row(s); re-run with --overwrite to apply):'
            ))
            for line in drift:
                self.stdout.write(self.style.WARNING(line))

        self.stdout.write(
            self.style.SUCCESS(
                f'License type seed complete. created={created} updated={updated} '
                f'renamed={renamed} deleted={deleted} retired_swept={swept} '
                f'drift={len(drift)} total={LicenseType.objects.count()}'
            )
        )

    def _sync_federal_floor(self, federal_state):
        """Set Federal's min_license_year to the earliest first_year across its
        seeded license types (the 1934 duck stamp today), data-driven."""
        from django.db.models import Min

        earliest = (
            LicenseType.objects.filter(state=federal_state, first_year__isnull=False)
            .aggregate(m=Min('first_year'))['m']
        )
        if earliest and federal_state.min_license_year != earliest:
            federal_state.min_license_year = earliest
            federal_state.save(update_fields=['min_license_year'])
            self.stdout.write(self.style.SUCCESS(
                f'Federal year floor set from data: {earliest}'
            ))

    def _state_for(self, code, states, federal_state):
        return federal_state if code == 'FD' else states.get(code)

    def _apply_renames(self, states, federal_state):
        """Repoint M2M references from renamed/merged rows to their canonical
        row (created from the CSV above), then delete the old row."""
        renamed = 0
        for (state_code, category, old_name), new_name in RENAMES.items():
            state = self._state_for(state_code, states, federal_state)
            old = LicenseType.objects.filter(state=state, category=category, name=old_name).first()
            if old is None:
                continue
            new = LicenseType.objects.filter(state=state, category=category, name=new_name).first()
            if new is None:
                self.stdout.write(self.style.WARNING(
                    f'Rename target missing for {old}: {new_name!r} not in CSV — skipped.'
                ))
                continue
            for listing in old.listings.all():
                listing.license_types.add(new)
            for item in old.collection_items.all():
                item.license_types.add(new)
            old.delete()
            renamed += 1
        return renamed

    def _apply_deletions(self, states, federal_state):
        deleted = 0
        for state_code, category, name in DELETIONS:
            state = self._state_for(state_code, states, federal_state)
            obj = LicenseType.objects.filter(state=state, category=category, name=name).first()
            if obj is None:
                continue
            if obj.listings.exists() or obj.collection_items.exists():
                self.stdout.write(self.style.WARNING(
                    f'Deletion skipped (still referenced): {obj}'
                ))
                continue
            obj.delete()
            deleted += 1
        return deleted

    def _sweep_retired_categories(self):
        swept = 0
        for obj in LicenseType.objects.filter(category__in=RETIRED_CATEGORIES):
            if obj.listings.exists() or obj.collection_items.exists():
                self.stdout.write(self.style.WARNING(
                    f'Retired-category row still referenced, kept: {obj} [{obj.category}]'
                ))
                continue
            obj.delete()
            swept += 1
        return swept
