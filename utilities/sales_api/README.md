# sales_api

A research prototype ("is this even possible?") for pulling hunting
and fishing license **sales price data** — the goal being price history
and rarity scoring for KeystoneBid listings. Standalone: nothing here
is imported by or imports from `apps/`.

**Read [RESEARCH_NOTES.md](RESEARCH_NOTES.md) first.** The short
version: there is currently no free, ToS-compliant, automated source
of *historical sold prices* for this category anywhere — not eBay
(sold-item APIs are decommissioned or business-gated), not WorthPoint
(its `robots.txt` blocks AI crawlers by name, including Claude, and its
Terms of Use separately prohibit scraping), not the auction-house
aggregators (no public API, only third-party scrapers of the same
kind). That's a real finding, not a shortcut — it shapes everything
below.

## What's actually implemented

1. **`ebay_client.py`** — a small wrapper around eBay's official,
   free **Browse API**. This only returns *active* listings (current
   asking prices), never sold prices — see RESEARCH_NOTES.md for why
   that's the ceiling of what eBay's API surface allows without
   restricted business approval. Still useful: a scarce category will
   simply show few active listings, which is itself a rough scarcity
   signal, and asking prices bound the market even without sale
   confirmation.

2. **`price_data_schema.py`** — a source-agnostic `PriceObservation`
   shape, so that three very different kinds of data — KeystoneBid's
   own completed orders, eBay active-listing asking prices, and
   hand-entered research (a price guide, an appraisal, Terapeak sold
   comps you look up yourself) — can sit in the same DataFrame without
   pretending they're equally authoritative. Every row carries
   `source_type` and `is_actual_sale` explicitly.

3. **`sales_data_exploration.ipynb`** — the notebook that ties it
   together: calls the eBay client (if you provide credentials — see
   below), and demonstrates the price-history and rarity-scoring
   functions on a small, clearly-labeled **synthetic** dataset (since
   there's no real historical data to run them on yet).

## Setup

```bash
pip install -r utilities/sales_api/requirements.txt
```

To actually pull live eBay data, register your own free eBay Developer
account and app — this script deliberately does not and cannot do that
step for you (creating accounts on your behalf is out of scope for an
assistant to do):

1. Go to <https://developer.ebay.com/my/keys> and sign up.
2. Create a keyset (production). You'll get an **App ID** (`EBAY_CLIENT_ID`)
   and **Cert ID** (`EBAY_CLIENT_SECRET`).
3. Put them in a `.env` file in this folder (never commit it):
   ```
   EBAY_CLIENT_ID=your-app-id
   EBAY_CLIENT_SECRET=your-cert-id
   ```
4. Run the notebook. Without credentials it still runs — it just skips
   the live eBay cell and says so explicitly, rather than failing
   ugly or fabricating a response.

## Why a notebook

You asked for this as a "what's possible" test rather than production
code, so it's structured to be read top-to-bottom as a narrative:
what was tried, what worked, what's blocked and why, and what the data
shape would look like once real observations exist — not a polished
pipeline.

## What this does NOT do (on purpose)

- Does not scrape eBay, WorthPoint, LiveAuctioneers, Invaluable, or
  Heritage Auctions. Each explicitly restricts that in its Terms of
  Use and/or `robots.txt` (WorthPoint's blocks Claude by name — see
  RESEARCH_NOTES.md). Respecting that isn't a limitation of the tool,
  it's the actual state of what's available.
- Does not attempt to defeat bot detection on any site.
- Does not fabricate sold-price data. The synthetic example rows in
  the notebook are labeled `SYNTHETIC EXAMPLE` in every place they
  appear, specifically so they're never mistaken for real market data
  if this notebook or its output is looked at later.

## Recommended path forward (from RESEARCH_NOTES.md's conclusion)

The one source of real historical sold prices for this exact category
that KeystoneBid can *actually* get, legally and for free, is its own
transaction history: every completed `Order` the marketplace processes
going forward is a genuine sold-price data point. That's a product
decision (capturing/exposing that history from `apps/orders`), not
something this research script can retroactively create — but the
`price_data_schema.py` shape here is designed so that feed, plus
occasional manually-curated research rows, plug in directly once it
exists.
