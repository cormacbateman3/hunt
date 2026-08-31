# UI/UX Redesign — master plan

**Design source of truth**
`docs/internal/design/ui-ux-redesign-model/project/KeystoneBid UX Revamp.dc.html`
(21-turn design document, ~100 screens, exported from Claude Design)

**Related plans** — this document does not replace them, it sequences the UI work
and carries over the items they left open.
- `docs/internal/dev_plan.md` — feature plan, tasks 10.x / 11 / 13.x
- `docs/internal/data_model_img_prefill_plan.md` — item-kind & add-on taxonomy, T0–T14

---

## How the three plans relate

`dev_plan.md` is the programme. `data_model_img_prefill_plan.md` is the schema and
taxonomy workstream underneath it. **The design model was drawn after both**, and
in places it reaches a different answer.

**Precedence, where two of them describe the same thing:**

> **For anything a member sees** — the design model wins, and this file records how.
> **For anything a member does not see** — schema, seeders, the reference-data
> pipeline, the prefill resolver — the data-model plan still rules, and the design
> has nothing to say about it.

That split matters because the two plans mostly do not overlap. The design almost
never contradicts the data-model plan; it *depends* on it. The exceptions are
listed below and are the only places to be careful.

### What the design supersedes

| Superseded | By | What changes |
|---|---|---|
| **T13 two-page create flow** — and it is **already shipped** (`templates/listings/listing_create_config.html`) | turn 6a/6b/6c | **Three steps, not two.** Destination first, as three cards that each state *the questions they will ask*. The "yours or stock" radio is deleted — 6a: *"it was solving a problem the destination choice solves better."* "From my collection" becomes a route on step 1 (duplicates first) that skips step 2 entirely, not a config toggle. Lot becomes a quieter second entry. The config page gets replaced in **Pass 5**. |
| **10.20 Final UI/UX Polish Pass** | Passes 1–11 | Its entire scope — global navigation, sensible grouping, consistent cards, a more engaging home page, the brand voice, the mobile pass — *is* this redesign. 10.20 becomes a sign-off checklist, not a task. |
| **10.11's "move filters to a horizontal layout"** | turn 1c / 13b | A **vertical left rail with result counts**, not horizontal. Already delivered in Pass 1. |
| **turn 5** (one door, then a disposition) | **turn 6** | Internal to the design, but worth knowing: 6a opens *"You're right and 5a was wrong: the destination should be the first question."* Build turn 6. |
| **turn 3a's trade board** | **turn 2e's** | ⚠ **The one place an earlier turn wins**, and a product-owner call rather than a reading. 3a's reasoning holds but it does not survive our width: 241px a side against 2e's 295px, because 3a spends a quarter of the page on a permanent rail. See Pass 7b. |

`10.10 Trade Re-Architecture` is **not** a conflict — the dev plan and the design
reached the same conclusion independently, in nearly the same words. Both delete
`listing_type='trade'` and make tradeability a property of the item.

**The dev plan is the authority on the default**, and it is worth quoting because
Pass 7 initially reached the opposite answer from the design's screens alone:

> *"Every collection item (and General Store listing) gets an owner-set 'Is Tradeable'
> flag. An item actively listed in The Auction House is automatically not tradeable."*
> — dev_plan 10.10

Open by default, closed by choice; the auction is the only thing that takes a piece
off the table. Settled in Pass 7.

### What still stands, untouched

Everything else in the data-model plan is unaffected, and several items the design
*depends on*:

- **T3 / T4 facets and year ranges** — and the design gives them a **new consumer**:
  the tracker matrix reads `LicenseType.first_year` / `last_year` to draw the
  hatched *never issued* cells, so a gap you could never fill is not counted
  against you (14b).
- **T5 taxonomy cleanup + the `RENAMES` map** — and 17b adds duplicate-candidate
  grouping *upstream* of the merge screen, which it calls "already right".
- **T11 governance** — non-clobbering seeders, drift report, approve-a-suggestion,
  merge tooling. 19b: `ReferenceDataSuggestion` "already has accept-and-apply,
  which is the whole job".
- **T13 image slots (`image_role`)** — **reinforced**, not superseded: turn 6b draws
  the labelled Featured·front / Back / three-optional slots exactly as T13 specs
  them. Still owed.
- **T13 lot images** — turn 9d draws the lot screen and matches T13's amendment
  (2–10 items, front/back each, box-lot guidance above 10).
- **T14 ledger**, **R6 gold labels**, **the prefill polish backlog**, **the Postgres
  check** — all untouched. 17b adds one thing: a **cleared-rate** column, because
  `PrefillCorrection` is a better signal than the tier table.

### What the design adds that the data-model plan deferred

The data-model plan put `WantedItem` "deliberately out of scope … revisit with
10.14". The design now specifies it (11b), along with several other fields — all
listed under **Field-level gaps** below.

---

## How to use this document

1. **Every pass re-reads the design model.** Open the `.dc.html` and read the turns
   named in the pass. Do not work from this summary alone — the copy, the exact
   metrics and the designer's rationale live in the source and the voice *is* the
   deliverable.

   > ### ⚠ Read the drawing, not the prose
   >
   > Each turn opens with a paragraph describing what changed. **That paragraph is
   > not the specification.** Find the frame by its `data-screen-label`, walk to the
   > matching `</div>`, and read the `style` attributes: every colour, size and
   > padding is stated there.
   >
   > Turn 3a was built from its paragraph and shipped wrong. The paragraph said "one
   > dark panel", "196px picker lists", "300px rail", "brass arrow", "Petrona 21px" —
   > all implemented — while the frame said the licences on that panel are **cream
   > `#f4f1e8` cards**, which is the entire point of the turn and was rendered at
   > `rgba(255,255,255,.055)`. It also said `#22301c` body against `#1e2a19` header
   > against `#1b2416` / `#2b3a22` cash feet: four greens where one had been used.
   >
   > **Then render the page and read it.** 429 tests were green over a screen whose
   > roster rows wrapped onto three lines and whose table text broke a character at a
   > time. Tests assert context keys and substrings; they cannot see a layout.
2. **Update this file at the end of every pass.** Move the pass to ✅, fill in the
   "What actually shipped" block, and record any deviation or newly-discovered gap.
3. **A pass ends at a commit boundary** with the suite green.

### Read the design document newest-first — this is the trap

**Turn 21 is at the top of the file. Turn 1 is at the bottom.** Turn numbers count
*down* as you scroll.

Turn 1 proposes the design language and a three-zone shell. **Turn 2a then revises
it** — *"every other page — compressed to 56px, with the trail on the left"* — and
every turn from 2 to 21 uses the revision. The evidence is not close:

| | Turn 1 (superseded) | Turns 2–21 (settled) |
|---|---|---|
| Frames using it | 5, all inside turn 1 | 18 |
| Masthead | 62px, search left, zones right | 56px, mark + zones left, search right |
| Zones | Hunt / My Bench / Collectors | **Hunt / Collections / My Bench / The Almanac** |
| Radii | 7 / 8 / 10 / 12px | **3px (×844), 4px (×359), 2px (×212)** |
| Elevation | drop shadows | hairlines — *"paper doesn't float"* |
| Nav type | 13.5px sentence case | 11.5px 700 uppercase, 0.15em |

**Where they disagree, the later turns win.** Turn 1 remains the only place the
palette and type scale are stated as a system, so it is still the source for those.
Its geometry is dead.

**One exception, and only one.** The trade board is built on **2e**, not 3a — a
product-owner call, because 3a's rail does not survive our width. It is recorded in the
supersedes table above and in Pass 7b. If you find another turn where the earlier
drawing looks better, that is a decision to take to the owner, not one to make while
implementing.

### Status legend

✅ done · 🔄 in progress · ⬜ not started · 🚧 blocked on a model

---

## ⚠ Screens still on pre-revamp markup

**Read this before concluding a screen was missed.** Several pages have not been
brought onto the design system yet, and it is not an oversight — they are scheduled.
Verified 2026-08-05 by counting `kb-` classes against inline `<style>` blocks and
`--color-*` legacy tokens; **the six form screens landed 2026-08-06 (Pass 8b)**:

| Screen | Template | Lands in |
|---|---|---|
| ~~Add / edit an item (sell step 2)~~ | `listings/listing_create.html`, `listing_edit.html` | **Pass 8b ✅** |
| ~~Add / edit a collection item~~ | `collections/collection_item_form.html`, `add_from_order.html` | **Pass 8b ✅** |
| ~~Shipping address~~ | `accounts/address_form.html` | **Pass 8b ✅** |
| ~~Collection item detail~~ | `collections/collection_item_detail.html` | **Pass 8b ✅** |
| Almanac | placeholder by design | Pass 14 |
| Staff | not built | Pass 11 |

Passes 5 and 7 built new screens on **either side** of the create form — the three
destination cards before it, the terms panels after it — and left the form in the
middle alone. That is the single biggest visual gap in the app right now.

---

## The design system

Canonical tokens live in `static/css/variables.css` and are consolidated from all
21 turns. Full component vocabulary in `static/css/kb-ui.css`, shell in
`static/css/shell.css`.

**Palette** — Deep Forest `#26331F`, Brass `#A07A26`, Rust `#9C3D1E`, Live Green
`#2F6B34`, Sage `#6D7A5F`, Tan `#8C7A4E`. Surfaces: white cards on a warm page
`#FAF8F3`; **parchment `#F2EEE4` is for grouping and quiet zones only, never the
default card background** — that single rule is what stops every page reading as
one flat beige mass.

**Type** — Petrona 600 for titles, prices, stat figures. Public Sans for all
working text. Page prose 14px; **card and table text is 13–13.5px** — do not
stretch 14px over card UI. `tabular-nums` on every price, count, countdown and
date. Emails use **Georgia, never Petrona** (9a: it won't render in mail clients).

**Three uppercase label sizes, not one** — 10px/0.14em card eyebrow,
10.5px/0.12em field label, 11px/0.09em section eyebrow, 11.5px/0.15em nav.

**Geometry** — 3px controls/chips, 4px cards/panels, 2px checkboxes, 999px only
for toggles and progress bars. Hairlines instead of shadows. Shell: 56px masthead
(158px on home), 44px tab band, 40px breadcrumb trail, 1280px page / 28px gutters.

**Staff is deliberately a different colour family** (17a): slate `#1F2733` + gold
`#C8AD6A` on `#F4F2EE`. *"Nobody should ever be unsure which one they're looking
at."*

---

# Pass log

## Pass 1 — Design system, shell, Hunt, listing detail, My Bench ✅ DONE

*2026-08-04 · commits `7175a74`, `5494684`, `06abf7d`, `fe64113` · 146 tests green*

**Design refs** — turn 1b (palette/type), turn 2a (the settled masthead), turn 1c
screens 1–3, turn 20a (readiness sheet).

**What actually shipped**

| Area | Detail |
|---|---|
| Tokens | `static/css/variables.css` rewritten: 5-step ink ramp, extended brand, four rule steps with the design's two drifted generations collapsed, tonal states, three-tier label system, full type scale, square radii. Legacy names alias through, so squaring five numbers squared the corners on every un-migrated page. |
| Shell | `shell.css` + `base.html`: 56px masthead with keystone mark, four zones, recessed search, message/alert counts, brass **List an item**, square avatar; 44px tab band; 40px brass breadcrumb trail; footer. |
| Zones | `config/urls.py`: `/hunt/`, `/collections/`, `/bench/`, `/almanac/`. `apps/core/context_processors.py` derives `kb_zone` from the resolved view name. |
| Hunt | `HuntView` — format as a multi-select filter with **faceted counts measured with every other filter applied**, local-pickup filter, sub-tabs, sort, removable chips. `/listings/auction-house|general-store|trading-block/` now 301 into Hunt with the format pre-applied, URL names kept. |
| Listing detail | Rebuilt. **Fixed a real bug**: `.listing-detail` was `2fr 1fr` with three children, so the bid panel wrapped below the image, under the fold. Now two children, sticky decision panel, 18 paragraphs → two spec tables, Q&A / bid history / shipping in tabs, quick-bid chips, "Your collection" gap panel. |
| My Bench | `apps/accounts/bench.py` — `needs_you()` reads each deadline back from the same constant the cron job enforces. Progress uses `State.issuance_unit_label`. Workspace tabs replace the username dropdown. |
| Almanac | Honest placeholder at `/almanac/` — nav slot with no model behind it yet. |
| Cleanup | `layout.css` + `custom.css` deleted (24 orphaned pre-revamp shell classes). |

**Deviations and notes**
- Built turn 1's shell first, then corrected to turns 2–21. See the reading rule above.
- **Home still uses the compressed 56px masthead.** The full 158px broadsheet
  masthead is turn 2a and belongs to Pass 2.
- `SHIP_BY_DAYS = 5` in `bench.py` is a promise, not a constraint — no job enforces
  it. Move to `MarketplaceSettings`.
- Listing detail omits the comparable-sales line: no price-history model exists and
  a fabricated comparable is worse than none.
- **Side effect: closes the `data_model` audit's T2 gap** — `item_kind` and
  `addons_attached` now render on listing detail (they previously appeared only on
  collection detail).

---

## Pass 2 — Home, the masthead, the Day Book ✅ DONE

*2026-08-04 · 159 tests green (13 added)*

**Design refs** — turn 2a (masthead), 2b (home signed in), 2c (home signed out).
Dev plan **10.17**.

**What actually shipped**

| Area | Detail |
|---|---|
| Masthead | `templates/components/_masthead.html` — the full 158px broadsheet: 32px strapline (*"Antique hunting licenses of the Commonwealth & beyond"* + date + sign out), 82px nameplate (32px mark, Petrona 33px, `EST. 2026 · PENNSYLVANIA`, 420px recessed search), 42px nav rule on `--kb-forest-deep` with the four zones and a live stat line. `base.html` gained a `{% block masthead %}` so **home overrides, every other page keeps the 56px bar**. |
| Home view | `apps/core/views.py:home` replaces the bare `TemplateView`. Two templates, chosen by auth — a stranger needs telling what this is, a member needs telling what changed. |
| The Day Book | `apps/core/daybook.py` — the ledger, hour in the mono margin. Draws on `Notification`, `Listing.created_at`, `Bid` and `ShipmentEvent`; **no new models**. Your own lines carry an emphasis and a tone (rust = on a clock, forest = yours, plain = news); parcels only surface to the two people they belong to. |
| Signed in | Greeting ruled off in 2px forest · the three marketplace names back **on the goods** · Closing soon (one 1.6fr hero card + three followers) · Day Book · Fresh on the shelves with the just-listed green dot · rail: collection progress, wanted matches, Almanac. |
| Signed out | Genuinely different page: 44px hero, forest stat block, marketplace strip, closing soon, fresh, and a three-step *How it works*. No greeting, no bench. |

**Deviations**
- The two map bands (Your counties choropleth, Hunt by ground) are **omitted, not
  faked** — they are Pass 9. The collection-progress panel carries the meter and
  the gap chips in the meantime.
- **Three questions** panel omitted — no model (Pass 15).
- The Almanac rail panel links to the placeholder rather than featuring a real
  entry (Pass 14).

---

## Pass 3 — Collections zone ✅ DONE

*2026-08-04 · 199 tests green (40 added)*

**Design refs** — turn 13a (browse collectors), 13b (everything owned), 3b
(collector profile), 18a (two of the three defects).

The zone now has **four tabs**: `Collectors` (opens first) · `Everything owned` ·
`Trade board` · `The map` — `templates/components/_collections_tabs.html`, band 2
of the shell. `/collections/` is one dispatching view (`collections_zone`).

**What actually shipped**

| Area | Detail |
|---|---|
| Collectors (13a) | `apps/collections/collectors.py` + `templates/collections/collectors.html`. Sorted by **overlap with you**, never join date. Big card for the ≤8 who overlap; compact card for everyone else; both carry county and size, so **nobody gets an empty card**. Rail: *Worth a look because* (four reasons, with counts), *Where they collect* (state + unit), *Era they collect* (chips), *Collection size* — all faceted the Hunt way, counts measured with every **other** filter applied. |
| Matching (13a + 3b) | `apps/collections/matching.py` — the 10.14 wanted-list matcher pointed at people instead of new listings, exactly as 3b says it should be. Answers both directions: who holds something I want, and do I hold something on theirs. |
| Everything owned (13b) | `templates/collections/browse_collections.html` rebuilt. Every filter kept; three things changed — categories read as **questions** (`LICENSE_TYPE_CATEGORY_QUESTIONS` in `apps/core/constants.py`), choices show as **removable chips**, and **Apply is gone** (it survives only inside `<noscript>`). Favourite count dropped from the card, owner kept — it is the seam between the two tabs. |
| Collector profile (3b) | `templates/accounts/profile.html` rebuilt from a gradient header into a display case with a person attached. Trust card beside the name, captioned display case, **Ground covered** (the 10.14 tracker on a public profile), decade chips over the collection, and the *"looking for"* rail cross-referenced against the viewer's own shelves — **you have one, 1931, mint**. Wants the viewer can answer float to the top. |
| Ground covered | `apps/collections/tracker.py` — units held against units issuing, the year span, and the **deepest unbroken run in one county**. Derived, never stored. Pass 4's matrix reads the same module. |
| Follow | New `accounts.Follow` (migration `0005`) with a unique constraint and a `no_self_follow` check. Not symmetrical, not a notification subscription — 13a and 3b both want the smaller thing: keep this person's case within reach. |
| Defect 1 (18a) | **Fixed.** `static/js/collections-filters.js` fetches first and clears second, so a dropped connection leaves the bar the collector was using intact; on failure it restores the previous state and says *couldn't load Colorado — try again* instead of rendering an empty select over nothing. |
| Defect 2 (18a) | **Fixed.** The multi-select panel is an absolutely positioned child of its filter item instead of a `document.body` append positioned once, so it moves with its trigger and can no longer float over unrelated rows mid-scroll. |
| Data defect found | `core/0004` seeds Pennsylvania's `issuance_unit_label` as *"County (historical); Wildlife Management Unit (WMU since 2003)"* — a true sentence in a field templates render as a **word** ("Any county…", "Counties 52 / 67"). Fresh installs got it; this dev DB happened not to. Migration `core/0009` falls any label carrying `;` or `(` back to `issuance_unit_type`. |

**Deviations, and why**

- **"Sets going"** on the collector card is **counties held** instead. There is no
  `CollectionSet` model until Pass 13; the card keeps the design's three-figure
  shape using a number that is real today. Swap it when 10.14 lands.
- **"Propose a trade"** on the collector card is **"See their case"**. A trade
  proposal today requires a *listing* (`trades:propose` takes a `listing_id`), so a
  button promising a proposal would not have delivered one. It becomes the designed
  action when 10.10 makes tradeability a property of the item — Pass 7.
- **Display-case captions** use the item's own `description`. The design draws a
  separate caption; a dedicated field is a candidate for Pass 4's my-collection work.
- **Badges** under the bio are omitted, not faked — no model until Pass 14.
- **"41 within a hundred miles"** in the header is **N will trade · N selling now**.
  Distance needs geometry we do not have (same reason as the map).
  *(Regained in Pass 9: the card line prints "N miles from you", stated home
  county to stated home county over the topology's centroids.)*
- The **State/County** facet reads *Where they collect*, filtered on their items,
  not on `UserProfile.county` — that field is still free text until Pass 6, and
  filtering people by an unvalidated string would quietly lose collectors.
- The **map tab** says it isn't drawn rather than drawing a control over nothing
  (16b's rule, and the design's own *"Map — no geometry"* screen).
  *(Drawn in Pass 9 — the shapes exist now, so the control may.)*
- **Trade board** leaves the zone for `/hunt/?format=trade` until Pass 7.

---

## Pass 4 — My Bench: the rest of the workspace ✅ DONE

*2026-08-05 · commits `290a8bd`, `e417b3f`, `541bb61`, `d1327f2`, `bfd2dd0`,
`b066bb0` · 309 tests green (106 added)*

**Register debts settled** — `SHIP_BY_DAYS` moved from a constant in
`apps/accounts/bench.py` to `MarketplaceSettings.ship_by_days` (`core/0010`), read
through `bench.ship_by_days()`. **Still owed:** `display_caption` on
`CollectionItem` — the display case reuses `description`, and a dedicated field is
now a Pass 5 candidate rather than a Pass 4 one.


**Design refs** — turn 8a–8e, turn 7a–7d.

> Pass 3 left two things here on purpose: **my collection** (10a/10b — case →
> results → list, bulk bar into selling, group-by, gaps as Map/Matrix/List) reads
> `apps/collections/tracker.py`, which now exists; and a **display-case caption**
> field, if the item description proves to be the wrong thing to show.

### Shipped so far

*2026-08-05 · 236 tests green (33 added)*

| Screen | Commit | What landed |
|---|---|---|
| **My listings** ✅ | `290a8bd` | `apps/listings/seller_desk.py` + rebuilt template. The **Interest** column — offers, unanswered questions, bids, watchers — from data already in the models. Anything waiting on the seller wins its row outright (edge marker, brass tint, the only filled button) **even against a lot closing in twenty minutes**: the reply is the thing that can lose the sale, the auction closes either way. Observations are checkable and hedged — "Quiet — try $170?" only above three watchers, "Nobody has looked yet" below it; relists counted down before they run out. Status chips filter without losing the other counts. |
| **Bids & offers** ✅ | `e417b3f` | `apps/accounts/ledger.py` + `templates/accounts/_ledger_row.html`. One page split by **direction** — *Chasing* / *On my things*; `/offers/mine/` redirects in. Three money columns everywhere: yours, theirs, what it means (`You'd keep $237.50 of it`, `next bid $412`). Row colour carries state: rust losing, green ahead, brass your turn. Withdraw is a POST form — **a bid cannot be taken back, an offer can until it's answered**, and the markup has to say which is which. |

### The rest of what shipped

| Screen | Commit | What landed |
|---|---|---|
| **Orders list** ✅ | `541bb61` | `apps/orders/ledger.py`. One column, not a Purchases card and a Sales card — split that way the two orders on a clock were never next to each other. Every row says **who is being waited on and what happens if nothing changes**, and each consequence is read back from the constant the management command enforces. A test asserts that per status, because a row promising a deadline the job does not keep is worse than no row. |
| **Order page** ✅ | `541bb61` | Eight stacked cards → a header, a **five-stop rail**, and one brass box that appears **only when it is actually your turn**. Two ways to ship side by side. Stripe session id and package inputs deleted. The seller sees what they keep; the buyer sees what they paid and not the commission, which is not theirs to see. |
| **The handshake, offered early** ✅ | `541bb61` | The one real behaviour change in the pass — see below. |
| **Saved** ✅ | `d1327f2` | `apps/favorites/saved.py`. Sorted by what closes soonest, countdown and your own bid state on the card, "forget this" demoted to a quiet foot line. Sold ones stay, greyed, with *Find another* running the same search against live listings. Pieces in other collections say **open to trades** — the item's own flag said literally. |
| **Notifications** ✅ | `d1327f2` | `apps/notifications/centre.py`. **Reading it marks it read**; the per-row form is gone and one honest *Mark all read* sits at the top. One sentence, hour in the margin, and the row's only button is the thing it is about — and only when there is somewhere for it to go. Three dot states and no more. Counts are taken **before** the marking, so the page describes what you are looking at rather than what is left. |
| **Messages** ✅ | `bfd2dd0` | `apps/messaging/threads.py`. Two panes, not two pages. The deal pinned with amount, your side and the live deadline. **Catch the agreement** — the nudge appears only for the person the clock runs against, only while there is time, and only while nothing is on the record. |
| **My collection** ✅ | `b066bb0` | Three views of one collection: everything, **what I'm missing** (the matrix), and the wanted list. `tracker.matrix()` and `wants.rows()`. |

### The handshake — what actually changed

The excuse flow lived on `Strike` and could only be started **after a strike had
been issued**. Nearly every late shipment is a show pickup, a combined parcel or a
buyer who said "no rush" — so the flow only ever arrived after somebody had already
been penalised for something both parties were fine with. That is the difference
between a rule and a fair rule.

`enforcement.OrderHandshake` (migration `0005`) + `enforcement/handshakes.py`:

- One party proposes, the other confirms. **An unconfirmed proposal does nothing** —
  an agreement one person made with themselves is not an agreement.
- **Both enforcement paths honour it**: `enforce_deterministic_policies` skips the
  `non_shipment` strike, `auto_complete_delivered_orders` skips the auto-complete.
  Tested in both directions, with and without.
- **Scoped.** A `shipping` handshake does not excuse a missed `receipt` — whoever
  agreed to wait for the parcel did not agree to that.
- **Lapses in 72 hours**, so a seller cannot park one against every order and stop
  shipping.
- Confirmation is under a `CheckConstraint`: either nobody agreed, or we can say who
  and when. (The same discipline 18a asks for on `Strike` — still owed there.)

### The matrix rule worth keeping

A decade the state was **never issuing in** is hatched, is not a link, and is left
out of the denominator. A gap you could never have filled is not a gap. The floor is
`State.min_license_year`; there is no per-county issuing record, so that is as
fine-grained as the data honestly allows and the module says so.

### Deviations, and why

- **Saved hunts strip** — omitted. Needs a `SavedHunt` model. In the register.
- **Named sets** on My collection (*All items / Resident 1913–1930 / Duplicates*) —
  omitted. Needs `CollectionSet` (Pass 13). In the register.
- **Closing price on a sold favourite** — the row says only that it sold. What it
  made is price history (Pass 12). In the register.
- **"Catch the agreement" does not read the messages.** A machine deciding a
  sentence was an agreement is worse than no feature at all, so the copy stays
  conditional — *"if the two of you have agreed something different"* — and a test
  holds that wording.
- **Import a spreadsheet** (10a) — not built; no importer exists and one is a
  feature, not a button.

---

## Pass 5 — The sell flow ✅ DONE

*2026-08-05 · commits `17ffc57`, `d64072b`, `42028c5` · 327 tests green (18 added)*

**Design refs** — turn 6a/6b/6c (**this supersedes turn 5** — 6's opening line is
*"You're right and 5a was wrong: the destination should be the first question"*).
Dev plan 10.8 amendments, T13.

**It replaced shipped code, as flagged.** `listing_create_config.html` is deleted;
the three-step flow is live.

### What shipped

| Piece | What landed |
|---|---|
| **Step 1 — where it's going** | `apps/listings/sell_flow.py` + `templates/listings/sell_start.html` at `/listings/sell/`. Three destination cards, each ending with **the questions it will ask** — the old config page asked the same thing with two radio buttons and showed no consequences. Below it, **from my collection**, duplicates first: thinning a collection is the common case for a second listing and a duplicate is the piece most likely to be parted with. Something already listed is not offered again. |
| **The "yours or stock" radio** | **Deleted.** It was solving a problem the destination choice solves better. |
| **Step 2 — the item** | `?to=` carries the destination; `?from_item=` carries a shelf item's details across. Reaching step 2 without a destination sends you back to step 1 rather than guessing. The destination is no longer asked twice. |
| **`image_role`** (T13, finally) | On both `ListingImage` and `CollectionItemImage`. "Featured" and "Back" were client-side labels keyed off the array index, so **reordering the grid relabelled the photographs** — a buyer could be told they were looking at the back of a licence when they were not. A partial `UniqueConstraint` allows one front and one back; a second "back" is somebody mislabelling a detail. Roles carry across when an item is listed, so the front stays the front. |
| **Step 3 — the terms** | One panel per destination, carrying only its own fields. The form held all three sets at once and hid two with JavaScript. Each panel ends with the same three things: the action, what it costs to change your mind, and one line of local knowledge. |
| **`Listing.minimum_offer`** | The design's "Nothing under". Wired into `create_offer`, and the message **names the figure** — the seller set a floor to save both of them the round trip, not to hide the price. A seller's counter is not measured against their own floor. |
| **The private block** | `CollectionItem.purchase_price` / `acquired_note` / `private_note`. Never public, never shown to a buyer, and explicitly **not price history** — price history is what listings sold for, this is what you spent. A test reads the public item page and the public profile and asserts none of it leaks. |
| **Edit listing** | Same shape as create, because an edit is not a different decision. One difference that matters: a lot **with bids on it says so**, since it cannot be cancelled and changing terms under people who have already bid is how disputes start. Photograph roles are a visible choice here, so moving one up or down changes the order and nothing else. |

### Deviations, and why

- **The lot route** (*"a box of several licences goes in the other way"*) — not
  built. Needs `ListingLotItem` / `inventory_format` (10.15 + T13's lot
  amendment). Marker in `sell_start.html`; in the register.
- **The collection destination's own terms panel** (public / display case /
  trade / the private block) is **not yet a third step** — those fields live on
  the existing collection item form. The three destination cards all route
  correctly; only the collection panel is still the old form.
- **"Which collection" (folder)** — omitted. Needs `CollectionSet` (Pass 13).
- **Comparable sales** in both selling panels — the design marks them as needing
  Price History (13.6). Omitted rather than faked; the wanted-list count that
  sits beside them **does** work today and is on the wanted list.
- **The prefill read-out** with per-field ✓ / ? / ○ / × is unchanged from what
  `prefill.js` already renders; the design's exact tick vocabulary is a polish
  item rather than new behaviour.


---

## Pass 6 — Auth and the ten settings rooms ✅ DONE

*2026-08-05 · commits `816f922`, `831bb7c`, `cf2d8de` · 351 tests green (38 added)*

**Register debts settled** — `UserProfile.county` is now `home_state` + `home_county`
FKs (`accounts/0006`, data migration `0007`), and the collectors rail asks **which
question you mean**: where they live, or where they collect. **Still owed:**
`display_caption` on `CollectionItem`, and the collection destination's own step 3 —
both moved on to Pass 7.


**Design refs** — turn 4a (sign in), 4b (create account), 4c (all ten rooms),
3c/3d. Dev plan **10.16** (versioned terms).

### What shipped

| Piece | What landed |
|---|---|
| **`home_county` as an FK** | CLAUDE.md has said *"`home_county` is an FK, not a string"* since the start; it was free text help-texted "User's home Pennsylvania county". Now `home_state` + `home_county`, picked from the same unit list the listings use, so a profile can never disagree with a listing about what a county is called. The form only offers units inside the chosen state and refuses a mismatch outright. |
| **The data migration** | Deliberately timid. Only exact matches inside the default state are taken, after stripping a trailing County/Parish/Borough. Anything else stays in the old text column and still shows through `UserProfile.place` — **nobody loses their county to a migration**. The reverse writes the unit name back, so a rollback keeps what the member had. |
| **Sign in / Create account** | `templates/registration/_form_shell.html` + both pages. Nav off, centred nameplate, hatched parchment, `FORM 1 · ENTRY` / `FORM 2 · NEW MEMBER`. "Keep me signed in" added. Password rules as a **ticking checklist** rather than a paragraph of help text or an error after submit — client-side, and the code says plainly that Django still does the checking. **A human at the bottom**: a real address and a promise of a real reply. |
| **Versioned Terms (10.16)** | `core.TermsVersion` + `TermsAcceptance` (`core/0011`). The form had **no checkbox at all**. Enforcement is only fair if you can say what somebody agreed to: a strike issued under 1.3 against a member who joined under 1.1 is not defensible. `PROTECT` on the version so one somebody accepted cannot be deleted; a `UniqueConstraint` so nobody accepts the same version twice. **Nothing is invented when the table is empty** — no published version means no checkbox. |
| **The right-hand column** | Says out loud that an address is needed to sell and a phone to trade — *but not today*. The gating rules are real and good; discovering them at the moment you try to list something is what makes them feel arbitrary. The figures beside it are counted, never rounded up. |
| **Settings — ten rooms** | `apps/accounts/settings_rooms.py`. Four groups (Me · Hunting · Selling · Account), grouped by **whose problem it is**; nothing in two groups. Each room loads only its own work, held by a test. An unknown room falls back rather than 404ing. |
| **Showcase layout** | `UserProfile.showcase_layout` — display case first / map first / one piece at a time / just the collection. On Profile & display. |

### A latent migration defect this uncovered

`collections/0001` declares two FKs as `core.county`; `core/0004` renamed that model
to `GeographicUnit`. `RenameModel` only rewrites references already in the migration
state when it runs, and **nothing pinned the ordering** — so the rename was free to
run first and the state failed to render:

```
Related model 'core.county' cannot be resolved
```

It sat there for six migrations and only surfaced when `accounts/0006` added
accounts→core edges and changed the topological order. Fixed by giving `core/0004`
the dependencies it always needed on the two migrations naming the old model. No
schema change: same table, same column, same constraint.

### Deviations, and why

Three rooms are **honest about what is not built** rather than showing controls that
save nowhere. Each carries a `DEFERRED` marker and says what it does today:

- **Notifications & mail** — per-type email preferences need a
  `NotificationPreference` model. Today everything on a deadline is emailed and
  nothing else is, and the room says so.
- **Alerts & saved hunts** — saved hunts need a `SavedHunt` model. A want does the
  same job for anything you can name, and the room points at the wanted list.
- **Records & export** — the downloadable copy is Pass 10 work. The room gives a
  real address to ask in the meantime.

---

## Pass 7 — Tradeability, the trade board tab, the first board ✅ DONE

> **Read Pass 7b before this section.** The board built here (turn 3a's dark table) was
> **set aside for turn 2e's four columns**. Everything below about the *rule* —
> tradeability, what an auction blocks, the trade board tab — still stands; the screen
> described at the end does not.


*2026-08-05 · commits `e2042bf`, `f41796f`, `7b55937`, `9387830`, `b4da1b1`,
`fb75bca` · 408 tests green (99 added)*

**Design refs** — turn 3a. Dev plan **10.10**.

**Register debts settled** — the **"Will trade" flag** and the **Trade board tab**
are both cleared. **Still owed:** "Propose a trade" as one click, now blocked on a
narrower and better-understood thing (below); `display_caption` on `CollectionItem`;
and the collection destination's own step 3 — all three carry forward.

### The rule, settled

10.10 and the design agreed that tradeability belongs to the item. What they did not
settle was the **default**, and Pass 7 got it wrong once before getting it right:

> **A piece is open to trade from the moment it is recorded** — in a collection or in
> the General Store — and the owner closes the ones that are not going anywhere.
> **Only an auction lot takes a piece off the table**, because an auction is a binding
> commitment to sell to the highest bidder and a trade struck mid-lot takes the goods
> out from under them. A fixed-price shelf carries no such promise, so a Store listing
> keeps all three ways of asking for the same licence: **buy it, offer money for it,
> offer a licence for it.**

The first attempt made `tradeability` three-state (`unset`/`open`/`closed`) so a
universal flag could not advertise something nobody had said. That solved the symptom
by asking a question the product does not ask. `unset` is gone; the field is
`open`/`closed` with `open` the default, and the flag it used to feed became a
**count** instead — see below.

### What shipped

| Piece | What landed |
|---|---|
| **`apps/collections/tradeability.py`** | Availability is **derived, never stored**. `open_to_trade()` (can take an offer today), `would_trade()` (the person-level question — somebody does not stop being a trader because one piece is at auction), `trade_block_reason()` — a sentence, not a boolean, because every refusal a member meets should say what it was. `HELD_BY_A_LOT` is exported so annotations ask the question in the one place it is defined. |
| **The three-state retreat** | `collections/0013` releases `unset → open`, drops it from the choices, and **deletes `trade_eligible`**. The pair still reverses cleanly: 0013 puts the column back before 0012 reverses into it. |
| **The owner's toggle** | `templates/collections/_trade_block.html`, shared by the item form and add-from-order. `tradeability` + `trade_wants` ("what you'd take for it, in your own words"), and a line saying an auction takes it off the table on its own and the Store does not. |
| **A count, not a flag** | With open as the default, "Will trade" would sit on every card again. The collector card shows **N to trade** — pieces you could ask about *today* — which varies and drops as their lots go live. Same figure on the profile chip, and it is the number the chip filters to. |
| **The dark table (3a)** | `propose_offer.html` rebuilt. One dark panel, 196px picker lists either side, 300px rail, light action band. `apps/trades/composer.py` holds the roster arithmetic: every row arrives with a **reason** (*they want this* / *closes a gap* / *duplicate ×2* / *at auction*), and the notes are what the sort reads. |
| **The right roster became a control** | It was a display case you could not pick from. `create_trade_offer` takes `requested_items` and re-checks ownership, public-ness and availability server-side — a hidden input is a suggestion. The listing's own piece is added regardless: it is what you came for. |
| **Cash both ways** | `TradeOffer.cash_direction` (`trades/0005`) under a `cash_amount >= 0` CheckConstraint. The direction carries the sign so no arithmetic has to remember whose side it is on; which strip lights is a question about *who is reading*, answered in `composer.table_for`. |
| **Trades from the General Store** | `TRADEABLE_LISTING_TYPES = ('trade', 'buy_now')`. Listing detail gains **Offer a licence instead** beside Buy now and Make an offer. Auctions still refuse, and that is the whole distinction. |
| **The decision screen** | `offer_detail.html` on the same table, then three weighted decisions — accept brass with a raised edge, counter outlined in forest, decline quietest. Accept goes through a confirmation naming what leaves and what arrives; **without JavaScript it cannot accept, never accepts without asking**. |
| **The struck trade** | `trade_detail.html` restyled: the same table under *What was agreed*, then two parcel panels with **yours first and edged**, because the only question that page answers is whose turn it is. |

### Four live bugs this pass found and fixed

1. **The ratchet.** Listing a piece wrote `trade_eligible = False` and *nothing ever
   wrote it back* — two places set it, four paths close a listing. A lot that expired
   unsold left the piece un-tradeable for good, silently. Deriving means none of the
   four can forget.
2. **Offer history leaked.** `offer_detail` built its thread by filtering on the
   listing alone, so what one proposer was willing to give up was shown to every rival
   proposer. Now scoped to the two people having the negotiation.
3. **Completed trades kept advertising pieces that had physically left.** A second
   collector proposes for a licence that went months ago, the owner accepts, cannot
   ship it, and takes a **non-shipment strike for something that was never theirs to
   give**. `_close_traded_pieces` closes both sides at delivery.
4. **Auto-created collection items had no photographs.** Listing something creates the
   item behind it; a seller who photographed a licence found a blank tile in their own
   collection while the same photographs sat on the lot.

Three more surfaced while wiring the toggle: both forms rendered `form.trade_eligible`
after that field went non-editable, so **the one control the whole rule depends on was
not on the page**; `WantedItemForm.__init__` reached for a `tradeability` field the
wanted list has never had (a `KeyError` on every wanted-item page); and a blank
tradeability was about to save as `open`, which would have flipped a piece its owner
had deliberately closed. It means *unchanged* now, and a test holds that.

### What Pass 7 did **not** do — see `10.10 remainder` below

The separate Trading Block browse and `listing_type='trade'` are still there. Removing
them is a data migration over live listings, not a restyle, and it is the last third of
10.10.

---

## Pass 7b — 10.10 finished, and the board rebuilt on 2e ✅ DONE

*2026-08-05 · commits `eac29eb`, `1b34609`, `7be99a3`, `fa43a48`, `c2ca31f`,
`0775661`, `079b77d` · **456 tests green** (68 added)*

**Design refs** — **turn 2e** (the built board), turn 3a (built, then set aside — see
the override below), 13a. Dev plan **10.10**, remaining scope.

> **Four review rounds.** The first three built 3a and were each rejected on fidelity;
> the fourth switched to 2e. What went wrong is worth keeping, because it is a
> process failure and not a taste one:
>
> 1. **Round one** built from the turn's *prose*, not its markup — implemented every
>    phrase while missing that the licences on the panel are cream cards, which is the
>    stated point of the turn.
> 2. **Round two** took the frame's values but never rendered the page: 429 green tests
>    sat over a grid whose children wrapped onto three lines.
> 3. **Round three** rendered text and read the words — right words, wrong layout.
> 4. **Round four** was the owner pointing out that the layout, not the styling, was
>    the problem all along.
>
> The rule is now at the top of this file: **read the drawing, then render the page and
> look at it.**

### The two knots, untied together

1. **`TradeOffer.trade_listing` was a non-null FK**, so an offer had nowhere to hang
   unless somebody had first put the licence up for sale. Now nullable, with
   **`TradeOffer.subject_item`** as the real anchor: the piece under negotiation.
2. **`Trade.listing` was a `OneToOneField` doing double duty** as the uniqueness
   anchor. Uniqueness moved to **`Trade.offer`**, where it is actually true — one
   accepted offer, one trade — and the *live* question ("is this piece already
   committed?") moved to `services.open_trade_on(item)`, which asks about the **piece**.
   You cannot promise the same licence to two people whether or not either negotiation
   went through a lot.

`trades/0007` fills both new columns from the old ones, so no existing negotiation
loses its subject and nothing is deleted — a trade struck against a lot still reads as
one.

### The screen was two screens, and 3a says it is one

The turn is headed *"The Trading Block — both rosters, the table, the rail, and three
decisions you can't miss."* Pass 7 built it as a composer **with** rosters and a
decision page **without** them, so arriving at an offer — the only way you ever reach
it from a notification — got the half with no table.

`offer_detail` **is** the composer now, opened on the deal as it stands with the sides
swapped for whoever is reading. Answering is *move a licence and send*; the middle
button is the counter. `counter_offer` redirects so old links land, and a settled
negotiation drops the shelves and becomes a record.

### What rendering it found

Two faults no test had caught, because both needed the page actually drawn:

- **The recipient could not counter at all.** The licence they were asked for is
  already on their side of the table and has no checkbox, so the form's *at least one
  offered item* refused every one-for-one. The rule belongs **after** the subject is
  placed; it is in the service now, with both halves checked.
- **The subject appeared twice** — fixed on the table *and* pickable on the shelf it
  came from.

### Fidelity against 3a, on a second reading

| Detail | What changed |
|---|---|
| Roster notes | Fall back to condition when a row has nothing else to say, so the shelves stop reading half-blank |
| Roster count | *"5 tradeable"*, not *"5 items"* — the shelf is what you can put on the table |
| The rail | Says **what moved** (*"added the 1944 Fulton, dropped the 1951 Elk, cash now $40"*) instead of a piece count that makes you open two rounds to compare |
| The subject | Sits on whichever side its owner is — which **flips** on a counter — and is left off that shelf |
| Terms | *"3 for 2"* on the table, *"My 3 for their 2"* in the band |

**One deliberate departure.** The design writes the band as *"My 3 for his 2"*. It says
**their**: nobody on this site has told us their pronouns, and a wrong guess in a
sentence about somebody's property is worse than the neutral word. A test holds it.

### ⚠ The board is built on turn 2e, not 3a — a deliberate override

*Product owner's call, 2026-08-05, after three rounds on 3a.* **This is the one place
in the whole redesign where an earlier turn wins**, so it is flagged here and in the
precedence table at the top.

3a's own reasoning is sound — one dark panel, direction from position rather than
colour. What it does not survive is our width. Measured in the same 1224px well:

| | Space per column |
|---|---|
| **3a** — 196px shelves + a 484px table split into two halves | **241px** a side |
| **2e** — `repeat(4, 1fr)`, no side rail | **295px** each |

That is 40% more room for the licences, and the licences were what had nowhere to be
read. 3a spends a quarter of the page on a permanent rail to serve a glance; 2e puts
the negotiation and the trader **below** the work and gives the whole width to the
four columns.

So the screen is 2e: **your shelf · what you give · what you receive · their shelf**,
four white cards edged and header-tinted by direction (rust leaving, green arriving),
one compact dark bar under them carrying the terms and the three decisions, and the
story strip and trader card below that.

3a's build is in the history at `1b34609` if the call is ever revisited.

### What the four-column build carries

| Piece | From the frame |
|---|---|
| Trader strip | `#f2eee4` band: 34px initials squares, both names in Petrona 20px, brass `↔`, badges right |
| Columns | `repeat(4, 1fr)` gap 14, white cards, `11px 13px` heads, `8px 13px` rows |
| Give / receive | `1px #9c3d1e` / `1px #2f6b34` edges; heads tinted `#fdf1e7` / `#eef3ea` |
| Row marks | 20px bordered `+`, filled `✓` on `#f2eee4` once laid, **nothing** on a held piece |
| **Cash** | **A box at the foot of each side**, with the `$` inside it |
| The bar | `#26331f`, terms `14.5px`, two outlined decisions and one brass |
| Story | `repeat(3, 1fr) 1.3fr` — three rounds and what was said |
| Notes | "Very good · on the table" · "Matches their wants" · "Closes a county gap" · "Listed in the Auction House" |

`--kb-hatch` on empty thumbnails, so a licence nobody has photographed reads as
un-photographed rather than broken.

### One click, at last — and to the right place

The three Pass 3 markers are cleared, but not the way the first build did it. There are
**two ways in and they mean different things**:

- **`trades:propose_on_item`** — you clicked a licence. It is on the table when the
  screen opens.
- **`trades:propose_to_person`** — you clicked a collector card. **The table opens
  empty.** The card picks a piece to *link* to; you did not choose it, and laying it out
  and calling it "what you came for" put words in your mouth. The negotiation is filed
  under whichever licence you actually ask for first.

### Corrections after review — five were logic, not styling

1. **The timeline merged separate negotiations.** It grouped every offer the same two
   people ever made about one licence, so two independent negotiations — ordinary after
   a decline — read as one history with three "Opened" rows. A negotiation is a
   **chain** linked by `counter_to`; `thread_offers` walks it and nothing else joins.
2. **"Closes a county gap" on every row.** Against an empty collection every county is
   a gap. It now needs a map to be a hole in, and a wanted-list match outranks it.
3. **Trade offers never reached Bids & offers.** The ledger read `Bid` and `Offer` and
   nothing else, so a sent trade left no trace on the bench. They sit by direction like
   everything else, with "3 licences" where a price would go.
4. **Revise-and-resend left the original live.** Only a counter *from the other chair*
   superseded the previous offer, so revising your own put two live negotiations about
   one licence on the bench — either acceptable.
5. **Public ≠ tradeable.** The other trader's shelf filtered on both, hiding every piece
   somebody had opened to trade and simply not put on show.

Plus: the subject piece got an `×` like everything else (the design draws one on every
card, and its own second round is *"asked for the 1944 Fulton instead"*); real
drag-and-drop, since the panel says drag; `user-select: none` so a drag stops
inverting the row's text; a 650ms hover card with a 4:3 image; and an "Offer for it"
label on the trade board changed to **"Propose a trade"**, because *offer* reads as
money and nothing there is for sale.

### Three deliberate departures from the drawing

| The frame | What shipped | Why |
|---|---|---|
| "0 strikes" beside the trader's name | **omitted** | Enforcement is between a member and us. Publishing a record turns a private penalty into a public one. Verified and completed-trade counts stay — those are theirs to advertise |
| "My 3 for **his** 2" | "for **their** 2" | Nobody here has told us their pronouns |
| "Reply to Walt…" over a box | the cell shows **what was said with the offers**; messaging moved to the trader card | It invented a conversation that had not happened — Walt has never written to you |

### Still open, and now genuinely small

- **`listing_type='trade'` itself.** Already unreachable — the sell flow's three
  destinations are collection / auction / store, and nothing creates one. Retiring the
  *enum* is a data migration over historical rows with `Trade` FKs pointing at them,
  which buys nothing today. Left alone deliberately; see the register.
- **Shared carrier/service** across both shipments (register).
- **Composer search without JavaScript** (register).

---

## Pass 8 — Letters, Q&A, reviews, reporting, appeals 🚧 IN PROGRESS

**Design refs** — turn 9a (emails), 9b (Q&A + reviews), 9c (report + appeal).
Dev plan **10.13**.

> **Where it stands:** letters ✅, Q&A ✅, reviews ✅ — **9a and 9b are done**.
> Only **9c (report + appeal)** is left, and it is blocked rather than
> unstarted: see the entry at the foot of this pass. Two letters are sent by
> nobody yet and are in the register with their triggers named.

- **One email shell, seven letters** ✅ **done 2026-08-06** · 535 tests green
  (27 added) · **six of the seven sent; two more registered, not dropped.**

  The charge was exact, not rhetorical: `templates/emails/notification.html`
  really did print `{{ notification.get_notification_type_display }}` as its
  heading with `{{ notification.message }}` pasted under it, closing with
  *"Please do not reply to this email."*

  **The fix was one level below the templates.** `send_notification_email`
  passed a letter only the notification, the user, and a URL **scraped out of
  the message text with a regex** — so no letter *could* say "Your bid was
  $390. It is now at $402." A prettier wrapper would have changed nothing.
  `apps/notifications/letters.py` is the missing half: one builder per letter,
  each resolving the real record (a `Notification` carries no FK to its
  subject — only a `link_url` like `/orders/12/`) and returning what the shell
  needs. Every builder fails soft to the plain letter, because these run in a
  cron job and one bad row must not stop the post.

  | Letter | Says |
  |---|---|
  | Outbid | your bid, the new bid, the close time and the countdown; the button is *Bid $412.00 and stay in it* |
  | Won | won-at, from whom, after how many bids, the total with shipping to your town; brass *Pay $220.40*, and the 24-hour consequence in bold |
  | Ship-by | who paid and when, the derived date, and the three ways out (label here / own postage / handshake) |
  | Sale made · Ended unsold · Payment went through | the same shell with their own headline and item block, as the designer says they should be |
  | Everything else (~30 types) | the shell, honestly filled — the first sentence becomes the headline, and the button borrows the **notification centre's own words** so the letter and the in-app row can't disagree |

  **The shell is tables and inline styles, not flexbox** — the honest
  translation of a design drawn in a browser, since Outlook and much of the
  mail estate read neither `display:flex` nor a `<style>` block. Every value
  is the frame's: 560px, Georgia, `#26331f` bar, `#fdfcf8` ground, the 88×68
  thumb, the hairlines. Nothing depends on an image loading, and the plain-text
  alternative is now **the same letter with the markup off** rather than the
  raw message string. `[KeystoneBid]` is gone from the subject: the sender name
  already says who it is from, and the front of a subject line should carry the
  item and the number.

  **Three faults the render caught that the tests did not** — worth recording,
  because it is the same lesson as the trade board: *"after one bids"*; HTML
  entities (`you don&#x27;t`) leaking into the plain-text part; and a county
  count that read **68 counties** for a 67-county state. All three now have
  tests. The third became a register entry rather than a patch.

  Seven old templates deleted (`emails/notification.html` and the six per-type
  ones); the `_extract_first_url` regex went with them.
- **Q&A** ✅ **done 2026-08-06** · commit `961c5e6` · 501 tests green (13 added).
  Answers indent 39px under their questions with the seller marked in brass
  (*"Harold Kreider, the seller"*); an unanswered one is visibly *waiting on an
  answer*; the head carries the count and the seller's **answer habit** ("answers
  within the day" — median over ≥3, and it says nothing rather than something
  damning below that). **Price talk is hidden the moment it is asked**
  (`qa.is_price_talk` — dollar figures and the stock haggling openers), shown only
  to its asker with the one-line norm and a *Make an offer instead →* link (the
  bid-box sentence on auctions); the seller is never notified, and hidden
  questions stay out of the public count. Flag became a quiet **Report** word on
  entries (the existing flag flow, reworded); the ask box ends with *write to
  them instead*, a real POST into Messages carrying the listing. Bylines are
  **M. Yoder** short forms — `initials_for` moved to `accounts.identity` (composer
  re-exports) and gained `short_name`; both are template filters now. One copy
  departure, standing: *"write to them instead"*, never "him" — pronouns are not
  guessed here. `django.contrib.humanize` joined the apps for the *yesterday /
  2 hours ago* bylines.
- **Reviews** ✅ **done 2026-08-06** · 508 tests green (7 added). The three words
  become **Good / Middling / Poor** at the model (stored keys unchanged — a label
  migration, so every display site changes at once; the derived *"98% positive"*
  summaries keep their phrasing). One shared card, `reviews/_review_form.html`,
  now serves **both** order and trade detail so the two can never drift: title
  asks about the counterparty by name, each option carries the line describing
  the deal it fits (role-aware — a seller reviewing a *buyer* reads "Paid on
  time, easy to deal with", not "packed it well"), the 255-character line has
  its counter, and the footer says both halves — *you can't change it
  afterwards* (true: no edit route, second submits turned away) and *a review
  isn't a complaint*. The **report-it word is deliberately not a link yet** —
  9c's Report model doesn't exist, and this document does not draw controls
  over nothing; when it lands, the sentence gains its link. A left review
  renders as the record it is: *"You said Good — '…'. A review stands as
  written."* Trade detail's hand-rolled pick row (which rendered a `---------`
  radio) is gone with its orphaned CSS.
- **Report / Appeal** ⬜ **BLOCKED, not skipped** — both 10.13, neither built.
  **Blocked on:** there is no `Report` model, and the appeal screen needs to
  bind to a `Strike` with its due date, marked date, expiry and prior-count
  (`apps/enforcement` has `Strike`, so the appeal is the nearer of the two).
  The design draws both fully — five report categories, four appeal reasons,
  the *"a person reads every one of these"* acknowledgement, and the rule that
  **standing is suspended while an appeal is open**.
  **Clears when:** the `Report` model lands (10.13 proper).
  **Then also:** the Q&A entry's quiet *Report* word and the review card's
  *report it* sentence both currently go nowhere by design — they should point
  into this flow the day it exists.

---

## Pass 8b — The forms nobody restyled ✅ DONE

*Completed 2026-08-06 · commits `bbc04ad, cc5d095, 4cb74ed, 29db9b4` · 488 tests
green (17 added). Raised in review 2026-08-05 and confirmed: the create/edit forms
were never brought onto the design system — Passes 5 and 7 built new screens around
them and left the middle alone.*

**Design refs** — turn 6b (step 2, the item), turn 5b (the collection room — its
*flow* died with turn 6, its *form body* is the only drawing of the collection
variant), 10a/11b (field grammar), 4c. Dev plan **10.8**, T13.

### What each screen became

| Screen | Built |
|---|---|
| `listing_create.html` | The 6b floor: 400px evidence rail (photograph slots, the read-out, the buyer's card) beside the work column. Taxonomy out of the drawer — seven plain selects under *"The detail collectors filter on"*, labelled the frame's way (*Who it was for*, *What it allowed*…). Condition is a chip ladder with no blank rung. Pass 5's `sl-terms` tail kept as-is. |
| `listing_edit.html` | Same floor. Photographs stay a **row list** rather than slots — on an edit the roles are settled facts (*a back stays a back*), and the rows say what each file is instead of re-asking. A deliberate reading, not a miss. |
| `collection_item_form.html` | The 5b room: five slots (front lives in the formset with its role, so it keeps its meaning if the piece is ever listed), the **written-for-you title panel** with its *Write my own* escape, the finer-detail drawer, then *Where it stands* — visibility, the trade block, disposition (edit only), and the **private block** that existed on the model but nowhere on a form. |
| `add_from_order.html` | One-column variant: the purchase up top on parchment, your-own-eye condition, the listing's photographs copying across on their own. |
| `collection_item_detail.html` | A specimen sheet: plates left with each photograph naming what it is, the record right, availability tags that say **where a departed piece went**, the owner's ledger on parchment. A departed piece loses its Sell button. |
| `accounts/address_form.html` | The slip. Places moved out to `static/js/address-autocomplete.js`, and **the failure is said aloud** — one quiet line under the street field when the script can't load, instead of a search box that does nothing. |

New furniture: `static/css/pages/item-form.css` (the `if-*` set, shared by all four
forms), `static/css/pages/collection-item.css` (`cd-*`), `static/js/item-form.js`
(slots, live preview, completeness-with-advice, the self-writing title — everything
degrades to plain inputs without JavaScript). `prefill.js`'s panel now renders the
drawing's plain list — tick, question mark, chip, miss — with *Use it* / *Suggest it*
in place, and flags the filled field in brass until cleared.

### The two riders, landed

- **`CollectionItem.disposition`** — `held / traded / sold_elsewhere / given_away /
  lost`. Anything but held blocks `open_to_trade` *and* `would_trade` at the source,
  and the shelf label is simply the disposition's own words. `_close_traded_pieces`
  now writes `disposition='traded'` **instead of** `tradeability='closed'` — the
  owner's standing answer is not what changed; the piece left. `traded` is never a
  form choice; a silent form keeps the recorded value (same rule as tradeability).
- **`issue_class`** — its own taxonomy category (*Special Issue, Limited Edition,
  Commemorative* + the Other flow), seeded through the pipeline like materials
  (`ISSUE_CLASSES` in `clean_reference_data.py`; regen was lossless, `created=4
  drift=0`). Threads everywhere the other six go: both forms, the API grouping, the
  rail. Both forms' taxonomy rows now come from **one constant**
  (`FORM_TAXONOMY_FIELDS`) so the labels can never drift again.

### Corrections to the record while in here

The data-model plan's 2026-08-03 audit said `image_role` didn't exist and listing
detail never showed T2. **Both were stale by the time this pass opened** — the
schema shipped with Pass 5's sell-flow work (listings `0019`, collections `0010`,
one-front-one-back constraints included) and listing detail already prints *Form*
and *Add-ons: still attached*. This pass finished the half that was genuinely owed:
a slot UI that **persists** the roles it shows. The audit notes are corrected in
`data_model_img_prefill_plan.md`.

### Deliberate departures from the drawing

| The frame draws | Built instead | Why |
|---|---|---|
| A **Restored** chip beyond a divider on the condition row | The eight-rung ladder only | The designer's own note says restored *isn't a rung* — "a repaired item can still be Excellent". That's a separate boolean wanting its own filter (10.11), card badge, and `WantedItem.repairs_ok` — one family, in the register. **CLEARED (Pass 9b)** — `is_restored` on both models, the divider drawn, the detail page prints it; the Hunt filter + card badge + `repairs_ok` stay with 10.11. |
| *"Save and come back to it"* secondary button | Omitted | There is no draft feature. Never draw a control over nothing (16b's rule). Register, with lots/drafts work. **CLEARED (Pass 9b)** — `Listing.status='draft'` exists; both step-2 buttons save one. |
| A separate **Condition description** box beside Serial | One Description field, placed per each frame | The model has one text field. Splitting it is a schema call nobody has made. **CLEARED (Pass 9b)** — the call got made: `condition_description` on both models. |

---

## Pass 9 — The map ✅

> **Status (2026-08-26): DONE.** Six commits on `feature/alpha-p4-pass9-map`.
> 556 tests green (21 added). Three register rows cleared: the Collections
> map tab, the profile's Ground covered figure, and the counted county gap in
> the outbid letter. The collectors browse regained its distance line.

**Design refs** — turn 9e (at size), **9f (the specimen sheet)**, and the
**Backtag map plates** (`Backtag Map Plates (standalone).html`, same folder —
note the repo's `Backtag Design Blueprint.html` is a *different* export and
contains no map). Dev plan **10.17**.

### What shipped

- **The data ships with the house.** us-atlas 3.0.1 `counties-10m.json`
  (3,231 counties keyed by FIPS, 842KB → 244KB gzipped), d3 7.9.0 and
  topojson-client 3.1.0 are committed under `static/` and served by
  WhiteNoise — the old browse map died fetching all three from a CDN at page
  view, and that failure mode is gone by construction.
- **`apps/core/ground.py` owns "what is real ground".** A county-type unit is
  real when it has a FIPS shape; PA's *Out-of-State* (code 68) and the
  Statewide row are records, not ground; a GMU has no FIPS and is still real.
  `/api/map/` serves both lenses keyed by FIPS — per-state and per-unit
  listed/owned/collectors, with statewide and unplaced listings **counted,
  never silently dropped** — and `?collector=` only ever shows another
  member's public pieces.
- **One component, two lenses, three depths** (`static/js/ground-map.js`,
  vanilla ES6). The 9f/plates reconciliation: they are the same map through
  opposite lenses. *Listed* lens = 9f (fixed buckets 0/1/2–4/5–9/10–24/25+,
  brass **inner rule** on held ground, "Only my gaps" toggle). *Owned* lens =
  the plates (0/1/2–3/4+ per county, 0/1–19/20–99/100+ nationally, gold
  **hatching + brass ring** for for-sale-on-unowned, nearest-gaps card via
  `topojson.neighbors` — adjacency free from the topology). Country → state,
  no third zoom; the panel is the click target; an empty county still opens
  it. No basemap, no pins, no draw-in, no shadow but the tooltip's.
- **Four surfaces, one include** (`components/_ground_map.html`): the Hunt
  tab (`/hunt/map/`, lands at state depth per 9f), the Collections tab
  (opens on the state the collector mostly collects, lens chips *My
  collection / For sale now*), the profile's Ground covered (small,
  collector's own state, public wall respected), and the foot of both home
  pages (small country, listed lens, click-through — dev plan 10.17).
- **Distance regained** — `utilities/build_county_centroids.py` distils
  3,231 centroids from the same topology (verified against real county
  centers), and the collectors card prints *"N miles from you"*, stated home
  to stated home, only when both homes have shapes.
- **The counted county gap restored** in the outbid letter, three registers
  deep: first piece in a state keeps *"That would be your first Sullivan"*,
  a collection under way gets *"one of the 26 counties you don't have yet"*
  (honest denominator at last), and one remaining gap is told it is the
  last. A pseudo-unit names no gap.

### Decisions and departures

- **Lens per surface, not a new drawing per surface** — the plates' chip row
  is read as a lens switcher over one component, which is what "the same
  component sits small at the foot of the home page" already demanded.
- **Selection style** follows 9f's *Chosen* (dark border + outer brass ring)
  in both lenses, over the plates' rust outline — 9f is the specimen sheet.
- **Albers at both depths** (geoAlbersUsa / fitted geoAlbers), over the
  plates' single-state Mercator, so state shapes match the national view.
- Plates rows **not built and registered instead**: the *"Almanac entry —
  Written"* card row (no Almanac exists) and the *Open to trade / Resident
  hunter / year-range* chips (need filter support in the endpoint).
- Old `?view=map` machinery deleted outright (153 template lines + the whole
  `show_map_toggle` branch), per dev plan 10.17's "no map on browse pages".
- The test that guarded the honest placeholder now guards the drawn map.

---

## Pass 9b — The add flow, straightened ✅

> **Status (2026-08-26): DONE.** Eight commits on
> `feature/alpha-p4-update-add-item`. 594 tests green (38 added). Opened by a
> screenshot of step 1 rendering as one giant uppercase brass button; closed
> with turn 6 built as drawn end-to-end plus the **Add Item Ideas** ledger
> (`Add Item Ideas (standalone).html`, committed beside the plates file).

**Design refs** — turn **6a/6b/6c** (the three steps), **Add Item Ideas
turns 4a–4e** (the ledger, the animations, the line bank, the build mapping).
Dev plan 10.8/10.9/T13.

### The bugs the review found (all fixed)

- **`.kb-sell` named two things** — the topbar's gold button (shell.css) *and*
  step 1's `<main>` (sell.css). The whole page inherited uppercase, brass,
  letterspacing and `nowrap`, and `display:none` under 900px hid it entirely on
  mobile. The page container is `.sl-page` now.
- **The "My collection" card was a dead loop** — `listings:create` only knew
  `auction`/`buy_now` and bounced `?to=collection` back to step 1. **"Sell
  this" was a loop too** — no destination, so it bounced to step 1 with the
  title in the search box.
- **The photo slots staged files into thin air** — the formset prefix is
  `additional_images`, the slot config said `#id_images-…`; back and detail
  uploads never bound.
- `listing_create` had no `@login_required` (and `sell_start` had two);
  error re-renders dropped `step`/`destination`; `trade_notes`/`allow_cash`
  sat in the form unrendered; editing a live auction silently recomputed
  `auction_end` (every edit reset the clock); `sell_flow.prepare_from_item`
  was a second, dead copy of the carry logic.

### What shipped

- **Step 3 is a page** (`/listings/<pk>/terms/`). Step 2 saves a **draft**
  (new status; browse never sees one, detail 404s strangers and walks the
  owner to the terms, My Listings grew a *Drafts* chip with *Finish the
  terms*) and its foot reads *Set the terms* / *Save and come back to it* /
  *Nothing is public until step 3 is done.* The terms page carries one
  destination's panel — auction: starting price, brass-ruled reserve,
  runs-for, smallest raise, a computed closes-line, relist + later-start
  switches; store: your price beside a computed **You'd keep**, offers with a
  floor, **Open to trade offers too** writing `tradeability`/`trade_wants`
  onto the piece — then the shared *Getting it there* strip, *What the books
  say* (the wanted-list count works today; comparable sales stay with 13.6),
  and the only publishing button on the site.
- **The third door opens** — the collection card lands on the collection item
  form wearing the flow's clothes (rail, breadcrumb, no selling gate), and
  its step 3 is the collection panel: profile, display case (six, enforced),
  trading, and the only-you block — fields the model already had. Step 2
  pops those fields so absent checkboxes can't read as "no". The CTA line
  says *"This closes your Sullivan gap — 42 of 67 counties"* only when the
  FIPS-real ground says it's true.
- **Condition, in two parts** — `condition_description` and `is_restored` on
  both models, the divider drawn, carried across every copy path, printed on
  the detail page. Grade labels dropped to sentence case per the frames.
- **The ledger** (Add Item Ideas 4a–4e) — four panel states off
  `PrefillJob.status`; typed Petrona lines from the reviewed bank
  (`prefill/config/ledger_lines.json` + `era_facts.json`; the red winks stay
  held); 4×1.5s with the early-cut, 8s hold and 12s plain-words rules; the
  tally (*N filled | M to check | K for you*, no "0 to check"); ✓/× per
  flagged row writing `PrefillCorrection` on click with five seconds of undo;
  the lock that never touches condition or material and never blocks Save;
  loupe/scan/sleeve on the front slot by job id, a still *READING* for
  reduced motion. **Material came off the read** — a photograph can't feel
  card from celluloid, so it counts among the "for you" blanks instead.
  `job_state` gained `line_facts` (unit vocabulary + two precomputed counts)
  so no line ever queries on its own.
- **The shelf skip** — *Sell this* lands on the short review (the item in
  two lines, the two selling doors); choosing one writes the draft straight
  from the shelf record and walks to the terms. Coming back resumes the
  draft; a live lot turns you back at the door. The terms page opens with
  the same two-line summary so terms are never set blind.

### Decisions and departures

- Items born from a *selling* draft start `is_public=False` and step into
  the light when the lot opens — an abandoned half-description must not sit
  on a public profile (6a's "created unpublished", applied).
- A live auction's edit page no longer offers *Runs for* or a go-live date —
  the clock question was answered when the lot opened.
- The step-1 shelf keeps its four-column grid and "All N items" as a link
  rather than a fifth tile; the lot line stays deferred with the lot route.
- **New register rows**: the store panel's *Cash either way / Items only*
  chips (need a home on the trade-offer flow, not `trade_wants` prose); the
  Restored **Hunt filter + card badge** and `WantedItem.repairs_ok` (10.11
  family); the auction panel's *"What the books say"* sales sentences
  (13.6, drawn with its own deferral note).

---

## Pass 9c — The add flow, made usable ✅

> **Status 2026-08-26** · 8 commits on `feature/alpha-p4-update-add-item`
> (stacked on Pass 9b) · full suite **617 green** (23 added) · 14-probe
> render-and-flow sweep on dev data clean. Driven by the owner's field
> report of the built flow — a dozen-plus bugs and design divergences,
> checked line-by-line against 6a/6b/6c and the Add Item Ideas standalone.

### The bugs the field report found (all fixed)

1. **The foot buttons looked dead.** An invisible non-field rule ("select
   at least one taxonomy attribute") rejected every step-2 save with
   nothing to point at. Drafts now save as thin as a title; the full
   requirements moved to `publish_gaps()` at the terms page — the only
   button that publishes ("required-to-publish fields gate publishing").
2. **The kept-upload notice loop.** A failed submit showed an ugly notice
   box with the thumbnail *outside* the slots ("0 of 5"), and the session
   stash never expired, so it haunted every later walk-up. Kept uploads
   now hang back **in their slots** (`data-kept`), the × really discards
   (`discard_kept`), a fresh GET clears the stash, and the retry POST
   re-attaches the file server-side. Collections create gained the same
   stash (its failed submits used to drop the photos silently).
3. **Reordering a photo duplicated it.** Slot thumbnails were natively
   draggable; Chrome synthesizes a File from a dragged `<img>`, and the
   panel's drop handler re-added it as a new upload. Thumbnails no longer
   drag natively and the panel ignores drops mid-reorder.
4. **Drag-and-drop dead on slots 3–5.** The detail slots' drop handler
   only understood internal reorders and swallowed OS files. Every slot
   now takes a file aimed at it, front and back included.
5. **The shelf offered items already up for sale** — including the quiet
   shelf records a marketplace listing writes behind the scenes. Anything
   with a draft/live/scheduled/pending listing stays off the shelf; its
   home is My Listings.
6. **The year hint quoted the wrong state** ("Pennsylvania: 1913–2001"
   under a Maryland item) and **PA arrived pre-chosen**. No default state
   ("Choose a state"); the hint names only the chosen state and rewrites
   client-side on change.
7. **"written for you · edit freely" before anything was written.** The
   note now appears only once the title has actually been machine-written
   (4a's own demo script does exactly this) and leaves when edited.
8. **The hint wall.** 6b's note verbatim: "the hint appears on the field
   you're in and nowhere else." Hints hide by default; focus-within,
   errors, flagged reads, and the two marked --stay (material, Restored
   explainer) show theirs. The vertical sprawl came mostly from this.
9. **Collections step 2 was still the Turn-5 drawing** — title in its own
   panel, taxonomy in a drawer, and a *required Resident status hidden
   inside the drawer* (the same invisible-rule trap as #1). Rebuilt to
   the 6b column; `resident_status` retired from the form.
10. **No navigation, no way out.** The 1·2·3 rail is links now; step 2
    has Cancel/Leave-it; the terms page moves a draft between the Auction
    House and the Store, walks it back to "Keep it in my collection", or
    discards it — a discard parks the described item on the shelf.

### The ledger, re-checked against 4a/4c/4e

- **Rows arrive one at a time** under the typed line while the read runs
  (4c: "the panel grows to the size of the answer") — they used to appear
  all at once at settle. Fields still fill together with the flash.
- **4e's tier treatment corrected**: high AND medium render green with
  *change*; amber (✓/×) is only near-floor matches, second-pass rescues,
  and inferences. The server computes a per-field `check` flag in
  `resolved_payload` (it alone knows `FUZZY_FLOOR`/`GEO_NAME_FLOOR`).
- **Never overwrites your hand**: a dirty field that disagrees with the
  read becomes a ○ *Use it* row instead of being overwritten — the answer
  to "what if there are user-entered fields?".
- **A changed front photograph re-reads** (token-guarded, one live run);
  removing it mid-read aborts back to state 1 (no photograph → no panel).
  The settled foot carries 4a's "Clearing a line empties the field." +
  **Read again**, so a re-read never waits for a failure.
- The ledger scrolls into view when a read starts — it was below the fold
  at exactly the moment it had something to say.

### Decisions and departures

- **Owner's call (2026-08-26), supersedes 6a's note**: selling from the
  shelf no longer skips to the terms. The door-picker writes the draft
  server-side as before but lands on **step 2 filled in** for a look-over
  ("what if the user wants to change something").
- The Turn-5 photographs copy ("Front and back are fixed slots…") was
  retired everywhere — it had been lifted from the superseded 5b frame;
  6b/4a's lines ("Pin, printing, stamps", "Drag to reorder these three")
  stand in its place.
- Loose records: the at-least-one-attribute and era-when-yearless rules
  are gone from the collections form entirely (a shelf record is the
  collector's own catalogue) and gate only *publishing* for listings.
- Small known limit: on a saved draft, the reorder gesture moves freshly
  staged detail photos; already-saved details hold their order (server
  `sort_order` — same as the edit page).

---

## Pass 9d — The field report, round two ✅

> **Status 2026-08-26** · 7 commits on `feature/alpha-p4-update-add-item`
> (stacked on 9c) · full suite **622 green** (5 added) · the owner's
> second field report, item by item, this time reproducing each failure
> with the exact requests a browser sends before fixing it.

### The dead button, found for real

`Slots.sync()` wrote `image_role` + `sort_order` into **every** formset
row whether or not a file was staged. Django counted those rows as
changed, demanded their required image, and rendered the four errors
only inside the hidden native inputs — so *Set the terms* reloaded the
page with nothing visible anywhere. (9c's loose-drafts fix had removed a
*different* blocker; this one survived because the pass never submitted
a browser-shaped POST.) Fixed at three layers: sync() marks only
occupied slots; the image forms' `has_changed()` reads a role without a
photograph as an empty slot; the error band prints per-row photograph
errors. Pinned by `TheBrowserShapedPostTests`. Drafts' home is now named
in the save message (My Listings → Drafts).

### LOOK AT THE DESIGN — the items taken verbatim this round

- **The 1·2·3 rail moved into the breadcrumb band, right-aligned** —
  4a/6a/6b draw it there ("1 · The Auction House ✓ — 2 · The item — 3 ·
  The terms"), not as its own row. The invented step-2 h1 + lede ("The
  item / Going to…") is gone: the frames start straight into the
  two-column floor. Both were why the ledger sat below the fold.
- **4a's microcopy exactly**: Description says *yours to write* (turning
  into the character count only once there is something to count) with
  4a's placeholder; Condition says *yours to grade — the read never
  guesses this*; the condition note's placeholder is the
  foxing-and-pins line; Material's hint is *Yours — a photograph can't
  feel card from celluloid*; the era select is labelled **Era**. Both
  textareas at the frame's two-line height. No paraphrase survived.
- **One instrument per run**: the scan overlay no longer switches
  variants when the job id lands mid-read (loupe→scan mid-look read as
  a glitch). The attempt seed varies it between runs, which is what
  "picked by job id, so a retry shows a different one" was for — noted
  as a mechanism departure (the local backend only knows the job id
  when the read is already over).
- **Cancel on the collections create** foot, same as the marketplaces.
- **"Is a value missing?"** is a quiet brass line opening into a bounded
  card, not a page-wide band.

### The ledger's remaining rough edges

- **Reordering was stuck**: the 9c fix (`img.draggable=false`) stopped
  native image drags but also blocked drag *initiation* from filled
  slots. The thumbnail is pointer-inert now (`pointer-events: none`), so
  drags start from the slot button — reorder works, duplicates stay
  dead.
- **"Suggest it" where "Use it" belonged**: a read the backend couldn't
  match may still name something that exists in the form's own options
  ("Nonresident" beside Non-Resident, "Statewide" beside the statewide
  row). Those recover into ○ *Use it* rows at settle; *Suggest it*
  remains for the genuinely unknown (its rows do work — they write a
  ReferenceDataSuggestion and flip to *Sent ✓*). `resolve_geo` also
  reads "Statewide" written as the unit *name* as the statewide answer.
- **A failed submit no longer erases the ledger**: the server hands the
  completed job back (`resume_state_json`, owner-checked) and the panel
  settles straight in describing the values the form kept; flagged rows
  return accepted, because submitting was the confirmation.

---

## Pass 9e — The Auction House runs itself ✅

> **Status 2026-08-26** · 5 commits on `feature/alpha-p4-update-add-item`
> · full suite **660 green** (38 added) · live-flow sweep on dev data:
> bid → extend → lazy close → winner panel → Settled row → Just-closed
> strip → anon outcome, all clean. Driven by the owner's field report of
> a won auction that never closed, and their sign-off on three calls:
> **proxy as the single mechanic**, **soft close**, **Just closed at 24h**.

### What the review found (and this pass fixed)

1. **Nothing closed in dev, and the close was cron-only.** The pipeline
   existed (winner, reserve, order, letters, relist) but only cron ran
   it. Now `close_auction()` is a service — row-locked, idempotent — and
   the detail page, the `bid_status` poll, and Bids & offers all close
   **lazily** the moment somebody looks. Cron (`close_auctions`) sweeps
   the unwatched; `manage.py run_jobs [--loop 60]` is the dev stand-in.
2. **A stale order could steal the win.** `Order.listing` is OneToOne
   and the close did `get_or_create(listing=…)` — a leftover paid order
   (from a T8 render-probe fixture that didn't clean up) would have been
   silently adopted as the sale of a $775 win. The close now refuses any
   order that isn't the winner's own pending one, logs loudly, and
   leaves the lot for a human. Probe fixtures deleted; probes must clean
   up after themselves (memory noted).
3. **Self-outbidding.** Dissolved by the mechanic change below.

### Proxy bidding — the one mechanic (owner's call)

`ProxyMax` holds each bidder's private standing maximum; visible `Bid`
rows stay what the room heard, with `is_proxy` marking automatic answers
("· auto" in the history). Resolution is eBay's: price moves one
increment at a time, ties keep the earlier hand, a maximum covering the
reserve jumps the price to it, the winner pays the standing price. The
leader entering a higher number just raises their ceiling. The bid box
reads **Your maximum bid** with a ?-popout explaining the mechanic; the
losing-volley toast is a *warning*, not a celebration. (dev_plan's
"Proxy Bidding — auto-bidding up to max" future item: **done**.)

### The last five minutes (owner: "state of the art")

- **Soft close**: any bid inside the final **2 minutes** resets the clock
  to 2 minutes (losing volleys included). Effectively **unbounded** —
  owner's call 2026-08-26: each reset demands new money on a binding
  bid, so a war converges on its own; `SOFT_CLOSE_CAP = 100` remains as
  a backstop against pathology only (~3 hours of continuous bidding,
  which no honest lot will see). Announced three ways: the bidder's
  toast, the page's "Extended — two more minutes for everyone", and the
  clock line's "extended ×N".
- **The room**: `bid_status` carries server time, the recent-bid feed,
  extensions, the viewer's standing, and the outcome in one payload.
  Polling paces itself — 10s far out, 5s inside ten minutes, **2s inside
  the window**, 30s when the tab is hidden. Five minutes out a live feed
  panel appears; the price pulses on movement; the countdown breathes
  rust under two minutes; on close the page swaps to the truth.
  "EXPIRED" retired for "Closing…".

### After the close

- **Settled** in Bids & offers: the last week of closed lots, one
  outcome row each — Review & pay / View order / Went to someone else /
  Reserve wasn't met / Didn't sell / The win lapsed.
- The detail page tells **everyone** the outcome (the signed-out used to
  get a login wall on a closed lot); one `_auction_outcome.html` partial.
- **Just closed** strip in the Auction House (Hunt, auction format): the
  last 24 hours, below the live grid so live lots keep the room.

### Register

- ~~No drawn frame exists for the room feed / Just-closed strip /
  ?-popout / non-winner outcome~~ — **RESOLVED**: as-built frames
  A1–A6 in `design/ui-ux-redesign-model/Auction Room (standalone).html`,
  drawn from the shipped markup so the design folder stays the source
  of truth.
- Soft close is effectively **unbounded** (owner's call, 2026-08-26):
  each reset demands new money on a binding bid, so a war converges on
  its own; `SOFT_CLOSE_CAP = 100` stays as a pathology backstop only.
- Second-chance offers to the runner-up: still deliberately out of
  scope (10.9's note stands).

---

## Pass 9f — Messages: one thread, a quiet watcher, and rooms ✅

> **Status 2026-08-26** · 4 commits on `feature/alpha-p4-update-add-item`
> · full suite **700 green** (40 added) · live sweep on dev data clean
> (pair dedupe, room open/render, watcher flags a grooming pattern as
> urgent with zero API keys configured). Owner approved all three in
> order; house rules applied — modular apps, admin-portal tunables,
> nothing hardcoded that an admin might want to turn.

### ① One thread per pair (8d honored)

The old model kept a conversation per (listing, pair, type) and the five
entry points passed four different combinations — a thread per
interaction. Now `Conversation` is unique per pair; `conversation_type`
is gone; listing/trade context is display-only, refreshed when an entry
point walks in about something new; a data migration folded every
pair's scattered threads into their earliest one. The deal strip and
the left-pane context line read the pair's LIVE deal ("Sale · {title}",
"Purchase · … — finished", "Trade · offer from {name}", "About ·",
"Nothing outstanding"). Resuming your one thread is never rate-limited.
The seller card's button says "Message {name}" — "Ask a question" was
the public Q&A tab two inches away. `send_message` gained the
email-verified bar. Fixed along the way: the thread page's `messages`
context key had been shadowing Django's messages framework — no toast
ever rendered there.

### ② The quiet watcher (apps/moderation)

Three tiers, each nearly free; the system only FINDS, humans DECIDE:

1. **WatchTerm** — admin-editable patterns (seeded minimal: minor-safety
   and explicit-threat signals). A hit flags; it never punishes.
2. **Free classifier** — OpenAI's moderation endpoint scores every
   message asynchronously (`OPENAI_API_KEY` optional in `.env`; without
   it scans record `skipped`, never silently clean).
3. **Claude escalation** — flagged threads read IN CONTEXT (prompt in
   `apps/moderation/config/escalation_prompt.md`); banter clears, malice
   surfaces with a one-line rationale. Claude can clear low-severity
   noise but can never veto an urgent hit.

Heated threads (both sides flagged within the window) surface once.
`ModerationEvent` is the queue (admin: resolve/dismiss/hide-message);
urgent findings page every staff account in-app. Every tunable —
thresholds, category lists, model, window, batch, master switch — lives
on the `ModerationSettings` singleton in the admin. `scan_messages`
runs in the `run_jobs` sweep; the absence of a `MessageScan` row IS the
queue (no signals; messaging untouched). The scanner reviews after
delivery — never in the send path. Profanity between friends, haggling,
and off-platform talk are explicitly nobody's business (tested).

**Ops notes for launch** (not code): put an explicit 18+ line in the
ToS; read 18 U.S.C. § 2258A (NCMEC reporting duty for apparent CSAM)
before going live; if fronted by Cloudflare, switch on their free CSAM
scanning tool for uploaded media.

### ③ Rooms (private group chats)

The campfire, not the forum: invite-only, invisible to non-members, no
directory anywhere. Any member adds; anyone leaves; only the opener
removes (the one power that fixes a bad add without staff). Tunables
(`groups_enabled`, `group_max_members`) on the `MessagingSettings`
singleton. The watcher reads room messages exactly like DMs; reports
work from inside a room. Public channels deliberately unbuilt.

### Register

- **Image attachments in rooms** — deferred, not dropped. Blocked on:
  the moderation pipeline proving out in production + an upload model
  with scan-at-upload. The messages surface stays text-only (8d's own
  rule) until then.
- **Staff-desk dressing** of the moderation queue + reports — Pass 11
  (the desk is drawn; the admin queue serves until then).
- No drawn frames existed for rooms or the watcher — as-built frames in
  `design/ui-ux-redesign-model/Rooms and the Watcher (standalone).html`.
- dev_plan §9.x scope limits ("no group conversations", "no automated
  flagging") — superseded with owner approval, noted there.

---

## Pass 9g — The thread, made worth reading ✅

> **Status 2026-08-27** · 1 commit on `feature/alpha-p4-update-add-item`
> · full suite **712 green** (12 added) · live sweep on dev data clean.
> The owner's field report on the shipped messages UI, item by item.

### Reporting: one place, two clicks, optional depth

The inline per-message Report dropdown + button (and the redundant
"Flag" link) are gone — they were bigger than the messages, sat beside
your OWN messages, and begged for accidental clicks. Reporting lives in
the header menu alone: reason → Report is two clicks; an optional note
("Anything we should know?") and an optional "Point at specific
messages" mode (checkboxes appear beside THEIR messages, multi-select,
riding the same form via the `form=` attribute) add depth without
steps. One action = one report = one rate-limit tick; pointed-at
messages are flagged for the reviewer; your own messages can't be
pointed at. New reasons: Scam or fraud · Fake or counterfeit item ·
Harassment or threats · Hate speech · Someone may be underage · Spam ·
Something else. Toasts now say "We'll look at it."

### The thread, to the 8d grammar

Bubbles (mine forest-on-cream — "the green side of the conversation" —
theirs parchment), the time tucked under the bubble on the avatar side
with "· read" from the real read record, date dividers ("FRIDAY 1
AUGUST"), and **context dividers**: `Message.context_listing` snapshots
what the thread was about at send time, so "About · {listing}" markers
keep one-thread-per-pair honest when the talk turns to a second listing
(the owner's screenshot-seven complaint — the old repointing erased the
first reference).

### The furniture

- The header menus (Block-or-report, Members, Report-or-leave) are real
  popovers now: title, small ×, click-away and Esc both close.
- The module takes the viewport: dead band above it trimmed, panes
  scroll internally.
- The left pane is identical everywhere (search + chips ride into open
  threads), sorted freshest-first via Coalesce, with a **Rooms** chip.
- The inbox auto-opens the freshest thread — the dead "Pick a
  conversation" pane survives only for a genuinely empty inbox, compact.
- "+ New room · a private group thread" sits above the search.
- Member pickers are real typeahead (`messaging:user_search`, login-
  gated, never returns yourself): pills on the open-a-room form, verified
  fill-in on the add box. Free-typed names still work without JS.
- The quiet word on brand-new exchanges only: "…screened for safety by
  machine. A person only reads a conversation if something is flagged or
  reported." (FAQ draft added to docs/internal/FAQs.md.)

### The watcher, answering the owner's question

One-sided hostility was never unwatched — every flagged message makes
its own event — but the thread-level rollup now covers both shapes:
"a genuine fight" (both sides flagged in the window) and "sustained
hostility" (one sender, same window). One open rollup per thread.
`ANTHROPIC_MODERATION_API_KEY` is supported as a dedicated key for the
escalation reads (falls back to `ANTHROPIC_API_KEY`), per
one-key-per-workload practice.

---

## Pass 9h — The popovers close, the pickers behave ✅

> **Status 2026-08-27** · 1 commit on `feature/alpha-p4-update-add-item`
> · full suite **720 green** (8 added) · live sweep on dev data clean.
> The owner's style report on 9g, plus one real bug it uncovered.

- **The unclosable popovers** (the round's real bug): `.ms-menu-panel`
  sets `display: flex`, which beats the `hidden` attribute's own
  `display: none` — so every panel sat open on page load and no click
  could close it. One explicit rule (`.ms-menu-panel[hidden]`) puts
  `hidden` back in charge, and a test now reads the stylesheet to pin
  it, since Django tests can't compute CSS.
- **Typeahead dropdowns anchored**: the results list was absolutely
  positioned with no `top`/`left`, so it landed over the input it
  served. Both pickers (open-a-room, add-a-member) now wrap the input
  in `.ms-picker-anchor` and hang the list below it.
- **Room form polish**: pills get daylight above the input; hint says
  "any **room** member can"; name placeholder is now
  "e.g. Maryland Waterfowl Collector Crew" (as-built doc updated).
- **Left pane glances**: a small brass ROOM tag beside room names, an
  unread dot beside the date plus bolder title/snippet on unread rows
  (the brass edge stays). The gray current-thread highlight stays.
- **Header buttons**: `.ms-quiet` never stripped native button chrome,
  so Report-or-leave/Block-or-report rendered as heavy gray UA buttons.
  Reset — report controls are quiet text (present, never the main
  show), and Members wears a soft chip so the two stop being twins.
- **Unblock now reopens the thread**: blocking closes the pair's
  conversation, but unblock only deleted the Block row — the thread
  stayed dead forever (the owner's mystery-closed demo thread).
  `services.remove_block` reopens unless a block still stands the
  other way; migration 0006 healed the stranded threads.

### The watcher's first live run (same day) — suite now 723

The owner put real keys in `.env`, sent a slur, and found zero scans.
Two causes, one real gap:

1. **Nothing runs the scanner in dev** — by design it sweeps after
   delivery via cron (`scan_messages`, included in `run_jobs`); dev has
   no cron, same shape as the auction that never closed. Local testing:
   `python manage.py run_jobs --loop 60` in a second terminal.
2. **OpenAI answered 429 on every call** — account-level (API billing
   not activated), not code. The Anthropic key was verified live: a
   real Claude verdict (urgent/threat, sound rationale) on a synthetic
   transcript. Providers now log the error BODY, not just the status.
3. **The gap**: a `skipped` scan was never retried — a transient
   provider failure let a message escape review forever. Now skipped
   means "not yet", never "never": `scan_pending` requeues skipped
   scans BEHIND the never-scanned (nulls-first ordering), so an outage
   backlog can never starve a fresh message of its first watch-term
   pass. Redone in place, one row per message; clean/flagged are
   settled and never rescanned. Three tests pin it.

Also cleaned: one orphaned urgent event (+ its staff page) left by an
earlier live probe whose conversation was probe-cleaned — events
survive conversation deletion via SET_NULL.

---

## Pass 9i — One item, told as one item ✅

> **Status 2026-08-27** · 1 commit on `feature/alpha-p4-update-add-item`
> · full suite **739 green** (19 added) · live sweep clean. The owner's
> four "regressions" — none caused by the messages work; one real code
> defect, one real design gap, one data wound, one invisible listing.

- **Collectors flattened** (the "detail is gone" report): the two-tier
  card design was fine — the featured tier had a blind spot. A wanted
  list that matches *nobody* ranked nobody, so every card fell to the
  compact tier. Now zero overlap falls back to biggest-cases-lead, same
  as no wants: the page keeps its shape. Also: the compact line used the
  "5 counties held" place-fallback beside its own counts ("…· 5 items ·
  5 counties" — a stammer); compact cards now say "Whereabouts unsaid".
- **Sold pieces now leave the collection** — the missing half of 8b's
  `disposition`. New `sold` ("Sold here") stamped by the sale lifecycle:
  paid order → sold (webhook + `transition_order`), refund/cancel →
  held again; never overwrites another story (traded, given away). Not
  a form choice, mirrors `traded`. Every census asks `disposition=
  'held'` now: profile grid (visitor), tracker/runs, decade chips,
  collectors figures/facets/case strips, want-matchers both directions,
  the shelf, ground counts. The owner still sees departed pieces in
  their own grid wearing their label — the catalogue keeps its history.
- **One item, told as one item**: a collection piece with a live lot
  wears a corner tag in the profile grid ("Selling now" / "Scheduled to
  sell" / "Sale pending") instead of reading as a second thing beside
  the Selling-now card.
- **Drafts and scheduled lots stop being invisible to their own
  seller**: an owner-only "On the way — only you see these" strip under
  Selling now links each one to its terms page. (The "missing" F3 was
  a scheduled auction created 26 Aug, visible nowhere.)
- **Shelf counts tell the truth**: "Search my 5 items" over a shelf
  showing one was three listed pieces counted as available. `shelf()`
  returns eligible/listed/total; the page says "1 available · 4 already
  on the market".
- **The alt-text-on-stripes cards** were data, not template: two image
  fields pointed at files gone from media/. #15 restored from the
  seeded original; #17's dead field cleared (that upload is lost — re-
  upload whenever). Truly imageless cards render clean stripes.
- **Probe purge**: five pre-cleanup-rule probe users deleted with all
  they owned (the QA render lot listing, a collection item, two
  conversations, an order, three listing questions).

---

## Pass 10 — Empty states, mobile, fifty states 🚧 IN PROGRESS

**Design refs** — turn 16a/16b (empty states), 15a/15b (mobile), 14a/14b (units).

- **The four unit-label substitutions** (14a/14b) ✅ **done 2026-08-27** ·
  747 green (8 added) · live sweep clean over the 26 states already seeded.
  What actually remained after T9 (which had quietly built most of it —
  `unit_label_plural` matrix headers, hatched never-issued cells,
  `real_units`, grid degrade, quiet inactive map states with a tooltip
  reason): the **counting rules**, which were lying in four places.
  - `tracker.ground_covered` measured "N of M" against ALL of a state's
    GeographicUnit rows — Statewide pseudo-unit and admin codes included
    (the "68 counties" family). Now `ground.real_units` is the one
    denominator, held intersects it, and the deepest run digs only real
    ground. Same treatment in `_collection_progress` (bench meters).
  - **`real_units` learned the honest boundary rule**: a shapeless
    county-type row is an administrative code only in a state whose other
    counties HAVE shapes; in a state with no geometry at all, counties
    are counties — 14b's "the list and the matrix work normally" — so
    the census never zeroes out with the map.
  - **The matrix gives Statewide its own first row** that fills cells but
    never moves the unit figure; admin codes left the rows entirely.
  - Collectors cards: a statewide piece no longer counts as a county
    (figures, home-county line). Landing band stops counting statewide
    listings among units. **"Countys" is not a word** — two `f'{label}s'`
    spellings replaced with `plural_unit`.
  - **The unit word rides beside each state** everywhere a state is
    chosen: `State.option_label` ("Colorado · GMU", county states bare)
    wired into all three item/wanted forms via `label_from_instance` and
    the four hand-rolled template selects. Mine-view filter label and
    group chip read the state's word.
  - The map's owned lens now counts held pieces only — ground.py's old
    "open question" note replaced by 9i's decision, both surfaces moved
    together.
- **Empty states — three shapes** ✅ **done 2026-08-27** · 755 green
  (8 added). The audit found most blocks already in-voice from earlier
  passes; what was missing was the machinery:
  - **Nothing matched (Hunt)**: each relaxation is the same search with
    one filter let go, wearing its own live count (rows that free
    nothing stay unsaid); "or keep the search and let it come to you —
    N collectors own one; M will trade" measured against real held
    shelves; **Save this as a want** carries the filters into a
    prefilled want form (`_wanted_initial_from_query`).
  - **Nothing left to do (Bench)**: the green rule (`kb-empty--clear`),
    "All clear. Nothing is waiting on you." + what's running (parcels in
    transit, auctions running) so the quiet reads as earned.
  - **Nothing yet**: the mine page stops rendering the filter rail over
    an unrecorded collection ("an empty control is worse than no
    control") and says "{6} of these become your display case"; the
    wanted-list empties (Hunt wants tab + mine) offer the 16a starters
    ("Anything from {home county}" / "A {first year}, any county" /
    "Write my own"), each a real prefilled link. "None listed" became
    "Nothing listed today" — the words empty/none/zero stay out of
    member-facing empty copy (audited all 14 blocks).
  - **Still open from 16a** ⬜: the new-member HOME variant (county
    greeting strip, "this page changes completely", collectors near you
    via the miles machinery, import-a-spreadsheet). Its "Today's three"
    chip is Pass 15 and its Almanac links are Pass 14 — the band waits
    on neither, just on its own build.
- **Mobile — chapter 12, 390pt, 44pt targets** ✅ **done 2026-08-27** ·
  760 green (5 added). Built as a phone layer over the real pages, not
  six separate screens:
  - **The four tabs** (Hunt · Mine · Bench · Add) fixed to the bottom at
    ≤640px, 52px targets, safe-area padding, Bench wearing the unread
    count. Members only — a visitor's topbar carries enough. The
    masthead's "Add an item" hands its job to the tab.
  - **What the phone drops**: the nine settings rooms and the trade
    composer's dual rosters hand the whole page to one line — "This is
    desk work — open it on a computer and it spreads out properly" —
    and the matrix hands over just its panel (the rest of My collection
    works fine on a phone). One `_desk_note.html` + `mobile.css` swap;
    the desktop never sees any of it.
  - **One column reading as rows**: the card grid flattens to
    thumb-left rows at phone width; 44px buttons and tap targets;
    context bands ride sideways instead of wrapping into a wall.
  - **Register (15b, deferred not dropped):** the camera screen that
    "justifies an app" (scan → do I own this → what they go for, no
    account needed) — blocked on Price History (Pass 12) for the
    comparable figures and on an add-time "you already own one"
    duplicate check that doesn't exist yet; the photo-prefill half is
    built. The letter→lot→bid path works today through the responsive
    lot page; its drawn one-number bid sheet can follow as polish.

**Pass 10 stands** with one carve-out open: the 16a new-member home
variant (the "this page changes completely" band) — everything else in
the pass is built.

---

## Pass 10b — One record, one editor ✅

> **Status 2026-08-27** · 1 commit on `feature/alpha-p4-1` · 767 green
> (7 added) · live sweep against the owner's real scheduled F3 clean.
> The field report on editing: "it is almost like we edited the Add an
> item form but the edit got left behind" — which was literally true.

- **Scheduled is not live.** The terms form treated any non-draft as
  live and stripped the clock fields, so a scheduled listing was
  locked: no reschedule, no go-up-now. Now scheduled edits on the same
  step-2 page as a draft (slots and all — the old combined editor
  redirects it there), its terms reopen with the set date shown, and
  publishing again is free: **a new date reschedules, a cleared date
  puts it up right now** (auction clocks recompute from the new
  go-live). `activate_scheduled_listings` was already in `run_jobs`.
- **One record, one editor.** A listed piece is a collection item on
  its way to market — the same physical thing, and two open edit forms
  is how two copies learn to tell different stories. While a lot exists
  (draft/scheduled/pending/active) the collection editor redirects to
  the lot's editor with a note, and **every lot save mirrors the shared
  descriptive fields back to the shelf record**
  (`_mirror_listing_to_source`). Terms, privacy and disposition remain
  each side's own business. Found under the same stone: a POST that
  omitted `source_collection_item` silently severed the pair — the
  field is disabled once bound, so the link cannot be orphaned.
- **The edit photo blocks speak.** "what each one is travels with the
  file" → "front, back or detail — the label sticks with the
  photograph". The raw ClearableFileInput chrome ("Currently:
  <filesystem path> Change:") is gone from every image field — plain
  file inputs beside the thumbnails that already show what's there.
  Blank formset extras stopped shouting DETAIL · NEW with a drop box:
  they read "Add a photograph", and the role dropdown appears only on
  rows that hold one.
- **Register:** ~~the live-listing editor still uses clean rows~~ —
  cleared same day by Pass 10c below.

---

## Pass 10c — The edit is the add form ✅

> **Status 2026-08-27** · 1 commit on `feature/alpha-p4-1` · 768 green ·
> live sweep clean. The rest of the same field report: "why not the add
> an item format we worked on" — no reason, so now it is.

- **The slot plan wears every editor.** `apps.core.slot_plan` was built
  to hold saved records ("the back slot is the row whose role is back")
  and the edit views simply never called it. Now the collection editor
  and the live-listing editor both render the same slot panel as the
  add flow — photographs already sitting in their slots, marked
  committed, × ticks the row's DELETE, drag reorders. The listings
  panel became one shared include (`_photo_slot_panel.html`) used by
  create, the step-2 revisits and the live editor; the old row layout,
  its role dropdowns and the up/down arrows are gone. (This also
  resolves the "auction updated but store didn't" impression — that was
  scheduled-vs-active taking different doors; both wear slots now.)
- **The dead trade-rules paragraph is deleted, not tucked away.** Since
  one-record-one-editor, a piece with a live lot cannot reach the
  collection form at all — explaining auction-lot and Store behaviour
  there was describing a state that cannot occur. The comment in
  `_trade_block.html` records why.
- **"Where it stands" is styled.** `kb-fieldset`, `kb-fieldset-legend`,
  `kb-radio-row` and `kb-field-note` had no CSS anywhere — bare browser
  fieldsets were the "unstyled text". The legends (Trade · Where it is ·
  Only you see these) now wear the panel eyebrow voice.

---

## Pass 10d — Fifty states, for real ✅

> **Status 2026-08-28** · 1 commit on `feature/alpha-p4-1` · 769 green ·
> live sweep: all 50 states active on the map. The owner gathered the
> full national reference set (50 states · 4,187 units · 545 license
> classes · 415 addons); reviewed, corrected and applied.

- **County-first everywhere (owner's decision, 2026-08-28).** The
  gathered data declared modern systems as ten states' primary word
  (CO=GMU with zero GMU rows, KS/MI=DMU, MN=DPA, MT=HD, ME=WMD,
  NH/NY/VT=WMU, WY=Hunt Area) and sorted system rows above counties.
  For a marketplace of 25-plus-year-old artifacts the printed geography
  is county or nothing, so: all 50 primaries are the county family
  (Parish for LA, Borough/Census Area for AK), counties sort first, and
  the GMU/WMD/DMU rows remain selectable below for the late-window
  items that genuinely carry them. Revisit per-state when unit
  validity-years land (register).
- **The county family is one rule** (`ground.COUNTY_FAMILY`): a
  county-family row with no FIPS shape, in a state whose family has
  shapes, is not drawable ground — PA's Co. 68 admin code and
  Virginia's six abolished jurisdictions (Elizabeth City County,
  Warwick, Norfolk County, Princess Anne, South Norfolk, Nansemond)
  behave identically: selectable and taggable, never counted, until
  validity-years exist. Independent City / Parish / Borough / Census
  Area / City and Borough / Municipality joined County in the check.
- **Apply mechanics**: DB pre-rename Norfolk → Norfolk City (seeder
  keys on (state, name)); pipeline regenerated losslessly (50 / 4,187 /
  1,005 rows); non-clobber seed first — every drifted row accounted for
  (10 = the relabels, 990 = the resort + slug conventions, 13 = the
  owner's duck-stamp/HIP year backfills) — then `--overwrite`. FD
  pseudo-state self-creates in `seed_license_types`, so its absence
  from the new states.csv is bootstrap-safe. New CSV columns
  (`first_year_source`, `added_date`, `agency_name_historical`) pass
  through the pipeline untouched.
- **Register:** unit validity-years (existing entry) now also carries
  the historic-jurisdiction case; ~730 addon rows still lack
  `approx_first_year` (gate suggestions only — fill opportunistically);
  MT's 306 hunting districts stay `geo_data_complete=False` by design.

---

## Pass 10e — The marketplace is a fact ✅

> **Status 2026-08-28** · 1 commit on `feature/alpha-p4-1` · 776 green
> (7 added). The field report's "major logic flaw": the live editor's
> quiet Where-it's-listed dropdown turned a Store listing into an
> auction with no clock and no starting price — the terms save cleared
> the store fields, nothing set auction terms, and the lazy closer
> swept the wreck as "ended, $None".

- **The type is locked on the live editor** (`_lock_marketplace`):
  disabled at the form level so no POST can flip it, and rendered as a
  static fact ("The General Store · move it") instead of a control.
  The "Started from" box is gone — the shelf link is structural
  (one record, one editor) and told a seller nothing.
- **Moving is a deliberate act now, both directions** (`listings:move`):
  off the market first, terms second. The listing returns to draft on
  the bench, the terms page asks the NEW marketplace's questions, and
  its foot button is the only thing that opens it again (fresh clock,
  cross-type fields cleared properly by the publish path). Guards:
  active listings only; **a lot with bids cannot move — bids stand**;
  pending offers are declined with a letter to their senders rather
  than left dangling.
- **"$None" can't print**: the detail's current-bid figure defaults
  a null price to 0.00 (the state is unreachable now, but the template
  stops lying if data ever wounds a listing again).
- The owner's 1964 WMD listing repaired to its store form (price,
  floor, offers, trade note, active).

---

## Pass 10f — Backtag ✅ (implementation plan §1–§3)

> **Status 2026-08-28** · 2 commits on `feature/alpha-p4-1` · 792 green
> (16 added). Tasks 1–3 of `backtag_implementation_plan.md`, plus the
> rename itself. §4–§7 (greetings, badges, sharing, seasons) remain in
> that plan, unscheduled here.

- **The name.** KeystoneBid → Backtag in every sentence a member reads
  (~80 files: templates, letters, admin titles, settings, scripts).
  Kept deliberately: the `kb-` CSS prefix, the `config` module, the
  repo name, `__keystonebid_demo__` — identifiers, not language.
- **The nav (§1).** The Market · Collections · Research · Dashboard.
  Paths renamed (/market/, /dashboard/, /research/) with the **URL
  names keeping their old words** so every reverse and sent letter
  still lands; old paths 301 with query strings preserved. Research
  opens onto two rooms: **The Field Guide** (the Almanac renamed) and
  **The Archives** — shell only per the plan, stating the permanent-
  census idea with a real count and a deliberately disabled search.
- **The header (§2).** Home masthead: three bars → two (strap, date and
  EST. line gone; Sign out only in the avatar menu, which already ran
  Profile → Settings → divider → Sign out). Sticky, condensing on
  scroll (nav + stat line collapse). `/` and Ctrl/Cmd-K focus search.
  **Typeahead** via `/api/search/` grouped Listings / Collectors /
  Counties, keyboard-walkable. **Badge colours split**: red only when
  action is required (`ACTION_TYPES` = order_paid, auction_won,
  moderation_urgent), brass for informational. **Dashboard action dot**
  from a cached `needs_you_count` — something waiting on you, distinct
  from Alerts.
- **The hero (§3).** "Nobody collects these to get rich." / the
  supporting line / *"History isn't going to save itself."* — image
  placeholder right, `Join the collection` + `Look around first`, the
  free-to-join fine print.
- **The mark (logo round 2, owner chose 2B+2C).** The numbered-tag
  glyph (die-cut card, punch hole, 13-for-1913) as an inline SVG
  component (`_mark.html`) that inherits each context's colour and the
  page's Petrona; the nav wordmark is bare — the 2C brass rule lives
  only on the auth lockup (owner's call, 08-30). Wired:
  topbar, masthead, footer (brass), auth lockup with COLLECT · RECORD ·
  PRESERVE, and a geometry-only favicon (the number drops below 24px,
  the silhouette stays). The full eight-file export set (PNG email
  header, print master, app tiles) is registered for when assets are
  cut properly.

**Register additions (14b, deferred not dropped):**
- `GeographicUnit` has no valid-from/valid-to years, so "19 of 185" in a
  redrawn-boundary state measures against today's map and quietly
  overstates gaps. Blocked on: unit validity fields + per-state boundary
  history data (owner gathers state data separately).
- The collectors card's "counties held" stat label stays the house word
  even for a GMU-state collector — a per-collector unit word needs a
  primary-state label annotation on the directory query. Cheap once
  wanted; noted at `templates/collections/collectors.html` stat label.

---

## Pass 10g — Home state is the default, not Pennsylvania ✅ · **10.21** (tasks_08-30 §1)

> **Status 2026-08-30** · on `feature/alpha-p4-tasks-0830` · 815 green
> (13 added). First of the six 08-30 intake items.

- **One rule, one place: `apps/core/defaults.py::default_state(user)`** —
  the member's `home_state` → the `is_primary_default` state → first
  alphabetically. Every surface that preselects a state goes through it.
- **Where it now opens at home:** the Market filter bar (`HuntView`),
  the Market map (`hunt_map`, which already did this — collapsed onto
  the helper), Everything-owned browse (`browse.resolve_state`), the
  My-collection filter sidebar, the Collectors tab, the Field Guide
  reference button, the geo-units and license-types APIs' no-param
  fallback, and the wanted-list starter chips.
- **Item forms guess home, never the site default.** `ListingForm` /
  `CollectionItemForm`: a fresh unbound form prefills the owner's home
  state (county list + year bounds follow); a member who never said one
  still gets "Choose a state" — the no-PA-guess rule stands. Bound
  POSTs that cleared the state stay cleared. `WantedItemForm` (which
  always had a PA fallback) now takes `user` and falls back home-first.
- **County prefills nothing** — per the intake note, `home_county` is
  who the member is, not where a search starts.
- **Registration requires home state** (10.26 groundwork): required
  field on the door, saved to the profile, FD pseudo-state excluded,
  alphabetical by plain name. Copy: "Filters and new records open on
  your state. Change it any time in Settings."
- **Bug found on the way:** `_primary_state` (accounts/views) read
  `profile.state` — a field that has never existed — so an empty shelf
  always landed on PA. Now falls back home-first via the helper.
- Tests: `apps/core/tests_defaults.py` (helper + every surface),
  registration coverage in `tests_auth.py` incl. the full POST the page
  produces.

---

## Pass 10h — The settings county list follows the state ✅ · **10.22** (tasks_08-30 §2)

> **Status 2026-08-30** · on `feature/alpha-p4-tasks-0830` · 817 green
> (2 added).

Exactly the wiring bug the intake suspected. The server half always
worked — a POST's county queryset is scoped to whatever state the POST
names — but the profile room rendered its fields in a generic loop and
never got the browser half every item form carries. Added the same
cascade (fetch `core:geo_units_api`, keep the selection when still
valid, reset to "Not saying" on a state change or cleared state), plus
the label following the state's own unit word ("Home county" → "Home
WMD"). Tests lock the script's presence on the room and the exact
pk-shaped request it makes.

---

## Pass 10i — Nothing is appended to a place name ✅ · **10.23** (tasks_08-30 §3)

> **Status 2026-08-30** · on `feature/alpha-p4-tasks-0830` · 822 green
> (5 added).

The audit found exactly one producer of "Baltimore County County":
`UserProfile.place` appended the state's unit label to the unit's name.
It feeds the profile header, breadcrumb, collectors cards, listing
detail's seller line, message threads and trade stories — one property,
one fix. Now "{unit}, {state}" with both names verbatim and the state
written out: *Lycoming, Pennsylvania* · *Baltimore City, Maryland*. The
profile header carries the intake's format: **of** Lycoming,
Pennsylvania. The collectors-card fallback built from held items
(`_home_counties`) matched to the same shape.

Everything else came back clean: every template renders
`county.name`/`county_ref.name` verbatim; the letters and the ledger
lines use the unit word grammatically as a count noun ("the last county
you need"), not as a suffix; the typeahead's label sits in its own meta
column. The 10.7 address-suffix class has no other member standing.

---

## Pass 10j — Destructive actions take two steps ✅ · **10.24** (tasks_08-30 §4)

> **Status 2026-08-31** · on `feature/alpha-p4-tasks-0830` · 831 green
> (9 added). Intake's open question (modal vs page) resolved: **dialog
> with JavaScript, plain page without** — both the same words.

- **One dialog for everything.** `window.kbConfirm` moved to `custom.js`
  (the photograph ×'s dialog, now shared); any control marked
  `data-kb-confirm="plain words"` gets intercepted, confirmed, then its
  own form submitted (`requestSubmit(button)` keeps name/value).
  `item-form.js` delegates instead of carrying a second copy.
- **Collection item.** "Strike it from the record" is off the detail
  page (Edit and Sell it remain) and off the legacy row partial; it now
  sits at the bottom of the edit form as a quiet rust link. The trigger
  keeps the house words; the dialog is plain: *This permanently deletes
  "{title}" — the record, its photographs, and your private notes. It
  cannot be undone.* No-JS: the link walks to the rebuilt confirm page
  (house markup, same plain words) — GET never deletes, POST does.
- **One-record guard found on the way:** the delete view would orphan a
  live lot (`source_collection_item` is SET_NULL). It now refuses while
  an operative lot exists and walks to the lot's editor instead — same
  rule as the edit redirect (10b).
- **Draft discard.** "Discard this draft" on the terms page was the one
  true one-click destroyer — now behind the same dialog. The copy's
  shelf promise ("the piece itself stays on your collection shelf") is
  unconditional because step 2 gives every draft a shelf twin (4e) —
  a test now locks that invariant.
- `_collection_item_row.html` is included nowhere (legacy) — its bare
  Delete removed anyway; registered for a future sweep of dead partials.

---

## Pass 11 — The staff desk ⬜

**Design refs** — turn 17a (desk), 17b (strike review, taxonomy, prefill),
19a (member page), 19b (moderation), 18a (three defects).

New `/staff/` in slate + gold. Django admin stays exactly as it is for editing
rows; this is the front door that answers *what gets worse if I don't touch it
today*.

- **Desk** — six stat tiles, queues ordered by consequence, "acts on its own
  tonight unless you look" at the top.
- **Strike review** — consequences stated beside each button. Every action writes
  `excuse_initiated_by`, so the audit trail says who decided.
- **Member page** — joins User, UserProfile, AccountRestriction, Strike and Block
  into one page with a merged timeline. Today that's five changelists filtered by
  username. Every action asks for a note, and **the note is the audit log the four
  toggles are missing**.
- **One moderation queue over four models** — ListingQuestion, Message, Review,
  Report. **One verb pair on every row** (Take down / Leave up) regardless of which
  app the sentence came from.
- **Taxonomy** — duplicate-candidate grouping upstream of the existing merge screen
  (which is already right).
- **Prefill analytics** — add a verdict and a **cleared-rate** column;
  `PrefillCorrection` is a better signal than the tier table. *"A high-tier guess
  that gets cleared is the most damning number you can collect."* Recommendation:
  stop prefilling condition grade until high clears 70%.
- **`MarketplaceSettings` deserves a screen, not a changelist** — changing a fee
  affects every live listing and every auction mid-flight; the page should say how
  many and ask whether it applies to those already running.

---

# Blocked on new models

The designer's own build order (20a). Each is independently shippable.

## Pass 12 — Price history 🚧 · dev plan **13.6**

**The most load-bearing thing missing.** The bid sheet, the camera screen, every
wanted-list row, the create-flow "what the books say" panel, the Almanac and the
unwritten-county panel all print a comparable-sales figure. **Twelve screens
across seven turns quietly depend on it.** Nothing else unlocks as much.

## Pass 13 — CollectionSet 🚧 · dev plan **10.14** (called CollectionFolder there)

**Owes the deferred register** — the collector card's third figure goes back to
**"sets going"**. Swap the annotation in `apps/collections/collectors.py`; the layout
does not change.


Name, optional rule, membership table for hand-picked ones. **Without it there is
no definition of what counts as a gap**, so the matrix (10b), the sets tabs, the
gap counts and the seed-the-wanted-list flow are all unbuildable.

Turn 11a: a rule is a target, not a folder — it knows what belongs, so it can count
what's missing, feed the matrix, seed the wanted list, and tell you a gap came up
for sale. Three sets ship as suggestions to every new collector.

## Pass 14 — The Almanac + badges 🚧

**Owes the deferred register** — the **earned badge row** under the profile bio, where
the marker sits in `templates/accounts/profile.html`.


**This is the one I missed on the first read.** It is a **nav-level zone** in every
turn from 2 to 21, currently a placeholder page.

- **Index** (12a) — five era guides, 67 county spotlights (every county has a page
  whether written or not; unwritten ones still carry the numbers), search,
  this-month's-county feature.
- **Entry** (12b) — hero image, brass breadcrumb, Petrona standfirst, author line
  with their holding beside it, body, a boxed **What to look for**, then
  **fourteen from this era are for sale now** and a corrections footer.
- **Write an entry** (21a) — a form with the shape of the article, not a blank
  page: subject (county / era / type / one licence / anything else), image, the
  one takeaway (becomes the standfirst), the body, up to three things to check,
  and sources (not published — what a moderator reads). Moderator publishes or
  sends back with a note; **no silent rejection**.
- **Corrections** — author sees them first, one-tap accept credits the corrector.
- **Thirteen badges, five categories** (21b) — colour *is* the category encoding.
  Four tests each passes: a collector would say it out loud; it's one query; money
  can't buy it; it helps somebody decide.
  **Rule the designer takes back:** the settings copy says tags "never come off".
  That can't hold — a badge recording **something you did** is permanent; one
  describing **how you are** (Twenty-five clean, Ships quick, Traded true) lapses
  when it stops being true. Nothing announces a lapse.

## Pass 15 — Three questions 🚧

Daily set, attempt per member, streak, monthly board. Last, because it is the only
thing on the sheet nobody asked for, and because the questions are generated from
real items with the identifying field hidden — **it needs the taxonomy clean first**
(17b).

---

# Deferred, not dropped

Everything shipped in a reduced form because something else has to land first.
**This table is the register.** Every entry has a matching marker in the code
reading `DEFERRED — … Blocked on: … Register: docs/internal/plan_design.md`, so
either end finds the other:

```bash
grep -rn "DEFERRED —" apps/ templates/ static/
```

Nothing here is a decision to do less. Each one is scheduled against the pass
that clears its blocker, and the pass that clears the blocker is responsible for
coming back for it.

| What is reduced | Where it lives now | Blocked on | Clears in | Restore by |
|---|---|---|---|---|
| ~~**"Will trade" flag** on the collector card~~ ✅ | now a **count** — *N to trade*, pieces you could ask about today | settled in Pass 7 — with open as the default a binary flag would sit on every card again, so the card carries a figure that varies instead | — | — |
| ~~**"Propose a trade"** as one click~~ ✅ | opens on the piece of theirs that answers one of your wants | settled in Pass 7b — `subject_item` is the anchor, uniqueness moved to `Trade.offer` | — | — |
| **`listing_type='trade'`** as an enum value | unreachable — nothing creates one, the sell flow offers collection / auction / store | nothing; retiring the value means migrating historical rows that accepted trades still point at, which buys nothing today | **later** | drop the choice and migrate the rows if they ever get in the way |
| **Shared shipping choice** on a trade | each side picks its own carrier on the trade page | `TradeOffer` has no carrier/service field; 10.10 wants it chosen once in the offer and flowing into both shipments | **7b** | add the fields; `_create_trade_shipments` already builds both sides |
| **Composer search without JavaScript** | the full shelf renders and the checkboxes work; the search box and chips do nothing | the table is a form mid-composition, and a GET round trip would empty it | **10** (with the mobile pass) | keep the client filter; add a no-JS fallback that preserves the picks |
| **"Sets going"** — the card's third figure | shows **counties held** instead | no `CollectionSet` model | **13** (10.14) | swap the annotation in `apps/collections/collectors.py`; the layout does not change |
| **Earned badges** under the profile bio | omitted; marker in `templates/accounts/profile.html` | no `Badge` model or its thirteen awards | **14** | render the badge row where the marker sits |
| **Display-case captions** | reuses the item `description` | no `display_caption` field on `CollectionItem` | **8** | add the field, fall back to `description` |
| **The lot route** — a box of several licences | not built; marker in `templates/listings/sell_start.html` | `ListingLotItem` / `inventory_format` (10.15, T13) | **later** | add the second entry beside the three destinations |
| **The collection terms panel** | the trade half now has a proper block (`templates/collections/_trade_block.html`); public / display case / the private block are still on the old form | nothing — it is scope left, not a blocker | **8** | give the collection destination its own step 3 |
| ~~**The map** (Collections tab, profile *Ground covered*)~~ | **CLEARED, Pass 9 (2026-08-26)** — both surfaces draw the ground-map component over committed county shapes | geometry landed (`static/data/counties-10m.json`); `valid_from`/`valid_to` still open below — until it lands, coverage is measured against **today's** map | — | done; the boundary-history caveat stays its own row |
| ~~**Trade board** tab~~ ✅ | local at `/collections/?tab=trade`, built from collection items and sorted by overlap with your wanted list | settled in Pass 7 | — | — |
| **Distance** — *"41 within a hundred miles"* | reads *N will trade · N selling now* | no geocoding, no geometry | **9 / 10** | add the measure to the header line |
| **Trade board on 3a's dark table** | built on **2e**'s four columns instead | nothing technical — 3a's rail costs 54px a side we do not have. Product-owner call, `1b34609` holds the 3a build | **later, if ever** | revisit if the page ever gets more than 1224px to work in |
| ~~**Filtering people by where they live**~~ ✅ | the rail now asks which question you mean | settled in Pass 6 | — | — |
| **Per-type mail preferences** | Notifications & mail says what arrives today | no `NotificationPreference` model | **later** | render the switches where the marker sits |
| **Records export** | the room offers a real address to ask | nothing but the work | **10** | build the CSV, including the private purchase block |
| ~~**`SHIP_BY_DAYS`**~~ ✅ | now `MarketplaceSettings.ship_by_days`, read via `bench.ship_by_days()` | settled in Pass 4 | — | a job that *enforces* it is still unwritten; it remains a promise |
| **Saved hunts** — standing searches that go looking for you | omitted from Saved; marker in `templates/favorites/list.html` | no `SavedHunt` model | **10** | render the strip where the marker sits |
| **Named sets** on My collection | omitted; marker in `templates/collections/my_collection.html` | no `CollectionSet` model | **13** | render the set strip |
| **Closing price** on a sold favourite | the row says only that it sold | price history | **12** | print what it made |
| **The wanted-match letter** — *"A 1916 Cameron has come up. First one in fourteen months."* | **not sent at all**; the shell and builders are ready, so this is one builder plus a trigger | three things, none of them the letter: no `wanted_match` notification type, no matching pass over `WantedItem` when a listing goes live, and no job to run it. The design calls this *"the best letter you can send"* | **10 / 13** (with saved hunts + `WantedItem` work, 10.14) | add the type, a `letters._wanted_match` builder, and fire it from listing publication; the scarcity line ("first one in fourteen months") needs price/listing history |
| **The seller's payment letter** — *"Your money for the 1938 Warren has arrived"* | **not sent at all**; `payment_received` is a declared notification type that **nothing anywhere creates** | no `create_notification(... 'payment_received')` call in the payment webhook or service — the buyer gets `payment_confirmed`, the seller gets nothing until the ship-by reminder | **later** (a payments change, not a design one) | fire it from the same place `payment_confirmed` is raised; the builder is a four-line sibling of `_payment_confirmed` |
| ~~**The counted county gap**~~ | **CLEARED, Pass 9 (2026-08-26)** — `apps/core/ground.real_units()` gives the honest denominator (a county-type row is real when it has a FIPS shape), and the outbid letter counts: first piece keeps the warm line, a collection under way gets *"one of the 26 counties you don't have yet"*, one gap left is told it's the last | — | — | done |
| **The plates' Almanac card row** — *"Almanac entry — Written"* on the selected-county card | not drawn; the county card carries owned / earliest / for-sale / held-by-others | the Almanac has no model (Pass 14 in the build order); a row pointing at nothing is a dead end | **14** | add the row with a link into the county's entry once entries exist |
| **The plates' extra map chips** — *Open to trade · Resident hunter · year range* | only the two lens chips (*My collection / For sale now*) and *Only my gaps* are live | `/api/map/` aggregates aren't filterable yet; a chip that doesn't change the counts would be decoration | with map-filter support (natural alongside 10.11's filter work) | filter the aggregate queries per chip and re-render from the same payload shape |

---

# Carried over from the other plans

Verified against the code on 2026-08-04.

## From `data_model_img_prefill_plan.md`

| Item | Status | Note |
|---|---|---|
| **T12 Department → Category** | ✅ **already shipped** | `ItemCategory` at `apps/core/models.py:14`; `category` FK on both `Listing` and `CollectionItem`. The plan's own 2026-08-03 audit confirms it. No action. |
| **T13 single-item image slots** | ✅ **shipped in Pass 5** | `image_role` now on both `ListingImage` and `CollectionItemImage` (`listings/0019`, `collections/0010`), with a partial `UniqueConstraint` allowing one front and one back. Roles carry across when a collection item is listed. |
| **T13 lot images** | ⬜ | `ListingLotItem` / `inventory_format` absent. Rides 10.15 → **Pass 5**. |
| **T14 general ledger** | ⬜ | No `apps/ledger`. Rides 10.18, after the UI work. |
| **T2 surfacing on listing detail** | ✅ **fixed in Pass 1** | `item_kind` + `addons_attached` now render in the spec tables. |
| R6 gold labels (`sandbox/gold.json`) | ⬜ | Prefill workstream, parallel. Feeds **Pass 11**'s analytics verdict. |
| Postgres sanity check | ⬜ | Pending a staging DB. |
| T4 remaining year blanks | ✅ accepted | Documented low-confidence blanks are the correct outcome. **Do not guess a floor to satisfy a checkbox.** |

## Field-level gaps the design needs (all verified absent)

| Gap | Design ref | Needed by |
|---|---|---|
| `Strike` **CheckConstraint** — excused ⇒ reason + initiated_by + confirmed_by + confirmed_at all present | 18a defect 3 | **Before** Pass 11 ships the moderator screen, not after |
| `MessageReport` → **`Report`** with nullable listing and order | 19b | Pass 8 (report flow has nowhere to write) |
| **Moderation action on `Review`** | 19b | Pass 11 — *today a libellous review cannot be taken down from the admin at all* |
| `WantedItem` — minimum grade, repairs-ok, **private ceiling price**, notify-me, show-on-profile | 11b (designer's own correction: they drew five fields that don't exist) | Pass 3 |
| `Listing.minimum_offer` floor | 5c / 6c / 8b | Pass 5 |
| `CollectionItem` — purchase price, acquisition, private note | 6c | Pass 5 ✅ |
| ~~`CollectionItem.trade_eligible` is a boolean defaulting to True~~ | 3a / 13a / 10.10 | ✅ **Shipped in Pass 7** — `tradeability` (`open`/`closed`, default `open`) + `trade_wants`. Availability is derived from live lots, never stored. |
| ~~`TradeOffer` cash runs one way only~~ | 3a / 10.10 | ✅ **Shipped in Pass 7** — `cash_direction` under a `cash_amount >= 0` CheckConstraint. |
| `TradeOffer` — shared carrier + service for both shipments | 10.10 | **later** — each side currently picks its own on the trade page |
| ~~`TradeOffer.trade_listing` nullable + a new home for `Trade`'s uniqueness~~ | 3a / 13a / 10.10 | ✅ **Shipped in Pass 7b** — `subject_item` anchors the negotiation; uniqueness is `Trade.offer`, and the live check is `open_trade_on(piece)`. |
| `GeographicUnit.valid_from` / `valid_to` | 14b | Pass 10 — until it exists, a Colorado collector's "19 of 185" is measured against today's map and **overstates their gaps** |
| ~~**`UserProfile.county` is a `CharField`**~~ | 4c / CLAUDE.md | ✅ **Shipped in Pass 6** — `home_state` + `home_county` FKs, with a timid data migration that leaves anything it cannot match exactly. |
| ~~Terms version + acceptance~~ | 4b / 10.16 | ✅ **Shipped in Pass 6** — `core.TermsVersion` + `TermsAcceptance`, recorded at registration. |
| `MarketplaceSettings.ship_by_days` | Pass 1 note | Pass 4 |

## Two JS defects in `browse_collections.html` (18a) ✅ FIXED in Pass 3

Both failed by **showing a plausible-looking interface rather than an error** — the
same rule as the empty states in 16b: never render a control over nothing. The JS
moved out of the template into `static/js/collections-filters.js` in the process.

1. **Silent fetch failure.** ✅ Changing state cleared the county select and all six
   type selects *first*, then fetched replacements in a bare `Promise.all` with no
   catch. Now: fetch first, clear second — nothing is touched until both responses
   are in hand — and on rejection the previous state is restored with one line
   under the bar saying which state couldn't be loaded.
2. **Floating multi-select panel.** ✅ Was appended to `document.body` and positioned
   once from `getBoundingClientRect`, so it floated over unrelated rows on any
   scroll. Now an absolutely positioned child of the filter item, which moves with
   its trigger for free — there is no position left to forget to recalculate.

Defect 3 (the unconstrained `Strike` excuse) is untouched and still due before
Pass 11 — see the carried-over table above.

## Three decisions the designer flags for the product owner (20a)

1. **"Set" for a named group** — because "collection" was doing two jobs. Folder or
   group work as well; it's a rename, not a redesign.
2. **The camera works signed out** (15b) — the best thing to put in front of a
   stranger at a show, but it's a product call about giving away your comparables.
3. **Condition prefill should be switched off** until high clears 70% (17b) — the
   designer arguing for *less* product.

---

## Screen index

Where every `data-screen-label` in the design document lands.

| Turn | Screens | Pass |
|---|---|---|
| 1b/1c | shell, Bench, Hunt, listing detail, propose trade | 1 ✅ / **7 ✅** |
| 2a–2e | masthead, home signed in/out, **trade board (2e — the one built)** | 2 ✅ / **7b ✅** |
| 3a–3d | trade board v2 *(built then set aside for 2e)*, collector profile, settings | **7 ✅**, **3 ✅**, 6 ✅ |
| 4a–4c | sign in, create account, ten settings rooms | 6 |
| 5a–5c | one door, add an item, offer it | 5 (superseded by 6) |
| 6a–6c | step 1 destination, step 2 item, step 3 terms | 5 |
| 7a–7d | orders list, order page, buyer states, handshake | 4 |
| 8a–8e | my listings, bids & offers, saved, messages, notifications | 4 |
| 9a–9f | letters, Q&A, review, report, appeal, lot, the map | 8, 9 |
| 10a/10b | my collection, matrix, wanted list | 4 (matrix 🚧 13) |
| 11a/11b | new set, new want | 13 🚧, 4 |
| 12a/12b | Almanac index, era guide, three questions, leaderboard | 14 🚧, 15 🚧 |
| 13a/13b | browse collectors, everything owned | **3 ✅** |
| 14a/14b | units, matrix, map fallback, state picker | 10 |
| 15a/15b | six mobile screens | 10 |
| 16a/16b | all empty states | 10 |
| 17a/17b | staff desk, strike review, taxonomy, prefill | 11 |
| 18a | three defects | **two fixed in 3 ✅**; the `Strike` constraint before 11 |
| 19a/19b | member page, moderation queue | 11 |
| 20a | readiness sheet — the designer's own build order | reference |
| 21a/21b | write an entry, thirteen badges | 14 🚧 |



Other Notes:
Where the design genuinely overrules — four places
T13's two-page create flow, which is already shipped. listing_create_config.html is live. Turn 6 makes it three steps, deletes the "yours or stock" radio ("it was solving a problem the destination choice solves better"), and turns "from my collection" into a route that skips step 2 rather than a config toggle. I've put a ⚠ on Pass 5 noting it replaces working code — and that we keep T13's image slots while dropping T13's config page.

10.20 Final UI/UX Polish Pass — I read its scope: global navigation, sensible grouping, consistent cards, an engaging home page, the brand voice, a mobile pass. That's the redesign, verbatim. 10.20 becomes a sign-off checklist rather than a task.

10.11's "move filters to a horizontal layout" — turn 1c makes it a vertical rail with counts. Already built that way in Pass 1.

Turn 5 → turn 6, internal to the design itself.

10.10 is not a conflict. The dev plan and the design independently landed on the same thing — tradeability is a property of the item, not a marketplace. Worth saying because it looks like overlap and isn't.

What's still owed from the data-model plan
Untouched, and some of it the design actively needs:

T3/T4 year ranges now have a new consumer — the tracker matrix reads first_year/last_year to hatch the "never issued" cells, so a gap you could never fill isn't counted against you
~~T13 image slots (image_role) — reinforced by turn 6b, not superseded~~ **shipped**: the schema landed with Pass 5's sell-flow work (listings 0019 / collections 0010, one-front-one-back constraints), and Pass 8b built the slot UI that persists the roles it shows
T13 lot images — turn 9d draws exactly T13's spec
T5 taxonomy cleanup, T11 governance — 19b says ReferenceDataSuggestion's accept-and-apply "is the whole job"
T14 ledger, R6 gold labels, prefill polish, Postgres check — all stand
And the design adds what the data-model plan deferred: it explicitly parked WantedItem ("revisit with 10.14"), and turn 11b now specifies its five fields.



---

# The inbox — raised in review, triaged 2026-08-05

Each of these was verified against the code before being given a status. Two were
one-line faults and are fixed; the rest are scheduled.

### ✅ Sign-in landed on My Bench instead of home — **fixed**

`LOGIN_REDIRECT_URL` was `/accounts/dashboard/`. Turn 2b makes the signed-in home the
page a returning member actually wants — what closed, what is closing, what arrived —
whereas the bench is where you go when you already know there is something to do.
Landing on a to-do list is a worse greeting than a newspaper. Now `/`, with a test.

### ✅ Blocking was broken both ways — **fixed**

Two faults, both from **rendering a write as a link**:

1. **Unblock silently did nothing.** `unblock_user_view` is POST-only, but the privacy
   room rendered it as an `<a href>` — wrapped, confusingly, in a `<form>` posting to
   `profile_edit`. Clicking it issued a GET, hit the method guard, and bounced you to
   your messages. That is exactly what it looked like from outside. It is a POST
   button now, and it returns to the room you were in rather than the settings front
   door.
2. **There was no way to block anybody.** The only route was `messaging:block_user`,
   which takes a **conversation** — so you had to already be mid-argument with somebody
   to block them, and blocking is most useful before that. New
   `messaging:block_person` takes a person, and the profile carries Block / Unblock as
   the quietest thing in the action row. 4c is clear that blocking works quietly and is
   not a complaint, so it is never styled as an accusation.

Seven tests, including one asserting the privacy room renders a `<form>` and not an
`<a href>` — the fault was invisible from behaviour alone.

### 🔄 Google address autocomplete — nothing was removed; likely a Google-side change

The code is intact at `templates/accounts/address_form.html:56–87` — a Places
`Autocomplete` on `line1` filling city/state/postcode from the components — wrapped in
`{% if google_maps_api_key %}`. **The key is present** (checked 2026-08-05: 39 chars,
reaching `settings.GOOGLE_MAPS_API_KEY`, passed into both address views), so the block
does render and the script tag is emitted. Nothing in this codebase took it out.

That points at the Google side, and the likeliest cause is dated: **the legacy
`google.maps.places.Autocomplete` was deprecated in March 2025** in favour of
`PlaceAutocompleteElement`, and keys on projects created after that cut-off cannot load
it — it fails in the browser console with the page looking exactly as though the
feature was removed. Next-likeliest: Places API not enabled on the key, or no billing
account.

**What to do:** open the address form and read the browser console; the error names the
cause outright. Then **Pass 8b** should move that inline script into
`static/js/address-autocomplete.js`, try `PlaceAutocompleteElement` first with the
legacy call as a fallback, and — the real fix either way — **say so on the page when
the loader fails** instead of silently rendering a plain text field, which is what made
this indistinguishable from a deletion.

### ⬜ The listing form still looks nothing like the design — **correct, and scheduled**

Honest answer: **not yet done, and the plan did not say so clearly enough.** Pass 5
rebuilt step 1 (`sell_start.html`, the three destination cards) and step 3 (the terms
panels), but **step 2 — `listing_create.html`, the actual item form — was never
touched.** It is pre-revamp markup: an inline `<style>` block, `--color-*` legacy
tokens, three `kb-` classes in the whole file. The same is true of
`collection_item_form.html`, `add_from_order.html`, `address_form.html` and
`collection_item_detail.html`, which is why the trade block added in Pass 7 sits in old
furniture.

It is now **Pass 8b**, *and* it is listed at the top of this document under **"Screens
still on pre-revamp markup"** — so the next person to ask this question finds the
answer before they finish scrolling.

### ✅ An unsold lot should come back to the collection — **and let them say it is gone** — shipped in Pass 8b

Half became true in Pass 7 (availability derived, lots release on their own). The
second half landed 2026-08-06: `CollectionItem.disposition` (`held / traded /
sold_elsewhere / given_away / lost`). Anything but held blocks both `open_to_trade`
and `would_trade`, the shelf label is the disposition's own words, and
`_close_traded_pieces` now records `traded` instead of overwriting the owner's
tradeability answer. The control lives on the edit form under **Where it is** —
never on create, where a piece is obviously in hand — and `traded` is never a form
choice. Still owed, in the register: **runs, the tracker matrix and county counts
still include departed pieces** — whether a sold-elsewhere 1926 Cameron still counts
toward "47 of 67" is a product question, not a bug fix.

### ✅ Special Issue / Limited Edition as an attribute — shipped in Pass 8b

Wanted, but **`addon_type` is the wrong home** and it is worth saying why before
somebody adds it there. `addon_type` holds things like *Turkey Tag* — physical add-ons
attached to a licence, one per item. A Special Issue turkey tag is **both**, so putting
them in the same category makes the collector choose between two true things.

Landed 2026-08-06 as its own category: `issue_class`, seeded through the pipeline
like materials (*Special Issue, Limited Edition, Commemorative* + Other; regen was
lossless, seeder `created=4 drift=0`). It inherits everything the other categories
have — both forms, the API grouping, the rail, the Other flow with admin promotion —
because everything reads `FORM_LICENSE_TYPE_CATEGORIES` and the forms' rows now come
from one shared constant. The name stayed `issue_class` as recorded here; renaming
is seed data plus one constant if a better word ever arrives.

---


In the trading block module everything says closes a gap even when it doesn't. Same with What you Came For it just makes one up if you came not through an item link (like just from a collectors page it will just randomlly say one is what you came for).





The Almanac. I put it in the nav and drew one entry on the home page, but never the section itself: era guides, county spotlights, the daily three questions.

Smaller, still real: lots listing, writing a review, Q&A on a listing, report/appeal forms, the national map at full size, and the notification emails (seven templates — worth doing, they're most people's main contact with the site).

Deliberately last: mobile, empty states, admin dashboard


Home Page Greeting Ideas:
Late one tonight, huh.
First light already.
Welcome back, [name].
Good to see you, [name].
Still chasing '37, [name]?
Sixty-two of sixty-seven.
One county left in Maryland.
Small game in two weeks.
Archery season's close.
Deer camp weather.
Last light of the season.
Good scouting weather out there.
Back tag weather, if there's such a thing.
Opening day's closer than you think.
Zeroed the rifle yet?
Public land's calling your name.
Quiet as a Sunday license office.
Nothing wrong with another look.
Fair morning for county-chasing.
Still holds up, this weather.
You know where the good ones hide.
You're closer than you think.
You've earned a look today.
Something's waiting in the trade box.
One bid came in overnight.
A trade offer's on the table.
Your wanted list got a hit.
The counties don't fill themselves.
Kept the bench warm for you.
Not much moving. Worth a look anyway.
Album's got room for one more.
New listing since you left.
Drawer's not as full as it looks.
Wind's up. Good day to sit and look.
Your collection always got room for one more.

Item provinance

For a listing, require at least one image (Front - we might want to require back too - image slots 3-5 are always optional though).

In the add item move the steps to the top right nav (see docs\internal\design\ui-ux-redesign-model\Backtag Design Blueprint.html for example).

Need to look at accessibility options - a lot of the user base will be older. One simple idea - in the top right a little popout button with a slider for text size. Need to research best practices.

Need to add a section somewhere on the site for like system information (probably in the top right dropdown). Need platform/system info, application version, release notes, and platform/system how-to's/FAQ's.
Will also probably need a like help button too - mainly so there is an easy point to submit something to admins. FAQs could possibly go there too.

In messages module. Add option to delete a thread - only deletes for user, system still stores the messages. Or maybe user can just archive.

----
parking lot:

daily trivia and daily polls are getting parking lot.

----
Current hunt season dates data:

Greetings — your original plan — is the best use, full stop. "Two weeks till opening day" hitting a PA user at the right moment is worth more than any ticker, because it's personal and ephemeral. This alone justifies the scraper.

1. Seasonal browse surfacing (the sleeper best use). Collector interest is seasonal: when turkey season is three weeks out, turkey stamps get more attention. A small homepage module — "Turkey opens in Maryland in 18 days" → a row of turkey tags and stamps currently listed — is authentic retail logic, not gimmick. It's the same instinct as a hardware store putting shovels out before the snow. Cheap to build too: you already have species/method facets on LicenseType, so it's a filter query keyed to the nearest opener.

2. Auction-timing hint for sellers. This one's unexpected but genuinely practical: an auction ending at 8am on opening morning of rifle season is ending while half its bidders are in a tree stand. One dry line in the listing form when the chosen end date collides with a major opener — "Heads up: this ends opening weekend of PA rifle. Your bidders may be in the woods." — is useful, funny, and shows the site knows its people better than almost anything else could.

3. Empty states and micro-copy. "Quiet in here this week. Rifle opened Monday — everybody's out." Costs nothing, lands exactly in the voice you've built, and turns a dead moment (no results, no messages) into a wink instead of a shrug. You already decided humor lives in low-stakes UI; this is that.

4. Notification/email timing. Instead of arbitrary marketing cadence, key the occasional digest to season moments: "Opening day Saturday — here's what came in from Pennsylvania this month." Same email, better excuse to send it, and the excuse is one your users actually care about.

PA not the default for everything - just choose state. — ✅ done, Pass 10g
(10.21): home state is the default everywhere, PA only for the undeclared.
The market sort and filter have some bugs.