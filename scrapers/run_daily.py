"""Daily pipeline orchestrator.

Order per PRD 5.3: FX first, then each listing source in isolation (a failing
source is logged in the run log, never fatal), then normalise/dedupe, compute
changes, write data, and leave digest sending to emailer/send_digest.py.

M1 state: FX is real; the source registry is empty. Sources are added per
milestone (M3: eBay, Bring a Trailer; M4: Cars & Bids, Hemmings; M5: Japan).
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import fx
from common.schema import DATA_DIR, validate

# Each entry: (source_name, callable) where the callable takes the FX day entry
# and returns a list of listing dicts per schema/listing.schema.json.
SOURCES: list[tuple[str, object]] = []


def run() -> int:
    started_at = dt.datetime.now(dt.timezone.utc)
    today = started_at.date().isoformat()

    fx_day = fx.fetch_rates()
    fx_log = fx.append_rates(DATA_DIR / "fx-rates.json", fx_day)
    validate(fx_log, "fx-rates")

    source_results = []
    all_records: list[dict] = []
    for name, collect in SOURCES:
        try:
            records = collect(fx_day)
            source_results.append(
                {"source": name, "ok": True, "records": len(records), "note": ""}
            )
            all_records.extend(records)
        except Exception as exc:  # per-source isolation: never fail the run
            traceback.print_exc()
            source_results.append(
                {"source": name, "ok": False, "records": 0, "note": str(exc)[:200]}
            )

    listings_path = DATA_DIR / "listings.json"
    if listings_path.exists():
        store = json.loads(listings_path.read_text())
    else:
        store = {"generated_at": today, "listings": []}

    # M1: no sources, so no reconciliation yet. M3 adds dedupe against the
    # store, change detection, and the relist heuristic here.
    changes = {
        "date": today,
        "new": [],
        "price_changed": [],
        "status_changed": [],
        "possible_relists": [],
    }
    validate(changes, "changes")

    active = [l for l in store["listings"] if l["status"] == "active"]
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

    store["generated_at"] = today
    listings_path.write_text(json.dumps(store, indent=2) + "\n")
    (DATA_DIR / "changes-latest.json").write_text(json.dumps(changes, indent=2) + "\n")
    (DATA_DIR / "run-log.json").write_text(json.dumps(run_log, indent=2) + "\n")

    ok = sum(1 for s in source_results if s["ok"])
    print(f"run complete: fx {fx_day['date']}, sources ok {ok}/{len(source_results)}, active {len(active)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
