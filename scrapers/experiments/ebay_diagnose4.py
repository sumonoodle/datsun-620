"""Diagnostic round 4: pin the vehicle category per marketplace, and count
the 620s the fix would recover.

Round 3 confirmed the US route works (category 6001 + a broad marque
query returns whole cars) but printed too much to read, and showed the
AU candidate id was wrong — it returned parts. This round is compact and
machine-readable: for every candidate category on every marketplace it
records how many returned items look like WHOLE VEHICLES rather than
parts, which is how a vehicle category identifies itself.

Vehicle-ness heuristic: a Motors vehicle title starts with a model year
and carries no "fits/for" parts phrasing. Good enough to tell a category
of cars from a category of door handles.

Writes data/research/ebay-categories.json for analysis and prints a short
summary. Scaffolding: delete once the collector is fixed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.patterns import RE_620, RE_OTHER_GEN
from listings.ebay_auth import mint_token

BROWSE = "https://api.ebay.com/buy/browse/v1/item_summary/search"
OUT = Path(__file__).resolve().parents[2] / "data" / "research" / "ebay-categories.json"

CANDIDATES = {
    "EBAY_US": ["6001", "6000", "174"],
    "EBAY_GB": ["9801", "31853", "131090", "9828"],
    "EBAY_DE": ["9801", "29690", "173", "16800"],
    "EBAY_AU": ["9801", "29690", "131090", "18320"],
}

_YEAR_LED = re.compile(r"^\s*(19|20)\d{2}\b")
_PARTS_PHRASE = re.compile(r"\bfits?\b|\bfor\b|kit\b|carburet|radiator|badge|"
                           r"decal|sticker|mirror|plug|seal|cable|lamp|light|"
                           r"carpet|mat\b|cover|handle|filter|pump|coil", re.I)


def looks_like_vehicle(title: str) -> bool:
    return bool(_YEAR_LED.search(title)) and not _PARTS_PHRASE.search(title)


def main() -> int:
    token = mint_token()
    findings: dict = {}
    with httpx.Client(timeout=40) as client:
        for marketplace, cats in CANDIDATES.items():
            findings[marketplace] = {}
            for cat in cats:
                try:
                    resp = client.get(
                        BROWSE,
                        params={"q": "datsun", "category_ids": cat, "limit": 100},
                        headers={"Authorization": f"Bearer {token}",
                                 "X-EBAY-C-MARKETPLACE-ID": marketplace})
                except Exception as exc:
                    findings[marketplace][cat] = {"error": str(exc)[:120]}
                    continue
                if resp.status_code != 200:
                    findings[marketplace][cat] = {"http": resp.status_code}
                    continue
                d = resp.json()
                items = d.get("itemSummaries") or []
                vehicles = [i for i in items if looks_like_vehicle(i.get("title", ""))]
                sixtwenties = [
                    {"title": i.get("title", ""),
                     "price": (i.get("price") or {}).get("value"),
                     "currency": (i.get("price") or {}).get("currency"),
                     "url": i.get("itemWebUrl", "")[:120]}
                    for i in vehicles
                    if RE_620.search(i.get("title", ""))
                    and not RE_OTHER_GEN.search(i.get("title", ""))
                ]
                findings[marketplace][cat] = {
                    "total": d.get("total", 0),
                    "fetched": len(items),
                    "vehicle_like": len(vehicles),
                    "sample_vehicles": [i.get("title", "")[:70] for i in vehicles[:5]],
                    "six_twenties": sixtwenties,
                }

        # For whichever category proved to be vehicles, also try the
        # descriptive queries a 620 might actually be titled with — Motors
        # titles are year+make+model and the model often reads "Pickup".
        for marketplace, cats in findings.items():
            best = max(cats.items(), key=lambda kv: kv[1].get("vehicle_like", 0),
                       default=(None, {}))
            cat_id, info = best
            if not cat_id or not info.get("vehicle_like"):
                continue
            extra = {}
            for q in ["datsun pickup", "datsun truck", "datsun 620"]:
                try:
                    resp = client.get(
                        BROWSE, params={"q": q, "category_ids": cat_id, "limit": 50},
                        headers={"Authorization": f"Bearer {token}",
                                 "X-EBAY-C-MARKETPLACE-ID": marketplace})
                    d = resp.json() if resp.status_code == 200 else {}
                except Exception:
                    d = {}
                items = d.get("itemSummaries") or []
                extra[q] = {
                    "total": d.get("total", 0),
                    "titles": [i.get("title", "")[:70] for i in items[:10]],
                }
            findings[marketplace]["_best_category"] = cat_id
            findings[marketplace]["_queries"] = extra

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(findings, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {OUT}")
    for mk, cats in findings.items():
        best = cats.get("_best_category")
        print(f"{mk}: best vehicle category = {best}")
        for cat, info in cats.items():
            if cat.startswith("_"):
                continue
            print(f"   cat {cat}: total={info.get('total')} "
                  f"vehicle_like={info.get('vehicle_like')} "
                  f"620s={len(info.get('six_twenties') or [])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
