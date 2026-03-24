"""
Standalone data-cleaning script for KeystoneBid reference data.

Usage:
    python utilities/clean_reference_data.py

Input:  utilities/reference_data_v0.csv
Output: utilities/cleaned/states.csv
        utilities/cleaned/license_types.csv
        utilities/cleaned/geographic_units.csv

This script is idempotent — re-running it regenerates the output files from the same source CSV.
It uses only Python's standard library (no pandas or external dependencies).
"""

import csv
import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
INPUT_CSV = SCRIPT_DIR / 'reference_data_v0.csv'
OUTPUT_DIR = SCRIPT_DIR / 'cleaned'

STATES_OUT = OUTPUT_DIR / 'states.csv'
LICENSE_TYPES_OUT = OUTPUT_DIR / 'license_types.csv'
GEO_UNITS_OUT = OUTPUT_DIR / 'geographic_units.csv'

# ---------------------------------------------------------------------------
# License-type taxonomy classification
# Each token from license_types_normalized is matched against these sets.
# Order matters: check more specific sets first.
# ---------------------------------------------------------------------------
RESIDENCY_TOKENS = {
    'Resident', 'Nonresident', 'Non-resident', 'Alien',
}
DURATION_TOKENS = {
    'Annual', 'Multi-year', 'Lifetime', 'Short-term',
    # Short-term sub-types — all map to Short-term category but we keep the original name
    '1-Day', '3-Day', '5-Day', '7-Day', '10-Day',
}
ELIGIBILITY_TOKENS = {
    'Youth', 'Junior', 'Senior', 'Disabled', 'Veteran',
    'Military', 'Apprentice', 'Mentored',
}
ACTIVITY_SCOPE_TOKENS = {
    'Hunting', 'Big Game Hunting', 'Combo Hunt/Fish', 'Sportsman',
    'Trapping', 'Furtaker', 'Fur Harvester', 'Trapping/Fur Harvester',
    'Trapping/Furtaker',
}

# Anything not matched by the four sets above defaults to 'addon'.
CATEGORY_ORDER = [
    ('residency', RESIDENCY_TOKENS),
    ('duration', DURATION_TOKENS),
    ('eligibility', ELIGIBILITY_TOKENS),
    ('activity_scope', ACTIVITY_SCOPE_TOKENS),
]


def classify_token(token):
    """Return the category string for a license-type token."""
    t = token.strip()
    for category, token_set in CATEGORY_ORDER:
        if t in token_set:
            return category
    return 'addon'


def slugify(text):
    """Very simple slugifier — lowercase, replace spaces/slashes with hyphens, strip specials."""
    s = text.lower().strip()
    s = re.sub(r'[\s/]+', '-', s)
    s = re.sub(r'[^a-z0-9\-]', '', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s


def parse_units(raw_units_str, unit_type):
    """
    Parse the pipe-delimited issuance_units string.

    Returns (units_list, geo_data_complete):
      units_list       — list of cleaned unit name strings
      geo_data_complete — True if the list was not truncated
    """
    if not raw_units_str:
        return [], False

    # Detect truncation marker like "[...92 total - see source URL]"
    truncated = bool(re.search(r'\[\.\.\.', raw_units_str))

    # Strip everything from the truncation marker onward
    clean_str = re.split(r'\s*\[\.\.\.', raw_units_str)[0]

    units = [u.strip() for u in clean_str.split('|') if u.strip()]
    return units, not truncated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    states_rows = []
    license_type_rows = []       # (state_abbrev, name, category, slug)
    geo_unit_rows = []           # (state_abbrev, name, unit_type, fips_code, geo_data_complete, sort_order)

    # Track (state_abbrev, name, category) to deduplicate license types per state
    seen_lt = set()

    with open(INPUT_CSV, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            state_name = row['state_name'].strip()
            state_abbrev = row['state_abbrev'].strip()
            state_fips = row['state_fips'].strip()
            issuance_unit_type = row['issuance_unit_type'].strip()
            issuance_unit_label = row['issuance_unit_label'].strip()
            raw_units = row['issuance_units'].strip()
            license_types_normalized = row['license_types_normalized'].strip()
            min_license_year = row['min_license_year'].strip()
            min_year_confidence = row['min_license_year_confidence'].strip()
            missing_geos = row.get('missing_geos', '').strip().lower()

            is_primary = 'True' if state_abbrev == 'PA' else 'False'

            # ----------------------------------------------------------------
            # State record
            # ----------------------------------------------------------------
            states_rows.append({
                'state_name': state_name,
                'state_abbrev': state_abbrev,
                'state_fips': state_fips,
                'min_license_year': min_license_year,
                'min_year_confidence': min_year_confidence,
                'issuance_unit_type': issuance_unit_type,
                'issuance_unit_label': issuance_unit_label,
                'is_primary_default': is_primary,
            })

            # ----------------------------------------------------------------
            # License type records
            # ----------------------------------------------------------------
            if license_types_normalized:
                tokens = [t.strip() for t in license_types_normalized.split('|') if t.strip()]
                for token in tokens:
                    category = classify_token(token)
                    key = (state_abbrev, token, category)
                    if key not in seen_lt:
                        seen_lt.add(key)
                        license_type_rows.append({
                            'state_abbrev': state_abbrev,
                            'name': token,
                            'category': category,
                            'slug': slugify(f'{state_abbrev}-{token}'),
                        })

            # ----------------------------------------------------------------
            # Geographic unit records
            # ----------------------------------------------------------------
            units, geo_complete = parse_units(raw_units, issuance_unit_type)

            # If missing_geos flag is set, mark incomplete regardless
            if missing_geos == 'y':
                geo_complete = False

            for idx, unit_name in enumerate(units):
                geo_unit_rows.append({
                    'state_abbrev': state_abbrev,
                    'name': unit_name,
                    'unit_type': issuance_unit_type,
                    'fips_code': '',       # populated for PA counties via seed command
                    'geo_data_complete': str(geo_complete),
                    'sort_order': str(idx),
                })

    # ----------------------------------------------------------------
    # Add universal 'Other' entries — one per category, state-agnostic
    # ----------------------------------------------------------------
    CATEGORIES = ['residency', 'duration', 'eligibility', 'activity_scope', 'addon']
    for cat in CATEGORIES:
        license_type_rows.append({
            'state_abbrev': '',       # empty = universal/cross-state
            'name': 'Other',
            'category': cat,
            'slug': slugify(f'other-{cat}'),
        })

    # ----------------------------------------------------------------
    # Write output CSVs
    # ----------------------------------------------------------------
    _write_csv(
        STATES_OUT,
        ['state_name', 'state_abbrev', 'state_fips', 'min_license_year',
         'min_year_confidence', 'issuance_unit_type', 'issuance_unit_label', 'is_primary_default'],
        states_rows,
    )
    print(f'[states]          {len(states_rows)} rows ->{STATES_OUT}')

    _write_csv(
        LICENSE_TYPES_OUT,
        ['state_abbrev', 'name', 'category', 'slug'],
        license_type_rows,
    )
    print(f'[license_types]   {len(license_type_rows)} rows ->{LICENSE_TYPES_OUT}')

    _write_csv(
        GEO_UNITS_OUT,
        ['state_abbrev', 'name', 'unit_type', 'fips_code', 'geo_data_complete', 'sort_order'],
        geo_unit_rows,
    )
    print(f'[geographic_units] {len(geo_unit_rows)} rows ->{GEO_UNITS_OUT}')

    print('\nDone. Re-run at any time to regenerate from the source CSV.')


def _write_csv(path, fieldnames, rows):
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == '__main__':
    main()
