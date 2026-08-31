"""Standardized shape for a single price observation, plus the handful
of analyses (price history, rarity scoring) that only need this shape
to work — regardless of whether the row came from KeystoneBid's own
completed orders, eBay's Browse API (active-listing asking prices), or
a manually curated research CSV.

This is deliberately source-agnostic. See README.md for why: there is
no single good automated source of historical sold-price data for this
category (see RESEARCH_NOTES.md), so the realistic path is combining
a few thin, honestly-labeled sources — and that only works if they all
land in one shape first.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Optional

import pandas as pd

# Every source this schema might ever be fed from. Keeping this closed
# and explicit (rather than a free-text string) means a chart built on
# this data can always show what fraction of it is real sales vs.
# asking prices vs. hand-entered research — see PRICE_OBSERVATION_COLUMNS.
SOURCE_TYPE_INTERNAL_ORDER = "internal_order"           # KeystoneBid's own completed sale
SOURCE_TYPE_EBAY_ACTIVE_LISTING = "ebay_active_listing"  # asking price, not a sale
SOURCE_TYPE_MANUAL_RESEARCH = "manual_research"          # hand-entered from a book/appraisal/etc.

SOURCE_TYPES = (
    SOURCE_TYPE_INTERNAL_ORDER,
    SOURCE_TYPE_EBAY_ACTIVE_LISTING,
    SOURCE_TYPE_MANUAL_RESEARCH,
)

PRICE_OBSERVATION_COLUMNS = [
    "source_type", "state", "license_type", "year_or_era", "condition",
    "price", "currency", "is_actual_sale", "sale_or_observed_date", "url", "notes",
]


@dataclass
class PriceObservation:
    source_type: str          # one of SOURCE_TYPES
    state: str                  # e.g. "Connecticut" — matches KeystoneBid's State model naming
    license_type: str            # e.g. "Resident Hunting License"
    year_or_era: str             # e.g. "1938" or "1920s" — kept as text since old items are often dated by era, not a hard year
    price: float
    is_actual_sale: bool         # False for eBay active-listing asking prices
    currency: str = "USD"
    condition: Optional[str] = None
    sale_or_observed_date: Optional[str] = None  # ISO date the price was recorded/observed
    url: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def observations_to_dataframe(observations: list[PriceObservation]) -> pd.DataFrame:
    if not observations:
        return pd.DataFrame(columns=PRICE_OBSERVATION_COLUMNS)
    df = pd.DataFrame([o.to_dict() for o in observations])
    return df[PRICE_OBSERVATION_COLUMNS]


def price_history_by_group(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """Median/min/max/count price per group — the "price history" view.

    Defaults to grouping by (state, license_type, year_or_era), which
    is the natural unit for this domain: two 1938 Connecticut hunting
    licenses are comparable to each other in a way a 1938 license and a
    1962 license from the same state usually aren't.
    """
    if df.empty:
        return df
    group_cols = group_cols or ["state", "license_type", "year_or_era"]
    return (
        df.groupby(group_cols)["price"]
        .agg(observation_count="count", median_price="median", min_price="min", max_price="max")
        .reset_index()
        .sort_values("median_price", ascending=False)
    )


def rarity_score(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """A scarcity proxy in [0, 100] per (state, license_type, year_or_era)
    group: fewer observations relative to the rest of the dataset -> a
    higher score.

    This is intentionally simple (inverse-rank of observation count) —
    it is a starting point for "how rare does this look given what
    we've recorded," not a valuation model. It gets more meaningful as
    more real observations (especially `is_actual_sale=True` ones) are
    added; with a handful of rows it will mostly reflect what's been
    looked at so far, not true market scarcity. Say so wherever this is
    surfaced in the app rather than presenting it as authoritative.
    """
    if df.empty:
        return df
    group_cols = group_cols or ["state", "license_type", "year_or_era"]
    counts = df.groupby(group_cols).size().reset_index(name="observation_count")
    max_count = counts["observation_count"].max()
    min_count = counts["observation_count"].min()
    spread = max_count - min_count
    if spread == 0:
        counts["rarity_score"] = 50.0
    else:
        counts["rarity_score"] = 100.0 * (max_count - counts["observation_count"]) / spread
    return counts.sort_values("rarity_score", ascending=False)
