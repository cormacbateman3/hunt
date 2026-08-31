"""Adapter for the 49 states whose official hunting digest is hosted on
eregulations.com.

Strategy (deliberately generic, not hardcoded per state):
1. Fetch the state's hunting index page.
2. Crawl every internal link under that state's `/hunting/` section
   (bounded — see `max_pages_per_state`). Verified against real
   sites: the URL naming isn't standardized enough to filter on —
   New Hampshire exposes a dedicated "deer-hunting-seasons" page, but
   Vermont puts the same season table directly on "deer-hunting" with
   no "season" in the slug at all. Content, not the URL, decides
   whether a page has season data.
3. Fetch each page, extract every HTML table, and normalize rows using
   header-name synonyms rather than exact header strings — we verified
   on New Hampshire that headers are things like "Season", "Inclusive
   Dates", "Wildlife Management Units", but there is no guarantee every
   state phrases it identically. A page whose tables have no
   recognizable date column simply contributes zero records — that's
   not an error, most pages under /hunting/ aren't season tables at all
   (e.g. licensing, CWD info, hunter education).
4. Species is derived from the page's URL slug (e.g.
   "deer-hunting-seasons" or "deer-hunting" -> "deer"), since it isn't
   reliably a table column.

Anything that doesn't fit the expected shape is kept, not dropped: rows
with no recognizable date column are still emitted as a SeasonRecord
with date_parsed=False and the raw row content preserved in `extra`.
"""
from __future__ import annotations

import time
import urllib.robotparser as robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import requests

from ..models import SeasonRecord, StateResult
from ..parsing import extract_tables, parse_date_range
from ..registry import ADAPTER_EREGULATIONS, StateEntry
from .base import BaseAdapter

USER_AGENT = (
    "KeystoneBid-SeasonsResearch/0.1 "
    "(+https://github.com/ ; utility script, low request rate, contact via repo)"
)

_DATE_HEADER_HINTS = ("date", "season dates", "inclusive")
_ZONE_HEADER_HINTS = ("unit", "zone", "wmu", "area", "county", "district", "region")
_LABEL_HEADER_HINTS = ("season", "weapon", "method", "type")

# Generic categories of /hunting/ links that are never going to carry a
# season table. Deliberately short and conservative — skipping them
# just saves requests, it isn't load-bearing: any state-specific page
# this misses still contributes zero records on its own once fetched,
# since it won't have a recognizable date column either.
_SKIP_URL_SUBSTRINGS = ("/pdf", ".pdf", "license", "fee", "education")

_robots_cache: dict[str, robotparser.RobotFileParser] = {}


def _robots_allows(url: str) -> bool:
    # RobotFileParser.read() uses urllib's default User-Agent, which
    # some sites 403 outright — and robotparser treats a 401/403 on
    # robots.txt itself as "disallow everything", which is the wrong
    # failure mode here. Fetch it ourselves with our real UA instead.
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            resp = requests.get(
                urljoin(origin, "/robots.txt"), headers={"User-Agent": USER_AGENT}, timeout=10
            )
            if resp.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(resp.text.splitlines())
        except Exception:
            # If robots.txt can't be fetched at all, fail open rather
            # than caching a broken parser as a hard "allow forever".
            return True
        _robots_cache[origin] = rp
    return rp.can_fetch(USER_AGENT, url)


def _find_header(headers: list[str], hints: tuple[str, ...]) -> str | None:
    for h in headers:
        low = h.lower()
        if any(hint in low for hint in hints):
            return h
    return None


def _species_from_slug(url: str) -> str:
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    for suffix in ("-hunting-seasons", "-seasons", "-hunting"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    return slug.replace("-", " ").strip() or "unknown"


class EregulationsAdapter(BaseAdapter):
    adapter_type = ADAPTER_EREGULATIONS

    def __init__(
        self, request_delay_seconds: float = 1.0, timeout: int = 20, max_pages_per_state: int = 40
    ):
        self.request_delay_seconds = request_delay_seconds
        self.timeout = timeout
        self.max_pages_per_state = max_pages_per_state
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _get(self, url: str) -> str:
        if not _robots_allows(url):
            raise PermissionError(f"robots.txt disallows fetching {url}")
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        time.sleep(self.request_delay_seconds)
        # eregulations.com doesn't send a charset in Content-Type, so
        # requests falls back to ISO-8859-1 per HTTP spec default and
        # mangles the UTF-8 en-dashes used throughout every date range
        # ("Sept. 15-Dec. 8"). The page is actually UTF-8 — decode it
        # as such rather than trusting the missing header.
        resp.encoding = "utf-8"
        return resp.text

    def _discover_candidate_pages(self, index_url: str, html: str) -> list[str]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        index_parsed = urlparse(index_url)
        section_path = index_parsed.path.rstrip("/")  # e.g. /vermont/hunting

        urls: set[str] = set()
        for a in soup.find_all("a", href=True):
            full = urljoin(index_url, a["href"]).split("#")[0]
            parsed = urlparse(full)
            if parsed.netloc != index_parsed.netloc:
                continue
            if not parsed.path.rstrip("/").startswith(section_path):
                continue  # stay inside this state's hunting section
            if parsed.path.rstrip("/") == section_path:
                continue  # the index page itself
            if any(skip in full.lower() for skip in _SKIP_URL_SUBSTRINGS):
                continue
            urls.add(full)

        ordered = sorted(urls)
        if len(ordered) > self.max_pages_per_state:
            ordered = ordered[: self.max_pages_per_state]
        return ordered

    def fetch(self, entry: StateEntry, season_start_year: int) -> StateResult:
        result = StateResult(
            state_code=entry.code, state_name=entry.name, adapter_type=self.adapter_type
        )
        index_url = entry.official_source
        try:
            index_html = self._get(index_url)
        except Exception as exc:  # noqa: BLE001 - surfaced via StateResult.error
            result.error = f"failed to fetch index page {index_url}: {exc}"
            return result

        result.pages_fetched.append(index_url)
        page_urls = self._discover_candidate_pages(index_url, index_html)
        if not page_urls:
            result.error = (
                f"no internal links found under {index_url}; site structure may have changed"
            )
            return result

        retrieved_at = datetime.now(timezone.utc).isoformat()

        for page_url in page_urls:
            try:
                html = self._get(page_url)
            except Exception as exc:  # noqa: BLE001
                # One bad page shouldn't kill the whole state — record
                # it in `extra` context via a synthetic error record
                # instead of silently continuing.
                result.records.append(
                    SeasonRecord(
                        state_code=entry.code,
                        state_name=entry.name,
                        species=_species_from_slug(page_url),
                        season_label="ERROR",
                        date_text="",
                        source_url=page_url,
                        retrieved_at=retrieved_at,
                        date_parsed=False,
                        extra={"fetch_error": str(exc)},
                    )
                )
                continue

            result.pages_fetched.append(page_url)
            species = _species_from_slug(page_url)
            tables = extract_tables(html)

            for table in tables:
                for row in table:
                    headers = list(row.keys())
                    date_header = _find_header(headers, _DATE_HEADER_HINTS)
                    zone_header = _find_header(headers, _ZONE_HEADER_HINTS)
                    label_header = _find_header(headers, _LABEL_HEADER_HINTS)

                    date_text = row.get(date_header, "") if date_header else ""
                    season_label = row.get(label_header, "") if label_header else ""
                    zone = row.get(zone_header) if zone_header else None

                    if not date_text:
                        # No recognizable date column at all — this row
                        # doesn't belong to a season table (e.g. a
                        # bag-limit table caught by the same page).
                        continue

                    start, end, parsed = parse_date_range(date_text, season_start_year)

                    result.records.append(
                        SeasonRecord(
                            state_code=entry.code,
                            state_name=entry.name,
                            species=species,
                            season_label=season_label or "unspecified",
                            date_text=date_text,
                            source_url=page_url,
                            retrieved_at=retrieved_at,
                            start_date=start,
                            end_date=end,
                            date_parsed=parsed,
                            zone=zone,
                            extra={"raw_row": row},
                        )
                    )

        if not result.records:
            result.error = (
                f"crawled {len(page_urls)} page(s) under {index_url} but found no "
                "table with a recognizable date column; site structure may have changed"
            )

        return result
