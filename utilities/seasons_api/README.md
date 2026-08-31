# seasons_api

A standalone Python utility that pulls U.S. hunting season schedules
into one standardized, structured format. **Not wired into the
KeystoneBid Django app** — this lives entirely under
`utilities/seasons_api/` and doesn't import or get imported by
anything in `apps/`.

Read [RESEARCH_NOTES.md](RESEARCH_NOTES.md) first — it explains why
this is built the way it is (there is no hunting-season API anywhere;
the closest thing to one is a shared vendor platform, `eregulations.com`,
that 49 states use for their official digital hunting digest, and even
that isn't fully consistent state-to-state).

## Quick start

```bash
pip install -r utilities/seasons_api/requirements.txt

# One state
python -m utilities.seasons_api.cli --states NH --out nh_seasons.json

# A few states, CSV output
python -m utilities.seasons_api.cli --states MD,PA --out seasons.csv --format csv

# Every state in the registry (slow — see "Politeness" below)
python -m utilities.seasons_api.cli --all --out all_seasons.json

# See what's implemented vs. not, per state
python -m utilities.seasons_api.cli --list-states
```

Run from the repository root so the `utilities.seasons_api` package
resolves.

## What you get

A JSON (or CSV) file where every record is a `SeasonRecord`
([models.py](models.py)):

```json
{
  "state_code": "NH",
  "state_name": "New Hampshire",
  "species": "deer",
  "season_label": "Archery",
  "zone": "WMU A - Note: Archery deer season ends one week early.",
  "method": null,
  "date_text": "Sept. 15-Dec. 8",
  "start_date": "2026-09-15",
  "end_date": "2026-12-08",
  "date_parsed": true,
  "source_url": "https://www.eregulations.com/newhampshire/hunting/deer-hunting-seasons",
  "retrieved_at": "2026-08-26T18:04:11.203Z",
  "extra": { "raw_row": { "...": "the untouched original row, for audit" } }
}
```

Fields that are genuinely standardized across states (`state_code`,
`species`, `date_text`, `start_date`/`end_date`, `source_url`,
`retrieved_at`) are typed, top-level fields. Fields that vary too much
to force into one shape (zone systems, weapon-class taxonomies, permit
quotas, "any deer" vs. "antlered only" restrictions) live in `extra`
rather than being flattened away or dropped — the CLI's JSON output
keeps them, the CSV export doesn't (CSV is a flat convenience view; use
JSON if you need the full row).

The top-level output also always accounts for every state you asked
for, whether or not it produced records — see `StateResult` in
[models.py](models.py). A state with `"error": null` and zero records
genuinely has no matching data right now; a state with a non-null
`error` failed for a stated reason. The two are never conflated.

## Architecture

```
registry.py         Which states exist, and how (if at all) we can pull them
models.py            SeasonRecord / StateResult — the standardized shape
parsing.py           Free-text date-range parser + generic HTML table extractor
adapters/base.py     BaseAdapter contract
adapters/eregulations.py   The one implemented adapter (49 states, table-based pages)
aggregator.py         Runs the right adapter per state, never drops a state silently
storage.py            JSON / CSV writers
cli.py                 Command-line entrypoint
tests/                 Offline unit tests (no network) for the parsing logic
```

Adding a new source means writing one more `BaseAdapter` subclass and
pointing the relevant `registry.py` entries at it — nothing else
changes. `aggregator.py` dispatches by `StateEntry.adapter_type`.

## Current coverage

Run `--list-states` for the live picture. As of writing:

- **49 states**: `adapter_type = eregulations`, using the generic
  table-based extractor. Verified working end-to-end on New Hampshire
  and Vermont (real HTML fetched, real tables parsed, real dates
  produced). **Pennsylvania is a known gap**: same platform, but its
  season page is written as nested prose lists instead of an HTML
  table, so the current adapter correctly reports zero records with an
  explicit error rather than guessing — see RESEARCH_NOTES.md for what
  a second adapter for that shape would need to do. Other
  eregulations-hosted states likely split between these two shapes (or
  others not yet seen); running the CLI against a new state is the way
  to find out, and any state whose crawl succeeds but is still shaped
  in a way this table extractor can't read will fail loud, not silent.
- **Alaska**: `adapter_type = unimplemented`. Not on eregulations.com;
  publishes on its own ADF&G site. Flagged, not silently skipped —
  `registry.py` carries the real source URL and a note on what a
  dedicated adapter would need to handle.
- **District of Columbia**: `adapter_type = not_applicable`. No general
  hunting seasons administered.

## Politeness / etiquette

- A single `requests.Session` with a real, identifying `User-Agent` is
  used (see `USER_AGENT` in `adapters/eregulations.py`) — never spoof a
  browser UA.
- `robots.txt` is checked (with a proper UA, not urllib's default —
  see RESEARCH_NOTES.md for why that matters) before every fetch.
- `--delay` (default 1 second) is applied between every HTTP request,
  not just between states. A full `--all` run will take a while by
  design — this hits a real third-party site on every state's behalf,
  and there's no reason to hammer it.
- The crawl per state is bounded (`max_pages_per_state`, default 40) so
  a state with an unusually large hunting section can't run away.

## Known limitations (documented, not hidden)

- **Date parsing assumes month/day text without an explicit year**
  (`parse_date_range` takes a `season_start_year` and infers the end
  year from month order). This matches New Hampshire and Vermont's
  format. States that print the year inline in every date (Pennsylvania
  does, in its prose format) aren't covered by this parser yet.
- **No species name normalization beyond the raw URL slug.** "deer" on
  one state and "whitetail-deer" on another would currently show up as
  different `species` strings. A canonical species-name mapping (e.g.
  keyed off KeystoneBid's own `LicenseType`/species reference data, if
  this is ever wired into the app) is a reasonable next step, not
  something guessed at here.
- **Zone/unit systems are not normalized at all** — they're kept
  verbatim in `zone` because WMU numbering, county names, and named
  regions aren't reconcilable without per-state reference data.
- **This is a point-in-time scrape**, not a live feed. Re-run it to
  refresh; nothing here schedules or caches automatically.

## Tests

```bash
python -m unittest utilities.seasons_api.tests.test_parsing -v
```

These are offline (fixed HTML fixtures, no network) and cover the date
parser and the rowspan/colspan-aware table extractor. There is no
network-based test suite here on purpose — the whole point of
`RESEARCH_NOTES.md` is that live site structure is exactly what breaks,
and a test that pins today's live HTML would just be committing to
today's snapshot of someone else's website.
