# Backtag (codebase: KeystoneBid)

Backtag is a Django marketplace for **antique/vintage hunting licenses** — buy, sell, trade
and collect. It was renamed from KeystoneBid in Pass 10f. Every word a member reads says
**Backtag**; code identifiers deliberately keep the old name (`kb-` classes, `--kb-*` tokens,
`config`, the repo). Don't rename identifiers.

For auctions we follow the **eBay model**: members set their own terms — we are never the
auctioneer or auction house. Only **expired** licenses are tradeable.

Brand voice for any member-facing copy: a well-worn field journal - earthy, honest, quietly
proud. Aged-paper tones, forest greens, warm browns, clean serif type. Never corporate,
never rustic kitsch. The app is striving for genuine authenticity.

## Plans — read before starting work

- **Roadmap and status index:** `docs/internal/plans/plan_workable_product_10062026.md`. It has
  phases 0–9 with tasks `W<phase>.<n>`, the owner decisions D1–D11 (§3) and the parked
  register (§11). Check §3 before starting any task marked ❓.
- **Design pass log:** `docs/internal/plans/plan_design.md` records what each pass shipped,
  the deviations, and the deferred register.
- **Product spec:** `docs/internal/plans/dev_plan.md`. Its status stamps stop at 10.9; the
  roadmap is current.
- **Data model and reference data:** `docs/internal/plans/data_model_img_prefill_plan.md`.
- **Prefill:** `image_prefill_model_dev_plan.md`.
- **Brand:** `backtag_implementation_plan.md`.
- **Intake lists:** `tasks_08-30-2026.md`, `todo.txt`.
- **Bug inbox:** `docs/internal/backtag_known_issues.xlsx`.
- **Research and context notes:** `docs/internal/research/`, `docs/internal/context/`.

**Update the plans whenever task status changes.** Stamp `✅ YYYY-MM-DD — <commit>` on the
W-task in the roadmap, and record the pass in `plan_design.md`.

If a dependency blocks a task, do not silently skip it. Move the task down the roadmap with
the dependency named. Nothing drops unless the owner agrees it won't be built; park it in
the roadmap's §11 instead.

## The design

**The design plans are not a suggestion; they are what we are building.**

- **Canvas:** `docs/internal/design/ui-ux-redesign-model/project/KeystoneBid UX Revamp.dc.html`,
  with `support.js` and `assets/`. It holds 21 turns and 58 frames (ids `1a`–`21b`),
  newest turn first. It is also on Claude Design: import
  https://claude.ai/design/p/5353903d-008e-4c32-8ae3-7e06d53e3302?file=KeystoneBid+UX+Revamp.dc.html
  through the claude_design MCP (https://api.anthropic.com/v1/design/mcp, auth via /design-login).
- **`Backtag Design Blueprint.html`:** the curated Backtag edition (55 screens, 15 chapters).
- **Standalone files:**
  - Add Item Ideas: the prefill ledger.
  - Auction Room: Pass 9e as built.
  - Rooms and the Watcher: Pass 9f as built.
  - Backtag Logo: mark 2B was chosen.
  - Backtag Map Plates.
- **Read the drawing, not the prose.** Find the frame by `data-screen-label` and take the
  exact hex and px values from its markup. Then render the page and look at it, at desktop
  width and at about 400px.
- **A screen with no frame** is built in the design system from its nearest frame. Say which
  frame you used.

## Tech stack (do not introduce alternatives without asking)

- **Backend:** Django 5.0, Python. The upgrade to 5.2 LTS is approved (D5, roadmap W8.2) and
  goes together with moving to the `STORAGES` setting.
- **DB:** SQLite in dev, PostgreSQL in prod (config switch only — keep code DB-agnostic).
- **Frontend:** Django templates (server-rendered), custom CSS and **vanilla ES6+ JS**.
  React is allowed but not used yet. d3 and topojson are vendored for the map.
- **Payments:** Stripe Checkout (we never touch card data). Seller payouts are **not built**;
  Stripe Connect waits on D2.
- **Shipping:** Shippo, through a hand-written REST client in `apps/shipping/providers/`.
- **Email:** AWS SES (SMTP backend in production, console backend in dev).
- **LLMs:**
  - The Anthropic API powers image prefill (Claude Haiku 4.5) and moderation escalation.
  - OpenAI's moderation endpoint is the classifier tier.
- **Address autocomplete:** Google Places. It runs only when `GOOGLE_MAPS_API_KEY` is set.
- **Static and media:** WhiteNoise for static files. AWS S3 for media, not wired yet (W8.4).
- **Background jobs:** Django management commands plus cron. Celery/Redis only at scale.
- **Hosting:** a single AWS EC2 t3.micro to start. AWS Lambda for heavy operations; the
  prefill Lambda backend isn't wired yet.

## Project layout

```
config/settings/{base,development,production}.py   # split settings; manage.py defaults to development
apps/
  accounts/      # auth, profiles, Follow, addresses, settings rooms, the Bench (member dashboard)
  bids/          # auction bidding, proxy max, soft close, winner resolution
  collections/   # CollectionItem, WantedItem, Collectors, trade board, tradeability
  core/          # reference data (State, GeographicUnit, LicenseType, ReferenceDataSuggestion),
                 # MarketplaceSettings, Terms, home/research pages, map + search APIs, seed/job commands
  enforcement/   # Strike, AccountRestriction, OrderHandshake (excuse flow) — no routes of its own
  favorites/     # saved listings/items
  listings/      # Listing, ListingImage, ListingQuestion (Q&A); the sell flow; the Market
  messaging/     # one Conversation per pair of members, rooms, blocks, reports
  moderation/    # the watcher: watch terms → classifier → LLM escalation → staff queue (flags only)
  notifications/ # in-app notifications + email letters
  offers/        # buy-now negotiation (Offer); buyers originate, sellers only counter
  orders/        # Order + AddressSnapshot, lifecycle/state transitions, seller/buyer ledger
  payments/      # Stripe Checkout + webhooks
  prefill/       # Django side of image prefill (PrefillJob, JSON API, ledger copy)
  reviews/
  shipping/      # Shipment, tracking, Shippo wrapper + polling fallback
  staff/         # /staff/ desk and moderation room
  trades/        # TradeOffer, Trade, composer, dual-shipment lifecycle
prefill/          # pure prefill logic (core.py) + config/ (prompts, extraction schema, knobs)
templates/        # ALL templates: base.html, components/, emails/, and one folder per app
static/css/       # reset, variables (--kb-* tokens), shell, kb-ui, mobile, staff; pages/ = one sheet per page
static/js/        # vanilla modules (item-form, prefill, ground-map, trade-composer, ...); vendor/
utilities/        # ref_data/ (hand-edited CSVs) → clean_reference_data.py → cleaned/ (what the seeders load);
                  # sales_api/, seasons_api/ = standalone research prototypes, not imported by apps/
sandbox/          # prefill evaluation notebooks
docs/             # internal/ (plans incl. the roadmap, design, research, context);
                  # tech_docs/; user_docs.md/ (member-facing FAQs + How-Tos drafts)
media/            # dev uploads only
requirements/{base,development,production}.txt
```

- **Each app owns its models, views, urls and admin.** Its templates live in
  `templates/<app>/`.
- **Keep coupling to model relationships only.**
- **Business logic lives in `services.py` or a named module beside it** (e.g. `sell_flow.py`,
  `composer.py`, `ledger.py`), never in views.
- **Keep the code modular** so it is easy to find and update.

## Domain rules that are easy to get wrong

- **Listing vs CollectionItem are separate.** CollectionItem is a member's own inventory,
  which may never be listed.
- **Snapshot, don't reference, for history.** Orders, Shipments and Trades use
  `AddressSnapshot` and snapshot pricing and shipping, so later profile edits never rewrite
  past records.
- **Only auctions lock an item exclusively.**
  - Tradeability is derived and open by default; a piece at auction is not tradeable.
  - Trading has no browse page of its own; "open to trade" is a filter.
  - `listing_type='trade'` is being retired (W6.19), so don't build on it.
- **No cart.** Buy-now delists a listing on *successful payment* (the Stripe webhook), never
  on the click. Offers are binding; buyers originate and sellers only counter.
- **Messaging and moderation:** one message thread per pair of members. Moderation flags
  messages for human review and never disables anyone automatically.
- **"Other" and filter cleanliness.**
  - *Today:* "Other" is a seeded LicenseType row in each category and a shape/color choice.
    Picking it files a ReferenceDataSuggestion. Member-entered values never appear in public
    browse filters until an admin promotes them; approval pushes the value into the data
    model for that attribute.
  - *Decided (roadmap D1, 2026-10-06; being built in Phase 2):*
    - Null means "not given".
    - A value that isn't on the list is a write-in stored with the item.
    - Accepting it creates the value and moves every waiting item onto it.
    - There is no "Other" bucket in public filters.
    - **The conversion must lose no data:** backup and dry-run report first, every existing
      "Other" link becomes a write-in, and the old rows are deleted only in a later release.
  - **Don't add new "Other" choices to taxonomy fields.** Genuine "something else" answers
    (strike, excuse and report reasons) stay, with a required note.
- **Required-to-publish fields gate publishing; optional fields never do.** Use the
  `listing_completeness_score` property; don't hard-block on recommended or optional fields.
- **Geography:**
  - A **"Statewide" GeographicUnit** exists per state for licenses not tied to a sub-unit.
  - Federal stamps attach to the "Federal" pseudo-state (code `FD`).
  - All 50 states are seeded, counties first.
- **Years:** the floor is the state's `min_license_year` (derived from data for `FD`). The
  ceiling is the current year − 25. Never type a literal year.
- **Home state is the default** wherever a state is preselected (`apps/core/defaults.py`).
  Never hardcode Pennsylvania. County never prefills.
- **Place names render verbatim** as `{unit}, {state}`, never with "County" appended
  (Baltimore City ≠ Baltimore County).
- **A listing's listed date is `Listing.published_at`,** never `CollectionItem.created_at`.
- **Prefill never fills material or condition,** and never overwrites a value the member
  entered.
- **Use explicit status fields** so cron/background jobs can drive automation.
- **Derive, don't hardcode.** If a value can be computed from seeded data, compute it.

## UI conventions

- **Styling:**
  - Tokens are `--kb-*` in `static/css/variables.css`.
  - Components use `kb-` classes from `kb-ui.css`.
  - Each page has one stylesheet in `static/css/pages/`.
  - Legacy `--color-*` styling is being retired (W7.10); never use it in new work.
- **Form errors:** every form and formset error renders visibly in the `.if-errors` band,
  never only inside hidden inputs.
- **Destructive actions take two steps:** a branded trigger, then a plain-language confirm
  (a modal with JS, a page without).
- **Empty states** never say "empty", "none" or "zero", and never show a control with
  nothing behind it.
- **Emails** go through the `templates/emails/letter.html` shell (Georgia, inline styles).
- **The staff desk** uses its own slate palette (`staff.css`).
- **Deferred work in code** is marked like this, not with TODO:
  `DEFERRED — <what>. Blocked on: <dependency>. Register: docs/internal/plans/plan_design.md`.
  Older markers still say `docs/internal/plan_design.md`; W0.3 fixes them.

## Conventions

- Prefer Django ORM relationships over free text (e.g. `home_county` is an FK, not a string).
- **Webhooks (Stripe, shipping) must be idempotent and authenticated.** The Shippo webhook
  isn't authenticated yet (W1.1).
- **LLM prompts, tool schemas and knobs live in config files** (`prefill/config/`,
  `apps/moderation/config/`), never inline in `.py`. Each exposes a prompt-version hash.
- Secrets live in `.env` (never committed). Read via python-dotenv. There's an `.env.example`.
- New env vars: add to `.env.example` and note them in the relevant settings file.
- **Migrations:** create and run, then sanity-check against both SQLite and Postgres before
  commit. Local Postgres isn't set up yet (W8.3).
- **Migrations must be safe on a live site (expand, then contract).**
  - Add columns as nullable or defaulted.
  - Backfill in a separate step.
  - Drop old fields one release after the code stops reading them.
  - Never rename a column in one step.
  - A data migration ships with a dry-run report and a backup first, and must lose no data.
- Use Django's built-in security defaults (CSRF, ORM, template autoescape, PBKDF2) — don't
  bypass them.
- **Test form flows with the exact POST the page's JS produces,** including the hidden fields
  and formset management values, not a tidy hand-built payload.
- **Probe and scratch scripts delete every row they create.**

## Workflow expectations

- **Branching:** branch `feature/alpha-pN-<name>` off `alpha-pN`, and commit at logical task
  boundaries with a short, descriptive message.
- **End of a pass:** it is squash-merged into `alpha-pN` as one commit,
  `alpha pN dev tasks TN - <name>`. Afterwards, `git diff alpha-pN <branch> --stat` must be
  empty.
- **GitHub:** the user initiates pushes and merges unless they hand that off.
- **When unsure about schema or domain behavior, ask rather than guess.** If the plans aren't
  clear, ask.

## Common commands

```bash
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
python manage.py createsuperuser

# Reference data — run in this order. Create-missing-only by default;
# --overwrite updates rows from the CSV and clobbers admin edits.
python manage.py seed_states
python manage.py seed_geographic_units
python manage.py seed_license_types

python manage.py seed_demo            # demo listings/items; remove_demo --yes clears them
python manage.py run_jobs [--loop N]  # every periodic job once — dev stand-in for cron
                                      # (doesn't run poll_shipments / poll_trade_shipments)
python manage.py test                 # ~860 tests, ~95 s
```
