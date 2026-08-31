"""One-off generator for sales_data_exploration.ipynb. Not part of the
deliverable itself — run this, then delete it, whenever the notebook
needs regenerating from scratch. Keeping cell content here (plain
strings) is much easier to edit/review than hand-writing notebook JSON.
"""
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(text):
    cells.append(nbf.v4.new_markdown_cell(text))


def code(text):
    cells.append(nbf.v4.new_code_cell(text))


md("""\
# Hunting & fishing license sales data — what's actually possible?

**Goal:** find a source of *historical sales prices* for antique/vintage
hunting & fishing licenses, to power a price-history and rarity feature
in KeystoneBid. This notebook is the research prototype for that
question — not production code.

**Headline finding:** there is no free, terms-of-service-compliant,
automated source of *historical sold prices* for this category, from
eBay, WorthPoint, or the auction-house aggregators. Every one of them
either decommissioned that data, gates it behind business-approval or a
paid subscription, or blocks automated access outright (WorthPoint's
`robots.txt` names `ClaudeBot` specifically). Full details, with
sources, in [`RESEARCH_NOTES.md`](RESEARCH_NOTES.md) next to this
notebook.

What *is* available and implemented below:
1. eBay's official **Browse API** — free, but active-listing asking
   prices only, never sold prices.
2. A source-agnostic schema (`price_data_schema.py`) so real data —
   whichever thin source it comes from — can be combined and analyzed
   the same way once it exists.
3. A demonstration of that analysis (price history, rarity scoring) run
   on a small **synthetic** dataset, since there's no real historical
   data to run it on yet. Every synthetic value below is labeled as
   such — none of it is real market data.
""")

code("""\
import sys
from pathlib import Path

# Run from the repo root; this also works if launched directly from
# utilities/sales_api/ since Jupyter's cwd is the notebook's folder.
REPO_ROOT = Path.cwd()
if not (REPO_ROOT / "utilities").exists():
    REPO_ROOT = REPO_ROOT.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "utilities" / "sales_api" / ".env")

import pandas as pd
import matplotlib.pyplot as plt

from utilities.sales_api.ebay_client import EbayBrowseClient, EbayCredentialsMissing
from utilities.sales_api import price_data_schema as pds

pd.set_option("display.max_colwidth", 60)
""")

md("""\
## 1. eBay Browse API — current active-listing asking prices

This is the one live, official, ToS-compliant data pull this notebook
makes. It needs your own free eBay Developer credentials (see
`README.md` — registering that account is a step for you, not this
script, to do). Without credentials, this cell explains that and moves
on rather than failing or faking a result.
""")

code("""\
QUERY = "vintage hunting license"

client = EbayBrowseClient()
try:
    listings = client.search_active_listings(QUERY, limit=50)
    print(f"Pulled {len(listings)} active listing(s) for {QUERY!r} from eBay's Browse API.")
except EbayCredentialsMissing as exc:
    listings = []
    print("No eBay credentials configured — skipping the live pull.\\n")
    print(exc)
""")

code("""\
listings_df = pd.DataFrame([l.__dict__ for l in listings])
if not listings_df.empty:
    display(listings_df[["title", "price", "currency", "condition", "item_web_url"]])
    out_path = REPO_ROOT / "utilities" / "sales_api" / "sample_data" / "ebay_active_listings_sample.csv"
    listings_df.to_csv(out_path, index=False)
    print(f"Saved {len(listings_df)} row(s) to {out_path}")
else:
    print("Nothing to show — see the explanation above.")
""")

md("""\
### Why active listings still tell you something

These are asking prices, not confirmed sales — real prices are often
lower after negotiation or auction dynamics. But two things about
*active listings* are still genuinely useful signals, and don't require
sold data at all:

- **Listing count as a scarcity proxy.** A search that returns 3 active
  listings nationwide is a meaningfully different rarity signal than
  one that returns 300, independent of price.
- **Asking price as a market ceiling.** Sellers rarely ask well below
  what similar sold items fetched; asking prices bound the market from
  above even without confirming what actually closed.

The cell below demonstrates the listing-count signal across a few
states, for a fixed license era, to show the *shape* of that analysis —
it only actually calls the API if credentials are configured.
""")

code("""\
STATES_TO_COMPARE = ["Connecticut", "Vermont", "Mississippi", "Hawaii"]

if listings:  # only re-query if the first live pull above actually worked
    counts = {}
    for state in STATES_TO_COMPARE:
        results = client.search_active_listings(f"vintage 1930s {state} hunting license", limit=50)
        counts[state] = len(results)
    counts_df = pd.DataFrame(sorted(counts.items(), key=lambda kv: kv[1]), columns=["state", "active_listing_count"])
    display(counts_df)
else:
    print("Skipped (no eBay credentials) — this would run one search per state and compare result counts.")
""")

md("""\
## 2. Why there's no historical *sold*-price source (summary)

Checked and ruled out — full detail with sources in `RESEARCH_NOTES.md`:

| Source | Status |
|---|---|
| eBay Finding API (`findCompletedItems`) | Fully decommissioned Feb 2025 |
| eBay Marketplace Insights API | Official replacement for sold data, but "Limited Release" — restricted to approved business partners, and even then capped at 90 days of history |
| eBay search/sold-listing pages (scraping) | Explicitly prohibited by eBay's User Agreement; `robots.txt` disallows the search paths it would need |
| WorthPoint (Worthopedia) | 545M+ historical prices exist, but `robots.txt` blocks AI crawlers **by name, including ClaudeBot**, and Terms of Use separately prohibit scraping. No public API. |
| LiveAuctioneers / Invaluable / Heritage Auctions | No official public API. Only third-party scrapers (e.g. paid Apify actors) exist, built against the same terms that block WorthPoint/eBay scraping. |
| Etsy | API only exposes active listings + a shop owner's own private sales — no cross-marketplace sold-comp search, and not a meaningfully stocked category anyway |
| Terapeak (eBay's own sold-comps tool) | Real and official, but bundled into Seller Hub for eBay *sellers* with a Store subscription — a manual web tool, not an API |
| Ira W. Cotton's *California Pictorial Hunting and Fishing Licenses* (2007) | A genuine niche print price guide for this exact category — not digitized or an API, but a legitimate manual reference for seeding research rows |

**Bottom line:** nothing clears the bar of "free, has real sold prices
for this category, and doesn't require either scraping something that
explicitly disallows it or business-tier paid API access."
""")

md("""\
## 3. A schema that doesn't pretend these sources are equal

`price_data_schema.PriceObservation` is deliberately source-agnostic —
built so KeystoneBid's own completed orders, eBay's asking prices, and
hand-entered research rows can all live in one DataFrame, each still
honestly labeled by `source_type` and whether it's an `is_actual_sale`.
""")

code("""\
import dataclasses
for f in dataclasses.fields(pds.PriceObservation):
    print(f"{f.name:<24} {f.type}")

print("\\nSource types:", pds.SOURCE_TYPES)
""")

md("""\
## 4. Demonstrating the analysis on a SYNTHETIC example

**Every price below is made up**, invented only to exercise
`price_history_by_group` and `rarity_score` from `price_data_schema.py`
so their behavior can be seen before any real data exists. Do not treat
any number in this section as a real market value.
""")

code("""\
# SYNTHETIC EXAMPLE DATA -- none of this is a real observed price.
synthetic_observations = [
    pds.PriceObservation(pds.SOURCE_TYPE_MANUAL_RESEARCH, "Connecticut", "Resident Hunting License", "1936", 45.0, True, notes="SYNTHETIC EXAMPLE"),
    pds.PriceObservation(pds.SOURCE_TYPE_MANUAL_RESEARCH, "Connecticut", "Resident Hunting License", "1938", 55.0, True, notes="SYNTHETIC EXAMPLE"),
    pds.PriceObservation(pds.SOURCE_TYPE_INTERNAL_ORDER, "Connecticut", "Resident Hunting License", "1938", 62.0, True, notes="SYNTHETIC EXAMPLE"),
    pds.PriceObservation(pds.SOURCE_TYPE_INTERNAL_ORDER, "Connecticut", "Resident Hunting License", "1938", 58.0, True, notes="SYNTHETIC EXAMPLE"),
    pds.PriceObservation(pds.SOURCE_TYPE_EBAY_ACTIVE_LISTING, "Vermont", "Combination License", "1927", 72.0, False, notes="SYNTHETIC EXAMPLE"),
    pds.PriceObservation(pds.SOURCE_TYPE_MANUAL_RESEARCH, "Mississippi", "Hunting Button", "1920s", 950.0, True, notes="SYNTHETIC EXAMPLE - badges from Southern states are noted as scarce"),
    pds.PriceObservation(pds.SOURCE_TYPE_EBAY_ACTIVE_LISTING, "Hawaii", "Hunting Badge", "1920s", 890.0, False, notes="SYNTHETIC EXAMPLE"),
]

synthetic_df = pds.observations_to_dataframe(synthetic_observations)
display(synthetic_df)
""")

code("""\
history = pds.price_history_by_group(synthetic_df)
display(history)

fig, ax = plt.subplots(figsize=(7, 4))
labels = history["state"] + " " + history["year_or_era"]
ax.bar(labels, history["median_price"])
ax.set_ylabel("Median price ($) -- SYNTHETIC EXAMPLE DATA")
ax.set_title("Price by state / era (SYNTHETIC EXAMPLE -- not real sales)")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.show()
""")

code("""\
scores = pds.rarity_score(synthetic_df)
display(scores)

fig, ax = plt.subplots(figsize=(7, 4))
labels = scores["state"] + " " + scores["year_or_era"]
ax.bar(labels, scores["rarity_score"], color="firebrick")
ax.set_ylabel("Rarity score (0-100) -- SYNTHETIC EXAMPLE DATA")
ax.set_title("Scarcity proxy: fewer observations -> higher score (SYNTHETIC)")
plt.xticks(rotation=30, ha="right")
plt.tight_layout()
plt.show()
""")

md("""\
Notice the rarity score here is really measuring "how few times have we
recorded this" — with 7 synthetic rows total, that's not yet a
meaningful scarcity signal. It becomes one as real
`is_actual_sale=True` observations accumulate (see Section 5).
""")

md("""\
## 5. Recommended path forward

1. **Capture KeystoneBid's own completed orders as price observations,
   going forward.** This is the one source of real, historical, sold
   prices for this exact category that's actually obtainable — every
   `Order` the marketplace completes already contains this data. That's
   a product/schema decision in `apps/orders`, not something this
   research script can retroactively create.
2. **Seed a small manual research set** using
   [`sample_data/price_observations_template.csv`](sample_data/price_observations_template.csv)
   — the same `PriceObservation` shape used above — from sources like
   the Cotton price guide, appraisals, or (if you personally have or
   get an eBay Store subscription) Terapeak's sold-comp lookup. This is
   manual by nature; there's no automatable version of it right now.
3. **Use the eBay Browse API pull in Section 1 as an ongoing, light
   signal** — active listing counts and asking prices, refreshed
   periodically, layered in as `is_actual_sale=False` rows so they're
   never confused with confirmed sales.
4. **Revisit eBay's Marketplace Insights API later.** It's the correct
   long-term answer if KeystoneBid ever has the business relationship
   with eBay to get Limited Release approval — worth re-checking as the
   app grows, not worth blocking on now.

None of this ships a price-history feature today. It gives KeystoneBid
a real, honestly-sourced way to start building one.
""")

nb["cells"] = cells
nbf.write(nb, "sales_data_exploration.ipynb")
print("wrote sales_data_exploration.ipynb with", len(cells), "cells")
