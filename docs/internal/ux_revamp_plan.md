# UX Revamp — implementation plan

Source design: `docs/internal/design/ui-ux-redesign-model/project/KeystoneBid UX Revamp.dc.html`
(a 21-turn design document, ~100 screens, exported from Claude Design).

Scope agreed with the product owner on 2026-08-03:

- **IA:** full change as designed. Four pillars → four zones. Format becomes
  a filter, not a destination. Old pillar URLs 301 into Hunt.
- **Screens:** foundation + core loop — the design system, the shell, and the
  core screens. Everything else in the document is deliberately out of scope
  for this pass.

## Read the document newest-first

**The design file is ordered newest-first: turn 21 is at the top, turn 1 at
the bottom.** This is easy to get wrong and expensive when you do.

Turn 1 proposes the design language and a three-zone shell
(`Hunt / My Bench / Collectors`, 62px bar, 7–12px radii). **Turn 2a then
revises it** — "every other page, compressed to 56px, with the trail on the
left" — and every turn from 2 to 21 uses the revision. The evidence is not
close:

| | Turn 1 | Turns 2–21 |
|---|---|---|
| Frames using it | 5 (all inside turn 1) | 18 |
| Masthead | 62px, search left, zones right | 56px, mark + zones left, search right |
| Zones | Hunt / My Bench / Collectors | Hunt / Collections / My Bench / The Almanac |
| Radii | 7 / 8 / 10 / 12px | 3px (×844), 4px (×359), 2px (×212) |
| Elevation | drop shadows on panels | hairlines only — "paper doesn't float" |
| Nav type | 13.5px sentence case | 11.5px 700 uppercase, 0.15em |

**Where the two disagree, the later turns win.** Turn 1 is still the only
place the palette and type scale are stated as a system, so it remains the
source for those; its geometry is superseded.

The design's own readiness sheet (section 20a) splits the remaining work into
*buildable today*, *needs a field or two*, and *needs a new model*. That
split is reproduced under "Not in this pass" below so nothing is lost.

---

## Phase 1 — Design system + the shell ✅ DONE

Palette, type and the fixed bands every page inherits. Built first against
turn 1, then corrected to the settled turn-2–21 system (see above).

| File | What |
|---|---|
| `static/css/variables.css` | The consolidated token set: ink ramp to 5 steps, brand extended (forest-deep/ink, brass-deep/bright, sage, tan), four rule steps with the design's two drifted generations collapsed onto them, tonal states, three-tier uppercase label system, full type scale, square radii. Legacy token names kept as aliases pointing at the new values — because `--radius-sm`/`--radius-md` alias through, squaring five numbers squares the corners on every un-migrated page for free. |
| `static/css/shell.css` | Masthead (56px), workspace band (44px), breadcrumb trail (40px), page well (1280 max / 28px gutters → 1224 content), footer. |
| `static/css/kb-ui.css` | Buttons, status + format badges, chips, listing card, panels, action rows, spec table, meter, fields, sub-tabs, empty state. |
| `templates/base.html` | The shell. Keystone mark + four zones hard left; global search recessed on the right — there was no global search at all before, only a per-page filter bar. Username dropdown deleted; the avatar carries only profile, settings, sign out. |
| `apps/core/context_processors.py` | Derives `kb_zone` from the resolved view name so the masthead marks the current destination without every template declaring it. |
| `apps/core/views.py` + `templates/core/almanac.html` | The Almanac placeholder. |
| `static/js/custom.js` | Nav toggle + account menu rewired; Escape closes the menu. |

Key palette decision, carried from the design: **parchment stops being the
default card background.** White surfaces on a warm page; parchment reserved
for grouping and quiet zones. That single change is what stops every page
reading as one flat beige mass.

Fonts are Petrona + Public Sans via Google Fonts, per the design. This is the
only external asset dependency added.

**The Almanac ships as a nav slot with no app behind it.** It is a zone in
the settled masthead, but the model is third in the designer's own build
order (after price history and collection sets). `/almanac/` renders a page
that says so plainly and points at the reference pages that do exist. A zone
that quietly appears later is harder to plan around than one that states
what it will be.

## Phase 2 — Hunt, one catalog ✅ DONE

| File | What |
|---|---|
| `apps/listings/views.py` | `HuntView`: format as a multi-select filter, faceted counts, local-pickup filter, sub-tabs (All / Ending soon / Matches my wants / Newly listed), sorting, removable filter chips. `pillar_redirect()` for the three old pillars. |
| `apps/listings/urls.py` | `auction_house`, `general_store`, `trading_block` are now permanent redirects into Hunt with the format pre-applied. URL names kept so existing `{% url %}` calls and inbound links keep working. |
| `config/urls.py` | The three zone roots: `/hunt/`, `/bench/`, `/collectors/`. |
| `templates/listings/hunt.html` | Left refine rail with result counts; one grid holding auctions, buy-now and trades. |
| `templates/listings/_card.html` | The card. Format badge on every card; on a trade card what the owner *wants* sits where a price would. |
| `static/css/pages/hunt.css` | Rail + results layout. |

Facet counts are measured with every *other* filter applied, so a collector
can see that only N items offer local pickup before spending a click.

`BaseListingListView` now accepts `q` as well as `search`, so the topbar
search and the in-page filter drive the same query.

## Phase 3 — Listing detail ⬜ NEXT

The live page has a real bug to fix first: `.listing-detail` is
`grid-template-columns: 2fr 1fr` with **three** children, so the seller card
takes the top-right cell and the bid panel — the only reason the page exists
— wraps into the wide left column below the image, under the fold.

Target: gallery left, one sticky decision panel right, the eighteen
`label: value` paragraphs become two labelled spec tables, and Q&A / bid
history / shipping move into tabs so the page has a bottom.

## Phase 4 — My Bench ✅ DONE (Needs you)

| File | What |
|---|---|
| `apps/accounts/bench.py` | `needs_you()` — every open obligation, soonest first: pay by, ship by, confirm receipt, offer expiry, trade expiry, your unshipped side of a live trade. Each deadline is read back from the same constant the cron job uses to enforce it. `needs_you_count()` is the cheap aggregate for the tab badge. |
| `apps/accounts/views.py` | `bench()` plus collection progress, closest gaps, wanted-list matches, account readiness. |
| `templates/accounts/bench.html` | Needs-you rows with urgency on the left edge; side rail. |
| `templates/components/_bench_tabs.html` | The old username dropdown, promoted to visible tabs. |
| `static/css/pages/bench.css` | |

Progress reads `State.issuance_unit_label`, so the panel says "Counties" in
Pennsylvania and the right word everywhere else. This is the cheap
high-value substitution the design flags in 14a.

**One honest gap:** `SHIP_BY_DAYS = 5` in `apps/accounts/bench.py` is the
handling window quoted to buyers, but unlike the other three deadlines no
background job enforces it. It should move to `MarketplaceSettings` when one
is written.

## Phase 5 — Trade board on the new shell ⬜ TODO

Propose-trade is turn 1c screen 4 and the flagship of the redesign.

---

## Not in this pass

Straight from the design's own readiness sheet (20a).

### Needs a field or two
- `WantedItem` — the design in 11b draws five fields that do not exist:
  minimum grade, repairs-ok, a private ceiling price, notify-me,
  show-on-profile. The designer flags this as their own mistake. The ceiling
  and the two booleans are what make a want more than a saved search.
- `Strike` — one `CheckConstraint`. Do this *before* the moderator screen
  ships, not after.
- `MessageReport` → `Report`, with nullable listing and order alongside the
  existing conversation and message.
- A moderation action on `Review`. The state field exists; nothing can change
  it, so today a libellous review cannot be taken down from the admin at all.
- `GeographicUnit.valid_from` / `valid_to` — only bites outside PA, where
  units get created and retired.
- Naming: `WantedItem.county` and `CollectionItem.county` both point at
  `GeographicUnit`. The model was renamed and the fields were not, which is
  exactly how "county" leaks back into the interface.

### Needs a new model, in the designer's build order
1. **Price history** (plan 13.6) — the most load-bearing thing missing.
   Twelve screens across seven turns print a comparable-sales figure.
2. **CollectionSet** (plan 10.14, called CollectionFolder there) — without
   it there is no definition of what counts as a gap.
3. **Almanac entries** — needs a writer more than a developer.
4. **Three questions** — the only thing on the sheet nobody asked for.

### Also deferred
- "Open to trade" is currently `listing_type == 'trade'`. The design argues
  trade availability is a *property* of an item, not a different kind of
  item — plenty of sellers will take cash *or* a swap. A proper
  `open_to_trade` boolean on any listing is a field-level change.
- Mobile screens (15a/15b), all empty states (16a/16b), the admin desk and
  member page (17a/19a), emails (9a–9f), the Almanac (12a/12b), badges (21b).
