"""Daily pipeline orchestrator.

Order per PRD 5.3: FX first, then each listing source in isolation (a failing
source is logged in the run log, never fatal), then reconcile into the store,
compute changes, and write everything. Digest sending is emailer/send_digest.py
(from M4).

Sources by milestone: M3 eBay + Bring a Trailer; M4 Cars & Bids + Hemmings;
M5 Goo-net + Yahoo/Buyee.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import fx, store as store_mod
from common.schema import DATA_DIR, validate
from listings import bat, carsandbids, ebay, hemmings

# (source_name, callable(fx_day) -> [listing records])
SOURCES: list[tuple] = [
    ("ebay", ebay.collect),
    ("bringatrailer", bat.collect),
    ("carsandbids", carsandbids.collect),
    ("hemmings", hemmings.collect),
]


def run(data_dir: Path = DATA_DIR, fx_fetch=fx.fetch_rates, sources=None) -> int:
    """Injectable for tests: fake FX, fake/crashing sources, temp data dir."""
    sources = SOURCES if sources is None else sources
    started_at = dt.datetime.now(dt.timezone.utc)
    today = started_at.date().isoformat()

    fx_day = fx_fetch()
    fx_log = fx.append_rates(data_dir / "fx-rates.json", fx_day)
    validate(fx_log, "fx-rates")

    source_results = []
    all_records: list[dict] = []
    seen_sources: set[str] = set()
    prev_log = {}
    prev_log_path = data_dir / "run-log.json"
    if prev_log_path.exists():
        prev_log = {
            s["source"]: s for s in json.loads(prev_log_path.read_text()).get("sources", [])
        }

    for name, collect in sources:
        prev_failures = prev_log.get(name, {}).get("consecutive_failures", 0)
        try:
            records = collect(fx_day)
            for rec in records:
                validate(rec | {"first_seen": today, "last_seen": today,
                                "history": [{"date": today, "status": rec["status"]}]},
                         "listing")
            source_results.append(
                {"source": name, "ok": True, "records": len(records), "note": "",
                 "consecutive_failures": 0}
            )
            seen_sources.add(name)
            all_records.extend(records)
        except Exception as exc:  # per-source isolation: never fail the run
            traceback.print_exc()
            source_results.append(
                {"source": name, "ok": False, "records": 0, "note": str(exc)[:200],
                 "consecutive_failures": prev_failures + 1}
            )

    listings_path = data_dir / "listings.json"
    if listings_path.exists():
        listing_store = json.loads(listings_path.read_text())
    else:
        listing_store = {"generated_at": today, "listings": []}

    listing_store, changes = store_mod.reconcile(listing_store, all_records, seen_sources, today)
    validate(changes, "changes")
    for listing in listing_store["listings"]:
        validate(listing, "listing")

    active = [l for l in listing_store["listings"] if l["status"] == "active"]
    gbp_prices = [l["price"]["gbp"] for l in active if l["price"]["gbp"] is not None]
    by_country: dict[str, int] = {}
    for l in active:
        by_country[l["country"]] = by_country.get(l["country"], 0) + 1
    run_log = {
        "date": today,
        "started_at": started_at.isoformat(timespec="seconds"),
        "sources": source_results,
        "totals": {
            "active": len(active),
            "by_country": by_country,
            "median_gbp": round(statistics.median(gbp_prices), 2) if gbp_prices else None,
        },
    }
    validate(run_log, "run-log")

    listings_path.write_text(json.dumps(listing_store, indent=2, ensure_ascii=False) + "\n")
    (data_dir / "changes-latest.json").write_text(json.dumps(changes, indent=2) + "\n")
    (data_dir / "run-log.json").write_text(json.dumps(run_log, indent=2) + "\n")

    ok = sum(1 for s in source_results if s["ok"])
    print(
        f"run complete: fx {fx_day['date']}, sources ok {ok}/{len(source_results)}, "
        f"active {len(active)}, new {len(changes['new'])}, "
        f"price changes {len(changes['price_changed'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
