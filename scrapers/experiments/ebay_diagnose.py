"""Diagnostic: why has the eBay collector returned ZERO records every day
for over a month?

eBay Motors is plausibly the largest single source of 620s in the world and
the collector has never contributed a listing. A rare truck explains a quiet
week, not a silent month, so this answers three questions with live data:

  1. RECALL — do whole vehicles even appear in the 200-item window our
     queries fetch? The self-test shows ~9,300 hits for "datsun 620" on
     EBAY_US, and if the first 200 by Best Match are all parts, no filter
     change can help: the trucks were never in the payload.
  2. FILTERS — for items that DO look like 620 vehicles, which stage drops
     them (620 regex, parts words, ad regex, category gate, price floor)?
  3. FIX — does restricting the search to the Cars & Trucks category
     (category_ids) surface whole vehicles that the broad query buries?

Prints only counts, titles, categories and prices — never the token.
Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import collections
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.patterns import RE_620
from listings import ebay
from listings.ebay_auth import mint_token

SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
# eBay Motors "Cars & Trucks" (US 6001). Other marketplaces use their own
# vehicle roots; the diagnostic reports what each actually returns rather
# than assuming the id carries over.
CATEGORY_TRIALS = {
    "EBAY_US": "6001",
    "EBAY_GB": "9801",
    "EBAY_DE": "9801",
    "EBAY_AU": "29690",
}


def _search(client, token, marketplace, query, category=None, limit=200):
    params = {"q": query, "limit": limit}
    if category:
        params["category_ids"] = category
    resp = client.get(
        SEARCH_URL,
        params=params,
        headers={"Authorization": f"Bearer {token}",
                 "X-EBAY-C-MARKETPLACE-ID": marketplace},
    )
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}: {resp.text[:160]}"
    return resp.json(), None


def _why_rejected(item):
    """Replay the collector's gates in order and name the first that fires."""
    title = item.get("title", "")
    cats = [c.get("categoryName", "") for c in item.get("categories", [])]
    if not RE_620.search(title):
        return "no-620-in-title"
    if ebay._PARTS_RE.search(title.lower()):
        hit = ebay._PARTS_RE.search(title.lower())
        return f"parts-word:{hit.group(0)!r}"
    if ebay._AD_RE.search(title.lower()):
        return "ad-regex"
    names = [c.strip().lower() for c in cats if c]
    if not any(n in ebay._VEHICLE_CATEGORY_NAMES for n in names):
        if any(ebay._NON_VEHICLE_CAT_RE.search(n) for n in names):
            return f"category-denied:{names}"
    price = item.get("price") or {}
    buying = item.get("buyingOptions") or []
    try:
        amount = float(price.get("value")) if price.get("value") else None
    except (TypeError, ValueError):
        amount = None
    if "FIXED_PRICE" in buying and "AUCTION" not in buying \
            and amount is not None and amount < 500:
        return f"price-floor:{amount}"
    return "PASSES"


def main() -> int:
    token = mint_token()
    with httpx.Client(timeout=40) as client:
        for marketplace, _country in ebay.MARKETPLACES:
            print(f"\n{'=' * 72}\n{marketplace}\n{'=' * 72}")

            for query in ebay.QUERIES:
                payload, err = _search(client, token, marketplace, query)
                if err:
                    print(f"  query {query!r}: {err}")
                    continue
                items = payload.get("itemSummaries") or []
                total = payload.get("total", 0)
                with_620 = [i for i in items if RE_620.search(i.get("title", ""))]
                print(f"\n  query {query!r}: total={total} fetched={len(items)} "
                      f"titles-with-620={len(with_620)}")

                cats = collections.Counter(
                    c.get("categoryName", "?")
                    for i in items for c in (i.get("categories") or []))
                print(f"    top categories: {cats.most_common(6)}")

                reasons = collections.Counter(_why_rejected(i) for i in items)
                print(f"    gate outcomes: {dict(reasons.most_common(8))}")

                for i in with_620[:5]:
                    verdict = _why_rejected(i)
                    price = (i.get("price") or {}).get("value", "?")
                    cat = [c.get("categoryName") for c in (i.get("categories") or [])]
                    print(f"      [{verdict}] {price} | {i.get('title','')[:62]} | {cat}")

            # The hypothesis: vehicles exist but sit outside the window a
            # parts-dominated keyword search returns.
            cat_id = CATEGORY_TRIALS.get(marketplace)
            if cat_id:
                payload, err = _search(client, token, marketplace,
                                       "datsun 620", category=cat_id, limit=50)
                if err:
                    print(f"\n  CATEGORY {cat_id} 'datsun 620': {err}")
                else:
                    items = payload.get("itemSummaries") or []
                    print(f"\n  CATEGORY {cat_id} 'datsun 620': total="
                          f"{payload.get('total', 0)} fetched={len(items)}")
                    for i in items[:12]:
                        verdict = _why_rejected(i)
                        price = (i.get("price") or {}).get("value", "?")
                        cat = [c.get("categoryName") for c in (i.get("categories") or [])]
                        print(f"      [{verdict}] {price} | {i.get('title','')[:62]} | {cat}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
