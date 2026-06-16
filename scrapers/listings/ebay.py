"""Collector: eBay Browse API (the current API; Finding was retired Feb 2025).

Recall-first: searches "Datsun 620" across the US/UK/DE/AU marketplaces and keeps
everything, letting the King Cab scorer rank results. Authenticates with the
OAuth client-credentials flow using EBAY_CLIENT_ID / EBAY_CLIENT_SECRET.

If credentials are absent (e.g. eBay developer approval still pending), the
collector skips cleanly and flags it, rather than failing the run.

NOTE: not yet verified against live data. Whether the Browse API returns vintage
Motors/vehicle listings the way we need is the open risk to confirm once
production credentials are in hand.
"""

from __future__ import annotations

import base64
import os

import httpx

from common.listings_common import ListingResult

SOURCE = "ebay"
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
MARKETPLACES = ["EBAY_US", "EBAY_GB", "EBAY_DE", "EBAY_AU"]
QUERY = "Datsun 620"


def _token(client_id: str, client_secret: str) -> str:
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    r = httpx.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def collect() -> ListingResult:
    client_id = os.environ.get("EBAY_CLIENT_ID")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET")
    if not client_id or not client_secret:
        return ListingResult(SOURCE, ok=False, note="no credentials set (awaiting eBay developer approval)")

    try:
        token = _token(client_id, client_secret)
        records = []
        for marketplace in MARKETPLACES:
            r = httpx.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": marketplace},
                params={"q": QUERY, "limit": 100},
                timeout=30,
            )
            r.raise_for_status()
            for it in r.json().get("itemSummaries", []) or []:
                price = it.get("price", {})
                loc = it.get("itemLocation", {})
                records.append({
                    "source": SOURCE,
                    "source_url": it.get("itemWebUrl", ""),
                    "title": it.get("title", ""),
                    "price_original": float(price["value"]) if price.get("value") else None,
                    "currency": price.get("currency"),
                    "country_code": loc.get("country"),
                    "photo_urls": [it["image"]["imageUrl"]] if it.get("image", {}).get("imageUrl") else [],
                    "status": "active",
                })
    except Exception as e:  # noqa: BLE001
        return ListingResult(SOURCE, ok=False, note=f"eBay API error: {e}")

    return ListingResult(SOURCE, ok=True, records=records)
