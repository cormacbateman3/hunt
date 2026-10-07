# Plan — Workable Product

**Started 2026-10-06 · revision 2 (same day, after a second full pass).** This plan takes Backtag
(repo: KeystoneBid) from where it stood on 2026-10-06 to a **workable product**:

- every core flow works end to end on a real staging server;
- the whole drawn redesign is built;
- the known bugs are fixed;
- the taxonomy and image prefill can be trusted;
- the operator (one person) has the tools to run the site and ship updates safely.

After that, the owner runs their own UI/UX redesign rounds on a stable base (§14), and then
launches (§13).

**Status legend:** ✅ done · 🔄 in progress · ⬜ not started · 🚧 blocked (dependency named) ·
❓ waits on an owner decision (§3) · ⏸ parked (§12) · ★ stretch (§11)

**Size:** S = small (hours) · M = medium (days) · L = large (a week or more)

**Task IDs:** `W<phase>.<n>` for build work and `WO.<n>` for the owner track (non-code). The
"From" column cites where each task came from:

| Short name | Source |
|---|---|
| dev | `docs/internal/plans/dev_plan.md` (section numbers like 10.11, or line numbers L…) |
| design | `docs/internal/plans/plan_design.md` (Pass N, register rows, L…) |
| frame | the design canvas `docs/internal/design/ui-ux-redesign-model/project/KeystoneBid UX Revamp.dc.html` (ids like 9c, 11b) |
| dm | `docs/internal/plans/data_model_img_prefill_plan.md` (T-items, R-items, acceptance #) |
| pf | `docs/internal/plans/image_prefill_model_dev_plan.md` |
| bt | `docs/internal/plans/backtag_implementation_plan.md` (§1–§7) |
| 0830 | `docs/internal/plans/tasks_08-30-2026.md` (10.21–10.26) |
| todo | `docs/internal/plans/todo.txt` |
| brief | `docs/internal/research/payments_tax_briefing_10062026.md` (Stripe Connect, 1099s, sales tax, account ownership, SMS, Django, legality) |
| audit | the 2026-10-06 code audit (every app, a test run, "Other", prefill, production settings) |
| ops | the 2026-10-06 operator audit (Django admin smoke test, staff desk, moderation, money records, external services) |
| xcheck | the 2026-10-06 second pass: every source doc checked line by line against this plan |
| util | the 2026-10-06 review of `utilities/`, personalization, usage tracking and low maintenance |
| book | Jason R. Reiman, *Pennsylvania Hunting Licenses — A Collector's Guide* (2024), the stakeholder's book, in `docs/internal/research/` (gitignored: 595 MB, all rights reserved) |

---

## 1. How this plan relates to the others (pending D10)

- **This file is the roadmap and the status index.** It says what's next, in what order, and
  what's blocking it.
- **The older docs stay as the record.** `plan_design.md` keeps the pass log and deviations.
  `dev_plan.md` keeps the product spec. The data-model and prefill plans keep their specs.
- **When a W-task finishes:**
  1. Stamp it here: `✅ YYYY-MM-DD — <commit or pass>`.
  2. Record the pass in `plan_design.md`, as CLAUDE.md requires.
  3. Stamp any source doc the task closes.
- **Nothing in the older docs is dropped by omission.** Anything not scheduled here is in §11
  Stretch or §12 Parked, with the reason and what would bring it back.

---

## 2. Where we are (2026-10-06)

### What's built and working

- **Size and health:** 18 apps and 97 templates. **861 tests, all green.** `check` is clean and
  there are no unmade migrations.
- **The three marketplaces:** auctions (proxy bidding, soft close), buy-now with binding offers,
  and trades with the four-column board and dual shipments.
- **The order spine:** orders with address and price snapshots, plus the handshake (excuse) flow.
- **Integrations, in test mode:** Stripe Checkout and Shippo.
- **Collections:** collections, Collectors, Everything owned, the matrix and wants views.
- **Messaging:** one thread per pair, rooms, and the moderation watcher.
- **The rest:** letters, Q&A, reviews, the ground map, all-50-states reference data, image
  prefill (local backend), the Backtag rename §1–§3, and the staff desk (first slice).

### Where the work and the docs stand

- **Last work was 2026-08-31,** on `feature/alpha-p4-2`, which hasn't been rolled into
  `alpha-p4`. `alpha-p4` is 130 commits ahead of `origin/main`.
- **The docs reorganization is uncommitted.** `dev_plan.md` stopped being stamped on 2026-08-03,
  `plan_design.md` on 2026-08-31.

### The biggest gaps (audit + ops + xcheck)

1. **Money**
   - **Sellers are never paid.** There's no Stripe Connect, yet two screens promise payouts.
   - **The platform fee is charged twice:** added to the buyer's total *and* deducted from the
     seller's take.
   - **Nothing records** Stripe fees, refunds, disputes, payouts or label costs.
   - **The platform silently pays for every trade label** and every seller-paid label.
   - **There are no refunds,** and a retried buy-now erases the first buyer's payment record.
2. **Safety holes**
   - The Shippo webhook is unauthenticated, and either party can post "delivered" to their own
     order with no tracking.
   - A 3-strike ban quietly lifts once the strikes expire.
   - Restrictions staff set by hand are overwritten every night.
   - Blocking a member doesn't stop them dealing with you.
3. **Live crashes**
   - The Dashboard crashes for anyone sent a trade offer on an unlisted piece.
   - In Django admin, no user can be opened or created (500).
   - The moderation-event list crashes on group rooms.
4. **Promised features that don't exist**
   - Sellers can't take a listing down.
   - Bought or traded pieces never reach the new owner's collection.
   - Local pickup is half-built.
   - There are no public Terms or Privacy pages.
5. **Moderation**
   - Claude reads the wrong part of the thread.
   - Two built-in "urgent" watch terms fire on ordinary collector talk.
   - The queue lists one row per message, with no record of whether a flag was real.
   - Nothing watches for off-platform payment scams.
   - OpenAI billing was never activated, so tier 2 has returned 429 on every call.
6. **Operator tools:** no order desk, refunds, job-health view, email-failure log or finance
   view. The staff tiles only work for superusers.
7. **Production isn't deployable.** The settings crash on start, there's no S3, no deploy config,
   no crontab, no CI, and the code has never run on Postgres. Django 5.0 has been out of support
   since April 2025.
8. **Taxonomy and prefill**
   - "Other" is a stored value in seven categories plus shape and colors, and the write-in text
     is thrown away.
   - Prefill has 8+ bugs, no matcher tests and no measured accuracy.
9. **About twenty old-style screens,** including the money pages, and two legacy routes still
   live.

---

## 3. Decisions

### 3a. Answered 2026-10-06

| ID | Decision | Notes |
|---|---|---|
| **D1** ✅ | **"Other" → null.** Null means not given. A value not on the list is a write-in stored with the item. Accepting it creates the value and moves every waiting item onto it. There's no "Other" bucket in public filters. Genuine "something else" answers (strike, excuse and report reasons) stay, with a required note. | **Owner's condition: no data lost in the process.** Phase 2 spells out the no-loss rules. |
| **D4** ✅ | **In scope:** the Field Guide, badges, lots, onboarding, phone verification. **Stretch (★):** Three questions. **Price history:** the owner is unsure how to approach it; see the recommendation below. | **Still parked:** spreadsheet import, provenance PDFs, admin broadcast, bt §6 and §7. |
| **D5** ✅ | **Django 5.0 → 5.2 LTS.** | Security fixes until April 2028. Do it together with the `STORAGES` move: on 5.2 the old storage settings are silently ignored (brief §8). |
| **D3** ✅ | **Trade money.** <br>• **A trade that ships:** $1 per side. Each side also pays its own label at cost when it's bought through Backtag. <br>• **A trade with no shipping** (two collectors at a show): **no $1 fee**. <br>• **Any cash add-on goes through Stripe and carries a fee, even in person** ("they're already going through the payment process at that point"). | Supersedes dev §8.3 ("$1 only with a platform label, no % on trades") and the `TradeFeeTransaction` docstring. **Mechanics:** with cash, the $1 fees ride on the cash charge, because a standalone $1 card charge loses ~33¢ to Stripe. Without cash, each $1 is added to that side's label charge. **Two details to confirm:** (1) the cash fee is the same % as sales (D12)? (2) does a side that ships with its own label (not bought through Backtag) still pay the $1? |

**Price history — recommendation (D4b, confirm).** The research found **no automated source of
sold prices that is free and allowed by the source's terms.** eBay's sold-data API is gated, and
WorthPoint and the auction houses forbid scraping. So:

- **In scope (W7.14):** price history built from Backtag's own completed sales, plus a staff tool
  to hand-enter researched comparables with source and date. Each is labelled by source and never
  blended. This costs little, and the data only grows from the day it starts.
- **Stretch (★S1):** the ~12 screens that display it. They show nothing until enough comparable
  sales exist, per the empty-state rule.
- **No scraping and no eBay API.** eBay's Browse API is partner-approval only, and the client in
  `utilities/sales_api/` was never run. Staff can hand-enter eBay asking prices into the
  comparables tool, labelled "eBay asking, {date}". Keep the prototype's source-labelled schema
  idea for W7.14.

### 3b. Open — each blocks the tasks named

| ID | Question | Recommendation | Blocks |
|---|---|---|---|
| **D2** | **How sellers get paid** | Research first (WO.1–WO.2). Stripe Connect can be set up three ways (brief §1; numbers in `docs/tech_docs/cost_estimate.md`): <br>• **A — Stripe sets pricing** (Standard accounts, direct charges). Backtag keeps its whole fee ($3.20 on a $40 sale at 8%). Stripe files the 1099s, and refunds and disputes land on the seller. **But** the buyer's card statement shows the *seller's* name (more "I don't recognize this charge" disputes), sellers get a full Stripe account, and Stripe Tax can't collect as the marketplace. <br>• **B — Backtag sets pricing, seller pays card processing** (Express-style accounts, destination charges, application fee = Backtag's % + Stripe's processing). The statement shows Backtag; onboarding is embedded in Backtag's pages with light Stripe branding; Stripe Tax works. Backtag pays $2 per active seller per month plus payout fees, and files 1099s through Stripe's tool. A one-sale seller nets Backtag $0.86 at 8%; 100 sales a month nets ≈ $240 before hosting. <br>• **C — Backtag sets pricing and absorbs processing** (the first recommendation): loses money on small, occasional sales. **Ruled out.** <br>**Recommendation: B**, because you want sellers to barely notice Stripe and buyers to see Backtag. Choose A if margin and the least upkeep matter more (~$80/mo more at 100 sales). The seller keeps the same $35.34 of a $40 sale at 8% under A and B. | W4.6, W4.10, launch |
| **D6** | Leaderboard on Three questions | Only matters if ★S2 is built. Recommend **no leaderboard**, which also drops the "Held the Month" badge (bt §5). | ★S2, W7.16 | no we are doing collection leaderboards (but elegantly)
| **D7** | Wants: 11b form vs 10.26 rules | **One thing.** The 11b drawing is the screen, and a want *is* a rule. Add priority (max 10), the seeded home-state want, plain-language AND/OR, and a 6-condition cap. `WantedItem` grows; no second model. | W6.6, W6.7 |
| **D8** | "Set" as the name; by-rule sets in the first cut | **"Set"**, with both by-hand and by-rule sets (11a draws both). Sets replace the 10.14 `CollectionFolder`. | W6.3 |
| **D9** | **Badges** | One list to settle: <br>• **How many:** 13 (21b) or 17 (bt §5). <br>• **Kept or lapsing:** "never taken away" (dev L2273) or lapse rules (21b). <br>• **Ratings:** "4.8+ rating" badges, but reviews are Good / Middling / Poor. <br>• **Dependencies:** the Storyteller and Heritage badges need parked features. <br>• **Category count:** 4 or 5. <br>• **"All Three"** hardcodes PA/MD/OH; derive it instead. | W7.16 |
| **D10** | This plan as the master roadmap | **Yes.** `plan_design.md` stays the pass log and the known-issues sheet stays the bug inbox. | §1 |
| **D11** | Issue class: null means "ordinary" *and* "not stated" | Seed an explicit **"Ordinary issue"** value. | W2.8 |
| **D12** | **Platform fee: rate, and who pays it** | The code does both today. Frames 6c and 7c draw **"Commission 8%" deducted from the seller**, the dev plan assumed 5%, and the code default is 0%. **Recommend the eBay model:** the buyer pays item + shipping, and the fee comes out of the seller's proceeds as the Connect application fee. Owner sets the rate. **Consider a minimum fee** (e.g. $1.50), so items under ~$20 don't lose money; under D2-B the card processing is passed to the seller on top of the fee. | W4.5, W4.6, W4.10 |
| **D13** | **Enforcement ladder** | **A 3-strike ban is permanent until staff lift it,** stored as a ban rather than a 10-year suspension the sweep recomputes. **Restrictions staff set by hand stay until staff lift them;** the nightly sweep only manages strike-derived ones. | W5.1 |
| **D14** | **Moderation: keep, narrow or drop the Claude tier, and watch for scams?** | Fix Claude's context first (W5.9), then run the evaluation (W5.12); the decision rules are in W5.12. Cost isn't the issue (~$0.14 per 100 escalations). **Separately, recommend adding an off-platform-payment / scam trigger** (W5.13). It's the one harm OpenAI's classifier can't see and where an LLM clearly adds value. The current prompt says off-platform deals "aren't our business"; scams differ. | W5.12, W5.13 |
| **D15** | **Who owns the business and the accounts** | With the stakeholder: form the entity (LLC), get an EIN and a business bank account, and **open every *live* account in the business's name from the start** (Stripe, AWS, Google Cloud, Shippo, domain, SES). Stripe can't reliably move a live Connect platform and its sellers to a new entity; Google Cloud billing profiles can't change type (brief §4). The developer gets team access, not ownership. Dev/test accounts can stay as they are for now. | WO.1–WO.5, W4.6, Phase 8 |
| **D16** | **Production database: Postgres on the EC2 box, or managed (RDS)?** | **RDS smallest instance.** It gives automated backups and point-in-time restore with nothing to babysit, and frees the t3.micro's 1 GB RAM for the app. On-box is cheaper, but backups and restores become your job. | W8.7, W8.20 |
| **D17** | **Staging: its own small instance, or the production box?** | **Its own small instance, stopped when idle.** A bad staging deploy can never touch production. | W8.5 |
| **D18** | **Branch model** | Once `alpha-p4` lands on `main`: feature branch → squash-merge into `main` (keeps the one-commit-per-pass habit). `main` deploys to staging automatically; a tag deploys to production. The `alpha-pN` integration branches retire. | W8.10–W8.12 |
| **D19** | **Usage tracking: how?** Yes, track usage, minimally; you can't fix a drop-off you can't see. Most metrics that matter come from the app's own tables. | **First-party events** (W5.36): one table, route names (never full URLs), a daily-rotating hashed session (never an IP), no new cookies, a nightly rollup, raw events kept 90 days, charts on the staff desk and in the digest. **Optional add-on:** Plausible (~$9/mo, cookieless, zero upkeep) if traffic sources matter. **Not** Google Analytics (cookies, consent, Google's data use) and **not** self-hosted Umami or Matomo (another service to patch on a 1 GB box). New tech, so it needs your OK (stack rule). | W5.36 |
| **D20** | **A "license-issue" reference table: this class of license in this year** | The stakeholder's book (book §2i) shows collectors think in issues: 1931 Resident, 1937 Special Issue, 1946 Special Deer Hunter. That level holds the facts `LicenseType`'s year spans can't: material, background and lettering colors, serial pattern, whether a county number is printed, issued count, rarity, source page. **Recommend yes, PA first, built from the book's facts** (with the author's blessing, WO.10). It powers prefill validation and color-dating (W3.18), Field Guide plates (W7.15), rarity, and the price-history comparison key (W7.14). | W2.23, W3.18, W7.14 |

### 3c. Small calls

Each comes with a default. The plan follows the default unless the owner says otherwise.

| Call | Default |
|---|---|
| Ship deadline: business or calendar days | **Business days** (dev L725) |
| Email verification for buy-now, binding offers, Q&A and listing creation (bids, messages and trades already require it) | **Required for every binding or public action** |
| Refund policy line in the Terms | **"All sales final; refunds only when an item doesn't ship, an order is cancelled, or a dispute is decided"** (dev L834) |
| Back photo required on listings | **Optional, prompted** (front stays required) |
| Prefill reads the back image too | **Not now** (one image keeps cost and latency down); parked |
| Watcher also scans Q&A and reviews | **Yes, after the evaluation** |
| Greeting "Evening, snipe hunter." | **Cut it.** 2e: never invent a nickname the member didn't pick |
| Settings rooms: save as you change, or Save buttons | **Keep Save buttons** (older members) |
| Archives search (bt §1) | **Park it.** Replace the disabled box with a plain line saying what the Archives will be (no dead control) |
| CollectionItem completeness score | **No** |
| Camera works signed out (20a) | Decide only if ★S3 is built |
| SMS sender for phone verification | **AWS End User Messaging Notify** (no registration wait). Toll-free is the fallback, but it needs the EIN and live Privacy and Terms URLs (brief §7) |
| Payout cadence | **Automatic weekly** under D2-B: about $1 a month per seller in 25¢ fees. Monthly saves about 75¢ but makes sellers wait, and the $2 per active seller is the same either way. Under D2-A, Stripe's default schedule applies |
| Server instance type | **Graviton (t4g) instead of t3:** about 20% cheaper. Django, Pillow, psycopg2 and rapidfuzz all ship ARM wheels. Same EC2 service, so not a stack change |
| Cost trims (`docs/tech_docs/cost_estimate.md`) | ✅ **Decided 2026-10-07: add Shippo's 7¢ per-label fee to the label price members pay** (W4.2). **The rest the owner decides when each comes up:** new-account AWS credits at signup (W8.5–W8.6); Graviton at server setup (W8.6); a 1-year reserved RDS instance and a server savings plan after ~3 months of steady use. Not Lightsail, not Postgres on the web server (§5 rule 4) |
| Signature confirmation on high-value shipments | **Yes, above $200**: the best chargeback evidence for "never received" |
| Support address and domain | Owner picks (WO.7); replaces `help@keystonebid.com` |
| Server: self-managed EC2 (the stack today) or a managed AWS runtime | **Stay on EC2,** automated: unattended security upgrades, certbot timer, a swap file, scripted deploys. Revisit if OS upkeep bites. |
| Auto-restrict a brand-new account after N member reports in 24h (reversible) | **Yes, N = 3.** Spam control without a person; staff can lift it |
| Season lines (bt §4 / §7) | **Not a scraper.** If wanted later: a hand-checked openers file for PA, MD and OH, refreshed each August (★S4) |

**Settled — don't reopen:**
- No cart.
- Trade is not its own browse.
- One thread per pair.
- The watcher flags but never disables.
- Only auctions lock an item.
- Counties first, all 50 states.
- Prefill never fills material or condition.
- The Market filter rail is **vertical, with counts** (1c and 13b supersede 10.11's horizontal
  layout).

---

## 4. Sequence at a glance

| Track / phase | What | Why here |
|---|---|---|
| **Owner track (WO)** | Business, accounts, tax and legal setup | **Runs in parallel from day one.** WO.1–WO.2 gate the *live* Stripe account, not the build. |
| **0** | Housekeeping and doc reconcile | Clean base |
| **1** | Fix what's wrong now | Crashes, safety holes and false promises first |
| **2** | Taxonomy: retire "Other" with no data lost | Prefill, filters, wants, sets and the staff taxonomy screen read it |
| **3** | Image prefill updates | Needs Phase 2's write-in |
| **4** | Money: records, fees, payouts, refunds, pickup, the books | Nothing real can sell without it |
| **5** | Trust, safety, moderation, operator tools, legal | Before strangers trade |
| **6** | Collections, discovery, social, home, trades, lots | The drawn features still owed |
| **7** | Finish the redesign | Old screens, legacy removal, Field Guide, badges, price-history foundation |
| **8** | Pipeline, infrastructure and operations | **Start no later than Phase 4.** Staging is needed to test Connect webhooks for real. |
| **9** | Beta gate and handoff | End-to-end on staging, then hand back |

---

## 5. Running itself — the low-maintenance rules (owner, 2026-10-06)

> "We need to focus on manageable maintenance. This thing will not have people on 24/7 managing
> it."

Every task in this plan is built to these rules. When a task can be done two ways, the one with
less human upkeep wins.

1. **Every waiting state has a deadline and an automatic outcome.** Unshipped orders auto-cancel
   and refund. Pickups auto-complete. Unshipped trade sides auto-cancel. Disputes auto-hold.
   Appeals lapse. Low-severity flags auto-close. Offers and listings expire. Nothing waits on a
   person to unstick it.
2. **Never promise fast human response.** Copy says "within a few days" or "within a week",
   never "a person will reply" without a time frame. Support auto-acknowledges with links to
   the help pages.
3. **Moderate after publishing, never before.** Q&A, reviews and Field Guide entries go live
   with a report link and the watcher behind them. No approval queues.
4. **Managed beats self-hosted.** Managed database (D16), hosted error monitoring, no
   self-hosted analytics or search.
5. **Reviewed static data beats live scrapers.** A hand-checked file refreshed by a manual
   yearly command goes quiet when stale instead of showing wrong data.
6. **One nightly self-check catches silent failure.** The OpenAI 429 failed on every call and
   nobody noticed until an audit (W8.28).
7. **Breakers instead of pages.** Prefill switches itself off at a spend or error cap, and the
   form still works without it.
8. **Cleanup is scheduled.** Sessions, raw events, unattached prefill images, old notifications
   and old releases are cleared by jobs, not by hand.
9. **An LLM tier earns its place partly by the human queue work it removes** (D14).

**Alert budget.** Target: **under one page a month** in steady state. An alert that fires twice
without needing action gets demoted. Every alert has a runbook entry (W8.21).

| Tier | Events |
|---|---|
| **Page immediately** (phone) | Site down for 2+ checks · deploy auto-rollback fired · burst of payment or webhook errors · Stripe disabled the webhook · an automatic refund failed · urgent moderation (threat, minor, CSAM) · database unreachable · backup failed 2 nights running · disk over 90% · TLS certificate under 7 days |
| **Same-day email** (only if something happened) | Stripe dispute opened (it has a response deadline) · a cron job missed its schedule · SES bounce rate over 4% · a self-check failure that isn't a page · spend over 80% of budget |
| **Weekly digest** (W8.19) | Orders, GMV, payouts · failed jobs and error counts · open reports and appeals, with the oldest's age · flags and the share that were real · write-ins waiting · sales-tax thresholds · AI cost and prefill accuracy · pending dependency updates · funnel numbers and top zero-result searches |
| **Staff desk only** | Individual low-severity flags, write-ins, reference suggestions, Q&A flags, prefill corrections, member notes |

**The owner's routine once this plan is done:**
- **Weekly (about an hour):** read the digest, merge the dependency PR, clear the desk.
- **Yearly:** refresh any yearly data file, check Django's support window (5.2 ends April 2028),
  rotate secrets.

---

## Owner track — business, accounts and money setup

These are owner tasks, mostly not code; Claude can draft and research. **Interpretation to
confirm:** `backtagadmin@gmail.com` is the new project account that should own the services and
API keys, instead of the owner's personal account. Personal cards are fine for dev charges now.
The stakeholder's (or the business's) card goes on live accounts.

| ID | Task | From | Depends | Status |
|---|---|---|---|---|
| WO.1 | **Read the briefing** (`docs/internal/research/payments_tax_briefing_10062026.md`) and settle **D15** with the stakeholder: legal owner, entity (LLC), EIN, business bank account. | brief §4 | — | ⬜ |
| WO.2 | **CPA and attorney.** CPA: home-state sales tax from the first sale, barter-exchange 1099-B, which fees are taxable, 1099-K filer setup. Attorney: Terms, privacy, item legality (duck-stamp photos, transfer statutes), payout holds, LLC and code ownership between stakeholder and developer. Question lists are in the brief. | brief | WO.1 | ⬜ |
| WO.3 | **Project identity.** `backtagadmin@gmail.com` owns the Google Cloud project (Places key) and the other service logins. Add role addresses on the domain once it exists. Use a password manager, MFA everywhere, stored recovery codes, and give the stakeholder access. | owner | — | ⬜ |
| WO.4 | **Move keys and accounts off personal accounts.** Stripe, Shippo, Anthropic (prefill and moderation keys), OpenAI, Google Maps Places, AWS (SES, S3, EC2, SMS), domain registrar, GitHub, Sentry. Dev/test keys can move any time. **Live** accounts open in the business's name (D15). The new Places key needs W1.11 first: new keys can't load the legacy autocomplete. | ops §5 | WO.3, W1.11 | ⬜ |
| WO.5 | **Billing and limits.** Dev on personal cards for now; the business or stakeholder card on every live account before launch. Set AWS Budgets alerts and Anthropic and OpenAI spend limits. | owner | WO.1 | ⬜ |
| WO.6 | **Activate OpenAI billing** on the project account. Tier 2 of the watcher has returned 429 on every call (design L1500–1505). | xcheck | WO.4 | ⬜ |
| WO.7 | **Domain and mailboxes.** Pick the domain. Set up a monitored reply-to mailbox (letters promise "replies reach a person, not a machine") and a support address to replace `help@keystonebid.com`. | xcheck | WO.1 | ⬜ |
| WO.8 | **Words only the owner can supply:** Terms and privacy text (with the attorney), FAQ and How-Tos (`docs/user_docs.md/`), greeting phrases, the hero photograph, the badge list (D9). | various | WO.2 | ⬜ |
| WO.9 | **Data only the owner can supply:** label 75–100 prefill photos (W3.9), review the regenerated reference spreadsheet (W2.17), confirm the names for the six "Other" activities (W2.1). | dm, audit | — | ⬜ |
| WO.10 | **Ask the author of the book (the stakeholder)** for: <br>• written permission to use the book's photos for the internal prefill gold set and evaluation (p90 credits other collectors' photos too); <br>• his blessing to use the facts and derived tables (colors by year, serial formats, issued counts) in the app and the Field Guide, with credit; <br>• answers to what the book leaves open: Senior Lifetime 1984 or 1985; junior serial suffixes R/S and senior Y; reproductions and restrikes, and how to spot them; when WMU 2H was created; paper-era colors; whether PA ever sold a hunt-and-fish combination. <br>Perhaps he'd also write Field Guide entries. The PDF holds his personal contact details: never publish them. | book | — | ⬜ |

---

## Phase 0 — Housekeeping and reconcile

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W0.1 | Commit the `docs/internal` reorganization, this plan, the brief and CLAUDE.md. | audit | S | — | ⬜ |
| W0.2 | Roll `feature/alpha-p4-2` into `alpha-p4` (T13, squash, verify an empty diff). Then land `alpha-p4` on `main` (D18). | audit | S | — | ⬜ |
| W0.3 | **Repoint paths** broken by the reorganization: `plan_design.md` L9–10, `dev_plan.md` L1891 and L1927, and every code `DEFERRED` marker's `Register:` line. The FAQ now lives in `docs/user_docs.md/` (a folder whose name ends in `.md`; consider `docs/user_docs/`). | audit, xcheck | S | W0.1 | 🔄 2026-10-06: CLAUDE.md done |
| W0.4 | CLAUDE.md corrections. | audit | S | — | 🔄 2026-10-06: rewritten; the Filter rule is final once W2.18 lands |
| W0.5 | **Reconcile `dev_plan.md`:** <br>• Stamp 10.10–10.26 with where they landed. <br>• Strike the cart leftovers (L2013–2019, L2117, L2144, L2152). <br>• Max year → current−25. <br>• Close the 9.2 "Not Yet Built" list. <br>• Stack conflicts (Tailwind, HTMX, Alpine, "React overkill"). <br>• Mark 9.4e duplicate-prevention and `trade_eligible` as superseded by computed tradeability. <br>• The "already built" claims for local pickup (L1901, L2160) are overstated. <br>• Proxy bidding (13.3) is built. <br>• The 10.18 "last-3-months cards" are superseded by the Bench (confirm). <br>• Note that D3 supersedes §8.3's trade-fee rule. | dev, xcheck | M | — | ⬜ |
| W0.6 | **Reconcile `plan_design.md`:** <br>• Strike the register rows already cleared. <br>• "2e" → canvas id **2d** for the four-column board. <br>• Register 3d onboarding and 11b want-from-a-listing. <br>• Fix the screen index (11b isn't built; the matrix shipped in Pass 4). <br>• Refresh the "pre-revamp screens" table (about 20 screens, not 2). <br>• "Distance": only the per-card miles shipped; the header line is W6.18. | design, xcheck | S | — | ⬜ |
| W0.7 | `backtag_known_issues.xlsx`: mark #3 resolved (Pass 10h). | audit | S | — | ⬜ |
| W0.8 | Sweep the dev DB for probe leftovers. | memory rule | S | — | ⬜ |
| W0.9 | **Strike the done items in `todo.txt`.** About 40 are done; the xcheck list maps each to its pass. Leave the open ones pointing at their W-task. | xcheck | S | — | ⬜ |
| W0.10 | Untrack `utilities/seasons_api/all_seasons.json` (2.7 MB of scraped third-party content committed to git). | util | S | — | ⬜ |

---

## Phase 1 — Fix what's wrong now

### 1A Crashes and safety holes

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W1.1 | **Shippo webhook auth.** Add a secret token or signature check, and re-fetch tracking from Shippo rather than trusting the posted status. **Check manual tracking numbers** against Shippo `/tracks` for both orders and trades (today any string moves the item to in-transit). Tests. | audit, xcheck | M | — | ⬜ |
| W1.2 | **Close the self-service status endpoint.** `orders:update_status` (`apps/orders/views.py:191`) lets either party post `label_created`, `in_transit` or `delivered` with no proof. That dodges the non-shipment strike and feeds auto-complete. Status should move only on carrier events or staff action. | xcheck | S | — | ⬜ |
| W1.3 | **Dashboard crash:** a trade offer on an unlisted piece. `bench.py:202, 207, 225, 230` read `trade_listing.title` / `trade.listing.title`, and both FKs have been nullable since Pass 7b. Add a test. | xcheck | S | — | ✅ 2026-10-07 — `TradeOffer.subject_title`; Bench titles and thumbs fall back to the piece; 3 tests |
| W1.4 | **Django admin 500s.** User and UserProfile add/change pages fail because `county` is `editable=False` but listed in the inline and fieldsets (`apps/accounts/admin.py:11, 52`). The ModerationEvent list fails on group rooms (`apps/moderation/admin.py:64`). **Add a permanent smoke test** that renders every registered admin's list, add and change pages. | ops | S | — | ⬜ |
| W1.5 | **A late payment on a cancelled order is captured as "paid"** while the order stays cancelled (`apps/payments/views.py:207–223`). Flag it to staff now; the automatic refund is W4.3. | ops | S | — | ⬜ |

### 1B Broken promises and wrong copy

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W1.6 | **Sellers can't take a listing down,** though the UI promises it (`listing_terms.html:221`, `listing_edit.html:341`). Allow it for auctions before the first bid (dev L1280), and fix the two messages that point at it (`listings/views.py:1353`, collections "Take the lot down first"). | xcheck | S–M | — | ⬜ |
| W1.7 | **Payout and fee copy.** Make it honest until Phase 4: `apps/orders/ledger.py:468` and the Payouts settings room (`profile_edit.html:209–213`, "Backtag never holds your money"). The buyer page shows a platform fee *and* the seller view deducts it (D12). | audit, ops, xcheck | S | — | ⬜ |
| W1.8 | **Phone-verification copy** promises a trade gate that nothing checks (`register.html:115`, `bench.html:158`, `profile_edit.html:106`). Make it honest until W8.24 ships. | xcheck | S | — | ⬜ |
| W1.9 | **Brand leftovers:** `help@keystonebid.com` (4 places), the letter footer "keystonebid.com", the listing breadcrumb "Hunt", the home rail "Almanac". The address comes from WO.7. | xcheck | S | WO.7 for the address | ⬜ |
| W1.10 | **The dead `listing_type='trade'` still drives live screens:** the Market's "Open to trade" filter (`listings/views.py:371–375, 407, 595`) and the home page's Trading Block count and link (`core/views.py:352–355`, which reads about 0). Use derived tradeability. The card branches on it (`home.html:139, 186`, `_card.html:64`, `bench.html:128`) go in W6.27. | xcheck, util | S–M | — | ⬜ |
| W1.11 | **Address autocomplete** uses the legacy `google.maps.places.Autocomplete`, which keys created after March 2025 can't load. The project-account key will be new, so this **blocks WO.4**. Move to `PlaceAutocompleteElement`. | design L2329, xcheck | S | — | ⬜ |
| W1.12 | **Dashboard "Wanted list" tab** links to `#wanted`, which doesn't exist. Want create, edit and delete land on the items view. Point both at `?view=wants`. | 0830 §6, xcheck | S | — | ⬜ |

### 1C Missing pieces of flows that exist

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W1.13 | **Seller's `payment_received` letter.** The type is declared but nothing creates it. | design L2168 | S | — | ⬜ |
| W1.14 | **Payment-due reminder** to auction winners before the 24-hour non-payment strike (dev L2446). | xcheck | S | — | ⬜ |
| W1.15 | **The ship clock:** <br>• Add `paid_at`, `shipped_at`, `delivered_at` and `completed_at` to Order (CLAUDE.md: explicit status fields). <br>• **One deadline source** (`MarketplaceSettings.ship_by_days`) for both the strike and the Bench. Today the strike uses a hard-coded 5 calendar days counted from `updated_at`, which resets on any save. <br>• Business days (§3c). <br>• `auto_complete_orders` keys off `delivered_at`. <br>• This starts the deadline sweeps in §5 rule 1 (continued in W4.8). <br>• Absorbs the old "ship_by_days has no job" item. | xcheck, design L2163 | S–M | — | ⬜ |
| W1.16 | **Stripe webhook idempotency and tests.** Store processed event IDs. Test `checkout.session.completed`, `payment_intent.succeeded`, a bad signature and a replay. | audit | M | — | ⬜ |
| W1.17 | **Message reports.** A missing reason is saved as "other"; require a reason, and require the note for "Something else". | audit | S | — | ⬜ |
| W1.18 | **Prefill "Suggest it" files every miss as `license_type`,** and admin accept falls back to `addon_type`. Fix both, and reject the 5 pending dev suggestions. **Must land before anyone accepts a suggestion.** | audit | S | — | ⬜ |
| W1.19 | Add `poll_shipments` and `poll_trade_shipments` to `run_jobs`. | audit | S | — | ⬜ |
| W1.20 | Buy-now review calls Shippo synchronously (30 s timeout). Use a short timeout, a cached estimate and a visible fallback. | audit | S | — | ⬜ |
| W1.21 | **Config hygiene:** <br>• Pin `requests`. <br>• `.env.example` gains `SHIPPO_API_KEY`, `SHIPPO_API_BASE_URL`, `SHIPPO_DEFAULT_*`, `SITE_URL`, `USE_S3`, `AWS_*` and `ANTHROPIC_MODERATION_API_KEY`. <br>• Drop the unused `DEBUG`. <br>• Fix the stale "stub" help on `auto_complete_orders`. | audit, ops | S | — | ⬜ |
| W1.22 | **"The market sort and filter have some bugs."** Sweep, list and fix; W1.10 is one known case. | design L2480 | M | W1.10 | ⬜ |
| W1.23 | **Test backfill:** payments (0 today), enforcement (0 of its own), shipping (4), reviews (7). | audit | M | W1.1, W1.16 | ⬜ |
| W1.24 | **Prefill fills the wrong county at high confidence** (book §1). <br>• The county-number pattern (`prefill/core.py:304`) can't read 1913–22 "COUNTY No. 46" or 1924 "No. 24 Co.". <br>• It misreads 1951+ antlerless licenses: "ADAMS Co 34" (a county name, then the license number) resolves to county 34, Juniata, at ≥0.8 confidence. <br>• **Fix:** accept the real formats; only use the number for 1913–1937 resident tags that aren't Special Issue or nonresident, numbers 1–67, and only when no county name was read; 0 or >67 means a sample. Tests from the book's examples. | book | S | — | ⬜ |

---

## Phase 2 — Taxonomy: retire "Other", with no data lost

**The shape (D1 ✅):**
- Null means not given.
- A value not on the list is a **write-in stored with the item.** It shows again on edit and
  carries over when a collection item becomes a listing.
- Accepting it creates the value and **moves every waiting item onto it**; merge does the same.
- Reject leaves the item null and keeps the note.

**No-data-loss rules (owner's condition):**
1. **Before any migration:** take a backup and produce a dry-run report listing every row touched.
2. **Every item on an "Other" value today gets a write-in row,** recording "none of these fit"
   even when the text was never saved.
3. **The six state rows that use "Other" for real activities are renamed,** not deleted.
4. **Existing suggestions are kept,** and linked to their items where that can be traced.
5. **Expand, then contract.** The release that converts items keeps the old "Other" rows. A
   *later* release deletes them, after counts are verified.

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W2.1 | **Name the six state activity-scope "Other" rows** (NC, VA, DE, AL, AR, ND), e.g. Falconry, Guide, Hound/Fox, Access/Habitat, Prerequisite certificate, Nongame. Use `RENAMES`; the owner confirms (WO.9). | audit | S–M | — | ⬜ |
| W2.2 | **Write-in model.** `ReferenceDataSuggestion` gets nullable FKs to `Listing` and `CollectionItem` (no generic FK). | audit | M | — | ⬜ |
| W2.3 | **Forms.** A *"Not on the list?"* control replaces the "Other" option on all four item forms and in the `item-form.js` title builder. Edit shows the write-in again, and collection → listing carries it. Browser-shaped POST tests. | audit | M | W2.2 | ⬜ |
| W2.4 | **Admin accept, merge and reject** that move the waiting items. Shape and colors stay code constants, so an accepted shape or color is a small code change. | audit, dm T11 | M | W2.2 | ⬜ |
| W2.5 | **Conversion release** (no-loss rules 1–4): write-ins for every "Other" link, linked suggestions, the dry-run report. | audit | M | W2.1–W2.4 | ⬜ |
| W2.6 | **Cleanup release** (rule 5): <br>• Delete the 7 universal "Other" rows. <br>• Strip `'other'` from `SHAPE_CHOICES` and `COLOR_CHOICES`. <br>• The cleaner (`clean_reference_data.py:247–256`) stops generating them. <br>• Add them to `seed_license_types` `DELETIONS`. <br>• Drop the `is_other` API flag. <br>• Remove shape and colors from the `LicenseType.category` choices. | audit | S–M | W2.5 verified | ⬜ |
| W2.7 | **Filters and dropdowns.** No "Other" facet (fixes the duplicates in six states). `LicenseType.__str__` shows the category. | audit | S | W2.6 | ⬜ |
| W2.8 | Issue class: seed "Ordinary issue" (D11). | audit | S | D11 | ❓ |
| W2.9 | **Retire `resident_status`.** It duplicates residency, and listing detail shows "Residency: Unknown" next to the real value. Migrate any values first. | audit | S–M | — | ⬜ |
| W2.10 | **Align the place fields.** `CollectionItem.county` vs `Listing.county_ref` + `is_statewide` + a text snapshot indexed on the text field. Use one shape, the per-state Statewide unit, and an index on the FK. **Rename** the `county` fields on CollectionItem and WantedItem to unit naming (20a: "how 'county' leaks back into the interface"). | audit, xcheck | M | — | ⬜ |
| W2.11 | Retire Listing's legacy `license_type` CharField. | dev L1991 | S | — | ⬜ |
| W2.12 | **One era list.** Forms end at "2000", prefill emits "2000s", and `_year_to_era` would produce "2010s", which isn't a choice. `era_facts.json` is not keyed by state, so PA facts would show for any state's license (book §2i). | audit, book | S | — | ⬜ |
| W2.13 | **Era soft warning on the forms.** `/api/license-types/` already returns `out_of_range` for a `year=`, but no page passes it (dm #9). | xcheck | S–M | W2.3 | ⬜ |
| W2.14 | **Seeder governance tests:** create-missing-only, drift report, `--overwrite`, `RENAMES`, plus the API year-gating test. | dm T11, xcheck | S–M | — | ⬜ |
| W2.15 | **Reference-data leftovers.** Most research corrections are already applied, so this replaces the old "apply research" task. <br>• **Re-run the T5/R5 sweep on the 50-state rows.** Draw and application rows came back (AK, ID, OR, UT, WA, CA, WI, NE, CT ×3, ND), and about 25 "License" rows were never sorted. <br>• **MD:** separate the county-scoped and statewide classes, add the 1977 anchor, and fix the MD notes that contradict the research. <br>• **OH:** the Archery, Muzzleloader and Antlerless notes, and the "Antlerless Deer" facet. <br>• **Where the book settles the earlier web research** (book §6): county numbers from 1913 (not "possibly 1924"); back display printed from 1921 (arm display in 1913); first archery license 1937; 53 counties open in 1928; Co. 68 closed (nonresident tags carry no county number); Big Game Tag 1936; the material sequence; archery and muzzleloader stamps 1976. | xcheck, book | S–M | — | ⬜ |
| W2.16 | **Canonical species list.** 30 overlapping `target_species` values (Deer/Antlerless/Antlered/Sika; Waterfowl/Duck/Goose…). Needed before the species facet (W6.13) and by the seasons tool. | xcheck | S | — | ⬜ |
| W2.17 | **Regenerate `data_model_review.xlsx`** from today's `ref_data` (the sheet has 25 states and empty review columns). Owner review (WO.9), then apply. | audit | M + owner | W2.1, W2.15 | ⬜ |
| W2.18 | Finalize CLAUDE.md's Filter Cleanliness rule. | — | S | W2.4 | ⬜ |
| W2.19 | **PA year corrections from the book** (book §2a): <br>• `states.csv` PA floor **1901**, not 1913 (nonresident licenses from 1901; a 1912 one is known). Keep per-class floors in the class rows. <br>• Junior **1963** (not 1913); Senior **1972**; Senior Lifetime **1985** (confirm 1984, WO.10); Nonresident Adult **1901**; NR 7-Day Small Game **1991**; Resident Furtaker **1985**; NR Furtaker **1950** (printed "NON-RESIDENT TRAPPER"); Disabled Veteran **1949**; Military **1944**. <br>• Archery License **1937** (the preserve era; 1951 was the first general archery license); Archery Stamp **1976**; Muzzleloader Stamp **1976**; Big Game Tag **1936**; Turkey Tag ≤**1968** (low confidence). <br>• "Bear Permit" is printed "BEAR LICENSE" (1981): rename or alias, instrument = license. | book | S–M | — | ⬜ |
| W2.20 | **PA license types the book documents and we lack** (book §2b): <br>• **Antlerless before 1951:** Female Deer (cloth, 1923–24); Special Deer (metal, 1925–26 and 1928); Special Deer Hunter (1930 and 1937 metal, 1943 and 1946 cardboard). Today the 1951 floor rejects them. <br>• Bonus Antlerless (1987; the orange "BONUS" band from 1988). <br>• **New values:** Landowner (who could hold it: 1925–26, 1928, 1930); Alien Non-Resident (residency, 1931–1971; the alias exists but can never match); NR 3-Day Special Regulated Shooting Grounds (1953–90); NR 5-Day Small Game (1985–90); Bobcat permit (2000+). <br>• **Issue classes:** add Sample/Specimen, Replacement and Complimentary; PA Commemorative rows (1976 Bicentennial, 1995 Centennial); Special Issue bounded to 1920–1937 for PA. The universal row can't hold state years, so this needs state-scoped issue-class rows. <br>• **Verify** the PA "Combo Hunt+Fish" row and the COMBINATION alias; the book ties PA combination licenses to archery and muzzleloader stamp slots, not fishing. | book | M | W2.6 | ⬜ |
| W2.21 | **Places and numbers** (book §2e): <br>• **Clear Out-of-State's `unit_number` of 68**, so county-number matching can never land on it. Keep the unit with its modern-code note. <br>• **PA WMU units** for 2003+ antlerless licenses ("WILDLIFE MANAGEMENT UNIT NO. 3A"). The book's map shows 23 units; `states.csv` says 22, so check 2H. <br>• Elk management areas (park unless needed). | book | S–M | — | ⬜ |
| W2.22 | **Two value-driving fields collectors use** (book §2g): a nullable `has_paperwork` ("with papers") and a nullable `issued_status` (issued / unissued / sample) on items and listings, following the `addons_attached` pattern. Migrations follow the no-data-loss rules. | book | S–M | — | ⬜ |
| W2.23 | **License-issue reference table (D20)**, PA first, seeded from the book's facts: per class and year, the material, background and lettering colors, serial pattern, whether a county number is printed, issued count, rarity, and source page. Covers resident and Special Issue 1913–1941 colors, nonresident metal, cloth (medium confidence, since cloth fades), and the paper years later. | book | M–L | D20, WO.10 | ❓ |

---

## Phase 3 — Image prefill updates

The owner flagged prefill as needing updates. These are the ones the audits found. **Add your own
as W3.18+.**

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W3.1 | **Year upper bound.** The resolver accepts up to the current year, but the forms cap at current−25. Share one helper. | audit | S | — | ⬜ |
| W3.2 | Replace the 1850 literal with `ABSOLUTE_MIN_LICENSE_YEAR`. | audit, dm | S | — | ⬜ |
| W3.3 | Derive color aliases from `COLOR_CHOICES` (olive, burgundy; add copper and bronze). | audit | S | — | ⬜ |
| W3.4 | **Cost rates.** `config.json` carries Haiku 3.5 prices; use Haiku 4.5's and restate the cost per image (~$0.0056). | audit | S | — | ⬜ |
| W3.5 | **Prompt caching is a no-op** (the prefix is under the minimum). Drop the markers or restructure; record which. | audit | S | — | ⬜ |
| W3.6 | Unmatched values become the item's **write-in** (Phase 2). | audit | S–M | W2.2–W2.4 | ⬜ |
| W3.7 | Make `prefill/core.py` Django-free. | audit | S | — | ⬜ |
| W3.8 | **Unit tests for the matcher:** county number, PA inference, year gating, the add-on matcher with the second pass mocked, serial O→0, the standalone add-on rule, aliases. | audit | M | W3.1–W3.3 | ⬜ |
| W3.9 | **Gold set and measured accuracy.** <br>• **75–100 labelled photos** (WO.9). Build the gold schema from the app's own vocabulary, including `item_kind`, `holder_eligibility` and `addons_attached`, plus **a year range** for undated tags. <br>• **Candidate pool: the stakeholder's book** (book §4). About 125–130 single-item photos, plus about 400 that could be cropped from grids. Labels are mostly free, because year, county and serial are printed and the section gives the class. Hard cases are built in: glass, paperwork, undated tags. **Needs the author's written permission (WO.10).** It's studio-lit and weighted to 1913–1941, so mix in real member uploads; it would flatter accuracy on its own. <br>• Measure precision per field and tier. Targets: **high tier ≥98% precision**; correction rate under 15% for high and under 40% for medium. <br>• Move the tier thresholds into `config.json`. <br>• **Material is extracted for analytics only.** It's never filled, so don't tune it. | dm R6, pf, xcheck, book | M + owner | W3.8, WO.10 | ⬜ |
| W3.10 | **PA county-number gate**, the wider follow-up to the W1.24 bug fix: never resolve a county number, or fire the PA prior, outside 1913–1937, on Special Issue (a keystone sits in the county slot), or on nonresident tags. Read the county from the serial range for 1937, 1943 and 1946 Special Deer Hunter tags (book p85, p45). | dm L69, xcheck, book | S | W1.24 | ⬜ |
| W3.11 | **Rewrite `era_facts.json` from the book.** <br>• **Wrong today:** 1920s "before the numbered-county systems settled"; 1970s "late for a back tag" (display was required until 2012); 1960s "pin-back era" (PA never used buttons). <br>• **Unsupported:** 1944 "thinner", 1943 "cut corners", 1930s "nobody bought these for fun". <br>• **Book-backed replacements:** 1913 first resident year, year printed vertically; 1923 the only year with corner keystones; 1924 aluminum that cracked; 1927 first tin; 1937 last county number; 1938 letters arrive; 1942 paper for the war; 1963 suffix letters and the first junior; 1976 Bicentennial. <br>• Paraphrase, never quote, and key the facts by state (W2.12). | xcheck, book | S | WO.10 | ⬜ |
| W3.12 | **Serial agreement-gating:** read the serial twice and fill only if both reads agree. | dm L9, L460 | S–M | W3.8 | ⬜ |
| W3.13 | Auto-suggest when 3+ members hit the same miss. | pf §6 | S–M | W3.6 | ⬜ |
| W3.14 | Feature flag and a per-member opt-out. | pf | S | — | ⬜ |
| W3.15 | **The "please verify, suggestions can be wrong" disclosure** (pf L180) appears nowhere. Confirm whether 4a–4e dropped it on purpose; if not, add it. | xcheck | S | — | ⬜ |
| W3.16 | Close the designer's "switch off condition prefill" question: condition is never extracted (doc only). | design 20a | S | — | ⬜ |
| W3.17 | Lambda backend → **W8.23**. | dev 10.5 | — | W8.8 | 🚧 |
| W3.18 | **Deterministic PA validation in `prefill/core.py`**, reading tables in `prefill/config/` (or the D20 table once it exists): <br>• **Impossible material and year:** cloth after 1923; metal before 1924 or after 1941; plastic before 2009; buttons or celluloid on any PA item. Flag these and lower the tier. <br>• **Antlerless before 1951** only in 1923, 1924, 1925, 1926, 1928, 1930, 1937, 1943 and 1946. <br>• **Color → year suggestions**, marked inferred, medium tier at most. Examples: yellow Special Deer is 1925 if the serial is ≤5713, else 1926; nonresident metal in black and yellow with no year is 1924–26. <br>• **Serial patterns by era:** digits only to 1937; one letter anywhere 1938–41; a prefix letter 1942–62; a suffix from 1963; plus M / AF / D / R prefixes. The I/O/Q/T/W/X exclusion applies only in the prefix era. <br>• **Year range from a printed fee** on the paperwork. <br>• **Soft check:** a 1913–37 serial far above that county's issued count is suspicious. | book | M | W1.24, W2.19–W2.21 | ⬜ |
| W3.19 | **Prompt cues** in `system_prompt.md`, one line each, paraphrased: <br>• Where the year, county number and serial sit by era. <br>• **Undated tags: don't invent a year;** report the colors, background first. <br>• Numbers that aren't the serial: BOOK No., BACK TAG NO. <br>• "LETTER 'X' IS PART OF NUMBER". <br>• Sewn back tags are Rectangle; "Tag (with hole)" is only for grommeted tags. <br>• **A tag photographed with its own paperwork is one license with papers, not a lot.** | book | S–M | — | ⬜ |
| W3.20 | **Aliases** from the book: RES, NON-RES, ALIEN NON-RESIDENT, FURTAKER(S), LANDOWNER, ARMED FORCES, DISABLED VET(ERAN), FEMALE DEER, SPECIAL DEER (HUNTER), BONUS, SPECIAL ISSUE, SPECIMEN, SAMPLE, REPLACEMENT, COMPLIMENTARY, BICENTENNIAL ISSUE, CENTENNIAL ISSUE, 5 DAY, HUNTING AND TRAPPING, SPECIAL REGULATED SHOOTING GROUNDS. | book | S | W2.20 | ⬜ |
| W3.21 | **Add `issue_class` to the extraction**, so Special Issue (the keystone in the county slot), Sample, Commemorative and Replacement can be prefilled. Today they never can be. | book | S | W2.20 | ⬜ |

---

## Phase 4 — Money

### 4A Records first (no Connect needed)

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W4.1 | **Payment records** that can reconcile with Stripe: amount, charge ID, balance-transaction ID, Stripe fee, net and paid time, filled from the balance transaction. **Stop reusing Order rows** when a buy-now is retried. Today the first buyer's payment record is wiped (`listings/views.py:1790–1819`). | ops | M | W1.16 | ⬜ |
| W4.2 | **Label records:** Shippo transaction ID, amount and purchase date on `Shipment` and `TradeShipment`. Today trade labels record no cost at all. **Rule (decided 2026-10-07):** the label price charged to members, for orders and trades, includes Shippo's 7¢ per-label fee. | ops | S | — | ⬜ |
| W4.3 | **Webhook coverage and disputes:** <br>• Expired or failed checkout releases the lock. <br>• Refunds and payouts. <br>• A late payment on a cancelled order → automatic refund. <br>• **Disputes:** the order goes on hold, the seller gets a letter, and **an evidence packet is submitted automatically** (tracking, delivery and signature, listing photos and description, condition grade, message history). The Terms say that under D2-B **dispute losses are recovered from the seller** by reversing the transfer. <br>• **Dispute rate goes in the digest.** Alert at 0.5%; card networks act around 0.9–1%. <br>Chargebacks have a ~120-day window, and "all sales final" doesn't prevent them. | audit, ops, owner chat | M | W1.16, W4.4 | ⬜ |
| W4.4 | **Refund model and service.** Payments logic moves out of `views.py` into `apps/payments/services.py`. | ops, audit | M | — | ⬜ |

### 4B Fees and payouts

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W4.5 | **One fee, one place (D12).** The buyer review pages, the auction-win review and both ledger views agree. Add a **listing-level fee snapshot,** so a MarketplaceSettings change doesn't silently reprice running listings (W5.24 asks the question). | xcheck | S–M | D12 | ❓ |
| W4.6 | **Stripe Connect (D2):** <br>• **Recommended D2-B:** Express-style accounts (Accounts v2 / controller properties; confirm v2 is GA) and destination charges, with the application fee = Backtag's % (D12) + card processing. <br>• **Embedded onboarding** inside a settings room, framed as "where should your money go", and asked only when someone first lists or receives trade cash (the readiness gate), never at signup. <br>• **Statement descriptor reads BACKTAG.** <br>• Automatic weekly payouts; payout status in the seller ledger. <br>• `account.updated` webhook; 1099 setup in Stripe's tool. <br>• Refund policy: reverse the transfer; is the fee refunded? <br>• **If D2 goes A instead:** Standard accounts and direct charges; Stripe files the 1099s. <br>Build in test mode now; the live account waits on WO.1. | brief §1–2, owner chat | L | D2, D12, W4.1, W4.4 | ❓ |
| W4.7 | **Trade money (D3 ✅):** <br>• **Shipped trades:** each side's label cost plus $1 is charged when the trade is accepted. <br>• **In-person trades:** no $1. <br>• **Cash add-on, shipped or in person:** a charge paid into the receiving member's Stripe account (direct or destination, per D2), carrying the fee; when there's cash, the $1 fees ride on it. <br>• **A trader receiving cash must have finished payout setup** (W4.6); a trade without cash never needs it. <br>• Write `TradeFeeTransaction` for every fee. | dev §8.3, ops, xcheck, owner 2026-10-06 | M–L | W4.6, D12 | ⬜ |

### 4C Cancellations and local pickup

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W4.8 | **Cancellations and deadline sweeps** (§5 rule 1), as one job: <br>• **Paid, unshipped:** at ship-by + 5 business days with no tracking, auto-cancel, refund and strike. The buyer can also cancel once the deadline passes (dev L742). <br>• **No carrier movement:** a letter to the seller at 7 days, an order-desk exception at 14. <br>• **Trades:** a cancel path (there is none today); an unshipped side auto-cancels with a strike (dev L744–747). <br>• **Connect onboarding stalled:** reminder letters. <br>• Staff cancel and refund (W5.18). | dev, xcheck, util | M | W4.4, W1.15 | ⬜ |
| W4.9 | **Local pickup end to end:** <br>• The buyer chooses at checkout. <br>• `Order.delivery_method` is actually set. <br>• A "Handed off" step. <br>• `TradeShipment.local_pickup` is used. <br>• No tracking-based strikes for pickups; a pickup auto-completes after 7 days unless someone reports a problem. <br>Only the listing badge and a filter exist today. | dev L1283–1290, xcheck | M | W1.15 | ⬜ |

### 4D The books (simple GL)

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W4.10 | **Simple general ledger** (dm T14, revised by ops and xcheck): <br>• **App name:** `apps/books`. "Ledger" already names two other things. <br>• **Models:** `LedgerAccount`, `LedgerEntry`, `LedgerLine`. <br>• **Postings** come from Stripe balance transactions. They are idempotent **per charge or PaymentIntent**, not per event ID, because one payment fires two events; the event ID is kept for audit. <br>• **Chart:** Stripe clearing, application-fee revenue, trade-fee revenue, Stripe processing fees, Shippo label expense, shipping pass-through, refunds and chargebacks, dispute losses, payouts to the bank, and manual expenses (AWS, Anthropic, OpenAI, domain). <br>• **Balance rules:** Σdebits = Σcredits is enforced in the service plus a test, since no portable cross-row constraint exists. Per-line constraints are portable. <br>• **Staff desk:** journal, trial balance, account totals, optional audited manual entries (AWS and AI invoices can stay with the CPA instead, which is less upkeep), and CSV export for the accountant. <br>• **History:** an opening entry or backfill for orders that predate the GL. <br>The chart depends on D2 and D12. Under destination charges (D2-B) the GL books each charge, the transfer to the seller, the Stripe fee and the application fee. Under D2-A, seller money never touches Backtag's books. | dm T14, ops, xcheck | M–L | D2, D12, W4.1–W4.4 | ❓ |
| W4.11 | **Exports and tax monitoring:** <br>• Admin order-history export for reconciliation, with order indexes (dev L2116–2118). <br>• **Monthly sales by ship-to state, with alerts at 50–75% of each state's threshold** (brief §3). | dev 10.18, brief | M | W4.1 | ⬜ |

### 4E Pages and checks

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W4.12 | **Money pages onto the design system:** `buy_now_review`, `auction_win_review`, `payments/success`, `offer_form`, `offer_detail`, `_shipping_section`. Delete the orphan `my_offers.html`. **Show auto-declined offers greyed out** in the seller's Bids & offers (8b). | audit, frame 8b | M | W4.5 | ⬜ |
| W4.13 | Retire the legacy `payments.Transaction` model and its admin. | audit | S | W4.10 | ⬜ |
| W4.14 | Verify the default-address gate still holds next to the Connect gate. | todo | S | W4.6 | ⬜ |
| W4.15 | **Test-mode run of every money path** with the Stripe CLI: auction, buy-now, offer, trade with cash, refund, dispute, local pickup. | — | S–M | 4A–4D | ⬜ |

---

## Phase 5 — Trust, safety, moderation and operator tools

### 5A Enforcement

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W5.1 | **Fix the ladder (D13):** <br>• A ban doesn't lift when strikes expire. <br>• Restrictions staff set by hand survive the nightly sweep. <br>• Send the `account_restricted` notice (declared, never sent): what, until when, and how to appeal. <br>• Fix `cancellation_abuse` double-counting. <br>• Strikes added in admin go through `issue_strike`. | ops, xcheck | M | D13 | ❓ |
| W5.2 | **Blocking stops dealing:** bids, offers, buy-now, checkout, trade proposals and Q&A all check `Block` (dev L1562). | xcheck | S | — | ⬜ |
| W5.3 | **Email-verified gate on every binding or public action** (§3c). | xcheck | S | — | ⬜ |
| W5.4 | **Q&A limits:** rate limit, verified email, block check, a limit on flagging. | dev L2466 | S | — | ⬜ |
| W5.5 | **`Strike` CheckConstraint** (18a), plus a **"held" state** for strike review (17b: land / hold / excuse). | frame 18a, 17b | S–M | — | ⬜ |

### 5B Reports and appeals

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W5.6 | **`Report` model** covering listings, items, members, reviews, Q&A **and orders** (not-as-described, reproduction sold as original). Wire the Q&A and review report links, which go nowhere today. | design Pass 8, 19b | M | — | ⬜ |
| W5.7 | **Appeals:** <br>• Bound to a `Strike` and/or an `AccountRestriction`. <br>• Lifecycle: submitted → under review → approved or denied. <br>• **Standing is suspended while an appeal is open, but an undecided appeal lapses after 21 days** (the strike resumes, with a letter), so enforcement never silently switches off. One appeal per strike; the copy promises "within a week". <br>• Approval can excuse the strike or lift the restriction. <br>• The member-facing Report and Appeal screens (9c). <br>• Enforcement letters from a `SystemMessageTemplate`, split out of the parked broadcast row. | frame 9c, dev L2064–2067 | M | W5.5, W5.6 | ⬜ |
| W5.8 | A moderation action on `Review`. | design L2198 | S | — | ⬜ |

### 5C Moderation rework (owner: "I don't like how it's working and displayed")

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
If the GPT classifier flags something I want it surfaced no matter what claude says.
The GPT free classifier seems great not sure why you are suggesting getting the paid one (unless it's really cheap).
| W5.9 | **Fix what Claude sees.** <br>• Today it gets the **newest 12 messages in the thread, not the ones around the flagged message,** so it often misses the message itself and the reply. <br>• Give it messages before and after the flagged one, with timestamps, buyer and seller roles, the listing title, and earlier findings on the sender. <br>• Delimit member text against prompt injection. <br>• Label a finding's real trigger, not "Claude escalation". | ops | S–M | — | ⬜ |
| W5.10 | **Stop the false alarms.** Starter "urgent" terms page staff for ordinary talk: "I'll find you a nicer 1952 Bucks button" reads as a threat, "15 short of a full run" and "12 counties into the set" as age under 18. Match whole phrases as documented (the code does substring matching), and re-check the urgent list. | ops | S | — | ⬜ |
| W5.11 | **Rework the queue display:** <br>• Low-severity findings auto-close as "unreviewed" after 30 days. Only threats, minors and CSAM page (after W5.10). <br>• Group findings by thread and member, not one row per message. <br>• Show only the watched categories. <br>• **Show what Claude cleared** (filterable). <br>• Fix the heated-thread rows (no names, no link). <br>• Show member reports and watcher findings on the same thread together. <br>• Enforcement actions from the scan page. <br>• **Resolve and Dismiss record "was this a real concern?"** plus an action note. That builds the evaluation set as a side effect. | ops | M | W5.5, W5.6 | ⬜ |
| W5.12 | **Evaluate Claude's value (D14).** <br>• **Data:** 300–500 labelled snippets: real flags, everything Claude cleared, a random sample of clean messages, and hand-written marketplace cases. <br>• **Run three policies:** A = watch terms + OpenAI only; B = today; C = Claude with the fixed context. <br>• **Measure:** queue volume, precision, **false-clear rate by category**, accuracy when upgrading to urgent, and how useful the rationales are. <br>• **Keep** if false-clears ≤2% (and zero on threats and minors) and it removes ≥30% of no-action items. <br>• **Narrow** if the cut is 15–30%. <br>• **Drop** if false-clears exceed 5% or the cut is under 10%. | ops | M + owner labelling | W5.9, W5.11 | ❓ |
| W5.13 | **Off-platform payment and scam trigger (D14).** A cheap pattern filter (Zelle, Venmo, CashApp, PayPal F&F, gift cards, wire, phone numbers, emails, links), then Claude scores scam risk. Evaluate it on its own labelled set. **On high scam risk, automatically post a system warning to the recipient in the thread** instead of paging staff (nobody is disabled). Rewrite the prompt line that waves off off-platform deals, so scams are separated from friendly deals. | ops | M | D14, W5.9 | ❓ |
| W5.14 | Scan Q&A and reviews with the watcher (§3c: yes, after the evaluation). | ops | S | W5.12 | ⬜ |

### 5D Operator tools — what one person needs to run the site

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W5.15 | **Staff role.** A Staff group with permissions, so desk tiles and the urgent-page link don't 403 for staff who aren't superusers. Or move the tiles off Django admin. | ops | S | — | ⬜ |
| W5.16 | **Harden risky admins.** <br>• Read-only money, status, snapshot and **message-body** fields; today staff can rewrite what a member said. <br>• Admin actions that go through services: mark delivered, cancel, excuse override, hold, refund. <br>• Hide the legacy Transaction admin. <br>• Add admins for ProxyMax, TermsVersion and TermsAcceptance, OrderHandshake and Follow. <br>• Keep a change history on the three settings records. | ops, dev L857 | M | — | ⬜ |
| W5.17 | **Member page (19a)** with an audit-note table. Restrict, suspend or ban (and it sticks), strike via the service, messaging off, unblock via the service, and full history. | frame 19a, ops | M | W5.1 | ⬜ |
| W5.18 | **Order desk.** <br>• Find by ID or member, with a timeline. <br>• Hold, cancel, refund or force-complete. <br>• Resend or void a label. <br>• **Shipments stuck in "exception".** | ops, dev L2186 | M | W4.4, W4.8 | ⬜ |
| W5.19 | **Staff listing takedown:** a "removed by staff" status, a reason, and a letter to the seller. | ops | S | — | ⬜ |
| W5.20 | **One queue (19b)** over reports, watcher findings, Q&A and reviews. | frame 19b | M | W5.6, W5.8, W5.11 | ⬜ |
| W5.21 | **Strike review (17b).** | frame 17b | M | W5.5 | ⬜ |
| W5.22 | **Taxonomy screen (17b):** write-ins with accept, merge and reject, plus duplicate grouping. | frame 17b | M | W2.4 | ⬜ |
| W5.23 | **Prefill analytics (17b):** the verdict and cleared-rate column, plus prefills and cost per day and correction rate per field and per prompt version. | frame 17b, pf | S–M | W3.9 | ⬜ |
| W5.24 | **MarketplaceSettings screen** with change history. A fee change says how many running listings it touches and asks whether to apply it to them. | design L2047 | S | W4.5 | ⬜ |
| W5.25 | **Job health.** Every cron command records a heartbeat: start, finish, ok, error. Add a desk tile, and an alert when a job misses its schedule (W8.17). | ops | S–M | — | ⬜ |
| W5.26 | **Email log.** Record attempts and the last error, and stop retrying after N tries with a staff tile; today a failed send retries forever. Record verification emails too. | ops | S–M | — | ⬜ |
| W5.27 | **Health dashboard** (10.18 cards): members, active listings by market, completed orders and trades, open reports and appeals, active restrictions, GMV, shipments in exception, money in flight. | dev L2114 | M | W4.1 | ⬜ |
| W5.28 | **Support inbox** (`SupportReport`): report a bug or ask staff. It auto-acknowledges with links to the help pages and promises "within a few days". | dev 10.13, util | S–M | — | ⬜ |

### 5E Legal, account and help

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W5.29 | **The Terms lifecycle.** <br>• **Mechanics:** publish a TermsVersion (none exists, so registration shows *no* checkbox), public URLs for the current and old versions, and **re-acceptance at next sign-in.** <br>• **Privacy notice v1.0** that discloses OpenAI and Anthropic as processors. The FAQ draft says "we never share message content," but the watcher sends message text to them. <br>• **DMCA policy and contact.** <br>• **Content:** the 18+ line, the item-legality rules (brief §9), and the refund-policy line. <br>Text comes from WO.8. Also a prerequisite for toll-free SMS. | frame 4c, dev L2539–2551, brief §9 | M + owner/legal | WO.8 | ⬜ |
| W5.30 | **Close my account** (open lots and negotiations finish first; completed deals stay on the books) and **change email**. | frame 4c | M | — | ⬜ |
| W5.31 | **Privacy toggles (4c):** show my collection, wanted list, county, progress, follower count; who may write to me; serial numbers hideable per item. | frame 4c, bt §6 | M | — | ⬜ |
| W5.32 | **`NotificationPreference`:** mandatory categories locked and enforced in the service layer; commercial-mail footer and unsubscribe. | dev L2063–2068 | M | — | ⬜ |
| W5.33 | **Help pages.** Admin-managed (editable without code): How it works, Buying, Selling, Trading, Marketplace rules, Enforcement & appeals. Start from the `docs/user_docs.md/` drafts. Add a version and release-notes line. | dev L2097–2101 | M | WO.8 | ⬜ |
| W5.34 | Delete or archive a thread for yourself only. | design L2458 | S | — | ⬜ |
| W5.35 | **CSAM operations notes:** the 18 U.S.C. § 2258A reporting duty, and scanning. Owner or legal. | design L1370 | S + owner | — | ⬜ |
| W5.36 | **Usage tracking (D19).** <br>• A first-party `Event` table: route name, object, hashed session, no IP; staff and bots excluded; search text stored only when a search returns nothing. <br>• A nightly rollup to `DailyMetric`; raw events kept 90 days; staff-desk charts and digest numbers. <br>• **The metrics that matter:** activation funnel; sell-through by format; zero-result searches; sell-flow drop-off and prefill acceptance; time to ship and dispute rate; repeat buyers and sellers; **wants with no matching listing, by county** (supply vs demand); want-match letter → purchase; trade completion; weekly active members by actions; ops (real-flag share, AI cost per listing, take rate net of costs). <br>• The privacy notice lists it (W5.29), including the Do Not Track / GPC answer CalOPPA requires. | util | S–M | D19, W1.15 | ❓ |
| W5.37 | **Spam control without a person:** a registration rate limit, a hidden honeypot field, and auto-restriction of a brand-new account after 3 member reports in 24 hours (reversible; §3c). | util | S | — | ⬜ |

---

## Phase 6 — Collections, discovery, social, home, trades, lots

### 6A Ownership and collections

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W6.1 | **Ownership transfer.** A completed sale or trade puts the piece on the new owner's shelf (7c: ask only what they paid and a private note). Lot contents become N shelf items (9d). Today "ownership does not transfer" (`trades/services.py:132`). This replaces `add_from_order`. | frame 7c, dev L760, xcheck | M | — | ⬜ |
| W6.2 | **Platform ownership chain:** "Previously in the collection of …", built from real history. | dev L2089 | S–M | W6.1 | ⬜ |
| W6.3 | **`CollectionSet` (D8).** <br>• By hand and by rule; set strip; terms row; "sets going"; the gap definition. <br>• **Replaces `CollectionFolder`;** update the code markers. <br>• **Suggested set templates from the book's collecting styles** (book p73–74): a county run, every year, every county, letter sets. <br>• Three suggested sets for new collectors, with "first decade" derived from `min_license_year`. <br>• A set seeds the wanted list, plus a "gap came up for sale" alert. <br>• A "Needed for my collection" toggle in the Market. | design Pass 13, frame 11a, xcheck | L | D8, Phase 2 | ❓ |
| W6.4 | **Collection presentation:** description, cover image, 2×2 mosaic, whole-collection favoriting. | 0830 §5 | M | W6.3 | ⬜ |
| W6.5 | Display-case caption (3b). | design L2153 | S | — | ⬜ |
| W6.6 | **Wants as rules (D7).** 11b's five fields, plus `item_kind` and category (dm L265), "Want it — from a listing", priority, and the seeded home-state want. | frame 11b, 0830 §6 | L | D7, Phase 2 | ❓ |
| W6.7 | Wanted-match job, a `wanted_match` type and the 9a letter. | design L2167 | M | W6.6 | ⬜ |
| W6.8 | **`SavedHunt`:** the saved-hunts strip, the Alerts room, the alert job. | design Pass 4/6 | M | — | ⬜ |
| W6.9 | **Records & export room:** a collection CSV (with a photos folder and a "Lately" history) and a **12-month purchases, sales and trades CSV** (dev L2116, frame 4c). | xcheck | S–M | W4.1 | ⬜ |
| W6.10 | My collection bulk actions (10a); confirm the drawn scope first. | design inventory | S–M | — | ⬜ |
| W6.11 | **Finish the Listing defaults room:** ships-from, how long lots run, closing time, allow offers, open to trade, local pickup. | frame 4c | S | W4.9 | ⬜ |

### 6B Discovery

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W6.12 | **Market filter rail** (vertical, per 1c and 13b): auto-apply (remove the Apply button), multi-select with counts, state-aware year bounds, **a price filter**. | todo, xcheck | M | W1.22 | ⬜ |
| W6.13 | **Missing facets:** species (needs W2.16), instrument, tags intact, restored (with a card badge and `repairs_ok`), Following, and the Store chips "Cash either way / Items only". | dm #10, design 9b, todo | M | W2.16, W6.6 | ⬜ |
| W6.14 | **The breadcrumb carries your filters,** ending "← Back to those 86 results" (2a). | frame 2a | S | — | ⬜ |
| W6.15 | Map chips (open to trade, resident hunter, year range) filtered at `/api/map/`. | design L2171 | S–M | — | ⬜ |
| W6.16 | **Related listings and "more from this seller"** are mostly built (`listings/views.py:845–878`). Left: re-rank "Similar items" with W6.32, and exclude blocked sellers. | dev 10.11, util | S | W6.32, W5.2 | 🔄 |
| W6.17 | Trust signals (10.12): seller card, review unlock, active-listings tab. Check against 1c and 3b first. | dev 10.12 | S–M | — | ⬜ |
| W6.18 | Collectors header "N within a hundred miles", and the "counties held" label for GMU-state collectors. | design register | S | — | ⬜ |
| W6.19 | Bid-history sparkline; the outbid notice while browsing other pages; a views column on the seller desk. | frame 2e, Blueprint ch08 | S | — | ⬜ |

### 6C Social and alerts

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W6.20 | **A trades list on the Dashboard** (ideas #13; 2e "Build"). Today a struck trade only shows when it's your turn. | xcheck | S–M | — | ⬜ |
| W6.21 | **A Following page,** and followed collectors' new listings in the Day Book. | frame 8c, ideas #10 | S–M | — | ⬜ |
| W6.22 | **Watch alerts:** a saved lot is closing soon, or has ended (2e #12 "First"; "the single biggest re-engagement lever"). | ideas #12 | S–M | — | ⬜ |

### 6D Home and arrival

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
UI for sign up should look like you are filling out a license, wouldn't that be cool?
| W6.23 | **Onboarding (3d):** counties you care about (dev's `target_county`, L1666), what you're hunting for, who to follow. Record which version is built, 3d or 2e's. | frame 3d, dev, xcheck | M | — | ⬜ |
| W6.24 | **New-member home (16a).** | design Pass 10 | M | W6.23 | ⬜ |
| W6.25 | **Greetings (bt §4)** without the Season bucket. Time-gated lines need the member's local time (a timezone field, or the browser's). Cut the nickname line (§3c). Want priority feeds the home bands. | bt §4, xcheck | M | W6.23 | ⬜ |
| W6.26 | Signed-out hero photograph (WO.8). | bt §3 | S + owner | — | ⬜ |

### 6E Trades leftovers

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W6.27 | Retire the `listing_type='trade'` enum (after W1.10). | design 7b | S–M | W1.10 | ⬜ |
| W6.28 | Shared carrier and service on `TradeOffer`, flowing into both shipments. Money is in W4.7. | todo, design L2149 | M | W4.7 | ⬜ |
| W6.29 | Composer search without JavaScript. | design L2150 | S | — | ⬜ |

### 6F Lots and accessibility

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W6.30 | **Lot listing (9d):** `inventory_format`, `ListingLotItem` with front and back images, box-lot guidance, the third route on sell-start. Cards show year and grade ranges with the count in the badge. **A lot can't be traded.** On receipt, its contents go to the shelf (W6.1). | frame 9d, dev 10.15 | L | W6.1 | ⬜ |
| W6.31 | **Text-size control** for older members. | todo, design L2453 | S–M | — | ⬜ |
| W6.32 | **Personalization scorer: rules, no machine learning.** <br>• `apps/collections/recommend.py`. First consolidate the three want matchers (`matching.want_clause`, `_wanted_matches`, `_match_wanted`). <br>• Each rule adds points and carries a plain-English reason: matches a want (weighted by priority), fills a county gap, extends a run, near home, matches an onboarding era or kind, a followed seller, like your favourites, fresh or closing soon. Points come off if you already hold one. <br>• Never your own listings or blocked sellers; at most 2 per seller and 2 per county in any band; a daily seed rotates ties. <br>• **It feeds the drawn surfaces, not a new "For you" band:** 2b's "fills a gap" tags and Your counties band, the Day Book, re-ranked Similar items, the Needed-for-my-collection toggle, the weekly letter. <br>• **Cold start:** home county → home state → within 100 miles (16a), plus the seeded home-state want. <br>• Scored per request over a few hundred candidates and cached 15 minutes. No new tables, no nightly job. | util, frame 2b/16a, 0830 §6 | M | W6.6, W6.23, W5.2 | ⬜ | I never said no ML? I love ML. But only ML if we need ML. If something is simpler and just as effective then no need for ML.

---

## Phase 7 — Finish the redesign

### 7A Remaining old screens

None of these were drawn. Build each from its nearest frame, then render it and look.

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W7.1 | `password_reset_*` (4 pages). | audit | S | — | ⬜ |
| W7.2 | `address_confirm_delete` (the two-step pattern). | audit | S | — | ⬜ |
| W7.3 | `state_detail`, `geographic_unit_detail` (nearest frames: 14a/14b and the map plates). | audit | M | — | ⬜ |
| W7.4 | `_reference_data_suggestion_form` (the W2.3 control replaces it on item forms). | audit | S | W2.3 | ⬜ |
| W7.5 | `verify_email` into the 9a letter shell. | audit | S | — | ⬜ |
| W7.6 | **Research, Field Guide and Archives:** move the inline styles into a page stylesheet. **Archives:** replace the disabled search box with a plain line (§3c); the search itself is parked. | audit, xcheck | S | — | ⬜ |

### 7B Retire legacy

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W7.7 | `/accounts/dashboard/`: repoint the redirects to the Bench, then 301 and delete. | audit | S | — | ⬜ |
| W7.8 | `/listings/`, `_listing_card.html` and `browse.css` → 301 to `/market/`. | audit | S | — | ⬜ |
| W7.9 | Delete the orphans (`_collection_item_row.html`, `trade.css`). Redirect `add_from_order` **only once W6.1 replaces it.** | audit, xcheck | S | W6.1 | ⬜ |
| W7.10 | Remove the legacy `--color-*` rules and aliases. | audit | M | W7.1–W7.9, W4.12 | ⬜ |

### 7C Partial frames and brand

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W7.11 | Phone bid sheet (15a). | design Pass 10 | S–M | — | ⬜ |
| W7.12 | Staff desk to the full 17a. | frame 17a | S | Phase 5 | ⬜ |
| W7.13 | The eight-file logo export set. Confirm the tagline reached the footer. | design 10f, bt §2 | S | — | ⬜ |

### 7D Model-blocked passes now in scope (D4)

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W7.14 | **Price-history foundation (D4b).** <br>• A comparison key over the taxonomy (state + license types + year/era); the prototype's grouping doesn't fit the M2M model. <br>• Observations from completed orders. <br>• A staff tool to enter researched comparables with source and date. <br>• **Labelled by source, never blended.** Rarity scores carry their caveat wherever shown. <br>• No scraping and no eBay API; staff may hand-enter eBay asking prices, labelled. Reuse the source-labelled schema idea in `utilities/sales_api/price_data_schema.py`. | design Pass 12, sales_api research | M | W4.1 | ⬜ |
| W7.15 | **Field Guide (Pass 14):** index, entry, write an entry, corrections (12a, 12b, 21a). Per-state and per-license-type pages. The map county card's "entry written" row. The home band and the 16b unwritten-county screen.  **Moderation:** member entries publish immediately for members in good standing; corrections arrive as suggestions with no deadline (§5 rule 3). <br>• **Content from the stakeholder's book, with his blessing (WO.10):** era-identification plates and color tables; Special Issue explained; the antlerless timeline; nonresident running stock; the prefix and suffix letter guide; the county-number table; collecting styles; the rarity scale and condition terms; the hold-it-to-the-light fraud check; issued-count charts. **No prices** (the ledger rule). Cite the primary sources (the 1902–1938 Game Commission reports; pre-1929 ones are likely public domain). | design Pass 14, bt §1, util, book | L | — | ⬜ |
| W7.16 | **Badges (Pass 14):** 21b plus the bt §5 renames, per D9. | design Pass 14, bt §5 | L | D9, W6.3 | ❓ |

### 7E Look at everything

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W7.17 | **Render-and-look sweep** of every member-facing template at desktop width and at **375px** (dev's minimum width), against its frame. Check **WCAG AA contrast.** | memory rule, dev L1411, L1436 | M | 7A–7D | ⬜ |

---

## Phase 8 — Pipeline, infrastructure and operations (dev 10.19)

### How shipping an update will work

**Goal:** one person can ship to a live site safely without watching it.

1. **Work on a feature branch,** committing at task boundaries as now.
2. **Open a pull request to `main`.** CI runs the tests on SQLite *and* Postgres, plus
   `check --deploy` and `makemigrations --check`. Red blocks the merge.
3. **Squash-merge.** **Staging deploys itself** within minutes.
4. **Look at staging.** When it's right, push a tag (e.g. `v2026.11.02`). **Production waits for
   one click of approval** in GitHub, then deploys.
5. **The deploy script on the server:**
   1. Back up the database.
   2. Build a new release folder, install, `collectstatic`.
   3. Run migrations (the plan is logged).
   4. Switch the `current` link and reload gunicorn gracefully, so in-flight requests finish.
   5. Run a **health check**. If it fails, **switch back automatically** and alert you.
   6. Keep the last 5 releases, so `deploy rollback` is one command.
6. **You hear about problems; you don't watch for them.** Sentry reports errors and missed cron
   runs. An uptime check watches `/healthz/`. CloudWatch alarms cover disk, memory and t3 CPU
   credits. A weekly digest email arrives (W8.19).

**Rules that keep live deploys safe:**
- **Migrations must work with the code that's already running (expand, then contract).**
  - Add columns as nullable or defaulted.
  - Backfill in a separate step.
  - Remove old fields one release *after* the code stops reading them.
  - Never rename a column in one step.
- **Data migrations** (like Phase 2's) run with a dry-run report and the pre-deploy backup.
- **A maintenance switch** serves a "back shortly" page, for the rare risky change.
- **Feature flags** in MarketplaceSettings let you ship something dark and turn it on from the
  staff desk.
- **Cron jobs pause during migrations** (they share the deploy lock).

### Tasks

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| **8A** | **Settings and platform** | | | | |
| W8.1 | **`production.py`:** <br>• Fix the logs-dir crash. <br>• Add `SECURE_PROXY_SSL_HEADER` and `CSRF_TRUSTED_ORIGINS`. <br>• A missing `SECRET_KEY` fails loudly. <br>• `CACHES` (database or file; rate limits are per-process today). <br>• **Move to `STORAGES`.** | audit, brief §8 | S–M | — | ⬜ |
| W8.2 | **Django 5.2 LTS (D5 ✅)**, done together with W8.1. Verify `collectstatic` and media storage actually work afterwards, because on 5.2 the old settings are silently ignored. | brief §8 | M | W8.1 | ⬜ |
| W8.3 | **Postgres locally** (14+ for 5.2), and the full suite run on it. | audit | S–M | — | ⬜ |
| **8B** | **Environments** | | | | |
| W8.4 | **Domain and DNS** (Route 53). | dev L2504 | S | WO.7 | ⬜ |
| W8.5 | **Staging instance (D17):** password-protected, test keys, its own database and bucket prefix. | dev 7.9 | M | D17, W8.1 | ❓ |
| W8.6 | **Production instance:** gunicorn, nginx, systemd, **unattended security upgrades**, a swap file on the 1 GB box, and certbot on its timer plus an expiry check. | dev §14 Phase 6, util | M | W8.5 | ⬜ |
| W8.7 | **Production database (D16).** | — | S–M | D16 | ❓ |
| W8.8 | **S3 for media** (django-storages + boto3), with upload validation. CloudFront is optional. Uploading straight from the browser to S3 with presigned URLs is optional later; not needed at this size, and prefill reads the image server-side. | dev 10.19, L86, owner chat | M | W8.1 | ⬜ |
| W8.9 | **SES:** domain, DKIM, SPF, DMARC. Bounces and complaints go to SES's account-level suppression list, with counts in the digest, not the desk. Plus the monitored reply-to (WO.7). | dev 10.19, util | S–M | W8.4, WO.7 | ⬜ |
| **8C** | **The pipeline** | | | | |
| W8.10 | **CI** (GitHub Actions): tests on SQLite and Postgres, `check --deploy`, `makemigrations --check`, branch protection on `main`. Replaces the Flask-era `deploy.yml`. | audit | S | W8.3 | ⬜ |
| W8.11 | **The deploy script:** release folders, backup, migrate, link switch, graceful reload, health check with auto-rollback, keep 5, `deploy rollback`. | dev L2491 | M | W8.6 | ⬜ |
| W8.12 | **CD:** `main` → staging automatically; a tag → production behind one-click approval. Connect through AWS SSM, so there's no open SSH port and no keys in GitHub. | — | S–M | W8.10, W8.11, D18 | ⬜ |
| W8.13 | `/healthz/`: database, cache, migrations applied, version. | — | S | — | ⬜ |
| W8.14 | **Maintenance switch** (a flag file nginx checks, and a field-journal "back shortly" page). | — | S | W8.6 | ⬜ |
| W8.15 | **Feature flags and automatic breakers** in MarketplaceSettings, editable from the staff desk. Prefill switches itself off when its daily spend or error rate crosses a cap; the form works without it. | util | S | W5.24 | ⬜ |
| **8D** | **Jobs** | | | | |
| W8.16 | **Crontab for all 15 job commands,** with explicit schedules, `flock`, runs from the current release, paused during migrations. Add `clearsessions` (database sessions pile up). Fix the README's command list. **Auctions also close themselves on view** (`bids.services.lazily_close`), so a missed run doesn't strand an auction; no EventBridge or Lambda is needed for it. | audit | S | W8.11 | ⬜ |
| **8E** | **Hearing about problems** | | | | |
| W8.17 | **Sentry:** errors, plus cron monitors (each job checks in, and a missed run alerts). | dev 10.19, ops | S | W5.25 | ⬜ |
| W8.18 | **Uptime check and CloudWatch alarms:** disk, memory, t3 CPU credit balance. | — | S | W8.6 | ⬜ |
| W8.19 | **Weekly owner digest email:** orders, payouts, failed jobs, pending flags, error count, sales-tax threshold status. | — | S | W5.27, W4.11 | ⬜ |
| **8F** | **Backups and recovery** | | | | |
| W8.20 | **Backups:** nightly database backups to a versioned bucket kept 30 days, plus the pre-deploy dumps (or RDS automated backups, per D16). Media bucket versioning. Log rotation. **A monthly automatic restore into staging**, with sanity checks and personal data scrubbed; the result goes in the digest. | dev L2548, xcheck | S–M | W8.7 | ⬜ |
| **8G** | **Runbooks** | | | | |
| W8.21 | **`docs/tech_docs/`:** ship an update, roll back, restore the database, rotate a secret, an alert fired, add a cron job, add an env var, migration rules, and **one entry per alert in the §5 alert budget.** | — | S–M | W8.11 | ⬜ |
| **8H** | **Integrations** | | | | |
| W8.22 | **Live wiring checklist:** <br>• Stripe live keys, webhook and Connect settings. <br>• Shippo live keys and webhook token. <br>• Google key restricted to the domain. <br>• Anthropic and OpenAI project keys. <br>• **Re-register every webhook per account and mode.** <br>• **Secrets in SSM Parameter Store** (free), written to the server at deploy, not a hand-copied `.env`. | ops, audit | S | WO.4, W4.6, W1.1 | ⬜ |
| W8.23 | **Prefill Lambda backend** with an HMAC callback: concurrency cap 10, no raw text in logs, Bedrock model ID and pricing. Until then the local backend holds a worker for each read. | dev 10.5, pf | M | W8.8, W3.7 | 🚧 |
| W8.24 | **Phone verification (D4 ✅)** through AWS End User Messaging Notify (§3c). Then gate trading on it as dev planned, and remove the honest-copy stopgap from W1.8. | dev 10.12, brief §7 | M | W5.29 if toll-free | ⬜ |
| W8.25 | **Security review** (`/security-review`), admin hardening, upload validation, rate-limit check. | dev 10.19 | M | most of 1–7 | ⬜ |
| W8.26 | **Retention jobs:** notifications after 12 months ("kept twelve months", but nothing deletes them), unattached prefill images after 30 days, raw usage events after 90 days (W5.36). | frame 8e, util | S | — | ⬜ |
| W8.27 | **Dependency updates:** Dependabot, grouped weekly. Patch releases auto-merge when CI is green (which deploys staging); production still waits for a tag. A calendar reminder for Django 5.2's end of support (April 2028). | util | S | W8.10, W8.12 | ⬜ |
| W8.28 | **Nightly self-check** (`manage.py selfcheck`): <br>• last Stripe and Shippo webhook within N days; <br>• Anthropic and OpenAI keys answer (no 401 or 429); <br>• SES sending; <br>• latest backup under 26 hours old; <br>• disk and memory; <br>• TLS certificate over 14 days, domain over 30; <br>• `check --deploy` clean and no pending migrations; <br>• cron heartbeats; <br>• oldest urgent flag and oldest appeal; <br>• spend against budget. <br>Failures route per the §5 alert budget. | util | S–M | W5.25, W8.17 | ⬜ |

---

## Phase 9 — Beta gate and handoff (dev 9.9, 10.18)

| ID | Task | From | Size | Depends | Status |
|---|---|---|---|---|---|
| W9.1 | **End-to-end on staging, every path:** <br>• **Accounts:** register → verify (email and phone) → address → Connect. <br>• **Auction:** list (including scheduled go-live and auto-relist) → bid → win → pay → label → track → deliver → complete → review → the piece lands on the buyer's shelf. <br>• **Other sales:** buy-now; offer → counter → accept; trade with cash; local pickup. <br>• **When things go wrong:** refund, dispute, cancel after a missed deadline, excuse and strike, report and appeal, block. <br>• **Everything else:** state-aware forms, notification preferences, Terms re-acceptance, exports and the GL, staff tools, prefill on real photos. | dev 9.9, L1641–1647, L2117 | M | Phases 1–8 | ⬜ |
| W9.2 | Regression checklist and a bug bash; triage the known-issues sheet. | dev 9.1 | M | W9.1 | ⬜ |
| W9.3 | `export_reference_data` (DB → CSV), so admin edits are versioned. | dm, dev 10.18 | S–M | Phase 2 | ⬜ |
| W9.4 | Fresh demo data on staging for the owner's redesign round. | — | S | W9.1 | ⬜ |
| W9.5 | Final reconcile of all plan docs; tag and hand off (§14). | — | S | all | ⬜ |

---

## 10. Exit criteria — "workable product"

1. **Every money path completes on staging** with test-mode Stripe Connect, Shippo, SES and S3:
   auction, buy-now, offer, trade with cash, local pickup, refund, dispute. **The seller is paid,
   and the books balance against Stripe.**
2. **No audit safety hole remains open,** and the security review has passed.
3. **The taxonomy is clean with no data lost,** and prefill accuracy is measured.
4. **Every in-scope drawn screen is built,** with no old styling and no legacy routes.
5. **The operator can run the site from the staff desk:** members, orders, refunds, takedowns,
   reports, moderation, jobs, email failures and finances, without raw admin edits.
6. **The legal minimum is live:** Terms with re-acceptance, a privacy notice, DMCA, help pages.
7. **Shipping an update is a merge and a click.** Staging auto-deploys, production deploys by tag
   with auto-rollback, backups have been restore-tested, and alerts reach the owner.
8. **The owner track is done through WO.5** (entity, accounts, billing) before anything goes live.
9. **The plan docs match the code.**

---

## 11. Stretch (★) — "ballpark", after the exit criteria

| ID | Item | Notes |
|---|---|---|
| ★S1 | **Price-history screens** (~12 screens across 7 turns: comps on terms, closing price on sold favorites, "What the books say", listing detail) | Built on W7.14. Each shows nothing until enough comparable sales exist. |
| ★S2 | **Three questions** (Pass 15) | It's the daily trivia the owner once parked (design L2463). Needs D6 and a clean taxonomy. |
| ★S3 | **15b camera** with the "you already own one" check | Needs ★S1. The "works signed out?" call (20a) is decided here. |
| ★S4 | **Season openers file** for PA, MD and OH: state, canonical species (W2.16), method, open and close dates, agency URL, "as of". Loaded by a yearly August command; it turns on the Season greeting bucket and a seasonal browse band. Each row carries its season year, so a missed refresh goes quiet instead of wrong. | `utilities/seasons_api/` stays a drafting aid, never a feed. eregulations.com's Terms of Use are still unreviewed. |

---

## 12. Parked — registered, not dropped

| Item | From | Why parked | Unparks when |
|---|---|---|---|
| Second-chance offers | dev 10.9, design 9e | Out of scope twice | Owner asks |
| Image attachments in messages and rooms | dev 9.8, design 9f | Needs upload scanning and the moderation pipeline proven | Moderation has run on staging |
| Public channels / forum | design 9f | Deliberately unbuilt | Owner decision |
| Admin DMs and broadcast | dev 10.13 | Not needed for workable (enforcement templates moved to W5.7) | After launch |
| Notification extras: daily digest with a send time, quiet hours, an SMS channel, a weekly Almanac letter | frame 4c | Beyond the preference basics (W5.32) | After launch |
| Backtag §6 visibility ladder | bt §6 | **Conflicts** with 7b "public ≠ tradeable" (design L729). The privacy guarantees moved to W5.31. | Owner decision |
| Backtag §7 season dates beyond ★S4 (auction-timing hint, season-aware empty states, season-timed emails) | bt §7, seasons_api | The scraper covered 21 of 49 states. **PA and OH failed,** multi-segment seasons are truncated, and some wrong dates still count as parsed. It can't run in production without regular upkeep. | ★S4 exists and the owner wants more |
| Backtag parking lot: trivia, polls, season calendar, Season Board, rotating facts, state records in greetings | bt | Unscheduled by design | — |
| Archives search | bt §1 | §3c default: park it | Owner decision |
| Google and Apple sign-in | dev §11, **frame 4b** | Designer: Beta | Beta |
| License grading model | license_grading plan | Concept only. **Its "scrape license images off the web" conflicts with eBay's and WorthPoint's terms.** | After launch |
| Trade-matching suggestions beyond wanted hints; estimated value ranges | dev L2167, L2199 | Beta+ | — |
| Revenue ideas, after there's liquidity: a paid research tier on price history (the Archives); dealer subscriptions (lower fee, storefront, bulk tools); affiliate archival supplies (sleeves, frames); a disclosed shipping-handling markup; collectibles-insurance referral; at most one clearly marked promoted slot, never mixed into results | owner chat (Sept 2026) | Liquidity first. **Estate consignment conflicts with "never the auctioneer"** and would need an owner and legal decision. Skip listing fees and a buyer's premium. | Steady transaction volume |
| *(moved)* Recommendations ranked by want priority | 0830 §6, ideas #15 | Now scheduled as **W6.32** | — |
| eBay Browse API feed | sales_api | Production access is eBay-partner-only, and a competing marketplace is unlikely to be approved; the client was never run. Hand entry covers it (W7.14). | eBay approves a partner application |
| Newsletter, Journal, Education Hub, stories, County Spotlights, Era Guides, Notable Figures, license timeline | dev §13, L2210–2237 | After launch (W7.15 may absorb County Spotlights) | — |
| Postgres full-text search; Celery/Redis; scaling path (ALB, second EC2, CloudFront) | dev §13, §16, CLAUDE.md | Scale | Scale |
| `GeographicUnit` valid-from/to years | design L1836 | Needs boundary data | Data found |
| Research backlog: Montana's 306 districts; add-on rows with no first year; a dated MD statewide license | design 10d, dm L390 | Research | Research done |
| `LicenseProduct` table | context | Derivable later | Needed |
| Provenance PDF upload | todo, dev 10.15 | D4: parked | Owner |
| Spreadsheet import | design Pass 4, 16a | D4: parked | Owner |
| Prefill reads the back image | dm L363, pf | §3c: not now | Accuracy needs it |
| Hover previews, mega-menu, 10-segment reputation bar | ideas file | The designer declined them (2e). *The activity feed is built, as the Day Book.* | Owner's redesign round |
| Archives sandbox ideas (census, named hunter, serial neighbours, fakes file) | Blueprint ch. 15 | Kept, not scheduled | — |
| "Brand store" | todo | Meaning unclear | Owner defines it |
| Trade board 3a revisit; county-first revisit per state | design | Later | — |

**Recorded overrides** (not open): bt §3 chose a hero photograph over 2e's "tonight's lead lot".
The owner overrode 6a so that selling from the shelf lands on step 2.

---

## 13. Launch track — after the owner's redesign round

Registered here so it isn't lost. It is not part of "workable".

- **Invite-only soft launch.** Registration is open today; add an invite mechanism.
- **Beta testers invited.**
- **Production checks:** live webhooks and SES verified in production, not just staging.
- **Beta recovery** (dev §12.1): tune shipping deadlines, strike rules and trade-gating
  thresholds from real use.
- **Public launch,** plus the dev §17.3 launch checklist.
- **Scaling path** when needed (dev §16).

---

## 14. Left for the owner's redesign round

- A full UI/UX clean-up, navigation and grouping, a more engaging home page.
- Customizable profile and collection views beyond the showcase layouts.
- Anything parked "for the owner's redesign round".
- Any screen the owner wants to change after using the workable product.

---

## Change log

- **2026-10-06 (rev 3)** — Added: the stakeholder's book review (W1.24, W2.19–W2.23, W3.18–W3.21, WO.10, D20, book content for the Field Guide); the utilities, personalization and usage review (§5 running-itself rules and alert budget, W5.36–W5.37, W6.32, W8.28, D19, ★S4); the trade-fee rule (D3 ✅); and the D2 rework (option B, after correcting the "$0.20 a sale" payout advice and reviewing the owner's September cost conversation).
- **2026-10-06 (rev 2)** — Second full pass. Every source doc was cross-checked line by line, plus
  an operator audit (admin smoke test, staff desk, moderation, money records, external services)
  and a payments/tax/legal research brief.
  - Recorded D1, D4 and D5.
  - Added D12–D18, the small calls, and the owner track.
  - Rebuilt Phase 4 (records, fees, Connect, trade money, cancellations, local pickup, the GL)
    and Phase 5 (enforcement, moderation rework, operator tools, legal).
  - Wrote the pipeline design into Phase 8.
  - Added about 70 missing items, live crashes included.
  - Moved price-history screens and Three questions to Stretch.
  - Moved the plan to `docs/internal/plans/`.
- **2026-10-06** — CLAUDE.md rewritten (W0.3, W0.4 partly done).
- **2026-10-06** — Plan created.
