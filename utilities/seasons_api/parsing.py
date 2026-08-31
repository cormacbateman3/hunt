"""Shared parsing helpers: free-text date ranges and HTML tables.

Kept separate from any single adapter because the same messy
"Sept. 15-Dec. 8" style text shows up across states that otherwise have
nothing else in common.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}

_MONTH_RE = r"[A-Za-z]{3,9}\.?"
_DASH_RE = re.compile(r"[‐-―−]")  # unicode hyphen/dash variants -> '-'

_RANGE_RE = re.compile(
    rf"(?P<m1>{_MONTH_RE})\.?\s*(?P<d1>\d{{1,2}})\s*-\s*"
    rf"(?:(?P<m2>{_MONTH_RE})\.?\s*)?(?P<d2>\d{{1,2}})",
    re.IGNORECASE,
)

_SINGLE_DATE_RE = re.compile(
    rf"(?P<m1>{_MONTH_RE})\.?\s*(?P<d1>\d{{1,2}})(?!\s*-)",
    re.IGNORECASE,
)


def _month_num(text: str) -> Optional[int]:
    return _MONTHS.get(text.strip(".").lower())


def parse_date_range(text: str, season_start_year: int) -> tuple[Optional[date], Optional[date], bool]:
    """Parse a free-text date range like "Sept. 15-Dec. 8" or "Oct. 25-26".

    `season_start_year` is the calendar year the season *begins* in
    (e.g. 2026 for the "2026-27" season). If the end month comes before
    the start month, the end date is rolled into the following year —
    this is how nearly every state's late-winter seasons ("Dec 26-Jan
    24") are published.

    Returns (start_date, end_date, parsed). On failure, both dates are
    None and parsed is False — callers must keep the raw `date_text`
    rather than dropping the record.
    """
    if not text:
        return None, None, False

    cleaned = _DASH_RE.sub("-", text).strip()

    m = _RANGE_RE.search(cleaned)
    if not m:
        # Single date (e.g. "Opens Sept. 1") — treat as a one-day range.
        m1 = _SINGLE_DATE_RE.search(cleaned)
        if not m1:
            return None, None, False
        month = _month_num(m1.group("m1"))
        if month is None:
            return None, None, False
        try:
            d = date(season_start_year, month, int(m1.group("d1")))
        except ValueError:
            return None, None, False
        return d, d, True

    m1_name = m.group("m1")
    m2_name = m.group("m2") or m1_name
    month1 = _month_num(m1_name)
    month2 = _month_num(m2_name)
    if month1 is None or month2 is None:
        return None, None, False

    try:
        start = date(season_start_year, month1, int(m.group("d1")))
    except ValueError:
        return None, None, False

    end_year = season_start_year if month2 >= month1 else season_start_year + 1
    try:
        end = date(end_year, month2, int(m.group("d2")))
    except ValueError:
        return None, None, False

    return start, end, True


_HEADER_HINTS = ("season", "date", "unit", "zone", "wmu", "weapon", "method", "area", "county", "district")


def _expand_grid(table) -> list[list[str]]:
    """Expand a <table> into a rectangular grid of cell text, resolving
    rowspan/colspan the way a browser would render it.

    Real-world regulation tables (eregulations.com included) lean
    heavily on rowspan to avoid repeating a species/method label down a
    column — naive row-by-row <td> reading misaligns every column after
    the first spanned cell, so this has to be handled generically
    rather than per-site.
    """
    grid: list[list[str]] = []
    # pending[col] = [remaining_rows, text] for an active rowspan
    pending: dict[int, list] = {}

    for tr in table.find_all("tr"):
        row: list[str] = []
        col = 0

        def _place_pending(row, col):
            while col in pending:
                row.append(pending[col][1])
                pending[col][0] -= 1
                if pending[col][0] <= 0:
                    del pending[col]
                col += 1
            return col

        col = _place_pending(row, col)

        for cell in tr.find_all(["td", "th"], recursive=False):
            col = _place_pending(row, col)
            text = cell.get_text(" ", strip=True)
            colspan = int(cell.get("colspan", 1) or 1)
            rowspan = int(cell.get("rowspan", 1) or 1)
            for i in range(colspan):
                row.append(text)
                if rowspan > 1:
                    pending[col + i] = [rowspan - 1, text]
            col += colspan

        col = _place_pending(row, col)
        if row:
            grid.append(row)

    width = max((len(r) for r in grid), default=0)
    return [r + [""] * (width - len(r)) for r in grid]


def _is_banner_row(row: list[str]) -> bool:
    # After colspan expansion a title cell's text is duplicated across
    # every column it spans, so "one non-empty cell" no longer holds —
    # check for one *distinct* non-empty value instead.
    non_empty = {c for c in row if c}
    return len(non_empty) == 1 and len(row) > 1


def _find_header_row(grid: list[list[str]]) -> int:
    for i, row in enumerate(grid):
        if _is_banner_row(row):
            continue
        hint_hits = sum(1 for c in row if any(h in c.lower() for h in _HEADER_HINTS))
        if hint_hits >= 2:
            return i
    return -1


def extract_tables(html: str) -> list[list[dict[str, str]]]:
    """Extract every HTML <table> as a list of {header: cell} row dicts.

    Uses BeautifulSoup directly (no pandas dependency). Rowspan/colspan
    are expanded into a full grid first (see `_expand_grid`) since
    published season tables rely on spanned cells to group rows under
    one species/method label. A header row is located by keyword hints
    rather than assumed to be row 0, because these tables commonly lead
    with a full-width title banner row instead of column headers.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    tables: list[list[dict[str, str]]] = []

    for table in soup.find_all("table"):
        grid = _expand_grid(table)
        if not grid:
            continue

        header_idx = _find_header_row(grid)
        if header_idx == -1:
            raw_headers = [f"col_{i}" for i in range(len(grid[0]))]
            data_rows = [r for r in grid if not _is_banner_row(r)]
        else:
            raw_headers = [h if h else f"col_{i}" for i, h in enumerate(grid[header_idx])]
            data_rows = grid[header_idx + 1:]

        # Some tables repeat a header label across spanned columns
        # (e.g. "Season" covering both a method name and a sex/age
        # restriction sub-column) — dedupe so later columns don't
        # silently overwrite earlier ones in the row dict.
        seen: dict[str, int] = {}
        headers = []
        for h in raw_headers:
            seen[h] = seen.get(h, 0) + 1
            headers.append(h if seen[h] == 1 else f"{h}_{seen[h]}")

        parsed_rows = []
        for cells in data_rows:
            if not any(cells) or _is_banner_row(cells):
                continue
            row = {headers[i]: cells[i] for i in range(len(headers))}
            parsed_rows.append(row)

        if parsed_rows:
            tables.append(parsed_rows)

    return tables
