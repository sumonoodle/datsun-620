"""Diagnostic round 2: is there ANY eBay API route to whole vehicles?

Round 1 was decisive about the cause: across 4 marketplaces x 3 queries
(~1,800 items) the Browse API returned parts, toys, posters and manuals —
and not one whole vehicle. Asking it for the Cars & Trucks category
directly returned total=0 on every marketplace, while Parts & Accessories
returns thousands. The filters never saw a truck to reject.

That leaves one question before choosing a fix: does another eBay surface
expose Motors vehicles to us?

  A. Browse, category-only (no keyword) — proves whether the vehicle
     category is empty-to-us in general or just for this query.
  B. Browse with the documented filter syntax variants, in case
     category_ids was simply the wrong knob.
  C. The legacy Finding API (findItemsAdvanced), which historically did
     carry Motors vehicles. eBay has been sunsetting it, so this also
     records whether it still answers at all.

Prints statuses and counts only. Scaffolding: delete after the decision.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings.ebay_auth import mint_token

BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
FINDING = "https://svcs.ebay.com/services/search/FindingService/v1"

# US Motors vehicle roots: 6001 = Cars & Trucks, 6000 = eBay Motors root,
# 174 = "Other Vehicles & Trailers". 220 is Toys (control: should return
# items, proving a category_ids query works at all).
US_CATEGORIES = ["6001", "6000", "174", "220"]


def browse(client, token, marketplace, **params):
    resp = client.get(
        BROWSE, params=params,
        headers={"Authorization": f"Bearer {token}",
                 "X-EBAY-C-MARKETPLACE-ID": marketplace})
    if resp.status_code != 200:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    d = resp.json()
    items = d.get("itemSummaries") or []
    sample = items[0].get("title", "")[:58] if items else ""
    warn = [w.get("message", "")[:90] for w in (d.get("warnings") or [])][:2]
    return f"total={d.get('total', 0)} fetched={len(items)} | {sample} | warnings={warn}"


def main() -> int:
    token = mint_token()
    with httpx.Client(timeout=40) as client:
        print("=== A. Browse: category only, no keyword (EBAY_US) ===")
        for cat in US_CATEGORIES:
            print(f"  category_ids={cat}: {browse(client, token, 'EBAY_US', category_ids=cat, limit=5)}")

        print("\n=== B. Browse: filter-syntax variants for the vehicle category ===")
        variants = [
            ("q + category_ids=6001", {"q": "datsun", "category_ids": "6001", "limit": 5}),
            ("q + filter categoryIds", {"q": "datsun", "filter": "categoryIds:{6001}", "limit": 5}),
            ("category_ids=6001 + sort newly", {"category_ids": "6001", "sort": "newlyListed", "limit": 5}),
            ("q=datsun truck, no category", {"q": "datsun truck", "limit": 5}),
        ]
        for label, params in variants:
            print(f"  {label}: {browse(client, token, 'EBAY_US', **params)}")

        print("\n=== C. Legacy Finding API (findItemsAdvanced, Motors 6001) ===")
        app_id = os.environ.get("EBAY_CLIENT_ID", "")
        try:
            resp = client.get(FINDING, params={
                "OPERATION-NAME": "findItemsAdvanced",
                "SERVICE-VERSION": "1.0.0",
                "SECURITY-APPNAME": app_id,
                "RESPONSE-DATA-FORMAT": "JSON",
                "REST-PAYLOAD": "true",
                "keywords": "datsun 620",
                "categoryId": "6001",
                "GLOBAL-ID": "EBAY-MOTOR",
                "paginationInput.entriesPerPage": "10",
            })
            print(f"  HTTP {resp.status_code}")
            body = resp.text
            print(f"  body[:400]: {body[:400]}")
        except Exception as exc:
            print(f"  {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
