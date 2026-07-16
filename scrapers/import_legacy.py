"""One-off: import the v1.0 build's collected listings into the new store.

Maps data/legacy/listings.json (old schema) into schema/listing.schema.json
records and merges them into data/listings.json, preserving first_seen dates
and price history. Idempotent: existing ids are left untouched. Run once at M3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import king_cab
from common.schema import DATA_DIR, validate

LEGACY = DATA_DIR / "legacy" / "listings.json"

_COUNTRIES = {"United States": "US", "United Kingdom": "GB", "Germany": "DE",
              "Australia": "AU", "Japan": "JP", "Canada": "CA"}


def _price(amount, currency, gbp, rate, date):
    return {"amount": amount, "currency": currency or "USD", "gbp": gbp,
            "fx_rate": rate, "fx_date": date}


def convert(old: dict) -> dict:
    source = old["source"]
    slug = old["id"].removeprefix(f"{source}-")
    country = _COUNTRIES.get(old.get("country") or "", "XX")
    fx_date = old.get("fx_date") or old["first_seen"]
    current = _price(old.get("price_original"), old.get("currency"),
                     old.get("price_gbp"), old.get("fx_rate_used"), fx_date)

    history = []
    for h in old.get("price_history", []):
        history.append({
            "date": h["date"],
            "status": "active",
            "price": _price(h.get("price_original"), old.get("currency"),
                            h.get("price_gbp"), old.get("fx_rate_used"), h["date"]),
        })
    if old.get("status") != "active":
        history.append({"date": old["last_seen"], "status": old["status"]})
    if not history:
        history = [{"date": old["first_seen"], "status": old["status"], "price": current}]

    return {
        "id": f"{source}:{slug}",
        "source": source,
        "source_listing_id": slug,
        "url": old["source_url"],
        "title": old["title"],
        "title_translated": None,
        "description_snippet": old.get("condition_notes"),
        "year": old.get("year"),
        "country": country,
        "region": old.get("region"),
        "drive_side": old.get("drive_side") or "unknown",
        "king_cab": king_cab.check(old["title"]),
        "price": current,
        "images": old.get("photo_urls") or [],
        "status": old["status"],
        "first_seen": old["first_seen"],
        "last_seen": old["last_seen"],
        "history": history,
        "relist": {"possible": False, "prior_id": None, "reasons": []},
    }


def main() -> int:
    legacy = json.loads(LEGACY.read_text())
    listings_path = DATA_DIR / "listings.json"
    store = (json.loads(listings_path.read_text()) if listings_path.exists()
             else {"generated_at": "2026-07-16", "listings": []})
    existing_ids = {l["id"] for l in store["listings"]}

    imported = 0
    for old in legacy:
        rec = convert(old)
        validate(rec, "listing")
        if rec["id"] in existing_ids:
            continue
        store["listings"].append(rec)
        imported += 1

    store["listings"].sort(key=lambda l: (l["first_seen"], l["id"]), reverse=True)
    listings_path.write_text(json.dumps(store, indent=2, ensure_ascii=False) + "\n")
    print(f"imported {imported} legacy listings ({len(legacy)} in legacy file)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
