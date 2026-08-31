"""Registry of all 50 states + DC and how (if at all) we can pull their
hunting season data.

Reality check (researched, not assumed): there is no federal or
cross-state API for hunting season dates. Each state wildlife agency
publishes its own seasons, in its own format (HTML page, PDF booklet,
prose news release, or some mix), on its own site. The one real point
of standardization we found: 49 of the 50 states have their *official*
digital hunting digest hosted on eregulations.com, a shared vendor
platform, under a predictable URL (``eregulations.com/<slug>/hunting/``)
with real HTML tables for season dates. That's the adapter we implement.

Everything else is marked "unimplemented" with the real official source
URL attached, per the project rule of never silently dropping a gap —
adding a state means writing one more adapter, not un-skipping a
silently-skipped one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

ADAPTER_EREGULATIONS = "eregulations"
ADAPTER_UNIMPLEMENTED = "unimplemented"
ADAPTER_NOT_APPLICABLE = "not_applicable"


@dataclass
class StateEntry:
    code: str
    name: str
    adapter_type: str
    # eregulations.com URL slug, e.g. "newhampshire" — only set when
    # adapter_type == ADAPTER_EREGULATIONS
    slug: Optional[str] = None
    # Where a human (or a future adapter) should look instead.
    official_source: Optional[str] = None
    note: Optional[str] = None
    extra: dict = field(default_factory=dict)


# USPS code -> full name for all 50 states + DC.
_STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

# States confirmed present in eregulations.com's state selector (checked
# live, see RESEARCH_NOTES.md in this folder). Slug rule observed from live pages
# (New Hampshire -> "newhampshire", New York -> "newyork"): lowercase the
# name and strip spaces. Put any state that breaks this rule here as an
# explicit override instead of special-casing it in code.
_EREGULATIONS_STATES = {
    "AL", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
    "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR",
    "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI",
    "WY",
}

# Overrides for states whose eregulations.com slug doesn't match the
# plain "lowercase, strip spaces" rule. Empty until proven otherwise —
# the CLI's `verify-slugs` command (see cli.py) flags any mismatch found
# at run time so this can be filled in without guessing.
_SLUG_OVERRIDES: dict[str, str] = {}

# States/territories known NOT to be on eregulations.com, with where
# their real data actually lives. Not implemented yet — flagged, not
# skipped.
_UNIMPLEMENTED_NOTES = {
    "AK": "Alaska Dept. of Fish & Game publishes seasons on its own site "
          "(adfg.alaska.gov/index.cfm?adfg=hunting.main), not eregulations.com. "
          "Needs a dedicated adapter — different HTML structure, region-based "
          "(not WMU-based) seasons.",
}

_OFFICIAL_SOURCES = {
    "AK": "https://www.adfg.alaska.gov/index.cfm?adfg=hunting.main",
    "DC": "https://dc.gov",  # no hunting seasons; kept for completeness
}


def _slug_for(code: str, name: str) -> str:
    return _SLUG_OVERRIDES.get(code, name.lower().replace(" ", ""))


def build_registry() -> dict[str, StateEntry]:
    registry: dict[str, StateEntry] = {}
    for code, name in _STATE_NAMES.items():
        if code == "DC":
            registry[code] = StateEntry(
                code=code, name=name, adapter_type=ADAPTER_NOT_APPLICABLE,
                official_source=_OFFICIAL_SOURCES["DC"],
                note="No general hunting seasons administered for the District.",
            )
        elif code in _EREGULATIONS_STATES:
            slug = _slug_for(code, name)
            registry[code] = StateEntry(
                code=code, name=name, adapter_type=ADAPTER_EREGULATIONS,
                slug=slug,
                official_source=f"https://www.eregulations.com/{slug}/hunting/",
            )
        else:
            registry[code] = StateEntry(
                code=code, name=name, adapter_type=ADAPTER_UNIMPLEMENTED,
                official_source=_OFFICIAL_SOURCES.get(code),
                note=_UNIMPLEMENTED_NOTES.get(code, "No adapter written yet."),
            )
    return registry


REGISTRY = build_registry()
