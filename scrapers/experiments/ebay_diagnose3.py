"""Diagnostic round 3: confirm the fix and measure what it recovers.

Round 2 overturned round 1's conclusion. Asking the Browse API for the
Cars & Trucks category with q="datsun 620" returns total=0, but the same
category with q="datsun" returns 28 items led by "1978 Datsun 280Z 2
seater" — whole vehicles. Unscoped, the category holds 33,075 cars. So
vehicles are NOT hidden from us; the two-token query "datsun 620" simply
does not match eBay Motors vehicle titles, which are built from
year + make + model fields where the model often reads "Pickup" rather
than "620". The month of zeros is a QUERY shape problem, not a platform
wall, and our filters were innocent all along.

This round proves the fix before it is written: for every marketplace,
search the vehicle category with the broad marque term and print every
title returned, so we can see exactly which 620s we have been missing and
which category id each marketplace needs.

The legacy Finding API answered HTTP 418 and is ruled out for good.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.patterns import RE_620, RE_OTHER_GEN
from listings.ebay_auth import mint_token

BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"

# Vehicle-category candidates per marketplace. Each site numbers its own
# tree, so the run reports which ids actually answer rather than trusting
# the US number to carry over.
CANDIDATES = {
    "EBAY_US": ["6001", "6000"],
    "EBAY_GB": ["9801", "31853", "131090"],
    "EBAY_DE": ["9801", "29690", "173"],
    "EBAY_AU": ["29690", "9801", "131090"],
}
QUERIES = ["datsun", "datsun pickup", "datsun truck"]


def search(client, token, marketplace, **params):
    resp = client.get(
        BROWSE, params=params,
        headers={"Authorization": f"Bearer {token}",
                 "X-EBAY-C-MARKETPLACE-ID": marketplace})
    if resp.status_code != 200:
        return None, f"HTTP {resp.status_code}"
    return resp.json(), None


def main() -> int:
    token = mint_token()
    with httpx.Client(timeout=40) as client:
        for marketplace, cats in CANDIDATES.items():
            print(f"\n{'=' * 70}\n{marketplace}\n{'=' * 70}")
            for cat in cats:
                payload, err = search(client, token, marketplace,
                                      q="datsun", category_ids=cat, limit=100)
                if err:
                    print(f"  cat {cat}: {err}")
                    continue
                total = payload.get("total", 0)
                items = payload.get("itemSummaries") or []
                print(f"  cat {cat} q='datsun': total={total} fetched={len(items)}")
                if not items:
                    continue
                for it in items:
                    title = it.get("title", "")
                    price = (it.get("price") or {}).get("value", "?")
                    cur = (it.get("price") or {}).get("currency", "")
                    is620 = bool(RE_620.search(title))
                    othergen = bool(RE_OTHER_GEN.search(title))
                    mark = "*** 620 ***" if (is620 and not othergen) else "           "
                    print(f"    {mark} {price:>9} {cur} | {title[:66]}")

            # A 620 vehicle may be titled without the model code at all
            # ("1978 Datsun Pickup"), so also try the descriptive terms.
            best_cat = cats[0]
            for q in QUERIES[1:]:
                payload, err = search(client, token, marketplace,
                                      q=q, category_ids=best_cat, limit=50)
                if err or not payload:
                    continue
                items = payload.get("itemSummaries") or []
                if items:
                    print(f"  cat {best_cat} q={q!r}: total={payload.get('total', 0)}")
                    for it in items[:15]:
                        title = it.get("title", "")
                        price = (it.get("price") or {}).get("value", "?")
                        print(f"      {price:>9} | {title[:66]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
