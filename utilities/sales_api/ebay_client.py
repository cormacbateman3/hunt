"""Minimal client for eBay's official Browse API.

Deliberately does not touch anything eBay's User Agreement or
robots.txt disallow. Concretely, that rules out:

- Scraping eBay search/completed-listing pages directly. eBay's user
  agreement prohibits "any robot, spider, scraper, data mining tools...
  to access the Services... without prior express written permission,"
  and robots.txt disallows the `/search?`-style paths this would need.
- The Finding API's old `findCompletedItems` call, which returned sold
  listings — fully decommissioned by eBay in February 2025.

What's left, and what this module wraps, is the **Browse API**: free,
official, requires only an eBay Developer account (register one
yourself at developer.ebay.com — this script can't and shouldn't do
that step for you, see README.md). It only returns *active* listings —
current asking prices, not sold/completed prices. See
RESEARCH_NOTES.md for why true historical sold-price data has no
free, ToS-compliant, programmatic source at all right now.

Auth: client-credentials OAuth grant (app-level token, no user login
needed) — see
https://developer.ebay.com/api-docs/static/oauth-client-credentials-grant.html
"""
from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

PRODUCTION_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
PRODUCTION_BROWSE_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
DEFAULT_SCOPE = "https://api.ebay.com/oauth/api_scope"

USER_AGENT = "KeystoneBid-SalesResearch/0.1 (utility script; official Browse API only)"


class EbayCredentialsMissing(RuntimeError):
    """Raised when EBAY_CLIENT_ID / EBAY_CLIENT_SECRET aren't set.

    This is expected the first time anyone runs this without their own
    eBay Developer account — it's a signal to go set one up, not a bug.
    """


@dataclass
class ListingRecord:
    """One normalized active-listing row.

    This is an *asking price*, not a sold price — eBay's official API
    surface has no free path to sold prices (see module docstring).
    Kept as its own type rather than reusing seasons_api's models
    since the domain (a marketplace listing) is genuinely different
    from a season date range.
    """
    item_id: str
    title: str
    price: Optional[float]
    currency: Optional[str]
    condition: Optional[str]
    item_web_url: str
    image_url: Optional[str]
    seller_username: Optional[str]
    seller_feedback_score: Optional[int]
    item_location_country: Optional[str]
    buying_options: list = field(default_factory=list)
    retrieved_at: Optional[str] = None


def _get_credentials() -> tuple[str, str]:
    client_id = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EbayCredentialsMissing(
            "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET not set. Register a free app at "
            "https://developer.ebay.com/my/keys (production keyset) and put the "
            "App ID / Cert ID in a .env file or your shell environment — this "
            "script deliberately does not create that account for you."
        )
    return client_id, client_secret


class EbayBrowseClient:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self._token: Optional[str] = None
        self._token_expires_at: float = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

    def _get_app_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token

        client_id, client_secret = _get_credentials()
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        resp = self.session.post(
            PRODUCTION_TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": DEFAULT_SCOPE},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        self._token = payload["access_token"]
        self._token_expires_at = time.time() + float(payload.get("expires_in", 7200))
        return self._token

    def search_active_listings(
        self,
        query: str,
        category_ids: Optional[str] = None,
        limit: int = 50,
        marketplace_id: str = "EBAY_US",
    ) -> list[ListingRecord]:
        """Search current active listings. NOT sold/completed items —
        see module docstring for why that distinction is unavoidable
        right now.
        """
        token = self._get_app_token()
        params = {"q": query, "limit": str(min(limit, 200))}
        if category_ids:
            params["category_ids"] = category_ids

        resp = self.session.get(
            PRODUCTION_BROWSE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": marketplace_id,
            },
            params=params,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return [normalize_item_summary(item) for item in resp.json().get("itemSummaries", [])]


def normalize_item_summary(item: dict) -> ListingRecord:
    """Map one Browse API `itemSummary` object to a ListingRecord.

    Field shape per eBay's published Browse API schema
    (developer.ebay.com/api-docs/buy/browse/types/gct:ItemSummary) —
    not derived from any scraped page.
    """
    price = item.get("price") or {}
    seller = item.get("seller") or {}
    image = item.get("image") or {}
    location = item.get("itemLocation") or {}

    raw_price = price.get("value")
    return ListingRecord(
        item_id=item.get("itemId", ""),
        title=item.get("title", ""),
        price=float(raw_price) if raw_price is not None else None,
        currency=price.get("currency"),
        condition=item.get("condition"),
        item_web_url=item.get("itemWebUrl", ""),
        image_url=image.get("imageUrl"),
        seller_username=seller.get("username"),
        seller_feedback_score=seller.get("feedbackScore"),
        item_location_country=location.get("country"),
        buying_options=item.get("buyingOptions", []),
    )
