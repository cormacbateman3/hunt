# Research notes

What was checked before writing any code, and why the notebook ends up
recommending what it does. Short version: **there is no free,
ToS-compliant, automated source of historical *sold* prices for this
category, anywhere.** Everything that has that data treats it as a
paid, gated, or explicitly bot-blocked commercial product.

## eBay

- **Finding API (`findCompletedItems`)** — the old way to query sold
  listings. Deprecated January 2024, fully decommissioned **February
  4, 2025**. No longer callable at all.
- **Marketplace Insights API** — the official replacement for sold-item
  data. It exists, but it's a **Limited Release API**: eBay's own docs
  say it's "restricted and not open to new users at this time" and
  requires business-level approval. Individual developers / small
  projects cannot get access. Even if approved, sales history is
  capped at the **last 90 days** — not the years of history a price-history
  feature would want.
- **Browse API** — free, open to any registered developer, no
  restrictions. But it only returns **active listings** (current asking
  prices), never sold/completed items. This is the one piece actually
  implemented here (`ebay_client.py`).
- **Scraping eBay directly** (search results or "sold" filter pages) —
  explicitly against eBay's User Agreement: *"You may not use any
  robot, spider, scraper, data mining tools... to access the Services...
  without our prior express written permission."* `robots.txt` backs
  this up structurally (`Disallow: /search?`, plus wildcard blocks on
  `*keyword=*`, `*sort=*`, `*filter=*` — exactly the parameters a sold-
  listing search would need). Not attempted, for both legal and
  practical reasons (eBay also runs active bot-detection on these
  pages; getting past it would mean the kind of detection-evasion this
  project won't build).
- **Terapeak** — eBay's own sold-comps research tool, but it's bundled
  into Seller Hub for eBay *sellers* (requires an eBay Store
  subscription) and is a manual web UI, not an API. Genuinely useful if
  you (the human) have or get an eBay seller account — just not
  automatable, and not something this script can sign you up for.

## WorthPoint

Worthopedia claims 545M+ historical sold prices — exactly what a price-
history feature would want — but:

- `robots.txt` disallows `/worthopedia` and `/inventory` **for named AI
  crawlers specifically, including `ClaudeBot` by name**, plus
  disallows `/worthopedia/*/price` and `/inventory/getPrice` for every
  crawler.
- Their Terms of Use separately prohibit "any data mining, robots,
  spidering, or similar data gathering and extraction tools," and
  content access is licensed for personal research use only, not
  extraction.
- No public developer API exists — just a paid subscription to the
  human-facing search product.

Given the site's robots.txt names Claude specifically, this was never a
candidate for scraping — noted here so the reasoning is on the record,
not just the conclusion.

## LiveAuctioneers / Invaluable / Heritage Auctions

All three publish auction-house "price realized" archives that would be
genuinely useful (LiveAuctioneers even has public `/price-result/...`
pages that turn up in search results). None publish an official public
API. What exists instead is a small industry of **third-party scrapers**
(e.g. Apify actors, ~$10/1000 results for LiveAuctioneers) built by
other people against these sites' HTML — which still means scraping a
site whose own terms almost certainly restrict it the same way eBay's
and WorthPoint's do, just enforced less visibly. Not implemented here
for the same reason WorthPoint wasn't: paying a third party to scrape
on your behalf doesn't change what's actually happening to the source
site's terms.

## Etsy

Checked briefly: Etsy's public API (v3) only exposes a shop's *active*
listings and, for sold history, only a shop owner's own private
"receipts" (not searchable across the marketplace). Not a source of
third-party historical comps at all, and vintage hunting/fishing
licenses aren't a meaningfully stocked Etsy category to begin with.

## What does exist: a real (if dated) print price guide

Ira W. Cotton's *California Pictorial Hunting and Fishing Licenses:
Handbook and Valuation Guide* (2007) is a genuine niche price guide for
this exact category, compiled from auction records. It's a book, not a
feed — no digitization or API. Useful as a manual reference for seeding
`manual_research`-sourced rows (see `price_data_schema.py`), not
something to automate against.

## The actual conclusion

No external source clears the bar of "free or reasonably priced, has
real historical sold prices for this specific category, and doesn't
require either scraping something that explicitly disallows it or
paying for gated business-tier API access." Given that, the sustainable
data source is the one KeystoneBid will generate itself: every
completed `Order` *is* a real sold-price observation the moment it
happens. The notebook's schema (`price_data_schema.py`) is built so
that source, eBay's active-listing asking prices (a legitimate current-
market signal, clearly flagged as `is_actual_sale=False`), and hand-
entered research (from Terapeak, the Cotton guide, appraisals, etc.)
can all be combined in one place — honestly labeled by source, not
blended together as if they were equally authoritative.
