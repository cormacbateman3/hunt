# UI/UX Redesign — master plan

**Design source of truth**
`docs/internal/design/ui-ux-redesign-model/project/KeystoneBid UX Revamp.dc.html`
(21-turn design document, ~100 screens, exported from Claude Design)

**Related plans** — this document does not replace them, it sequences the UI work
and carries over the items they left open.
- `docs/internal/dev_plan.md` — feature plan, tasks 10.x / 11 / 13.x
- `docs/internal/data_model_img_prefill_plan.md` — item-kind & add-on taxonomy, T0–T14

---

## How to use this document

1. **Every pass re-reads the design model.** Open the `.dc.html` and read the turns
   named in the pass. Do not work from this summary alone — the copy, the exact
   metrics and the designer's rationale live in the source and the voice *is* the
   deliverable.
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

## Pass 3 — Collections zone ⬜ NEXT

**Design refs** — turn 13a (browse collectors), 13b (everything owned), 3b
(collector profile), 10a (my collection), 10b (matrix + wanted list).

The zone has **four tabs**: `Collectors` (opens first) · `Everything owned` ·
`Trade board` · `The map`.

- **Collectors** — people sorted by *overlap with you*, not join date. Big card for
  the ~8 who overlap (of-your-wants / items / sets going, "in his words", a strip
  of the display case, Propose a trade + Follow); compact card for everyone else.
  Nobody gets an empty card — county and size are always known.
- **Everything owned** — the existing item browse, kept. Three changes: the six
  license-type categories stop being labelled with database names and read as
  questions a person would ask; choices show as removable chips, not nine closed
  dropdowns; **Apply is gone**, the grid updates as you go.
- **Collector profile** — a display case with a person attached, not a settings
  page in public. Trust card, display case, and a "looking for" rail
  cross-referenced against the viewer's own collection (*you have one, 1931, mint*).
- **My collection** (lives in My Bench, not here) — reorder to case → results →
  list, bulk bar leading into selling, group-by, gaps as Map/Matrix/List.
- **Two JS defects to fix in `browse_collections.html`** (18a) — see Carried-over.

---

## Pass 4 — My Bench: the rest of the workspace ⬜

**Design refs** — turn 8a–8e, turn 7a–7d.

- **My listings** — the **Interest** column is the missing one: bids, watchers,
  offers, unanswered questions in one place. Unanswered things get the rust edge
  and the only filled button. Honest observations on duds ("nineteen days, six
  watchers — try $165?"; "one relist left of three").
- **Bids & offers** — merge `my_bids` and the offers list, split by **direction**:
  *Chasing* and *On my things*. Three money columns: mine, theirs, what it means
  ("You'd keep $214 of it").
- **Saved** — favourites sorted by what closes soonest, with countdown and bid
  state on the card. Sold ones stay, greyed. Saved hunts strip.
- **Messages** — two panes, not two pages. The deal stays pinned on screen with
  amount, your side, live deadline. **Catch the agreement**: a buyer saying "Monday
  is fine" is exactly the handshake case and is invisible to enforcement today.
- **Notifications** — reading marks read (drop the per-row Mark-read form). One
  sentence with the hour in the margin. Three dot states: rust = on a clock,
  brass = wants an answer, nothing = news.
- **Orders list** — one ledger, not Purchases + Sales cards. Status in plain
  English with the consequence: *cancelled in 14 hours*, *a strike on Thursday*,
  *assumed received on Monday*. One action per row.
- **Order page** — eight cards → a header, a **five-stop rail**, and one
  brass-bordered "Your turn" box. Two ways to ship side by side. Money, addresses
  and the other party move right. **Delete the Stripe session id and the package
  inputs** (captured on the listing).
- **The handshake, offered early** (7d) — today the exception flow appears only
  once a strike exists, after the damage. Offer it beside the deadline, in the
  seller's own word, with the strike ladder printed next to it.

---

## Pass 5 — The sell flow ⬜

**Design refs** — turn 6a/6b/6c (**this supersedes turn 5** — 6's opening line is
*"You're right and 5a was wrong: the destination should be the first question"*).
Dev plan 10.8 amendments, T13.

- **Step 1 — where it's going.** Three destination cards (My collection / The
  Auction House / The General Store), each ending with *the questions it will ask*.
  Below: **from my collection**, duplicates first — this skips step 2 entirely.
- **Step 2 — the item.** 400px evidence rail on the left: photographs with
  **labelled slots** (Featured·front, Back, three optional) and the prefill
  read-out with per-field ✓ / ? / ○ / ×. Title and Description at the top under
  their real names. Taxonomy out of the drawer. Live buyer's-card preview.
- **Step 3 — the terms.** One panel per destination, each carrying only its own
  fields, each ending with the action, the cost of changing your mind, and one line
  of local knowledge. Shared shipping strip from selling defaults.
- **Lot listing** (9d) — quantity 2–10, one row per piece with front/back, over 10
  routes to box-lot guidance. Rides **10.15**.

---

## Pass 6 — Auth and the ten settings rooms ⬜

**Design refs** — turn 4a (sign in), 4b (create account), 4c (all ten rooms),
3c/3d. Dev plan **10.16** (versioned terms).

- **Sign in / Create account** — read like a membership application from a licence
  office. Nav bar off, centred nameplate, hatched parchment ground, `FORM 1 · ENTRY`
  / `FORM 2 · NEW MEMBER`. Password rules as a ticking checklist. **A human at the
  bottom** — a real address and a promise of a real reply; auth is where older
  users get stranded. Terms acceptance is versioned (10.16) — the current form has
  no checkbox at all.
- **Settings — six stacked cards on one 720px page become ten named rooms**, in
  four groups: **Me** (Profile & display, Verification & trust, Addresses) ·
  **Hunting** (Alerts & saved hunts, Notifications & mail) · **Selling** (Listing
  defaults, Payouts & fees) · **Account** (Privacy & blocking, Records & export,
  Policies & standing).
- Profile & display carries the **showcase-layout picker** (Display case first /
  Map first / One piece at a time / Just the collection).

---

## Pass 7 — Trade board v2 ⬜

**Design refs** — turn 3a. Dev plan **10.10**.

The two middle columns become **one dark panel — the table the licences are laid
on** — so the items are the brightest thing on screen and direction is read from
position plus a brass arrow, not from border colour. Dual rosters left and right,
full right rail for the negotiation block and the other trader's card, and a light
action band under the table restating the terms in Petrona 21px before three
weighted decisions: **Review & accept** brass with a raised edge, counter outlined
in forest, decline quietest.

`propose_offer.html`, `offer_detail.html` and `trade_detail.html` are already
strong — restyle onto the new system, do not restructure.

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

## Pass 9 — The map ⬜

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

Name, optional rule, membership table for hand-picked ones. **Without it there is
no definition of what counts as a gap**, so the matrix (10b), the sets tabs, the
gap counts and the seed-the-wanted-list flow are all unbuildable.

Turn 11a: a rule is a target, not a folder — it knows what belongs, so it can count
what's missing, feed the matrix, seed the wanted list, and tell you a gap came up
for sale. Three sets ship as suggestions to every new collector.

## Pass 14 — The Almanac + badges 🚧

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

# Carried over from the other plans

Verified against the code on 2026-08-04.

## From `data_model_img_prefill_plan.md`

| Item | Status | Note |
|---|---|---|
| **T12 Department → Category** | ✅ **already shipped** | `ItemCategory` at `apps/core/models.py:14`; `category` FK on both `Listing` and `CollectionItem`. The plan's own 2026-08-03 audit confirms it. No action. |
| **T13 single-item image slots** | ⬜ **genuinely outstanding** | `image_role` does not exist — grep returns zero. "Featured"/"Back" are client-side badges keyed off array index, so reordering the grid relabels them and nothing persists. Needed by **Pass 5**. |
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
| `CollectionItem` — purchase price, acquisition, private note | 6c | Pass 5 |
| `GeographicUnit.valid_from` / `valid_to` | 14b | Pass 10 — until it exists, a Colorado collector's "19 of 185" is measured against today's map and **overstates their gaps** |
| **`UserProfile.county` is a `CharField`** | 4c / CLAUDE.md | Pass 6. CLAUDE.md says *"`home_county` is an FK, not a string"*; it is currently free text help-texted "User's home Pennsylvania county". This is the bug class that produces "Towson, MD, PA". |
| Terms version + acceptance | 4b / 10.16 | Pass 6 |
| `MarketplaceSettings.ship_by_days` | Pass 1 note | Pass 4 |

## Two JS defects in `browse_collections.html` (18a)

Both fail by **showing a plausible-looking interface rather than an error** — the
same rule as the empty states in 16b: never render a control over nothing.

1. **Silent fetch failure.** Changing state clears the county select and all six
   type selects *first*, then fetches replacements in a bare `Promise.all` with no
   catch. Offline or a 500 leaves empty dropdowns in a state that definitely has
   counties, with nothing suggesting a retry. Fix: fetch first, clear second;
   restore the previous selection on rejection and say so.
2. **Floating multi-select panel.** Appended to `document.body` and positioned once
   from `getBoundingClientRect`. Nothing recalculates. Six of these sit in a strip
   that scrolls sideways on any narrow window, so a live checkbox list floats over
   unrelated rows — you can tick the wrong filter without knowing which one you
   touched. Fix: close on scroll/resize, or better, position it as a child of the
   filter item.

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
| 1b/1c | shell, Bench, Hunt, listing detail, propose trade | 1 ✅ / 7 |
| 2a–2e | masthead, home signed in/out, trade board | 2 |
| 3a–3d | trade board v2, collector profile, settings | 7, 3, 6 |
| 4a–4c | sign in, create account, ten settings rooms | 6 |
| 5a–5c | one door, add an item, offer it | 5 (superseded by 6) |
| 6a–6c | step 1 destination, step 2 item, step 3 terms | 5 |
| 7a–7d | orders list, order page, buyer states, handshake | 4 |
| 8a–8e | my listings, bids & offers, saved, messages, notifications | 4 |
| 9a–9f | letters, Q&A, review, report, appeal, lot, the map | 8, 9 |
| 10a/10b | my collection, matrix, wanted list | 3 (matrix 🚧 13) |
| 11a/11b | new set, new want | 13 🚧, 3 |
| 12a/12b | Almanac index, era guide, three questions, leaderboard | 14 🚧, 15 🚧 |
| 13a/13b | browse collectors, everything owned | 3 |
| 14a/14b | units, matrix, map fallback, state picker | 10 |
| 15a/15b | six mobile screens | 10 |
| 16a/16b | all empty states | 10 |
| 17a/17b | staff desk, strike review, taxonomy, prefill | 11 |
| 18a | three defects | 11 (+ constraint before it) |
| 19a/19b | member page, moderation queue | 11 |
| 20a | readiness sheet — the designer's own build order | reference |
| 21a/21b | write an entry, thirteen badges | 14 🚧 |
