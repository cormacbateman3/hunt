# Payments, tax and accounts: briefing for Backtag

**Researched 2026-10-06.** This is not tax or legal advice. It is a sourced starting point for the
conversation with a CPA and an attorney (see the question lists at the end). Stripe, AWS and Django
pages were read live on that date. **[unverified]** marks anything that could not be confirmed.
Roadmap links: D2, D3, D12, D15 and the owner track in
`docs/internal/plans/plan_workable_product_10062026.md`.

---

## 1. Stripe Connect: how sellers get paid

- **The old account types are legacy.** Stripe now calls Standard, Express and Custom "legacy" and
  points new platforms to [Accounts v2](https://docs.stripe.com/connect/accounts-v2), or to v1 with
  [controller properties](https://docs.stripe.com/connect/accounts).
  - Each seller account is defined by its dashboard type (full, express or none) and two
    responsibilities, `fees_collector` and `losses_collector`. Both responsibilities are fixed at
    creation and can't be changed later.
  - An "Express-like" setup is dashboard `express` with both responsibilities set to `application`.
  - **[unverified]** The v2 example uses a `.preview` API version. Confirm v2 is generally
    available before building on it.
- **The three charge types and who bears losses**
  ([charges](https://docs.stripe.com/connect/charges)):

  | Charge type | Where money lands | Who bears refunds and chargebacks |
  |---|---|---|
  | **Direct** | The seller's account | The seller's balance; Stripe can carry negative-balance liability |
  | **Destination** | The platform is the merchant of record | The platform's balance, including the $15 dispute fee ([pricing](https://stripe.com/pricing)); it recovers money by reversing the transfer to the seller |
  | **Separate charges and transfers** | The platform | Same as destination, but refunds never reverse transfers automatically |

  Separate charges and transfers is only for multi-party splits or delayed transfers.
- **Fit for an eBay-style marketplace taking a % fee: destination charges with an
  `application_fee_amount`.** The full charge goes to the seller, the fee comes back to the
  platform, and Stripe's processing fee comes out of the platform's share.
  - Stripe's own example: a $10 charge with a $1.23 platform fee and a $0.59 Stripe fee leaves
    the platform $0.64 ([destination charges](https://docs.stripe.com/connect/destination-charges.md?platform=web&ui=stripe-hosted)).
  - On a refund, by default the seller keeps the transfer and the platform keeps its fee. To claw
    them back, set `reverse_transfer` and `refund_application_fee`.
- **What Connect costs when the platform controls pricing**
  ([Connect pricing](https://stripe.com/connect/pricing)):
  - **$2 per monthly active account**, meaning any month in which that seller receives a payout.
  - **0.25% + 25¢ per payout.** Instant Payouts cost 1%.
  - 1099 forms: $2.99 per IRS e-file, $1.49 per state e-file, $2.99 per mailed copy.
  - If Stripe controls pricing instead (direct charges, where the seller pays Stripe), the platform
    pays none of these.
- **Worked example (card pricing 2.9% + 30¢), when the platform sets pricing.** Take a seller
  whose only sale that month is $40, at a 10% fee: $4.00 fee − $1.46 card − $2.00 active-account
  − $0.34 payout = **$0.20** to the platform. **At 8% it's a $0.60 loss.** With five sales to the
  same seller that month, the platform nets about $2.00 per sale.
  - **Correction (2026-10-06):** batching payouts does *not* avoid the $2. It's charged for any
    month in which a seller receives a payout. So occasional sellers, which this site will have
    many of, are the expensive case.
- **When Stripe sets pricing** (Standard accounts, direct charges):
  - **Platform:** pays no Connect fees and no card processing, and keeps its whole fee ($4.00 at
    10%, $3.20 at 8%).
  - **Stripe:** files the 1099-Ks.
  - **Seller:** pays Stripe's processing (~$1.46 on $40), absorbs refunds and disputes in their own
    account, and needs a full Stripe account.
- **The trade cash add-on works** under either model. With destination charges: charge member A
  through Checkout with `transfer_data[destination]` set to member B and `application_fee_amount`
  set to the platform's cut. With direct charges: create the charge on member B's account, with the
  same application fee.
  - B must finish onboarding first.
  - Both $1 trade fees can ride on that one charge, with B's $1 deducted from B's proceeds.
  - A standalone $1 card charge would lose about 33¢ to Stripe, so don't charge it on its own.
  - Keep the add-on tied to the goods being traded. Stripe
    [prohibits](https://stripe.com/legal/restricted-businesses) peer-to-peer money transmission.

## 2. Seller onboarding and 1099s

- **What a US individual seller provides** in Stripe-hosted onboarding:
  - Name, email, phone, date of birth, home address (no PO box), last 4 of SSN.
  - Bank account, merchant category code, a URL or product description, statement descriptor and
    terms acceptance.
  - The URL can be prefilled with the seller's Backtag profile page.
- **Who files the 1099-Ks.** Stripe files them only where Stripe controls pricing. **With
  destination charges, the platform is responsible**
  ([tax reporting](https://docs.stripe.com/connect/tax-reporting)).
  - Stripe's 1099 tool files federal and state forms, shows each seller's TIN status, and delivers
    the forms.
  - You configure the form type, filer type, calculation method, and state registration IDs (e.g.
    MD, VT).
  - Key dates: enable Stripe's outreach to sellers by **Jan 4**, file by **Jan 22**, forms to
    sellers by **Feb 1**.
- **Federal 1099-K threshold.** The One Big Beautiful Bill (signed July 4, 2025) retroactively
  restored **more than $20,000 and more than 200 transactions**, cancelling the $2,500/$600
  phase-in ([IRS, Oct 23 2025](https://www.irs.gov/newsroom/irs-issues-faqs-on-form-1099-k-threshold-under-the-one-big-beautiful-bill-dollar-limit-reverts-to-20000)).
- **Lower state thresholds** for tax year 2026 ([Stripe table](https://docs.stripe.com/connect/1099-k)).
  Small sellers in these states will get forms:
  - $600: DC, MD, MA, MT, VT, VA.
  - $1,000 and 4 transactions: IL.
  - $1,000: NJ.
  - $2,500: AR.
- **Trades may need a different form.** A "barter exchange" must file Form 1099-B per exchange once
  it has 100 or more exchanges in a year ([i1099b](https://www.irs.gov/instructions/i1099b)).
  Stripe's tool covers only 1099-K, NEC and MISC, so this is a CPA question.

## 3. Sales tax

- **Marketplace facilitator rules.** Once a marketplace crosses a state's threshold, it collects
  and remits sales tax on its sellers' sales, and the sellers usually don't need to register
  ([SST](https://www.streamlinedsalestax.org/for-businesses/marketplace-sellers)).
  - Where the platform has physical presence, some states require collection from the **first
    sale**. **Your home state matters most.**
- **Thresholds** ([2026 roundup](https://trykintsugi.com/sales-tax-guides/usa/economic-nexus)):
  - Most states: $100k in sales.
  - CA and TX: $500k. NY: $500k and 100 transactions. AL and MS: $250k.
  - Several states dropped the transaction count: IL from Jan 1 2026
    ([IDOR](https://tax.illinois.gov/research/publications/bulletins/fy-2026-12.html)), UT in 2025,
    KY from Aug 1 2026, plus others.
  - Still using about 200 transactions: AR, DC, GA, HI, **MD**, MI, MN, NE, NV, NJ, **OH**, RI, VT,
    VA, WV.
- **What is taxable.**
  - Paper collectibles are tangible goods and taxable by default. **[unverified]** No exemption
    for expired licenses or used stamps was found.
  - Shipping varies by state. Georgia and Louisiana tax it even when listed separately; Maryland,
    Massachusetts and Florida exempt it under conditions
    ([Stripe](https://stripe.com/resources/more/is-shipping-taxable)).
- **Stripe Tax as the marketplace collector**
  ([docs](https://docs.stripe.com/tax/tax-for-marketplaces)):
  - Works with destination charges and separate charges and transfers. **Not with direct charges.**
  - The platform claws the collected tax back from the seller, by reversing the transfer or
    transferring less.
  - Cost: 0.5% per transaction (no-code setup) or 50¢ per API transaction, only where registered.
    **Threshold monitoring alerts are free.** Filing needs Tax Complete.
- **A realistic first year:**
  1. A CPA settles whether you must collect in your home state from day one.
  2. Every order records ship-to state, gross and count. Order address snapshots already make
     this possible.
  3. A monthly by-state report alerts at 50–75% of each threshold, and Stripe Tax monitoring is on.

## 4. Who owns the accounts (do this before anything goes live)

- **Stripe.** For a business sale, Stripe Support can update the owner/representative, bank, email,
  legal name and tax ID
  ([Stripe](https://support.stripe.com/questions/transfer-a-stripe-account-to-a-different-entity-due-to-a-business-sale-or-acquisition)).
  - **[unverified]** Whether a live Connect platform can move to a new legal entity with its
    connected sellers intact. If it can't, every seller onboards again.
  - **Open the live platform account in the right name from the start.**
- **AWS.** An account can be assigned to another person or business, with AWS's consent and no
  outstanding balance
  ([requirements](https://aws.amazon.com/legal/aws-account-assignment-requirements/)).
  - AWS Organizations transfers (since Nov 2025) move billing and governance, not legal ownership.
- **Google Cloud.** A payments profile's type (Individual or Organization) can't be changed
  ([Google](https://support.google.com/paymentscenter/answer/9028746?hl=en)). The fix is a new
  billing account, then relinking projects to it.
- **Practical order:**
  1. LLC, then EIN, then business bank account.
  2. Role email addresses on the company domain.
  3. Open Stripe, AWS, Google Cloud, Shippo, SES and the domain registrar in the business's name.
  4. The developer gets team or IAM access, not ownership. Everyone uses MFA and a shared password
     vault.
  - SMS sender registration needs the EIN anyway.

## 5. Money transmission

- **Federal.** FinCEN's payment-processor exemption
  ([31 CFR 1010.100(ff)(5)(ii)(B)](https://www.ecfr.gov/current/title-31/subtitle-B/chapter-X/part-1010/subpart-A/section-1010.100);
  [FIN-2014-R009](https://www.fincen.gov/sites/default/files/administrative_ruling/FIN-2014-R009.pdf))
  requires a purchase of goods, bank-only clearing, and a formal agreement with the seller.
- **Stripe's position.** Stripe is a licensed money transmitter, and with Connect the platform
  never holds or controls seller funds ([Connect](https://stripe.com/connect)).
- **Caveats:**
  - Never route buyer money through the company's own bank or PayPal.
  - No spendable "wallet" balances.
  - Stripe does **not** provide escrow. Manual payouts can be held up to 2 years in the US, meant
    for late deliveries or likely refunds
    ([manual payouts](https://docs.stripe.com/connect/manual-payouts)).
  - Keep any hold short and tied to order or trade status, and have an attorney review it.

## 6. Shippo labels

- **How labels are billed.** Shippo charges the account holder's card or ACH, and bills carrier
  adjustments after delivery. **[unverified]** The billing page returned 403, so this comes from
  search excerpts.
  - API pricing: 30 free labels a month, then 7¢ per label ([pricing](https://goshippo.com/pricing/api)).
- **Platform options**
  ([integration options](https://docs.goshippo.com/docs/oauth_integrations/buildingshippointegration)):
  - **White label:** one platform account; the platform pays Shippo and bills its users. This is
    what Backtag does today.
  - **Managed Shippo Accounts:** sub-accounts under the platform, still billed to the platform.
  - **OAuth:** sellers connect their own Shippo accounts and Shippo bills them directly.
- **Passing label costs on:**
  - The buyer pays a shipping line and the platform keeps it rather than transferring it to the
    seller.
  - Or add the label cost to `application_fee_amount`, so it comes out of the seller's proceeds.
  - Trades: each side pays for its own label when the trade is accepted.
  - Decide who absorbs the later carrier adjustments.
- **Today:** Backtag buys every label on its own account. Seller-paid order labels and **all trade
  labels are absorbed by the platform and never recorded.**

## 7. Phone verification by SMS on AWS

- **Registration is required.** US texts must come from a registered 10DLC number, toll-free number
  or short code, and that includes AWS's OTP feature
  ([AWS](https://docs.aws.amazon.com/pinpoint/latest/developerguide/send-validate-otp.html)).

  | Option | Setup time | Cost |
  |---|---|---|
  | **10DLC** | Brand and vetting 1–2 business days each; campaign up to 4 weeks; number up to 10 days | ~$4 brand + $40 vetting + $10/mo per campaign ($2 low-volume) + $1/mo per number; ~$0.0058 per message + carrier fee |
  | **Toll-free** | ~15 days | ~$2/mo |
  | **Short code** | ~12 weeks | $995/mo + $650 setup (overkill) |
  | **AWS End User Messaging Notify** (blog dated July 28 2026) | None: AWS supplies registered senders, including US | ~$0.045 per message + SMS charges |

  - 10DLC sources: [timeline](https://docs.aws.amazon.com/sms-voice/latest/userguide/registrations-10dlc.html),
    [registration best practices](https://aws.amazon.com/blogs/messaging-and-targeting/10dlc-registration-best-practices-to-send-sms-with-amazon-pinpoint/).
  - **Toll-free:** needs an EIN unless you register as a sole proprietor. **From Sept 15 2026, new
    registrations also need live Privacy Policy and Terms URLs.**
  - **Notify:** pre-approved message templates only; basic tier is 200 messages a day, 1 per
    second ([blog](https://aws.amazon.com/blogs/messaging-and-targeting/getting-started-with-aws-end-user-messaging-notify/)).
  - **Notify is the simplest path for a side project.**

## 8. Django

- **Support status** ([djangoproject](https://www.djangoproject.com/download/)):
  - 5.0 lost all support on **Apr 2 2025**.
  - **5.2 LTS gets security fixes until April 2028** (latest is 5.2.18).
- **5.1 removed** `DEFAULT_FILE_STORAGE`, `STATICFILES_STORAGE`, `get_storage_class()`,
  `Meta.index_together` and `length_is`.
  - This repo still uses the old settings: `config/settings/base.py:137`, `development.py:44`,
    `production.py:60-61`.
  - After the upgrade they would most likely be ignored silently, so WhiteNoise and S3 would fall
    back to the defaults with no error. **Move to `STORAGES` as part of the upgrade, and check
    with `collectstatic`.**
- **Version floors on 5.2:** PostgreSQL 14+, Python 3.10–3.14.

## 9. Legality

- **Transfer bans target use, but the wording can be broad.**
  - Montana says a person may not "loan or transfer any license to another person," with no
    "while valid" limit ([MCA 87-6-304](https://mca.legmt.gov/bills/mca/title_0870/chapter_0060/part_0030/section_0040/0870-0060-0030-0040.html)).
    Idaho is similar ([36-405](https://legislature.idaho.gov/statutesrules/idstat/Title36/T36CH4/SECT36-405)).
  - Collecting old licenses is a long-established hobby.
  - **[unverified]** Only a few states were checked.
- **Duck stamps.**
  - [16 USC 718e](https://www.law.cornell.edu/uscode/text/16/718e) bars transferring a signed stamp
    during its hunting year (July 1 to June 30), and bars altering or counterfeiting stamps.
  - The FWS limits reproductions of stamp imagery to philatelic, educational, historical or
    newsworthy use, or to licensees
    ([FWS](https://www.fws.gov/service/license-duck-stamps-or-junior-duck-stamp-imagery);
    [18 USC 504](https://www.law.cornell.edu/uscode/text/18/504)). This raises a question about
    listing photos.
- **Wildlife parts.** Selling or bartering migratory-bird parts is illegal
  ([16 USC 703](https://www.law.cornell.edu/uscode/text/16/703)), so framed displays with feathers
  are caught.
- **What the Terms of Service should say:**
  - Only items whose validity has ended. That excludes current-season licenses, still-valid
    multi-year licenses, lifetime licenses of living holders, e-licenses, and signed current-year
    duck stamps.
  - Items are collectibles only and grant no hunting privilege.
  - No reproductions unless clearly marked and lawful.
  - The seller warrants ownership and authenticity.
  - No wildlife parts.
  - ID numbers and dates of birth on recent items must be covered.
  - Backtag is a venue, never the auctioneer.
- **Stripe's profile.** Stripe doesn't restrict collectibles, but it bans "fake references or
  ID-providing services," so describe the category clearly in the Stripe platform profile.

---

## Questions to bring to a CPA or attorney

- Must we collect sales tax in our home state from the first sale? Do trades and cash add-ons count
  as facilitated sales, and what is the tax base for a barter?
- Are we a "barter exchange" that must file 1099-Bs? Which 1099-K filer type are we? How do we
  handle backup withholding when a seller's TIN is missing?
- Are the % fee, the $1 trade fee and the shipping we charge taxable?
- Do payout holds tied to delivery or trade completion keep us inside the payment-processor and
  agent-of-payee exemptions?
- Do listing photos of duck stamps need FWS permission?
- Does a broadly worded transfer statute (e.g. Montana's) create risk for selling expired licenses?
- What privacy duties do we have for personal details printed on licenses?
- How should ownership of the LLC and the code be documented between the stakeholder and the
  developer?

## Decisions to make before building payouts

- **Entity and representative.** Form the legal entity and choose who is Stripe's representative,
  before any live account is opened.
- **How to set up Stripe Connect.** **Recommendation (revised again 2026-10-06): B.**
  - **A — Stripe sets pricing** (Standard accounts, direct charges):
    - No Connect fees; the platform keeps its whole fee.
    - Stripe files the 1099-Ks and carries refund, dispute and negative-balance losses. This is
      the least upkeep.
    - **But** the buyer's card statement shows the *seller's* name
      ([statement descriptors](https://docs.stripe.com/connect/statement-descriptors)), which
      invites "I don't recognize this charge" disputes.
    - Sellers get a full Stripe account with Stripe's dashboard and emails.
    - Stripe Tax can't collect as the marketplace.
  - **B — Backtag sets pricing; the seller pays card processing** (Express-style accounts,
    destination charges, application fee = Backtag's % + Stripe's processing):
    - The statement shows Backtag.
    - Onboarding is embedded in Backtag's pages with limited Stripe branding.
    - Stripe Tax works.
    - Backtag pays $2 per active seller per month plus payout fees, files the 1099s through
      Stripe's tool, and recovers disputes from the seller by reversing the transfer. That
      recovery must be in the Terms.
    - A one-sale seller nets Backtag $0.86 at an 8% fee.
  - **C — Backtag sets pricing and absorbs processing:** loses $0.60 on a one-sale $40 seller at
    8%. **Ruled out.**
  - **Why B:** the owner wants sellers to barely notice Stripe, and wants buyers to see Backtag.
    Choose A instead if margin and the least upkeep matter more.
- **Fee schedule.** The percentage, any minimum fee, who sees it (buyer surcharge or seller
  deduction — the code does both today), and how the $1 trade fees are collected (bundled into the
  add-on or the label charge).
- **Payout timing.** Under B, use automatic weekly payouts: about $1 a month per seller in 25¢
  fees. Monthly saves about 75¢ but makes sellers wait, and the $2 per active seller is the same
  either way. Under A, Stripe's default schedule applies. Either way, decide whether payouts wait
  for confirmed delivery.
- **Refunds and chargebacks.** Whether refunds always reverse the seller's transfer, whether the
  platform fee is refunded, and whether Stripe may debit sellers' banks for negative balances.
- **Shipping.** Platform-owned Shippo or sellers' own accounts, and who pays carrier adjustments.
- **Trades.** When the cash add-on is released.
- **Phone verification.** AWS Notify, a toll-free number, or email-only at launch.
