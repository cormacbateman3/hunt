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

### Status legend

✅ done · 🔄 in progress · ⬜ not started · 🚧 blocked on a model

---

## ⚠ Screens still on pre-revamp markup

**Read this before concluding a screen was missed.** Several pages have not been
brought onto the design system yet, and it is not an oversight — they are scheduled.
Verified 2026-08-05 by counting `kb-` classes against inline `<style>` blocks and
`--color-*` legacy tokens:

| Screen | Template | Lands in |
|---|---|---|
| **Add / edit an item** (sell step 2) | `listings/listing_create.html`, `listing_edit.html` | **Pass 8b** |
| **Add / edit a collection item** | `collections/collection_item_form.html`, `add_from_order.html` | **Pass 8b** |
| **Shipping address** | `accounts/address_form.html` | **Pass 8b** |
| **Collection item detail** | `collections/collection_item_detail.html` | **Pass 8b** |
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
- The **State/County** facet reads *Where they collect*, filtered on their items,
  not on `UserProfile.county` — that field is still free text until Pass 6, and
  filtering people by an unvalidated string would quietly lose collectors.
- The **map tab** says it isn't drawn rather than drawing a control over nothing
  (16b's rule, and the design's own *"Map — no geometry"* screen).
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

## Pass 7 — Trade board v2 ✅ DONE

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

## Pass 7b — 10.10 finished ✅ DONE

*2026-08-05 · commits `eac29eb`, `1b34609` · 429 tests green (21 added)*

**Design refs** — turn 3a, 13a. Dev plan **10.10**, remaining scope.

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

### One click, at last

The three Pass 3 markers are all cleared. The collector card opens on the piece of
theirs that **answers something on your own wanted list**, falling back to whatever
they most recently opened; the trade board's tile opens on its own piece. Landing on a
chooser would ask a question the card already knows the answer to.

### The rebuild against the frame's own values

*Second correction, 2026-08-05. The first build of 3a came from the turn's paragraph;
this one comes from its markup. See the reading rule at the top of this document.*

**The two rendering faults** — invisible to a green suite, obvious the moment the page
was drawn:

1. `.tb-piece-hit` was a **three-column grid with four in-flow children**, so the mark
   wrapped onto a second row under every licence in both shelves.
2. `.tb-note` was `white-space: nowrap` in an `auto` column, so "WHAT YOU CAME FOR"
   claimed ~130px of a ~241px half and the title broke a character at a time.

Both had the same cause: **the note was a column when the design has it as the second
line inside the text**. The row is `display:flex` with three children now.

**Structure**

| | Was | Now (from the frame) |
|---|---|---|
| Outer | one 4-column grid `196 1fr 196 300` | `1fr 300px`, rail beside the **whole** left stack |
| The band | nested in the centre column, ~484px | spans the full 900px floor |
| Halves | `1fr 30px 1fr`, bare glyph | `1fr 1px 1fr`, **30px brass disc** on the hairline |
| Roster | header/list/foot as three loose blocks | **one white card**, hairline-divided rows |

**Colour** — six tokens added, because the frame uses distinctions one flat green
cannot carry: `--kb-table` `#22301c` · `--kb-table-edge` `#1a2416` · `--kb-table-head`
`#1e2a19` · `--kb-table-cash` `#1b2416` · `--kb-table-cash-on` `#2b3a22` · plus
`--kb-on-forest-give` `#d9ab5f` / `--kb-on-forest-get` `#9fc48c` for the two half
labels.

**The licences are cream now.** `--kb-cream` cards on the dark table — *"the licenses
on the table become the brightest objects on the page"*, which is what the turn is for.

**Other corrections from the same read**

- A piece on the table **stays on its shelf**, tinted and ticked, and appears as a card
  as well. It is a clone, not a move; the shelf keeps the checkbox that submits.
- Shelf notes are **two words** — `trade_block_label()` beside `trade_block_reason()`.
  "The owner has closed this piece to trade" ran off a 196px row and was the wrong
  voice for somebody's own collection. It reads "At auction" / "You closed this".
- `shown` and `total` count **the same set**; they printed "1 of 0".
- The cash strip's direction and figure now turn round **with the reader** — Rae asks
  for $40, so Rae sees "to me" and Walt sees "from me" — and the figure is rendered
  server-side rather than waiting for a script.
- The band gives a **date**: "Both ship by Mon 10 Aug", not "within 5 days".
- Decline is a real white button with the softest border, not a text link; accept is
  `14px/700` at `14px 30px` against the other two at `13px/600` at `12px 20px`.
- Trader card is **parchment** with a 38px **square** of initials, and carries "Ships
  in N days on average" — withheld below three shipped parcels, because one fast
  parcel is not a reputation.

`TheDrawingTests` holds the eight facts the layout depends on that a suite *can* see.

### Still open, and now genuinely small

- **`listing_type='trade'` itself.** Already unreachable — the sell flow's three
  destinations are collection / auction / store, and nothing creates one. Retiring the
  *enum* is a data migration over historical rows with `Trade` FKs pointing at them,
  which buys nothing today. Left alone deliberately; see the register.
- **Shared carrier/service** across both shipments (register).
- **Composer search without JavaScript** (register).

---

## Pass 8 — Letters, Q&A, reviews, reporting, appeals ⬜

**Design refs** — turn 9a (emails), 9b (Q&A + reviews), 9c (report + appeal).
Dev plan **10.13**.

- **One email shell, seven letters** — green bar, mark, date, a **serif headline
  that is a sentence** (not the enum label the generic template prints today), an
  optional item block, one action, a footer saying why it arrived. 560px, Georgia,
  nothing depends on an image loading. Two lines worth stealing: *"Replies to this
  address reach a person, not a machine"* and, on anything with a deadline, the
  consequence in plain words.
- **Q&A** — answers indent under questions with the seller marked in brass. Price
  talk gets hidden with a one-line explanation and a link to Make an offer —
  kinder than a Flag button and it teaches the norm once.
- **Reviews** — each of the three options gets a line describing the deal it fits,
  and the footer draws the line between a poor review and an actual complaint.
- **Report / Appeal** — both 10.13, neither built. **Blocked on the `Report` model**
  (see Carried-over).

---

## Pass 8b — The forms nobody restyled ⬜

*Raised in review 2026-08-05 and confirmed: the create/edit forms were never brought
onto the design system. Passes 5 and 7 built new screens around them and left the
middle alone, which is why the trade block added in Pass 7 sits in old furniture.*

**Design refs** — turn 6b (step 2, the item), 10a/11b (collection item), 4c (field
grammar). Dev plan **10.8**, T13.

| Screen | State today |
|---|---|
| `listings/listing_create.html` | pre-revamp: inline `<style>`, `--color-*` legacy tokens, **3 `kb-` classes in the whole file** |
| `listings/listing_edit.html` | same shape, same problem |
| `collections/collection_item_form.html` | same |
| `collections/add_from_order.html` | same |
| `collections/collection_item_detail.html` | same — inline styles throughout |
| `accounts/address_form.html` | same, **and** its Places script wants moving out to `static/js/` and made to say when it fails to load |

Restyle onto `kb-ui.css`, not a rewrite: the field grammar, the prefill panel and the
image slots all work. What changes is the furniture — the three uppercase label sizes,
the 3px/4px geometry, hairlines instead of the dashed drop zone, and the same
`_trade_block.html` / private-block fieldsets the design draws.

**Two things ride along**, because they are the same files:

- **`CollectionItem.disposition`** — `held` / `sold elsewhere` / `given away` / `lost`.
  A lot that expires unsold already releases the piece on its own (Pass 7), but nothing
  can record that a piece has physically **left**, so somebody who sold it at a show has
  no way to stop it being offered. It is also the honest home for the ownership gap
  `_close_traded_pieces` currently papers over.
- **`issue_class` taxonomy** — *Special Issue*, *Limited Edition*, *Commemorative*. Its
  own category, not `addon_type` (see the inbox for why). Touches the seed data and the
  filter rail as well as these forms.

---

## Pass 9 — The map ⬜

**Owes the deferred register** — the Collections **map tab** and the profile's
**Ground covered** panel both draw a placeholder today. The arithmetic already exists
in `apps/collections/tracker.py`; only the geometry is missing. The header line on the
collectors browse also regains its **distance** measure.


**Design refs** — turn 9e (at size), **9f (the specimen sheet — read this one
carefully)**. Dev plan **10.17**.

An **engraved survey map, not a web map**. Flat parchment ground, 0.5px hairline
borders, five green steps, type that looks set rather than rendered.

- **Quantise the ramp on fixed counts, never on max.** The current code runs
  `scaleSequential([0, max], interpolate('#e8f5e2','#1a5c0d'))` — the designer
  flags this outright: no two counties share a shade and **the legend can never be
  honest**. Buckets: 0 / 1 / 2–4 / 5–9 / 10–24 / 25+.
- Fill = what's for sale; **brass inner rule = a county you already hold**. The two
  together answer the only question a collector brings to a map.
- Three depths, one component: country → state → county. No third zoom.
- Non-county states draw as a grid of named blocks in the same shades.
- Never a dead end: an empty county still opens the panel.
- Not to do: no basemap, no pins, no animated draw-in, no shadow/radius/gradient.

---

## Pass 10 — Empty states, mobile, fifty states ⬜

**Design refs** — turn 16a/16b (empty states), 15a/15b (mobile), 14a/14b (units).

- **Empty states — three shapes.** *Nothing yet* (Petrona sentence naming what will
  be here, one dark button, a real number from the database). *Nothing matched*
  (filters as removable chips, each relaxation with its own count, then save it as
  a want). *Nothing left to do* (**green rule** — a reward, not a failure).
  Two rules: never render an empty control; never use the words empty, none or zero.
- **Mobile — six screens, 390pt, 44pt targets.** Two things happen on a phone: you
  get a letter and bid, or you're at a show with a licence in your hand. Tabs are
  Hunt / Mine / Bench / Add. The desk work (matrix, sets, settings rooms, Almanac
  article, dual rosters) becomes one line: *open this on a computer*.
- **The four unit-label substitutions** (14a) — the cheapest high-value item on the
  readiness sheet. Every label and every sentence saying "county" reads
  `issuance_unit_label`; numbered units sort by `unit_number` and print with their
  type prefix; `is_statewide` renders as **Statewide** wherever a unit name would
  go; anything drawing a shape checks `geo_data_complete` first and **disables the
  map toggle with the reason attached rather than hiding it**.

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
| **The map** (Collections tab, profile *Ground covered*) | honest placeholder + a hatched panel; the figures beside it are real | county **geometry** does not exist; `GeographicUnit.valid_from`/`valid_to` absent | **9 / 10** | draw the choropleth; the arithmetic in `apps/collections/tracker.py` is already there |
| ~~**Trade board** tab~~ ✅ | local at `/collections/?tab=trade`, built from collection items and sorted by overlap with your wanted list | settled in Pass 7 | — | — |
| **Distance** — *"41 within a hundred miles"* | reads *N will trade · N selling now* | no geocoding, no geometry | **9 / 10** | add the measure to the header line |
| ~~**Filtering people by where they live**~~ ✅ | the rail now asks which question you mean | settled in Pass 6 | — | — |
| **Per-type mail preferences** | Notifications & mail says what arrives today | no `NotificationPreference` model | **later** | render the switches where the marker sits |
| **Records export** | the room offers a real address to ask | nothing but the work | **10** | build the CSV, including the private purchase block |
| ~~**`SHIP_BY_DAYS`**~~ ✅ | now `MarketplaceSettings.ship_by_days`, read via `bench.ship_by_days()` | settled in Pass 4 | — | a job that *enforces* it is still unwritten; it remains a promise |
| **Saved hunts** — standing searches that go looking for you | omitted from Saved; marker in `templates/favorites/list.html` | no `SavedHunt` model | **10** | render the strip where the marker sits |
| **Named sets** on My collection | omitted; marker in `templates/collections/my_collection.html` | no `CollectionSet` model | **13** | render the set strip |
| **Closing price** on a sold favourite | the row says only that it sold | price history | **12** | print what it made |

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
| 2a–2e | masthead, home signed in/out, trade board | 2 ✅ |
| 3a–3d | trade board v2, collector profile, settings | **7 ✅**, **3 ✅**, 6 ✅ |
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
T13 image slots (image_role) — reinforced by turn 6b, not superseded; still absent from the schema
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

### ⬜ An unsold lot should come back to the collection — **and let them say it is gone**

Half of this is already true and became true in Pass 7: availability is derived, so a
lot that expires or is taken down releases the piece **on its own**, with no flag to
restore. What is missing is the second half — **nothing can record that a piece has
left**. Somebody who sold it at a show off-site has no way to say so, and the piece
sits in their collection being offered to people.

Needs a disposition on `CollectionItem` (`held` / `sold elsewhere` / `given away` /
`lost`), which is genuinely useful beyond this: it is what the ledger and the export
need, and it is the honest place for the ownership-transfer gap that
`_close_traded_pieces` currently papers over by closing tradeability. **Pass 8b.**

### ⬜ Special Issue / Limited Edition as an attribute

Wanted, but **`addon_type` is the wrong home** and it is worth saying why before
somebody adds it there. `addon_type` holds things like *Turkey Tag* — physical add-ons
attached to a licence, one per item. A Special Issue turkey tag is **both**, so putting
them in the same category makes the collector choose between two true things.

It is a property of the **issue**, so it wants its own taxonomy category —
`issue_class`, seeded with *Special Issue*, *Limited Edition*, *Commemorative*. That
inherits everything the other categories already have: the browse rail, faceted counts,
the "Other" free-text flow with admin promotion, and the prefill resolver. The cost is
that it touches the seed data, the six form dimensions, the filter rail and the prefill
config, which makes it a **data-model task, not a UI one** — it belongs with T5, and it
is listed there as well. **Pass 8b**, unless the category name should be something else,
which is a call worth making before the seed data exists.

---


In the trading block module everything says closes a gap even when it doesn't. Same with What you Came For it just makes one up if you came not through an item link (like just from a collectors page it will just randomlly say one is what you came for).