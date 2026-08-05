# KeystoneBid

review docs\internal\design\ui-ux-redesign-model in detail.
or access it here:
Use the claude_design MCP (https://api.anthropic.com/v1/design/mcp, auth via /design-login) to import this project:
https://claude.ai/design/p/5353903d-008e-4c32-8ae3-7e06d53e3302?file=KeystoneBid+UX+Revamp.dc.html

Focus on these files (the whole project is readable):
- `KeystoneBid UX Revamp.dc.html`

Also read these files the selection imports:
- `assets/keystone-mark.svg`
- `assets/keystonebid-logo.png`
- `support.js`

Implement: `KeystoneBid UX Revamp.dc.html`

## What this project is

KeystoneBid is a Django marketplace for **antique/vintage hunting licenses**
(buy, sell, trade).
For auctions, we follow the **eBay model**: users set their own terms - we are never the auctioneer or
auction house. Only **expired** licenses are tradeable.

Brand voice for any user-facing copy: a well-worn field journal - earthy, honest, quietly
proud. Aged-paper tones, forest greens, warm browns, clean serif type. Never corporate,
never rustic kitsch.

the redesign docs are located here: docs\internal\design\ui-ux-redesign-model
plan: docs\internal\plan_design.md
other plans: docs\internal\data_model_img_prefill_plan.md
General dev plan: docs\internal\dev_plan.md

update the plan whenever status on tasks changes: docs\internal\plan_design.md

The app is striving for genuine authenticity.

The code should be modular - so that it is easy to find and do updates.

## Tech stack (do not introduce alternatives without asking)

- **Backend:** Django 5.0, Python
- **DB:** SQLite in dev, PostgreSQL in prod (config switch only — keep code DB-agnostic)
- **Frontend:** Django templates (server-rendered) + custom CSS + **vanilla ES6+ JS** + html + react 
- **Payments:** Stripe Checkout (we never touch card data)
- **Shipping:** Shippo
- **Email:** AWS SES
- **Background jobs (MVP):** Django management commands + cron. Celery/Redis only at scale.
- **Hosting:** AWS single EC2 t3.micro to start.
- AWS Lambda for heavy operations.
- AWS S3 for media.

## Project layout

```
config/settings/{base,development,production}.py   # split settings
apps/
  accounts/      # auth, profiles, verification, addresses
  bids/          # auction bidding, winner resolution
  collections/   # CollectionItem, WantedItem (user-owned inventory)
  core/          # shared reference data: State, GeographicUnit, LicenseType, ReferenceDataSuggestion
  enforcement/   # Strike, AccountRestriction, excuse flow
  favorites/     # saved listings/items
  listings/      # Listing, ListingImage (listing_type: auction/buy_now/trade)
  messaging/
  notifications/
  offers/        # buy-now price negotiation (Offer); buyers originate, sellers only counter
  orders/        # Order + AddressSnapshot, lifecycle/state transitions
  payments/      # Stripe checkout + idempotent webhooks
  reviews/
  shipping/      # Shipment, tracking, provider wrappers + polling fallback
  trades/        # TradeOffer, Trade, dual-shipment lifecycle
  notifications/ # in-app + email
templates/        # base.html + components/
static/css, static/js
media/            # dev uploads only
requirements/{base,development,production}.txt
```

Each app is **self-contained** (own models/views/templates/urls). Keep coupling to model
relationships only. Business logic lives in `services.py`, not in views.

## Domain rules that are easy to get wrong

- **Listing vs CollectionItem are separate.** CollectionItem is user-owned inventory that
  may never be listed.
- **Snapshot, don't reference, for history.** Orders/Shipments/Trades use `AddressSnapshot`
  (and snapshot pricing/shipping) so later profile edits never rewrite past records.
- **Filter cleanliness rule:** user-entered "Other" free-text values are flagged and do
  **not** appear in public browse filters until an admin promotes them to system values.
  Instead they grouped in an "Other" option in dropdowns, until admin approval. Admin approval
  means the value is pushed to the data model for the associated attribute.
- **Required-to-publish fields gate publishing; optional fields never do.** Use the
  `listing_completeness_score` property - don't hard-block on recommended/optional fields.
- **"Statewide" GeographicUnit** exists per state for licenses not tied to a sub-unit;
  federal stamps attach to a "Federal" pseudo-state.
- **Use explicit status fields** so cron/background jobs can drive automation.

## Conventions

- Prefer Django ORM relationships over free text (e.g. `home_county` is an FK, not a string).
- Webhooks (Stripe, shipping) must be **idempotent**.
- Secrets live in `.env` (never committed). Read via python-dotenv. There's an `.env.example`.
- New env vars: add to `.env.example` and note them in the relevant settings file.
- Migrations: create and run, then sanity-check against both SQLite and Postgres before commit.
- Use Django's built-in security defaults (CSRF, ORM, template autoescape, PBKDF2) — don't
  bypass them.

## Workflow expectations

- Commit at logical task boundaries with a short, descriptive message (the plan commits per
  feature, e.g. "Buy-now complete"). User will initiate commits to Github.
- When unsure about schema or domain behavior, ask rather than guess. If docs\internal\dev_plan.md is not clear, then ask.

## Common commands

```bash
python manage.py runserver
python manage.py makemigrations && python manage.py migrate
py manage.py createsuperuser
python manage.py seed_reference_data   # counties / license types
python manage.py test
```