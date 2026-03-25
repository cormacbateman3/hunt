"""
Rebuild cleaned reference-data outputs from the structured source CSV files in utilities/ref_data/.

Usage:
    python utilities/clean_reference_data.py
"""

import csv
import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
REF_DATA_DIR = SCRIPT_DIR / 'ref_data'
OUTPUT_DIR = SCRIPT_DIR / 'cleaned'

STATES_IN = REF_DATA_DIR / 'states.csv'
GEOGRAPHIC_UNITS_IN = REF_DATA_DIR / 'geographic_units.csv'
LICENSE_CLASSES_IN = REF_DATA_DIR / 'license_classes.csv'
ADDONS_PERMITS_IN = REF_DATA_DIR / 'addons_permits.csv'

STATES_OUT = OUTPUT_DIR / 'states.csv'
GEO_UNITS_OUT = OUTPUT_DIR / 'geographic_units.csv'
LICENSE_TYPES_OUT = OUTPUT_DIR / 'license_types.csv'

REQUIRED_STATE_COLUMNS = {
    'state_name',
    'state_abbrev',
    'state_fips',
    'min_license_year',
    'min_year_confidence',
    'min_year_source',
    'issuance_scope',
    'issuance_unit_type',
    'issuance_unit_label',
    'agency_name',
    'agency_name_historical',
    'licensing_start_year',
    'licensing_start_source',
    'notes',
}
REQUIRED_GEO_COLUMNS = {
    'state_abbrev',
    'unit_name',
    'unit_type',
    'unit_number',
    'fips_code',
    'is_statewide',
    'geo_data_complete',
    'sort_order',
    'notes',
}
REQUIRED_LICENSE_CLASS_COLUMNS = {
    'state_abbrev',
    'license_class_name',
    'residency',
    'holder_eligibility',
    'activity_scope',
    'duration',
}
REQUIRED_ADDON_COLUMNS = {
    'state_abbrev',
    'addon_name',
    'addon_type',
    'target_species',
    'hunting_method',
    'is_federal',
    'is_mandatory',
}

CONTROLLED_MATERIALS = [
    'Paper/Cardstock',
    'Metal Button',
    'Metal Tag',
    'Celluloid',
    'Fabric/Canvas',
    'Plastic',
]
CONTROLLED_SHAPES = [
    'Rectangle',
    'Square',
    'Button/Disc',
    'Tag (with hole)',
    'Strip',
    'Irregular/Custom',
]
CONTROLLED_COLORS = [
    'Orange',
    'Yellow',
    'Red',
    'Crimson/Dark Red',
    'Forest Green',
    'Lime/Bright Green',
    'Blue',
    'Navy',
    'White',
    'Cream/Ivory',
    'Gray',
    'Silver',
    'Brown/Tan',
    'Gold',
    'Pink',
    'Purple',
    'Black',
    'Multi-color',
]


def slugify(text):
    slug = text.lower().strip()
    slug = re.sub(r'[\s/]+', '-', slug)
    slug = re.sub(r'[^a-z0-9\-]', '', slug)
    return re.sub(r'-+', '-', slug).strip('-')


def read_csv(path, required_columns):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(required_columns - columns)
        if missing:
            raise ValueError(f'{path} is missing columns: {", ".join(missing)}')
        return list(reader)


def validate_geo_rows(rows):
    statewide_tracker = {}
    for row in rows:
        if row['unit_type'].strip().lower() == 'county' and row['fips_code'].strip():
            fips = row['fips_code'].strip()
            if not re.fullmatch(r'\d{5}', fips):
                raise ValueError(f'Invalid county FIPS code: {fips} ({row["state_abbrev"]} {row["unit_name"]})')
        if row['is_statewide'].strip().lower() == 'true':
            statewide_tracker[row['state_abbrev'].strip()] = True
    missing_statewide = [state for state in sorted({row['state_abbrev'].strip() for row in rows}) if state not in statewide_tracker]
    if missing_statewide:
        raise ValueError(f'Missing Statewide geographic-unit rows for: {", ".join(missing_statewide)}')


def build_states(rows):
    cleaned = []
    for row in rows:
        cleaned.append(
            {
                'state_name': row['state_name'].strip(),
                'state_abbrev': row['state_abbrev'].strip(),
                'state_fips': row['state_fips'].strip(),
                'min_license_year': row['min_license_year'].strip(),
                'min_year_confidence': row['min_year_confidence'].strip(),
                'min_year_source': row['min_year_source'].strip(),
                'issuance_scope': row['issuance_scope'].strip(),
                'issuance_unit_type': row['issuance_unit_type'].strip(),
                'issuance_unit_label': row['issuance_unit_label'].strip(),
                'agency_name': row['agency_name'].strip(),
                'agency_name_historical': row['agency_name_historical'].strip(),
                'licensing_start_year': row['licensing_start_year'].strip(),
                'licensing_start_source': row['licensing_start_source'].strip(),
                'notes': row['notes'].strip(),
                'is_primary_default': str(row['state_abbrev'].strip() == 'PA'),
                'slug': slugify(row['state_name']),
            }
        )
    return cleaned


def build_geographic_units(rows):
    cleaned = []
    for row in rows:
        cleaned.append(
            {
                'state_abbrev': row['state_abbrev'].strip(),
                'name': row['unit_name'].strip(),
                'unit_type': row['unit_type'].strip(),
                'unit_number': row['unit_number'].strip(),
                'fips_code': row['fips_code'].strip(),
                'is_statewide': row['is_statewide'].strip(),
                'geo_data_complete': row['geo_data_complete'].strip(),
                'sort_order': row['sort_order'].strip(),
                'notes': row['notes'].strip(),
                'slug': slugify(f'{row["state_abbrev"].strip()}-{row["unit_name"].strip()}'),
            }
        )
    return cleaned


def add_license_type(rows, seen, state_abbrev, name, category):
    clean_name = name.strip()
    if not clean_name or clean_name.lower() in {'', 'n/a', 'na', 'unknown'}:
        return
    if category == 'residency' and clean_name.lower() == 'any':
        return
    key = (state_abbrev, clean_name, category)
    if key in seen:
        return
    seen.add(key)
    rows.append(
        {
            'state_abbrev': state_abbrev,
            'name': clean_name,
            'category': category,
            'slug': slugify(f'{state_abbrev or "universal"}-{category}-{clean_name}'),
            'is_system_value': 'True',
        }
    )


def build_license_types(license_class_rows, addon_rows):
    cleaned = []
    seen = set()

    for row in license_class_rows:
        state_abbrev = row['state_abbrev'].strip()
        add_license_type(cleaned, seen, state_abbrev, row['residency'], 'residency')
        add_license_type(cleaned, seen, state_abbrev, row['holder_eligibility'], 'holder_eligibility')
        add_license_type(cleaned, seen, state_abbrev, row['activity_scope'], 'activity_scope')
        add_license_type(cleaned, seen, state_abbrev, row['duration'], 'duration')

    for row in addon_rows:
        state_abbrev = 'FD' if row['state_abbrev'].strip().upper() == 'FEDERAL' else row['state_abbrev'].strip()
        add_license_type(cleaned, seen, state_abbrev, row['addon_name'], 'addon_type')

    for material in CONTROLLED_MATERIALS:
        add_license_type(cleaned, seen, '', material, 'material')
    for shape in CONTROLLED_SHAPES:
        add_license_type(cleaned, seen, '', shape, 'shape')
    for color in CONTROLLED_COLORS:
        add_license_type(cleaned, seen, '', color, 'colors')

    for category in (
        'residency',
        'holder_eligibility',
        'activity_scope',
        'duration',
        'addon_type',
        'material',
        'shape',
        'colors',
    ):
        add_license_type(cleaned, seen, '', 'Other', category)

    return sorted(cleaned, key=lambda row: (row['category'], row['state_abbrev'], row['name']))


def write_csv(path, fieldnames, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    state_rows = read_csv(STATES_IN, REQUIRED_STATE_COLUMNS)
    geographic_rows = read_csv(GEOGRAPHIC_UNITS_IN, REQUIRED_GEO_COLUMNS)
    license_class_rows = read_csv(LICENSE_CLASSES_IN, REQUIRED_LICENSE_CLASS_COLUMNS)
    addon_rows = read_csv(ADDONS_PERMITS_IN, REQUIRED_ADDON_COLUMNS)

    validate_geo_rows(geographic_rows)

    cleaned_states = build_states(state_rows)
    cleaned_geographic_units = build_geographic_units(geographic_rows)
    cleaned_license_types = build_license_types(license_class_rows, addon_rows)

    write_csv(
        STATES_OUT,
        [
            'state_name',
            'state_abbrev',
            'state_fips',
            'min_license_year',
            'min_year_confidence',
            'min_year_source',
            'issuance_scope',
            'issuance_unit_type',
            'issuance_unit_label',
            'agency_name',
            'agency_name_historical',
            'licensing_start_year',
            'licensing_start_source',
            'notes',
            'is_primary_default',
            'slug',
        ],
        cleaned_states,
    )
    write_csv(
        GEO_UNITS_OUT,
        [
            'state_abbrev',
            'name',
            'unit_type',
            'unit_number',
            'fips_code',
            'is_statewide',
            'geo_data_complete',
            'sort_order',
            'notes',
            'slug',
        ],
        cleaned_geographic_units,
    )
    write_csv(
        LICENSE_TYPES_OUT,
        ['state_abbrev', 'name', 'category', 'slug', 'is_system_value'],
        cleaned_license_types,
    )

    print(f'[states]           {len(cleaned_states)} rows -> {STATES_OUT}')
    print(f'[geographic_units] {len(cleaned_geographic_units)} rows -> {GEO_UNITS_OUT}')
    print(f'[license_types]    {len(cleaned_license_types)} rows -> {LICENSE_TYPES_OUT}')


if __name__ == '__main__':
    main()
