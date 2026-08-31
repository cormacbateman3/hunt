"""Standardized data model for a single hunting season entry.

States do not agree on species names, zone/unit systems, weapon
classes, or even whether a "season" is a date range, a permit-draw
window, or a quota. `SeasonRecord` is the common denominator: every
field that *can* be standardized is a typed field, and everything
state-specific that can't be forced into a shared shape goes into
`extra` rather than being dropped.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


@dataclass
class SeasonRecord:
    # --- standardized across all sources ---
    state_code: str            # USPS 2-letter code, e.g. "NH"
    state_name: str            # "New Hampshire"
    species: str                # normalized lowercase, e.g. "deer", "turkey"
    season_label: str           # source's own label, e.g. "Archery", "Muzzleloader"
    date_text: str               # raw text as published, e.g. "Sept. 15-Dec. 8"
    source_url: str
    retrieved_at: str           # ISO 8601 timestamp of the scrape

    # --- standardized, but may be None if parsing failed ---
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    date_parsed: bool = False

    # --- present on many but not all sources ---
    zone: Optional[str] = None            # WMU / zone / unit / county, as published
    method: Optional[str] = None          # weapon/method if distinct from season_label

    # --- catch-all for anything state-specific we didn't force into the
    # fields above (e.g. permit quotas, "antlerless only", draw deadlines) ---
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["start_date"] = self.start_date.isoformat() if self.start_date else None
        d["end_date"] = self.end_date.isoformat() if self.end_date else None
        return d


@dataclass
class StateResult:
    """Outcome of running an adapter against one state.

    Kept distinct from SeasonRecord so a state that yields zero records
    because of a real error is never confused with a state that
    genuinely has no seasons open right now.
    """
    state_code: str
    state_name: str
    adapter_type: str
    records: list[SeasonRecord] = field(default_factory=list)
    error: Optional[str] = None
    pages_fetched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "state_code": self.state_code,
            "state_name": self.state_name,
            "adapter_type": self.adapter_type,
            "record_count": len(self.records),
            "records": [r.to_dict() for r in self.records],
            "error": self.error,
            "pages_fetched": self.pages_fetched,
        }
