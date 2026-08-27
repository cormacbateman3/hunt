"""The ledger's voice — lines and facts for the read panel.

Add Item Ideas 4d/4e. The typed lines the panel plays live in
``prefill/config/ledger_lines.json`` and the year sentences in
``prefill/config/era_facts.json`` — reviewed copy, never the model's
memory. This module serves the bank to the page once, and computes the
few cheap facts a lookup line is allowed to cite (a line that cites a
number only fires if the number is already computed — never a query on
the critical path).
"""

import json
from functools import lru_cache
from pathlib import Path

from prefill.core import CONFIG_DIR


@lru_cache(maxsize=1)
def line_bank() -> dict:
    return json.loads((CONFIG_DIR / 'ledger_lines.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1)
def _era_facts() -> dict:
    return json.loads((CONFIG_DIR / 'era_facts.json').read_text(encoding='utf-8'))


def line_bank_json() -> str:
    """The bank, serialised once for a template's KBPrefill.init."""
    bank = {key: value for key, value in line_bank().items()
            if not key.startswith('_') and key != 'winks_held'}
    return json.dumps(bank)


def era_fact(year) -> str:
    """The reviewed sentence for a year — exact year wins over decade."""
    if not year:
        return ''
    facts = _era_facts()
    exact = facts.get(str(year))
    if exact:
        return exact
    try:
        decade = f'{(int(year) // 10) * 10}s'
    except (TypeError, ValueError):
        return ''
    return facts.get(decade, '')


def line_facts(job) -> dict:
    """The computed facts the lookup lines may cite, or {} when thin.

    Runs only on a complete job, off the resolved payload: the unit
    vocabulary line needs the state's own word for its ground; the counts
    lines need this collector's holdings for the county and the site-wide
    count. Two indexed queries, both optional.
    """
    payload = job.resolved_payload or {}
    fields = payload.get('fields') or {}

    facts = {}
    year = (fields.get('license_year') or {}).get('value')
    fact = era_fact(year)
    if fact:
        facts['era_fact'] = fact

    unit_id = (fields.get('geographic_unit') or {}).get('value')
    if unit_id:
        from apps.collections.models import CollectionItem
        from apps.core.models import GeographicUnit

        unit = (GeographicUnit.objects.select_related('state')
                .filter(pk=unit_id).first())
        if unit and unit.state and not unit.is_statewide:
            from apps.collections.tracker import plural_unit

            label = unit.state.issuance_unit_label or 'County'
            facts['county_name'] = unit.name
            facts['state_name'] = unit.state.name
            facts['unit_label'] = label
            facts['unit_plural'] = plural_unit(label).lower()
            facts['my_county_count'] = CollectionItem.objects.filter(
                owner=job.user, county=unit).count()
            facts['site_count'] = CollectionItem.objects.filter(
                county=unit).count()
    return facts
