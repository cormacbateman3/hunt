# Data Model Changes — Item Kind & Add-on Taxonomy (Refined 2026-06-11 · Updated 2026-07-10)

Scope: Adds the missing top levels of the item hierarchy (department → category → item kind), restructures the add-on taxonomy into facets, and adds era data so the taxonomy matches antique artifacts instead of modern license catalogs. Builds on the existing State / GeographicUnit / LicenseType work — no restructuring of those models.

2026-07-10 update: research results folded in (see "Research results" below — two corrections), plus four additions: **T12** department→category top level, **T13** two-page create flow + standardized image slots, **T14** admin general ledger, and the corrected Out-of-State/Co. 68 note.

**Execution status (updated 2026-07-22, branch `feature/alpha-p3-t0-t14`):** T0–T5, T6a, T7, **T8**, T10, T11 Phase A, and T12 are **shipped and verified** (research applied to ref_data, migrations + backfill run, seeders drift-free and idempotent, API year-gating live, forms/admin wired). T8 live 17-image run: every diagnosed failure case fixed (Turkey Tag [high], MD Deer Tag [high], Muzzle Loader matched via alias + second pass, county-number ⇒ PA prior fired, serial suffix preserved, addon kind gating). Follow-ups landed 2026-07-22: PA **Deer Tag** + **Small Game Tag** rows added (run-revealed vocab gap, artifact evidence from the 1979 test item); `MAX_IMAGE_EDGE` 1120 → **1568** (readability over cost, per Cormac); prompts/schema/aliases/knobs **externalized to `sandbox/prefill_config/`** (`system_prompt.md`, `extraction_tool.json`, `second_pass_prompt.md`, `concept_aliases.json`, `config.json`) with a `PROMPT_VERSION` hash — nothing prompt-like is hardcoded in Python anymore, and `PrefillJob.prompt_version` consumes the hash in 10.5.

**Prefill polish deliberately deferred** (model is good-enough; revisit after core workflows): R6 gold labels + per-tier precision scoring (notebook cell is ready), serial agreement-gating, threshold tuning against the gold set, prompt iteration on the remaining single-image misses. Remaining elsewhere: T6b/T9/T13 ride 10.8; T13 lot images ride 10.15; T14 rides 10.18. Postgres sanity check pending a staging DB.

Domain rationale: The marketplace trades physical artifacts, not legal privileges. A base license (PA back tag), a standalone stamp/tag (Federal Duck Stamp, antlerless paper license), and a license with species tags still attached are three different things that currently all flatten into the same dimension set. `item_kind` disambiguates; the existing `addon_type` M2M is reinterpreted by kind (license → "privileges attached/included on this item"; addon → "what this item is").

This revision follows a full repo review (2026-06-11). It records what the current system already does, what dev plan 10.5+ already covers, what new data actually needs collecting, and the refined tasks.

---

## Research assignments — exact data to collect

All of this goes into `utilities/ref_data/*.csv` — the hand-edited source layer. Never edit `cleaned/`; it is build output. Ground rules:

- `approx_first_year` / `approx_last_year` = when the physical product was **issued under that name/form**, not when a season existed. Blank last year = still issued / unknown. Low confidence is fine — say so in `notes`; these years gate suggestions, ordering, and prefill matching, never validity.
- One row per **artifact-name era**: if a product was renamed (paper "Antlerless Deer License" → modern "Antlerless Deer Permit"), use separate rows with separate spans, not one stretched row.
- In `addons_permits.csv`, the `addon_type` column is the instrument printed on the artifact: `Stamp`, `Tag`, `Permit`, or `License` (new value for standalone license-paper add-ons; the pipeline normalizes it to `instrument='license'`).
- Always fill `source_url` (a named offline source like the county-code PDF is fine).

### Research results (2026-07-10) — status, corrections, and how to apply

Delivered in `docs/internal/compass_artifact_wf-8a6645f9-…_text_markdown.md`. **The CSVs have not been edited yet** — applying the results is part of T0 (geo) and T4/T5 (addons). Status:

- **R1 ✅ + correction.** County numbers confirmed stable/alphabetical (Adams 01 … York 67), numbered era 1913(–possibly 1924)–**1937**; "Special Issue" un-numbered overflow 1920–1937. **Correction: "OUT-OF-STATE Co. 68" is a modern administrative code** — no early-tag printing found; a 1935 PA nonresident metal tag used a statewide serial (#8251). Keep the row with the corrected note; never present it as a verified historical printing.
- **R2 ✅.** Five PA rows delivered with year spans (Antlerless Deer License 1951–2002 high-conf; Muzzleloader License 1974– and Archery License 1951– high-conf floors; Turkey Tag / Big Game Tag first-year unknown, integral format ended ~2011).
- **R3 ✅ + correction.** All 9 PA floors delivered (Bear 1981 verified, Elk 2001, Pheasant 2017, DMAP 2003, PA Duck Stamp 1983, Antlerless Permit 2003, Archery 1951, Muzzleloader 1974). **Correction: PA's first spring gobbler season (1968) required no separate permit** — the floor stays 1968 but low-confidence; the purchasable separate spring-turkey permit is modern (second-bird tag). MD: 3 of 8 filled (Migratory Stamp 1974–2024, Bear 2004, Snow Goose 2009); Archery/Muzzleloader/Sika/Bonus/Furbearer remain blank low-confidence. FD confirmed.
- **R4 ✅.** MD Deer Tag / Turkey Tag rows delivered; spans left blank (low confidence, single-artifact evidence) — fine, floors gate only. Bonus context: MD county-scoped and statewide licenses overlapped ~two decades → add both classes to `license_classes.csv`.
- **R5 ✅.** Decision table: GA Big Game License **keep** (instrument=license), MI Deer License (Firearm) **keep**, PA Elk License **keep**, IN Deer License Bundle **delete** (no collectible artifact).
- **R6 ◐.** gold.json schema proposed; the 17 images still need labeling (open).
- **R7 (unassigned extra) — keep the free part.** OH wasn't assigned, but the CSV already has all 6 OH rows under the exact names researched, so the OH floors (Deer Gun 1943, Spring Turkey 1966, Wetlands Habitat Stamp 1982) apply to existing rows at zero cost; the two net-new OH rows (Deer Tag 1943, Fall Turkey Permit) are optional. No further OH research planned.

**Integration checklist when applying to `addons_permits.csv`:**

1. Federal rows keep `state_abbrev = "FEDERAL"` (pipeline maps → FD). The research wrote `"US"` — don't copy that.
2. Keep existing names as keys — the seeder keys on `(state, name, category)`. Research shortened "HIP Certification (Harvest Information Program)" to "HIP Certification"; either keep the long name or route the rename through the T5 `RENAMES` map. Same rule for any name drift.
3. OH "Deer Gun Permit" `hunting_method` stays `Firearm` (research wrote "Gun").
4. Facet edits from research (target_species "Waterfowl", "Sika Deer", "Antlered Deer", …) are safe to apply directly.
5. Preserve the per-row confidence phrasing in `notes` — admin enrichment (T10) works off it.
6. After applying: run `clean_reference_data.py`, diff `cleaned/`, reseed, and spot-check `/api/license-types/?state=PA&year=1969`.

### R1 — PA county numbers + Out-of-State unit (P0, ~30 min, do first)

File: `ref_data/geographic_units.csv` (`state_abbrev, unit_name, unit_type, unit_number, fips_code, is_statewide, geo_data_complete, sort_order, notes`).

1. Move the PA `unit_number` values 1–67 (currently only in the hand-edited `cleaned/` copy — a rebuild would erase them) into the PA county rows here, verifying each against `utilities/references/pa_county_code_map.pdf`. The prefill county-number resolver depends on these.
2. Add the nonresident unit row (10.8 needs it as a selectable option; prefill can use it). **Use the corrected row** — 68 is a modern administrative code, not a verified early-tag printing:

   ```csv
   "PA","Out-of-State","County","68","","False","True","69","Modern administrative code for non-resident/out-of-state; appears on PA county-code map PDF. NOT verified as printed on 1913-1937 nonresident metal tags (those used statewide serial numbers, e.g. 1935 NR license #8251)."
   ```

3. **Resolved (research 2026-07-10):** numbering was stable and alphabetical (Adams 01 … York 67); numbered era 1913(–possibly 1924)–**1937** with un-numbered "Special Issue" overflow 1920–1937. Use 1937 as the reliable end bound in matching logic; the back-tag *display* law (until 2012) is a different fact — don't conflate.

Done when: regenerating `cleaned/` reproduces the numbers (acceptance #3) and "Co. 68" resolves.

### R2 — PA historical add-on / standalone-license products (P0 — the prefill accuracy unlock)

File: `ref_data/addons_permits.csv` (`state_abbrev, addon_name, addon_type, target_species, hunting_method, is_federal, is_mandatory, approx_first_year, approx_last_year, notes, source_url`).

Add at least these five rows — drafted with TBDs to replace:

```csv
"PA","Turkey Tag","Tag","Turkey","Any","False","False","TBD","TBD","Fall turkey tag integral/attached to the back-tag license (seen on 1969 test artifact). NOT the modern Special Spring Turkey Permit.","TBD"
"PA","Big Game Tag","Tag","Multiple","Any","False","False","TBD","TBD","Big-game attach portion on mid-century PA licenses (seen on 1969 test artifact).","TBD"
"PA","Antlerless Deer License","License","Antlerless Deer","Any","False","False","TBD","TBD","Standalone paper license, county-issued under county quotas (county era 1951-2002 per states.csv notes). Separate row from the modern Antlerless Deer Permit.","TBD"
"PA","Muzzleloader License","License","Deer","Muzzleloader","False","False","TBD","TBD","Standalone paper muzzleloader/flintlock license, pre-dates the modern Muzzleloader Stamp (seen on 1970s test artifact).","TBD"
"PA","Archery License","License","Deer","Archery","False","False","TBD","TBD","Standalone paper archery license, pre-dates the modern Archery Stamp.","TBD"
```

Per row research: first year issued, last year (or rename year), county-issued or statewide, and what the artifact physically is (feeds the prefill rubric). Sources: PA Game Commission history pages, waterfowlstampsandmore.com (already cited throughout `states.csv`), collector sites, completed auction listings (photos are evidence of name + year).

Why: sandbox images 15/17 produced would-prefill-wrong matches ("TURKEY TAG" → Special Spring Turkey Permit) purely because these rows don't exist. Highest-leverage data task in this plan.

### R3 — Year ranges for the existing PA / MD / FD addon rows (P0)

File: same. Fill `approx_first_year` (and `approx_last_year` where the product ended/renamed) on:

- PA (9 rows): Archery Stamp, Muzzleloader Stamp, Bear Permit, Antlerless Deer Permit, Elk License (Lottery), Waterfowl/Migratory Bird Stamp, Pheasant Permit, DMAP Antlerless Tags, Special Spring Turkey Permit (this doc has said 1968+, spring only — verify).
- MD (8 rows): MD Migratory Game Bird Stamp, Archery Stamp, Muzzleloader Stamp, Bonus Antlered Deer Stamp, Sika Deer Stamp, Furbearer Permit, Black Bear Hunting Permit, Snow Goose Conservation Order Permit.
- FD: Federal Duck Stamp (1934, already filled), HIP (1998, already filled) — confirm only.

The floor matters most: `approx_first_year` is what mechanically rejects a modern permit as a match on a 1969 item. Don't agonize over last years.

### R4 — MD historical integral tags (P1)

File: same. The 1960s MD license tags seen in test images:

```csv
"MD","Deer Tag","Tag","Deer","Any","False","False","TBD","TBD","Integral deer tag on 1960s MD licenses (seen on test artifact).","TBD"
"MD","Turkey Tag","Tag","Turkey","Any","False","False","TBD","TBD","Integral turkey tag on 1960s MD licenses (seen on test artifact).","TBD"
```

This also kills the Sika-Deer-Stamp false match: once a real "Deer Tag" row exists (plus species facets), the wrong candidate loses.

### R5 — Audit the "License"-named addon rows (P1 — judgment, not research)

File: same. ~20 rows contain "License" (GA "Big Game License (deer/turkey/bear)", MI "Deer License (Firearm)", IN "Deer License Bundle", …). Decide per row:

- Standalone add-on privilege document → keep; set `addon_type` to `License`.
- Actually the state's base license → remove from this file; make sure `license_classes.csv` covers it.
- Modern e-licensing bundle with no collectible artifact ("Deer License Bundle") → delete; record the decision in notes or the commit message.

### R6 — Gold labels for the 17 sandbox images (parallel, prefill workstream)

File: `sandbox/gold.json` (new). One object per image with correct values: state, license_year, geographic_unit, serial_number (exact characters, prefix/suffix letter position preserved), residency, activity_scope, duration, addons (list of artifact names), material, shape, colors. Powers the per-tier precision scoring (prefill note #7 below) so every model/resolver change becomes a before/after number.

---

## Data model structure (the fact/dimension view)

In star-schema terms: the **item is the fact row** (grain: one row = one physical artifact). The unusual part is that `LicenseType` is one physical table holding **six logical dimensions**, partitioned by its `category` column — a dimension pool reached through one M2M bridge instead of six FK columns.

```
REFERENCE (dimension) SIDE                              ITEM (fact) SIDE
──────────────────────────                              ────────────────
ItemCategory (T12) ─────────────── FK category ────────▶ Listing / CollectionItem
  department → category                                 grain: 1 row = 1 physical artifact
  (1 seeded row: "Sporting Antiques"                           │
   → "Licenses & Permits")                                     │
                                                               │
State ──1:N──> GeographicUnit                                  │
  │            (County/GMU/WMD/… +                             │
  │             one 'Statewide' row per state)                 │
  │                     ▲                                      │
  │                     └────────── FK county_ref ─────────────┤
  ├──────────────────────────────── FK state ──────────────────┤
  │                                                            │
  └──1:N──> LicenseType  <──────── M2M license_types ──────────┤
            one table = 6 logical dimensions,                  │
            split by `category`:                               │  inline (degenerate) dims:
              residency             (single-select*)           │    license_year, era_label,
              holder_eligibility    (single-select*)           │    shape, colors, condition_grade,
              activity_scope        (single-select*)           │    serial_number, resident_status
              duration              (single-select*)           │
              addon_type            (truly multi-valued)       │  NEW (T1/T2/T12):
              material              (single-select*)           │    item_kind, addons_attached,
            + T3/T4 attributes on addon rows:                  │    category
              target_species, hunting_method,                  │
              instrument, first_year, last_year                │

* single-select is enforced by the forms, not the schema — the M2M allows multiples everywhere.
  LicenseType.state scoping: NULL = universal; 'FD' = federal; a form's candidate list =
  chosen-state rows + universal rows + FD rows.
```

Where the hierarchy intuition does and doesn't apply:

- **The top of the hierarchy is Department → Category (T12):** one seeded row ("Sporting Antiques" → "Licenses & Permits") stamps every item; invisible in the UI until a second category exists. `item_kind` is the next level down, interpreted *within* the category; the whole LicenseType dimension pool belongs to the licenses category.
- **Geography is the only true drill hierarchy below that:** State → GeographicUnit (with the per-state "Statewide" row meaning "no sub-unit" and the FD pseudo-state for federal stamps).
- **License-type dimensions are flat, state-scoped value lists.** The `state` FK is scoping, not a level; there is no parent/child inside a category. T3's facets are *dimension attributes* on addon rows, not hierarchy levels.
- **Time becomes two-level with T4:** `State.min_license_year` — the state-level floor, already enforced in validation (distinct from `licensing_start_year`, which is when the state legally began licensing — context only) → `LicenseType.first_year/last_year`, the per-product span. The item carries the actual year. This is exactly the "first time the state issued a license" vs. "first time xyz specific permit was issued" distinction.

**Where cross-dimension dependencies live.** Deliberate stance: dimensions are independent descriptors of *what is verifiable on the artifact*, not a combinatorial catalog of legally-valid license products. Hard constraints are limited to identity; real-world correlations are soft signals:

| Dependency | Hard or soft | Lives where |
|---|---|---|
| State → which geo units / type values are offered | Hard scoping | Form querysets + the two `/api/` endpoints |
| Geo unit must belong to the chosen state | Hard | `ListingForm.clean` |
| Year ≥ state floor (max bound comes in 10.8) | Hard | Form clean (+ filters, 10.11) |
| `item_kind` → which dimensions apply at all | Structural (new) | T1 + T6 conditional sections + T9 per-kind completeness |
| Year ↔ addon-product plausibility | Soft | T4 ranges: API ordering, form warning, prefill rejection |
| Nonresident → no home county | Soft — and instructive | Not modeled, on purpose. PA's "Out-of-State" code 68 is a **modern administrative code** (research 2026-07-10: no early-tag printing found; a 1935 NR metal tag used a statewide serial) — still added as a selectable unit per 10.8, as an option, not a constraint. |
| Addon implies hunting; pre-1980 implies Annual | Soft inference | Prefill resolver only, capped at medium tier |

Soft-not-hard is the right default because the data-entry source is "what a seller can read off a 60-year-old artifact" — hard combinatorial rules would block legitimate oddities. Warnings, ordering, and prefill gating do the work everywhere except identity (state / unit / year floor).

**The product grain you may be missing from fact/dim modeling does exist — in the raw layer.** Each `license_classes.csv` row *is* a product ("PA Resident Hunting License" = Resident × General × Hunting × Annual). The cleaning script explodes those combos into independent value lists and discards the product row — the same flattening harm as the addon facets. We are not building a `LicenseProduct` table now (artifact-first tagging is right for a marketplace where many antiques don't map to a known product), but `license_classes.csv` stays authoritative and growing so a future product dimension (combination suggestions, price history by product) can be derived without recollecting anything.

---

## How the data flows today (verified)

```
utilities/ref_data/*.csv          ← hand-edited source of truth (faceted)
        │  utilities/clean_reference_data.py
        ▼
utilities/cleaned/*.csv           ← GENERATED (license_types.csv is flattened to name-only)
        │  manage.py seed_states / seed_geographic_units / seed_license_types
        ▼
core.State / GeographicUnit / LicenseType (DB)
        │
        ├─ /core/api/license-types/?state=  → {category: [{id, name, is_other}]}  (apps/core/views.py)
        ├─ ListingForm / CollectionItemForm  → single-select per category; "_other" → ReferenceDataSuggestion
        ├─ Browse filters → per-category {cat}_id params (apps/listings/views.py)
        └─ sandbox/prefill_lib.py ReferenceData → resolver matching
```

Three findings from the review that shape this plan:

1. **The add-on facets already exist in the raw data.** `utilities/ref_data/addons_permits.csv` has `addon_type` (instrument: Stamp/Tag/Permit/Access Pass/Habitat Fee/Harvest Record), `target_species`, `hunting_method`, `is_federal`, `is_mandatory`, `approx_first_year`, `approx_last_year`, `notes`, `source_url`. `clean_reference_data.py:build_license_types()` is where they get flattened to bare names. T3 is therefore a pipeline/model change, **not** a data-collection task.
2. **Year-range data does NOT exist** — only 2 of 201 addon rows have `approx_first_year` (Federal Duck Stamp 1934, HIP 1998). T4 needs real research. The CSV columns are already there, just empty.
3. **Pipeline hazard (fix first):** the PA county numbers 1–67 powering the prefill county-number resolver were hand-edited into `utilities/cleaned/geographic_units.csv` (currently uncommitted), but `cleaned/` is **generated** — re-running `clean_reference_data.py` wipes them. They must be backported to `ref_data/geographic_units.csv`.

## What dev plan 10.5+ already covers (do not duplicate here)

| Concern | Where it lives | Implication for this plan |
|---|---|---|
| Multiple Add-on Types form widget (M2M is single-select today) | 10.8 | T6 does not re-plan it; item_kind UI rides the same 10.8 form overhaul; T13's two-page create flow + image slots are further 10.8 amendments |
| Year min/max validation (state min, current−25) on form + filters | 10.8 / 10.11 | T4's per-type soft warning is additive, finer-grained, never blocking |
| "Is a value missing?" suggestion-entry UX | 10.8 | T10's "don't see your tag/stamp?" entry point folds into that work |
| Browse multi-select filters + value counts | 10.11 | Facet filters (species, instrument) and "tags intact" land there |
| **Lots**: `inventory_format = single\|lot` on Listing + `ListingLotItem` | 10.15 | **Conflict with the draft's `item_kind='lot'` — resolved below: lot is removed from item_kind.** T13 adds the lot image spec (qty ≤ 10, front/back per item, one group featured image, box-lot guidance above 10) |
| county CharField → optional snapshot; retire legacy `license_type` CharField | 10.8 | Do those migrations alongside T1/T2 if timing allows (same models/files) |
| Unmatched prefill values → ReferenceDataSuggestion | 10.5 spec §6 | Already designed; T8 only changes extraction/resolution behavior |
| PrefillJob / PrefillCorrection models | 10.5 spec §3 | Unchanged |

**One amendment to 10.5:** the spec says "Data/DB: No change to Listing/CollectionItem." That is no longer true — this plan is the prerequisite schema work, and the sandbox results (bottom of this doc) show the vocabulary/taxonomy is the prefill model's dominant failure mode. Sequence: this plan's migrations + seed work land **before** 10.5 finishes (suggested slot: "10.5a").

## Decisions baked into this revision (each reversible, say so before migrations run)

1. **`item_kind` = `license | addon` only — no `lot`.** What-the-artifact-is and how-it-is-packaged are orthogonal axes; 10.15's `inventory_format` + `ListingLotItem` owns packaging, is more developed (contents disclosure, item-level exclusivity, auction/buy_now-only), and explicitly forbids lots in collections — which `CollectionItem.item_kind='lot'` would contradict. The prefill extraction schema still returns `lot` as an extraction-only signal (T8) routed to UX guidance ("this looks like multiple items"), never written to the DB until 10.15 exists. *(Confirmed 2026-06-11: lot is a property of the listing — a sale/packaging format — not of the artifact.)*
2. **No stored `is_federal` field.** It is fully derivable (`state.code == 'FD'` — the seeder already maps FEDERAL→FD pseudo-state, and forms/API already include FD rows for every state). The API returns it computed (T7); the resolver derives it. One less column to keep consistent.
3. **Instrument choices reconciled with actual data.** Draft proposed stamp/tag/permit/license/fee/certification; the data contains Stamp(35)/Tag(32)/Permit(122)/Access Pass(3)/Habitat Fee(5)/Harvest Record(2)/Other(1). Normalization map: Stamp→`stamp`, Tag→`tag`, Permit→`permit`, Access Pass→`permit`, Habitat Fee→`fee`, Harvest Record→`certification`, Other→blank. `license` is added for standalone paper license artifacts (e.g., PA county-issued Antlerless Deer License) surfaced by T5. `is_mandatory` stays out of the model (regulatory fact, not artifact-relevant).
4. **Department → Category ships as one small reference table, minimal now (added 2026-07-10).** `ItemCategory` carries a `department` label field — one table for two levels while department has exactly one value; split out a `Department` table only when a second department actually exists (trivial migration then, speculative table now). One seeded row: department **"Sporting Antiques"** (working name — rename is seed data, not schema), category **"Licenses & Permits"**. `item_kind` stays a CharField whose choices are interpreted per category — license/addon are the kinds *of* "Licenses & Permits"; a future "Publications & Guides" category (regulation guides, gun guides) defines its own kinds and its own attribute pool when it becomes real, and that design is deferred until then. Why add the FK now at all: every item row gets category-stamped from day one; retrofitting later means a backfill that guesses category from content.

## Maintenance workflow — from CSV pipeline to governed reference data

Today's flow (hand-edit CSVs → `clean_reference_data.py` → `cleaned/` → seeders → DB) is a bootstrap pipeline, not a governance model. The script's specific harms, beyond the T3 facet flattening: it discards the product grain of `license_classes.csv`, it emits dead `shape`/`colors` taxonomy rows nothing reads (T5), and its controlled vocab is hardcoded *and* duplicated in `apps/core/constants.py`. What it does well — column validation, slug generation, statewide-row checks, dedup — is worth keeping.

**Phase A — now, with this plan (T11): DB becomes the editing surface; CSVs remain the bootstrap.**

- `ref_data/` is the only hand-edited layer (T0); `cleaned/` must regenerate losslessly.
- **Seeders stop clobbering.** Default = create missing rows only + print a drift report (rows where DB ≠ CSV), touch nothing. `--overwrite` for the deliberate dev reset. Without this, T10's admin enrichment (list-editable years, facet fixes) is silently erased on the next seed run.
- **Close the suggestion loop.** Admin action on ReferenceDataSuggestion: "Approve → create/update LicenseType" (`is_system_value=True`, stamps reviewed_by/at). CLAUDE.md already promises "admin approval means the value is pushed to the data model" — this builds the missing half. The same action covers facet/year corrections (`suggestion_type='correction'`).
- **Merge tooling in admin.** Generalize T5's seeder RENAMES into a LicenseType admin action "Merge into…" (repoint M2M references, delete the duplicate) so prod-discovered dupes don't need a deploy.
- **Controlled vocab single-sourced.** `shape`/`colors` (and condition) stay code constants in `constants.py` — small, stable, already model-field choices, and 10.8 extends them in code; delete `CONTROLLED_SHAPES`/`CONTROLLED_COLORS` from the cleaning script along with the dead rows. `material` stays DB-backed (it already is a LicenseType category); its bootstrap list in the script is fine.

**Phase B — at 10.18 (Admin Dashboard & Exports): invert the flow.**

- `manage.py export_reference_data`: DB → `ref_data/` CSVs, so admin-edited reference data is versioned in git and syncs dev ↔ prod. From beta on, the DB is the system of record; seeders become first-install bootstrap only.

---

## Tasks

### T0 — Reference-data pipeline hygiene (do first, no DB change)

- Backport PA `unit_number` 1–67 from `cleaned/geographic_units.csv` into `ref_data/geographic_units.csv` so regenerating `cleaned/` is lossless (assignment R1). Verify: run `clean_reference_data.py`, diff `cleaned/` — must be a no-op apart from intended changes.
- While in there: add the PA "Out-of-State" unit row (code 68) with the **corrected note** — modern administrative code, not a verified early-tag printing (research 2026-07-10). 10.8 still needs it as a selectable unit for nonresident listings.
- Apply the R1 research output while editing (county numbers verified against the code-map PDF; corrected Out-of-State note).
- Going forward, `ref_data/` is the only hand-edited layer; `cleaned/` is build output.

### T1 — Add `item_kind` to Listing and CollectionItem

- `item_kind = CharField(max_length=20, choices=[('license','License'),('addon','Add-on / Stamp / Tag')], default='license')` — non-null.
- Required to publish. Note: there is no separate publish gate in code today — "required" *is* form validation (plus `listing_completeness_score` which is display-only in admin/detail). So: form-required radio now (T6a), folded into the 10.8 required/optional regroup later.
- Backfill data migration (refined heuristic): `license` if the M2M has any of residency / holder_eligibility / activity_scope / duration; `addon` if it has addon_type and **none** of those four; everything else (e.g., only material/shape/colors) → `license` and log to console for manual review. Do not block the migration.
- `WantedItem` deliberately out of scope (single `license_type` FK; revisit with 10.14 wanted-matching).
- No new index yet — two-value field, low selectivity; revisit in 10.11 if browse splits by kind.
- Files: `apps/listings/models.py`, `apps/collections/models.py`, migrations in both apps (combine with T2).

### T2 — Add `addons_attached` to Listing and CollectionItem

- `addons_attached = BooleanField(null=True, blank=True)` — only meaningful when `item_kind='license'` and ≥1 addon_type selected. True = tags/stamps physically attached/intact; False = referenced but detached/used; null = unknown.
- Optional; counts toward completeness when applicable (T9). Surfaces in listing detail now; "tags intact" browse filter ships with 10.11.

### T3 — Facet fields on LicenseType (addon rows) + pipeline restore

Model (`apps/core/models.py`, all `blank=True`, populated only where `category='addon_type'`):

| Field | Type | Examples |
|---|---|---|
| `target_species` | CharField(50) | Deer, Antlerless Deer, Turkey, Bear, Waterfowl, Elk, Trout |
| `hunting_method` | CharField(30) | Archery, Muzzleloader, Firearm — only methods visible on the artifact |
| `instrument` | CharField(20), choices | `stamp / tag / permit / license / fee / certification` |

Pipeline (this is most of the task — the data already exists):

- `clean_reference_data.py`: `build_license_types()` passes `target_species`, `hunting_method`, normalized `instrument`, `approx_first_year`, `approx_last_year` through for addon rows; add the year columns to `REQUIRED_ADDON_COLUMNS`; extend the `license_types.csv` output columns.
- `seed_license_types.py`: read the new columns into `defaults={...}`.
- No stored `is_federal` (decision 2).

### T4 — Year-range fields on LicenseType ⚠ requires new data collection

- `first_year = IntegerField(null=True, blank=True)`, `last_year = IntegerField(null=True, blank=True)` — the span the product existed (PA county-numbered tags 1913–1937; Federal Duck Stamp 1934+; PA Special Spring Turkey Permit 1968+). Null = unbounded. Low-confidence ranges fine — they gate suggestions/ordering, not validity.
- **Data to research** (assignments R2/R3/R4 — the only genuinely new data in this plan): populate `approx_first_year`/`approx_last_year` in `addons_permits.csv` for all PA addon rows (9 modern + new T5 historical), both FD rows, and the MD historical rows. Other states opportunistic, fed by the ReferenceDataSuggestion queue. **Status 2026-07-10: researched ✅ — rows and floors delivered in the compass doc; apply to the CSV per the integration checklist in "Research results".**
- Relationship to existing bounds: `State.min_license_year` (already enforced) is the absolute state floor; per-type ranges are finer-grained and **soft** — listing form shows a warning, never blocks (T6/10.8); prefill resolver rejects era-impossible candidates (T8).
- Consumers: `/api/license-types/?state=PA&year=1969` ordering (T7); form soft warning (10.8); prefill gating (T8).

### T5 — Taxonomy seed-data cleanup ⚠ partially new data

- **Collapse acquisition-method variants** (29 rows match OTC/Draw patterns): merge e.g. CO "Deer Tag (Limited Draw)" / "(Over-the-Counter)" → one "Deer Tag". Draw vs. OTC is not determinable from the artifact. Keep only artifact-visible method distinctions (Archery / Firearm / Muzzleloader) — those move into `hunting_method`.
- **Add historical rows** (new data — assignments R2/R4, with facets + years): minimum set from observed test images — PA: Turkey Tag, Big Game Tag, Antlerless Deer License (paper, county-issued), Muzzleloader License, Archery License; MD: Deer Tag, Turkey Tag (1960s integral tags). Expand per state as listings reveal gaps. **Status 2026-07-10: rows delivered (PA ×5, MD ×2, optional OH ×2) — see the research doc.**
- **Sweep misfiled rows** (assignment R5): ~20 addon rows contain "License" (GA "Big Game License (deer/turkey/bear)", MI "Deer License (Firearm)", IN "Deer License Bundle", …). Audit each: reclassify to a base-license dimension, or keep as addon with `instrument='license'` when it is a standalone license-paper artifact. **Status 2026-07-10: decision table delivered — GA/MI/PA keep with `instrument='license'`; IN "Deer License Bundle" delete.**
- **Seeder must survive renames/merges.** Today `update_or_create` keys on `(state, name, category)`, so a rename creates a new row and **orphans the old one with live M2M references**. Add a `RENAMES = {(state, category, old_name): new_name}` map to `seed_license_types.py`: repoint `listings`/`collection_items` M2M from old → new row, then delete the old row. This is what makes acceptance #7 real.
- **Drop dead shape/colors taxonomy rows**: the cleaning script emits `shape` (7) and `colors` (19) LicenseType rows, but forms/API/browse all use `FORM_LICENSE_TYPE_CATEGORIES` which excludes them (shape/colors live as model fields with choice constants). They were never selectable, so no references exist — stop emitting them and delete via the seeder sweep.

### T6 — Form behavior (split: minimal now / full in 10.8)

**T6a — ships with T1/T2 (minimal):** `item_kind` radio as the first input on listing + collection forms (no conditional hiding yet); `addons_attached` checkbox shown under the add-on picker. Without this the prefill 10.5 rollout (collection form first) has no field to write and everything keeps defaulting to license during 10.5–10.7 testing.

**T6b — belongs to 10.8 (form overhaul owns the form):** selection drives conditional sections —

- `license` → full dimension set; addon section labeled "Attached / included add-ons"; show `addons_attached`.
- `addon` → addon picker labeled "What is this item?"; show material/shape/colors, state, year, geographic unit; hide residency, holder_eligibility, activity_scope, duration.
- Vanilla JS, same pattern as the state-aware dropdown work. Lot behavior moved to 10.15.

### T7 — API updates (small; ship with T3/T4)

- `/api/license-types/` addon entries include `target_species`, `hunting_method`, `instrument`, `first_year`, `last_year`, and computed `is_federal` (`state.code=='FD'`).
- Accept optional `year` param: era-appropriate options ordered first, out-of-range entries flagged (`out_of_range: true`) so the form can soft-warn without a second call.

### T8 — Image-prefill integration (after T0–T5; amends the 10.5 spec) — ✅ shipped 2026-07-22 (sandbox)

- Extraction schema: add `item_kind` enum `license / addon / lot / unknown` with a short rubric ("standalone stamp/tag/permit vs. base license; multiple distinct items photographed together = lot"). `lot` is extraction-only → UI guidance, no DB write (decision 1).
- Resolver gates by kind: no activity_scope/duration inference for `addon`; for `addon`, addon_type resolution identifies the item itself.
- Add-on matching: species facet first, then full names; candidates outside `first_year`/`last_year` for the resolved year are rejected.
- Plus the sandbox findings below (per-item addon tiers instead of `_min_tier`, second-pass constrained matching, domain priors, prompt upgrades, gold set) — tracked in the prefill workstream, not this data-model plan.

### T9 — Required/optional + completeness (with 10.8)

- `item_kind` joins required-to-publish (T6a makes it form-required immediately; 10.8 regroups).
- Reclassify "strongly recommended" per kind: activity_scope recommended only for `item_kind='license'`; for `addon`, addon_type is the recommended field.
- `listing_completeness_score` computed against the kind-appropriate check set; count `addons_attached` when applicable. (CollectionItem has no completeness property today — adding one is optional, decide during 10.8.)

### T10 — Admin (ship with T3/T4)

- LicenseType admin: list filters for `instrument`, `target_species`; `list_editable` `first_year`/`last_year` for fast enrichment.
- Listing/CollectionItem admin: `item_kind` filter.
- ReferenceDataSuggestion: **no schema change needed** (verified — `target_model='license_type'` + free-text fields cover facet/year corrections). The "don't see your tag/stamp?" entry point on the add-on section folds into 10.8's "Is a value missing?" rework.

### T11 — Reference-data governance, Phase A (ship with the T3/T4 seeder changes)

- Seeder non-clobbering default + drift report + `--overwrite` flag (all three seed commands).
- ReferenceDataSuggestion admin action: approve → create/update the LicenseType row.
- LicenseType admin action: "Merge into…" with M2M repointing.
- Remove `CONTROLLED_SHAPES`/`CONTROLLED_COLORS` from `clean_reference_data.py`; `constants.py` is the single source for form-choice vocab.
- Details in the "Maintenance workflow" section above; Phase B (DB→CSV export, flow inversion) lands in 10.18.

### T12 — Department → Category top level (ships in the same migration batch as T1/T2)

- New `ItemCategory` in `apps/core`: `department` CharField(60) (one value for now: "Sporting Antiques"), `name` ("Licenses & Permits"), `slug`, `sort_order`, `is_active`. Data migration creates the seeded row first; then `Listing.category` / `CollectionItem.category` = `FK(ItemCategory, on_delete=PROTECT)` backfilled to it and made non-null. Seeder bootstrap + admin-editable (T11 rules apply).
- **Not exposed on forms or browse while only one category exists** — set in code, invisible to users. When a second category becomes real: category select moves onto the create-flow config page (T13), becomes a browse facet, and per-category kind sets / attribute pools get designed then.
- `WantedItem`: skip for now (same reasoning as T1).
- Hierarchy after this task: Department (1) → Category (1) → `item_kind` (license | addon) → dimensions. See the updated diagram.

### T13 — Two-page create flow & standardized image slots (spec here; implementation rides 10.8 + 10.15)

**Two-page listing creation (10.8).** Page 1 is a short config step; page 2 is the details form shaped by those choices — replaces the single form that morphs mid-edit.

- Page 1 (config): marketplace (The Auction House / The General Store), inventory format (single item / lot — appears once 10.15 ships), source (from my collection / new item), category (hidden while single, per T12). Optionally start the prefill image upload here so extraction runs while the user fills page 2 — hides the 2–4s latency entirely.
- Page 2 (details): rendered per config; single vs lot layouts differ (below); from-collection prefills safe fields as today.
- Server-side: config travels with the page-2 submit (hidden fields or session); both pages validate server-side; hitting page 2 without config redirects to page 1.

**Single-item image slots (10.8).** Labeled slots instead of a free-form pile, for cross-listing consistency: slot 1 **"Featured"** (badge — this is `featured_image`, the front of the item), slot 2 **"Back"**, then optional detail slots. Keep the current upload styling and the Mona Lisa placeholder icon. Schema: `image_role = CharField(choices: back | detail, default 'detail')` on `ListingImage` and `CollectionItemImage` (front/featured already lives on `Listing.featured_image`; collection front = first image). Front/back roles later feed prefill (serials are often on the back).

**Lot image structure (10.15 amendment).** Keeps lots clean and fully disclosed:

- Seller picks lot quantity **2–10** (hard max 10). The form renders one row per item: **two upload slots (Front / Back)** + a short per-item description → `ListingLotItem` rows gain `front_image` (required) / `back_image` (optional) ImageFields.
- One overall **Featured** image (all items photographed together) stays on `Listing.featured_image`.
- **Over 10 items = "box lot":** don't enumerate — contents disclosed in the description plus a few overall photos (form guidance copy). Still `inventory_format='lot'`, no per-item rows. This amends 10.15's disclosure rule: text disclosure suffices above 10.
- Per-item duplicate/exclusivity checks stay as specced in 10.15.

### T14 — Simple general ledger in admin (near end; target dev-plan slot 10.18)

Basic double-entry book of record for platform money, derived from Stripe/order events. Stripe remains the money mover — the GL is bookkeeping, admin-only, no user-facing surface.

- Models (small `apps/ledger`): `LedgerAccount` (code, name, type: asset/liability/revenue/expense; seeded chart: Stripe Clearing, Seller Payables, Platform Fee Revenue, Trade Label Fee Revenue, Shipping Passthrough, Refunds/Chargebacks, Adjustments) · `LedgerEntry` (timestamp, memo, source_type + source_id — order/trade/payout/manual, created_by) · `LedgerLine` (entry FK, account FK, debit, credit). Constraint: per entry, Σdebits = Σcredits.
- Postings live in the existing payments service layer, **idempotent per Stripe event id** (same rule as webhooks): payment succeeded → debit Stripe Clearing / credit Seller Payable + Platform Fee Revenue; refund → reversing entry; trade label fee → its revenue account.
- Admin: journal list (filters: account, source, date), a trial-balance / account-totals view, manual adjustment entries (admin-only, audited), CSV export riding the 10.18 export work.
- Explicitly not v1: payout reconciliation automation, tax handling, user-facing statements (users get the 10.18 purchase/sales exports).

---

## New data to collect (complete list — exact structures in "Research assignments" at the top)

1. **Year ranges** (T4 / R3): ✅ researched 2026-07-10 — PA 9/9, FD 2/2, MD 3/8, OH 3/6 floors delivered. **Not yet applied to the CSV.** Remaining blanks (MD Archery/Muzzleloader/Sika/Bonus/Furbearer; OH Archery/Muzzleloader/Antlerless) stay empty low-confidence — they gate suggestions only; fill opportunistically (MD DNR guide back-issues / ODNR digests per the research doc).
2. **Historical addon/license rows** (T5 / R2, R4): ✅ researched — PA ×5 + MD ×2 (+ optional OH ×2) rows drafted with facets, years, sources. **Not yet applied to the CSV.**
3. **Nothing for facets** — already in `addons_permits.csv`; un-flatten the pipeline.
4. **Nothing for item_kind / addons_attached / category** — backfilled from existing M2M data / seeded default, then user-entered.
5. (Prefill workstream, parallel — R6): `gold.json` labels for the 17 sandbox images, growing to ~75–100. **Still open** (research delivered the schema only).
6. Open research threads (low priority): a 1913–1937 PA *nonresident* tag photo to settle the Co. 68 printing question; a dated 1950s–70s MD statewide license to pin the integral-tag span.

## Migration / execution order

1. **T0** ref_data backport + apply R1 research + regen check (no DB).
2. **Core migration:** ItemCategory + seeded row (T12) and LicenseType facets + year fields (T3, T4 schema).
3. **Listings/Collections migration:** `item_kind` + `addons_attached` + `category` FK + backfill (T1, T2, T12) — consider bundling 10.8's county-CharField/legacy-license_type retirement here if convenient (same files).
4. **Pipeline + seed data:** clean_reference_data.py changes; **apply the R2–R5 research rows/floors to `addons_permits.csv`** (integration checklist); T5 cleanup incl. RENAMES map; re-run seeders on SQLite + Postgres.
5. **T6a minimal form exposure + T7 API + T10 admin + T11 governance hardening.**
6. **T8 prefill schema/resolver** — needs 1–4; this unblocks finishing 10.5.
7. Deferred into existing dev-plan tasks: T6b + T9 + T13 (two-page flow, single-item image slots) → 10.8; facet/tags-intact filters → 10.11; lots incl. T13 lot-image spec → 10.15; T14 ledger → 10.18.

## Acceptance criteria

| # | Criterion |
|---|---|
| 1 | Every Listing and CollectionItem has an `item_kind`; the forms require it. |
| 2 | A standalone duck stamp and a license with a turkey tag attached are distinguishable by `item_kind` alone. |
| 3 | Regenerating `cleaned/` from `ref_data/` is lossless (PA unit numbers + facet/year columns survive a re-run). |
| 4 | `first_year`/`last_year` populated for all PA addon rows and federal stamps; API `year` param orders/flags accordingly. |
| 5 | No draw/OTC variants remain in the taxonomy; historical minimum set seeded with facets. |
| 6 | Backfill migration completes on existing data with ambiguous rows logged, none broken. |
| 7 | Seeders are idempotent across row merges/renames — renamed rows repoint M2M references, no orphans. |
| 8 | Prefill resolver never prefills activity_scope or duration on an `item_kind='addon'` extraction; era-impossible addon candidates are rejected. |
| 9 | (10.8) Listing form shows/hides dimension sections by kind without reload; era warning on out-of-range selection. |
| 10 | (10.11) Browse filters add-ons by species and instrument; "tags intact" filter works. |
| 11 | Re-running seeders without `--overwrite` never clobbers admin-edited reference rows (drift is reported); approving a ReferenceDataSuggestion creates/updates the taxonomy row from admin alone. |
| 12 | Every Listing and CollectionItem carries a `category` FK to the seeded ItemCategory; no category UI is visible while only one category exists. |
| 13 | (10.8/10.15) Create flow is two pages (config → details); single-item forms show labeled Featured/Back slots (Mona Lisa placeholder kept); lots capture 2–10 items with Front/Back per item + one group Featured image; >10 routes to box-lot guidance. |
| 14 | (10.18) Every ledger entry balances (Σdebits = Σcredits), postings are idempotent per Stripe event, and admin can view journal + trial balance and export CSV. |

---

image prefill model:

## What the results actually show

Extraction is in good shape. State, year, county-number resolution, geo names, colors, shape — nearly all correct, including the cases I flagged as risky: `Co. 21` → Cumberland, `Co. #2` → Allegheny, `COUNTY NUMBER 36` scanned out of raw text. So I retract the county-number float-key concern (your DB clearly stores ints) and the truncation worry didn't manifest at these transcription lengths. The errors that *did* show up cluster in four places, and three of them aren't matcher bugs — they're vocabulary and policy problems:

**1. The addon taxonomy doesn't contain what's printed on 50-year-old items.** This is the dominant failure and the thing I underweighted last round. Your taxonomy is built from modern license catalogs; the artifacts are 1920–1980 products with different names:

- Img 15: item says "TURKEY TAG" (1969) → resolved to **"Special Spring Turkey Permit" at medium tier** — that would prefill, and it's wrong (it's the fall tag integral to the license).
- Img 9: MD "DEER TAG" → matched **"Sika Deer Stamp"** — the single-token-overlap risk from last round, confirmed in the wild. (Hidden by the tier aggregation, see #2, but the match itself is wrong.)
- Img 17: "MUZZLE LOADER" → unmatched. Not a vocab-coverage miss, an alias gap: `CONCEPT_ALIASES` has `MUZZLELOADER` but `_norm` preserves the space. One-line fix — also try the space-collapsed key.
- Img 15: the "BIG GAME TAG" attachment was never extracted at all.

No matcher tuning fixes "the right answer isn't in the candidate list." That's why T4/T5 in the task doc (historical rows, species facets, year ranges) are prefill work as much as marketplace work — with `first_year/last_year`, "Special Spring Turkey Permit" on a 1969 item gets rejected mechanically.

**2. `_min_tier` aggregation throws away good matches.** Img 17: "Antlerless Deer" matched cleanly, but the addon row's overall tier is unmatched because Muzzle Loader dragged it down — so the form prefills *nothing*. You already carry per-item results in `items`; prefill matched items individually and route unmatched ones to suggestions. Drop the aggregate tier from the form contract entirely.

**3. One missed read cascades.** Img 14 (the 1923 tag): "PENNSYLVANIA RESIDENT HUNTER'S LICENSE TAG" is printed *vertically* on the left edge — the model missed it, state came back null, and that nuked geo (`Co. 36` had no state to resolve against), activity_scope, and duration. Two fixes: tell the model to check rotated/vertical/edge text explicitly, and add a domain prior in the resolver — the "COUNTY NUMBER NN" format is uniquely PA 1913–1937, so that pattern alone should resolve state=PA at medium tier even when no state name was read.

**4. Silent errors at high confidence — the calibration point, confirmed.** Img 1: `material = Metal Button` at high tier on what is plainly a stamped rectangular metal tag (img 2, same item type, said Metal Tag — it's inconsistent, not systematically wrong). Img 17: serial extracted as `531O1H` at 0.90 conf — the item reads `53101H`; classic O/0 confusion. Img 15: item prints `23560 G` (suffix), output normalized it to `G 25060`-style prefix because the prompt's only example is a prefix. Every one of these errors carried 0.85–0.99 confidence, which is exactly why conf can't be the load-bearing signal.

Smaller resolver paper cuts visible in the output: img 13's `era_guess` shows as unmatched/0.0 next to a perfectly good year — when `license_year` resolves, drop era entirely instead of rendering a red row. Img 17's `duration` is unmatched/0.0 *with* `inferred: yes` — the model listed it in `inferred_fields` but omitted it from `per_field_confidence`, and `conf_of` defaults to 0; default inferred-but-unscored fields to ~0.65 instead. And one observation worth keeping deliberate: in imgs 6 and 15 the model read the *collector's mat annotations* ("LETTER 'G' IS PART OF NUMBER") as item text. It helped here, but it violates your own transcription rule and could mislead — give annotations their own schema field (`context_text`) so they're usable as weak evidence instead of contaminating the transcription.

## How to make it highly accurate

Ranked by expected impact against the errors actually observed:

**1. Fix the vocabulary, not the matcher** (T4/T5). Historical addon rows, species facets, year-range gating, and matching against the species facet before full names. Of the ~9 real errors in this run, this eliminates four at the root — including both of the would-prefill-wrong cases. Everything else is polish by comparison.

**2. Add a constrained second pass for anything that doesn't exact-match.** Text-only Haiku call: transcription + the state's (year-gated) candidate list as `id: name` pairs, instructed to return matching ids **or none**. This is the piece that gets you from "fuzzy matching is brittle" to "highly accurate": a model choosing from a closed set with a none-option doesn't produce Sika-Deer-class errors, and it handles spacing/synonym variants ("Muzzle Loader", "Doe License") without you maintaining an alias dictionary forever. ~0.2 milli-$ per invocation, and it only fires on misses — your run averaged 3.9 milli-$/image, so this is noise.

**3. Per-item addon prefill** (#2 above). Free accuracy — correct matches you're already computing and then discarding.

**4. Encode domain priors as validators.** You know things the model doesn't: COUNTY NUMBER format ⇒ PA; PA back-tag serials are 1–6 digits with at most one letter, so an interior `O` is almost certainly `0` (flag or auto-correct with the tier dropped); a species tag implies the year's season existed. These are cheap, deterministic, and catch exactly the high-confidence silent errors.

**5. Prompt upgrades** (cached, so free): rotated/vertical/edge text instruction; a material rubric ("Button/Disc = round pinback; stamped flat metal = Metal Tag"); preserve the printed position of serial letters (prefix *or* suffix) with one example of each; "every 'ATTACH THIS TAG' portion is an addon — list them all"; separate `context_text` field; omit `era_guess` when a year is read.

**6. Agreement-gating for the serial.** Run extraction twice (or re-extract just the serial on a tighter crop) and only prefill when both agree. Serial is the field where a wrong prefill does the most damage and is least likely to be caught by the user; agreement is the only reliable signal for character-level reads.

**7. Formalize these 17 into a gold set and grow it to ~75–100.** A `gold.json` of correct field values per image plus a scoring cell in the notebook that reports per-field precision *per tier*. Then the tier definitions stop being vibes: "high" means ≥98% measured precision or the threshold moves until it does. Every change above becomes a before/after number instead of eyeballing 17 HTML tables.

Endpoint this gets you to: high-tier prefills you can trust blindly (≥98%), medium as "probably right, please glance," and the genuinely unreadable stuff routed to suggestions instead of wrong guesses — which is the right product behavior for a listing form anyway. If you want, next pass I can write the second-pass resolver function + the gold-set scoring cell so they drop straight into the sandbox notebook.
