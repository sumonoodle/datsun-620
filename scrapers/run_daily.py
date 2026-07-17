"""Daily pipeline orchestrator.

Order per PRD 5.3: FX first, then each listing source in isolation (a failing
source is logged in the run log, never fatal), then reconcile into the store,
compute changes, and write everything. Digest sending is emailer/send_digest.py
(from M4).

Sources by milestone: M3 eBay + Bring a Trailer; M4 Cars & Bids + Hemmings;
M5 Goo-net + Yahoo/Buyee (both IP-blocked, retired); Asia expansion
2026-07-17: Goo-net Exchange, Carsensor, Yahoo Auctions direct (supersedes
Buyee) and Kaidee, per docs/asia-sources.md.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import fx, store as store_mod, translate
from common.schema import DATA_DIR, validate
from listings import (bat, carsandbids, carsensor, ebay, goonet_exchange,
                      hemmings, kaidee, yahoo_auctions)

# (source_name, callable(fx_day) -> [listing records])
SOURCES: list[tuple] = [
    ("ebay", ebay.collect),
    ("bringatrailer", bat.collect),
    ("carsandbids", carsandbids.collect),
    ("hemmings", hemmings.collect),
    ("goonet_exchange", goonet_exchange.collect),
    ("carsensor", carsensor.collect),
    ("yahoo_auctions", yahoo_auctions.collect),
    ("kaidee", kaidee.collect),
]


def run(data_dir: Path = DATA_DIR, fx_fetch=fx.fetch_rates, sources=None) -> int:
    """Injectable for tests: fake FX, fake/crashing sources, temp data dir."""
    sources = SOURCES if sources is None else sources
    started_at = dt.datetime.now(dt.timezone.utc)
    today = started_at.date().isoformat()

    # FX must not be a single point of failure: on any fetch/parse problem,
    # fall back to the most recent cached rates (each listing stores the rate
    # it was converted at, so a stale day is accurate, just dated).
    fx_path = data_dir / "fx-rates.json"
    try:
        fx_day = fx_fetch()
        fx_log = fx.append_rates(fx_path, fx_day)
        validate(fx_log, "fx-rates")
    except Exception:
        traceback.print_exc()
        if not fx_path.exists():
            raise  # first ever run: no cache to fall back to
        fx_day = json.loads(fx_path.read_text())["latest"]
        print(f"fx: fetch failed, using cached rates from {fx_day['date']}")

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
            # One malformed record must not discard the source's good ones.
            valid = []
            for rec in records:
                try:
                    validate(rec | {"first_seen": today, "last_seen": today,
                                    "history": [{"date": today, "status": rec["status"]}]},
                             "listing")
                    valid.append(rec)
                except Exception:
                    traceback.print_exc()
                    print(f"{name}: dropped one schema-invalid record")
            dropped = len(records) - len(valid)
            source_results.append(
                {"source": name, "ok": True, "records": len(valid),
                 "note": f"{dropped} invalid record(s) dropped" if dropped else "",
                 "consecutive_failures": 0}
            )
            # Only sources that actually returned records drive withdrawal
            # ageing: an empty-but-"successful" scrape is more likely a silent
            # parser break than a genuinely emptied market.
            if valid:
                seen_sources.add(name)
            all_records.extend(valid)
        except Exception as exc:  # per-source isolation: never fail the run
            traceback.print_exc()
            source_results.append(
                {"source": name, "ok": False, "records": 0, "note": str(exc)[:200],
                 "consecutive_failures": prev_failures + 1}
            )

    # Translation pass: best-effort, per PRD never fatal and never blocking.
    for rec in all_records:
        if rec.get("title_translated") is None and translate.needs_translation(rec["title"]):
            rec["title_translated"] = translate.translate(rec["title"])

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
