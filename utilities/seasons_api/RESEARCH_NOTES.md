# Research notes

What was actually verified before writing any code, so the design
decisions below aren't guesses.

## There is no hunting-season API, anywhere

Searched for a federal or cross-state API/open-data feed for hunting
season dates. There isn't one. Each state wildlife agency sets and
publishes its own seasons independently (species, zones, weapon
classes, and terminology all differ by state). State GIS open-data
portals (Texas, Washington, etc.) publish *geospatial* hunting-related
layers — hunt area boundaries, wildlife management unit polygons — not
season date attribute data. Confirmed no Socrata/ArcGIS dataset exists
for season dates specifically.

## The one real standardization point: eregulations.com

49 of the 50 states (all except Alaska) host their **official** digital
hunting digest on `eregulations.com`, a shared vendor platform
contracted by the state agencies themselves — not a third-party
aggregator. Confirmed live:

- State selector on the homepage lists 49 states (Alaska absent).
- URL pattern is consistent: `eregulations.com/<slug>/hunting/`, where
  `<slug>` is the state name lowercased with spaces removed (verified
  against New Hampshire -> `newhampshire`, New York -> `newyork`,
  Pennsylvania -> `pennsylvania`, Vermont -> `vermont`).
- `robots.txt` only disallows `/cpresources/`, `/vendor/`, `/.env`,
  `/cache/` — the hunting content is not blocked.

Alaska is not on eregulations.com; it publishes via its own ADF&G site
(`adfg.alaska.gov`), which has different structure entirely and is not
implemented (see `registry.py`, marked `unimplemented` with a note,
never silently dropped).

## What is NOT standardized, even within eregulations.com

This was the real surprise, found by testing three states end-to-end
(New Hampshire, Vermont, Pennsylvania):

1. **URL naming isn't consistent.** New Hampshire has a dedicated page
   per species-season (`deer-hunting-seasons`). Vermont puts the same
   content directly on the species page (`deer-hunting`, no "season" in
   the slug). The adapter therefore crawls every page under a state's
   `/hunting/` section rather than filtering by URL keyword.

2. **Content shape isn't consistent.** New Hampshire and Vermont render
   season dates as real HTML `<table>` elements (with heavy `rowspan`
   use to group rows under one species/method). **Pennsylvania renders
   the same information as nested `<ul><li>` WYSIWYG prose** with no
   `<table>` tag anywhere on the page — a completely different DOM
   shape carrying the same information.

   The current adapter (`adapters/eregulations.py`) only implements the
   table-based extraction path. On a Pennsylvania-shaped page it
   correctly finds zero parseable tables and reports that explicitly as
   an error on the state's result (`StateResult.error`) rather than
   silently returning zero records as if the state had no open seasons.
   **A nested-list extractor for this second shape has not been
   written yet** — this is a known, flagged gap, not a silent
   omission. Extending coverage to Pennsylvania-shaped states means
   adding that second parser, likely as `adapters/eregulations_prose.py`,
   and having the aggregator try table-extraction first, falling back
   to prose-extraction per state.

3. **Real bugs found and fixed while testing against live pages** (kept
   here so the next person doesn't have to rediscover them):
   - `eregulations.com` doesn't declare a charset in `Content-Type`, so
     `requests` defaults to ISO-8859-1 per the HTTP spec and mangles
     every UTF-8 en-dash in a date range. Fixed by forcing
     `resp.encoding = "utf-8"`.
   - Python's `urllib.robotparser` fetches `robots.txt` with urllib's
     default User-Agent, which some sites reject with 403 — and
     `robotparser` treats a 401/403 *on robots.txt itself* as "disallow
     everything," which is the wrong failure mode. Fixed by fetching
     `robots.txt` ourselves with our real User-Agent.
   - Rowspan/colspan expansion duplicates a title banner cell's text
     across every column it spans, so a naive "row has exactly one
     non-empty cell" banner check stops matching after expansion. Fixed
     by counting *distinct* non-empty values instead of cell count.
   - Spanned header cells (e.g. one "Season" header spanning a method
     column and a sex/age-restriction sub-column) produce duplicate
     header names; building a row dict from them silently drops the
     first column's data via key collision. Fixed by de-duplicating
     header names before building rows.

## Why not just scrape the individual state .gov sites directly?

Considered and rejected as the primary approach for this pass: unlike
eregulations.com, official agency sites have no shared structure
whatsoever — Texas Parks & Wildlife splits seasons across PDFs and
several HTML pages; Pennsylvania Game Commission's *own* site
communicates season changes primarily through prose news releases, not
a stable reference table. That would mean up to 50 bespoke, brittle
parsers with no shared foundation. eregulations.com, despite its own
inconsistencies, is at least a single site to build against, and it's
the *official* publication channel (not a copy), so accuracy traces
back to the same source a direct-to-agency scrape would.
