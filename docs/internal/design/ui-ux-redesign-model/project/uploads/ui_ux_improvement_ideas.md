# KeystoneBid UI/UX Improvement Ideas

Reference: https://github.com/cormacbateman3/hunt/tree/alpha-p3 (READ ONLY)  
Prototype: `src/App.tsx`

---

## Priority Stack

| # | Idea | Effort | Impact | Status |
|---|------|--------|--------|--------|
| 1 | Mega-menu nav (Browse → 3-pillar panel) | Low | High | ✅ Prototyped |
| 2 | Breadcrumb path (Home › Browse › Listing) | Low | Medium | ✅ Prototyped |
| 3 | Unified Marketplace (collapse 3 browse views) | Medium | Very High | ✅ Prototyped |
| 4 | Onboarding wizard (3-step post-registration) | Medium | High | ✅ Prototyped |
| 5 | Listing detail sticky bid panel + quick-bid buttons | Low | High | ✅ Prototyped |
| 6 | Card type-accent line + timer overlay | Low | Medium | ✅ Prototyped |
| 7 | Home split-screen hero + Ending Soon strip | Medium | Medium | ✅ Prototyped |
| 8 | Create listing 2-step wizard with live preview | Medium | Medium | ✅ Prototyped |
| 9 | Collections horizontal identity cards | Low | Low | ✅ Prototyped |
| 10 | Activity feed / social layer | Medium | Very High | Not started |
| 11 | Seller reputation signals | Low | High | Not started |
| 12 | Watchlist / saved search alerts | Medium | High | Not started |
| 13 | Trade flow: "My Trades" list view + CTA on cards | Low | Medium | Not started |
| 14 | Listing micro-engagements (outbid toast, sparkline) | Low | Medium | Not started |
| 15 | Homepage personalization (post-onboarding feed) | Medium | Medium | Not started |
| 16 | Empty states everywhere | Low | Low | Not started |
| 17 | Mobile responsiveness | High | Medium | Not started |

---

## New Ideas (not yet prototyped)

### 10 — Activity Feed / Social Layer
Biggest missing engagement driver. Collectors want to know what's happening right now.
- **Live activity strip** on home: "PA_Heritage_Co just listed a 1934 Clinton County license" / "Outbid alert on 1919 Elk County"
- **"X people watching"** counter on listings — social proof creates real urgency
- **Follow collectors** (onboarding step 3 already seeds this) — their new listings appear in your feed
- alpha-p3: `apps/notifications/` exists — extend to publish feed events, render in home view

### 11 — Seller Reputation Signals
Buyers have no trust signal beyond a sale count today.
- **Verified Seller** badge at 10+ sales, no disputes
- **Response time** label on trade listings: "Usually responds within 2 hours"
- **Transaction history bar** on listing detail: 10-segment visual (filled = completed sale)
- alpha-p3: fields on `UserProfile`; computed in a template tag

### 12 — Watchlist / Saved Search Alerts
Biggest re-engagement lever for a niche marketplace.
- **Saved search**: "Alert me when a 1930s Bradford County license is listed"
- **Watchlist badge** in nav (heart icon, count pill)
- **"Similar to items you watch"** row at bottom of listing detail
- alpha-p3: `apps/favorites/` exists — extend with `SavedSearch` model + periodic task

### 13 — Trade Flow (keep what exists, polish the gaps)
`propose_offer.html`, `offer_detail.html`, and `trade_detail.html` are excellent — do not redesign them. Just:
- **"My Trades" list view** — simple landing page showing all active proposals/trades in one place (users lose track today)
- **"Propose a Trade" CTA on listing cards** for trade-type listings — one-tap path into the existing propose flow
- alpha-p3: add `trades/my_trades/` list view; simple queryset filter on `TradeOffer` by user

### 14 — Listing Micro-engagements
Small things that make browsing feel alive:
- **"Just listed" green dot** on cards under 24 hours old
- **Bid history sparkline** in listing detail — shows price trajectory over the auction lifetime
- **"You were outbid" toast** — red band slides up from bottom when browsing
- **Hover preview** on listing cards — floating expanded card on hover, no click required

### 15 — Homepage Personalization
After onboarding, the home page should feel curated:
- Hero text adapts: "Welcome back — 3 auctions ending in your saved counties"
- "Recommended for you" section filtered by era/county preferences from onboarding
- alpha-p3: pass personalized querysets from `home` view using `UserProfile.era_interests` / `county_interests`

---

## Trades: What Exists in alpha-p3 (do not redesign)

- `propose_offer.html` — drag-and-drop 4-column board with confirmation modal. Excellent.
- `offer_detail.html` — offer terms, accept/decline/counter/withdraw, offer history. Clean.
- `trade_detail.html` — full lifecycle: shipping, Shippo labels, receipt confirmation, disputes, post-trade review. Comprehensive.

Only gap: a **"My Trades" list view** so users can see all active proposals and trades in one place.

---

## Engagement Principles

1. **Urgency without anxiety** — timers and "X watching" create real urgency; avoid fake scarcity
2. **Progress/momentum** — outbid alerts and "you're winning" states keep users invested in auctions
3. **Social proof at decision time** — seller reputation on listing detail (when buying decision is made), not on browse cards
4. **Zero blank pages** — every section needs content or an empty state with a clear next action
5. **Return triggers** — watchlist alerts + ending-soon digests are the single biggest re-engagement lever
6. **One primary action per screen** — bid / buy / propose; don't dilute with competing CTAs
