# Backtag — running cost estimate

**As of 2026-10-06.** These are rough figures, not quotes. AWS prices are on-demand, us-east-1.
Before committing, check the AWS figures in the [AWS Pricing Calculator](https://calculator.aws/).

**Assumes early-stage traffic and the roadmap's recommendations:**
- About 100 sales a month at a $40 average, and about 30 active sellers.
- About 2,000 emails, 300 photo reads (prefill) and 50 phone verifications a month.
- A managed database (D16), its own staging server (D17), and phone verification through AWS
  Notify.

## What the app costs to run

| Item | What it's for | Monthly | Yearly |
|---|---|---:|---:|
| Domain (.com, Route 53) | The web address | $1.25 | $15.00 |
| Route 53 hosted zone | DNS for the domain | $0.50 | $6.00 |
| EC2 t3.micro (production) | The web server ($0.0104/hr) | $7.59 | $91.08 |
| EBS disk, 20 GB gp3 | The server's disk ($0.08/GB) | $1.60 | $19.20 |
| Public IPv4 address | AWS charges for every public IP ($0.005/hr) | $3.65 | $43.80 |
| RDS Postgres db.t4g.micro | Managed database ($0.016/hr), with automated backups | $11.68 | $140.16 |
| RDS storage, 20 GB gp3 | Database disk ($0.115/GB) | $2.30 | $27.60 |
| Staging server | t3.micro stopped when idle (~60 hrs/mo) plus its disk; Postgres runs on the box | ~$3.00 | ~$36.00 |
| S3 | Photos and database backups (~15 GB) | ~$1.00 | ~$12.00 |
| SES email | $0.10 per 1,000 emails | $0.20 | $2.40 |
| Phone verification (SMS) | ~$0.054 per text, via AWS Notify | ~$2.70 | ~$32.40 |
| Claude Haiku: photo prefill | ~$0.0056 per photo read | ~$1.70 | ~$20.40 |
| Claude Haiku: moderation | ~$0.0014 per flagged message | ~$0.15 | ~$1.80 |
| OpenAI moderation | Message screening | $0 | $0 |
| Shippo API | 30 labels a month free, then 7¢ a label (postage is paid by members) | ~$4.90 | ~$58.80 |
| Google Places autocomplete | Address lookup; stays inside Google's free monthly allowance | $0 | $0 |
| Sentry (Developer plan) | Error alerts; 1 user, 5,000 errors a month | $0 | $0 |
| GitHub | Code and CI on the free plan | $0 | $0 |
| CloudWatch | A few alarms, inside the free allowance | $0 | $0 |
| **Total to run the site** | | **≈ $42** | **≈ $506** |

## Bringing it down (still AWS, still a proper setup)

| Change | Saves / mo | Saves / yr | Trade-off | When |
|---|---:|---:|---|---|
| Add Shippo's 7¢ label fee to the label price members already pay | $4.90 | $58.80 | Members pay 7¢ more per label | At launch |
| Graviton server: t4g.micro ($0.0084/hr) instead of t3.micro | $1.46 | $17.52 | None (ARM; the app's packages all support it) | At launch |
| New-account AWS credits (up to $200 over the first 6 months) | — | up to $200, year one only | Free-plan limits apply; check the terms | At signup |
| 1-year reserved database, no upfront ($11.68 → $8.47) | $3.21 | $38.52 | A one-year commitment | After ~3 months of steady use |
| 1-year savings plan on the web server | ≈ $1.70 | ≈ $20.60 | A one-year commitment | After ~3 months of steady use |

**Recommended result: about $31 a month, about $371 a year.** Year one is lower still once the
credits are applied. About $30 a month is roughly the floor for a managed database, a separate
staging server, backups and monitoring.

**Bigger cuts, not recommended:**
- **Lightsail instead of EC2** for the web server. A $7/mo bundle includes the public IPv4 and a
  40 GB disk. It saves about $3–4 a month, but the hands-off deploy setup (SSM) needs extra
  work, and savings plans don't apply.
- **Postgres on the web server instead of RDS.** For example, a 2 GB Lightsail box at about
  $12/mo, plus daily snapshots at about $2/mo. It saves about $8 a month more, but you lose
  point-in-time restore, and the database becomes yours to maintain. That runs against the
  low-maintenance rule.

## Optional add-ons

| Item | When you'd want it | Monthly | Yearly |
|---|---|---:|---:|
| Plausible analytics | If traffic sources matter (D19) | $9.00 | $108.00 |
| Sentry Team | More than one person on alerts, or more than 5,000 errors a month | $26.00 | $312.00 |
| Email on the domain (e.g. Google Workspace) | A real `support@` inbox; forwarding to Gmail is the free option | ~$7–8.40 per user | ~$84–101 per user |
| Postgres on the web server instead of RDS | Saves money, but backups and restores become your job, and the 1 GB box would likely need to grow to a t3.small | ≈ −$7 | ≈ −$84 |

## Payment costs (these scale with sales)

These come out of each sale, not a monthly bill. The example uses 100 sales a month at $40 from
about 30 active sellers, and an 8% platform fee. The fee rate isn't decided yet (D12).

Stripe Connect can be set up three ways (D2), and the choice decides whether the fee is profit.

- **A: Stripe sets pricing.** Standard accounts, direct charges.
- **B: Backtag sets pricing and the seller pays card processing (recommended).** Express-style
  accounts, destination charges; the application fee is Backtag's % plus Stripe's processing.
- **C: Backtag sets pricing and absorbs processing.** Ruled out.

| Backtag's side, per month | A | **B (recommended)** | C |
|---|---:|---:|---:|
| Platform fee in (8% of $4,000) | +$320.00 | **+$320.00** | +$320.00 |
| Card processing (2.9% + 30¢), $146 | $0 (Stripe takes it from sellers) | **$0 (passed to sellers in the fee)** | −$146.00 |
| Connect: $2 per seller in any month they get a payout | $0 | −$60.00 | −$60.00 |
| Connect: 0.25% + 25¢ per payout | $0 | −$16.30 | −$16.70 |
| 1099 filing | $0 (Stripe files) | ~−$3.75 | ~−$3.75 |
| **Left after payment costs** | +$320 / mo (≈ $3,840 / yr) | **≈ +$240 / mo (≈ $2,879 / yr)** | ≈ +$94 / mo (≈ $1,123 / yr) |
| **Left after running the site (−$42)** | ≈ +$278 / mo (≈ $3,334 / yr) | **≈ +$198 / mo (≈ $2,375 / yr)** | ≈ +$52 / mo (≈ $617 / yr) |

**One $40 sale from a seller who sells once that month:**

| | A | **B** | C |
|---|---:|---:|---:|
| Backtag keeps, at 8% | $3.20 | **$0.86** | −$0.60 (a loss) |
| Backtag keeps, at 10% | $4.00 | **$1.66** | $0.20 |
| Seller keeps, at 8% | $35.34 | **$35.34** | $36.80 |
| Buyer's card statement shows | the seller's name | **Backtag** | Backtag |
| Stripe visible to the seller | a full Stripe account, dashboard and emails | **onboarding embedded in Backtag's pages, light branding** | same as B |
| Stripe Tax can collect as the marketplace | no | **yes** | yes |

**What this shows:**
- **C loses money** on small, occasional sales. Stripe's fixed $2 per active seller each month
  eats the fee, and batching payouts doesn't avoid it.
- **A keeps the most** (~$80/mo more than B at this volume) and has the least upkeep: Stripe files
  the 1099s, and refunds and disputes land on the seller. But buyers see the seller's name on
  their statement, which invites "I don't recognize this charge" disputes. Sellers also deal with
  Stripe directly.
- **B keeps Stripe nearly invisible** and puts Backtag on buyers' statements. Its one-sale margin
  is thin but positive. A minimum fee (D12) protects cheap items.

If sales tax collection becomes necessary, Stripe Tax adds about 0.5% of sales (~$240 a year at
this volume). Threshold monitoring is free.

## One-time and business costs (not in the totals)

Get quotes. These vary a lot by state and provider.

| Item | Notes |
|---|---|
| LLC formation and the state's yearly report | State filing fees vary. Owner track WO.1. |
| CPA consult | Sales tax, 1099s, how the fee is taxed (WO.2) |
| Attorney review | Terms, privacy, item legality (WO.2) |
| 10DLC or toll-free SMS registration | Not needed with AWS Notify; the fallback costs ~$4–$50 to register plus ~$2–$10 a month (brief §7) |

## Notes

- **The AWS free tier doesn't help much.** New accounts (since July 2025) get starter credits for
  their first months rather than a year of free usage. Treat any credits as a bonus, not a plan.
- **Biggest levers, in order:** the Stripe setup (D2: A, B and C differ by up to ~$226 a month at
  this volume), the fee rate and any minimum fee (D12), then the database choice (RDS ≈ $14/mo).
  Graviton servers (t4g instead of t3) save about 20% on the web server.
- **Corrections to an earlier estimate:**
  - A new AWS account no longer gets 12 months of free RDS and EC2 (that changed July 15, 2025).
  - Prompt caching saves nothing on prefill: the prompt is below Haiku 4.5's caching minimum.
  - Compute Savings Plans cover EC2 but not RDS.
- **Update this sheet** when D2, D12, D16, D17 or D19 are decided, and once real usage numbers
  come in from the weekly digest (W8.19).

**More sources:**
[Lightsail pricing, 2026](https://cloudburn.io/blog/amazon-lightsail-pricing) ·
[RDS db.t4g.micro reserved pricing](https://calculator.holori.com/aws/rds/db.t4g.micro) ·
[AWS Free Tier credits, July 2025](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-free-tier-credits-month-free-plan/).

**Sources:**
[EC2 t3.micro and public IPv4 pricing](https://calculator.holori.com/aws/ec2/t3.micro/us-east-1) ·
[AWS public IPv4 charge](https://spendark.com/blog/aws-pricing-changes-2026/) ·
[RDS for PostgreSQL pricing](https://aws.amazon.com/rds/postgresql/pricing) ·
[db.t4g.micro pricing](https://www.bytebase.com/dbcost/rds/instance/db.t4g.micro/) ·
[Sentry free plan](https://costbench.com/software/developer-tools/sentry/free-plan/) ·
[Sentry pricing](https://capterra.com/p/165426/sentry/pricing) ·
[Google Places pricing, 2026](https://www.woosmap.com/blog/google-places-api-pricing).
Stripe Connect, Shippo, AWS SMS and Django figures come from
`docs/internal/research/payments_tax_briefing_10062026.md`; Claude per-call costs come from the
2026-10-06 audit.
