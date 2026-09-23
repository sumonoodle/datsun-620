"""Daily pipeline orchestrator.

Order per PRD 5.3: FX first, then each listing source in isolation (a failing
source is logged in the run log, never fatal), then reconcile into the store,
compute changes, and write everything. Digest sending is emailer/send_digest.py
(from M4).

Sources by milestone: M3 eBay + Bring a Trailer; M4 Cars & Bids + Hemmings;
M5 Goo-net + Yahoo/Buyee (both IP-blocked, retired); Asia expansion
2026-07-17: Goo-net Exchange, Carsensor, Yahoo Auctions direct (supersedes
Buyee) and Kaidee, per docs/asia-sources.md.

Two trucks, one pipeline: `python run_daily.py` runs the Datsun 620 into
data/; `python run_daily.py --model hilux` runs the 3rd-generation petrol
Hilux (listings_hilux/) into data/hilux/. Both share data/fx-rates.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import fx, store as store_mod, translate
from common.schema import DATA_DIR, validate
from listings import (barnfinds, bat, carsandbids, carsensor, classiccars,
                      ebay, everycar, flex, goonet_exchange, hemmings, kaidee,
                      kijiji, kleinanzeigen, kuruma_ex, pistonheads, ratsun,
                      retrorides, trovit, truck2hand, yahoo_auctions)

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
    ("truck2hand", truck2hand.collect),
    ("classiccars", classiccars.collect),
    ("kijiji", kijiji.collect),
    ("barnfinds", barnfinds.collect),
    ("flex", flex.collect),
    ("kuruma_ex", kuruma_ex.collect),
    ("everycar", everycar.collect),
    ("pistonheads", pistonheads.collect),
    ("ratsun", ratsun.collect),
    ("retrorides", retrorides.collect),
    ("trovit", trovit.collect),
    ("kleinanzeigen", kleinanzeigen.collect),
]

# Sources that are blocked by design rather than broken by accident, and
# whose real route is the Phase C email alerts the owner is setting up.
#
# 2026-09-20 probing established these are IP-level bans on datacentre
# ranges, not path rules or bugs: Cars & Bids 403s its own HOMEPAGE, and
# Hemmings challenges every dynamic page while serving only static files.
# Both robots.txt files ALLOW the paths we ask for, so there is nothing to
# fix and nothing to wait for — their block will not lift because we tried
# again. See docs/sources-deep-dive.md.
#
# Owner decision 2026-09-23: keep running them, so a lifted block is still
# noticed, but stop them reading as a fresh failure every morning. They are
# reported separately and excluded from the "sources ok" headline, which
# otherwise understated a healthy run by two every single day.
EXPECTED_BLOCKED = {"carsandbids", "hemmings"}


def run(data_dir: Path = DATA_DIR, fx_fetch=fx.fetch_rates, sources=None,
        fx_path: Path | None = None) -> int:
    """Injectable for tests: fake FX, fake/crashing sources, temp data dir.
    `fx_path` defaults to the data dir's own log; the Hilux run points it at
    the shared data/fx-rates.json."""
    sources = SOURCES if sources is None else sources
    data_dir.mkdir(parents=True, exist_ok=True)
    started_at = dt.datetime.now(dt.timezone.utc)
    today = started_at.date().isoformat()

    # FX must not be a single point of failure: on any fetch/parse problem,
    # fall back to the most recent cached rates (each listing stores the rate
    # it was converted at, so a stale day is accurate, just dated).
    fx_path = fx_path or data_dir / "fx-rates.json"
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
        # A source can be perfectly "ok" and still be broken: eBay reported
        # ok/0 records every day for a MONTH while an unscoped query drowned
        # in parts (2026-09-14). Nothing counted that, so nothing noticed.
        # A run that fails does not add to the quiet streak — it is already
        # flagged as failing, and everycar's five failing days should not
        # have also read as five quiet ones.
        prev_zero = prev_log.get(name, {}).get("consecutive_zero_runs", 0)
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
                 "consecutive_failures": 0,
                 "consecutive_zero_runs": prev_zero + 1 if not valid else 0}
            )
            # Every source that completes without raising drives withdrawal
            # ageing, records or not: collectors raise on suspicious-empty
            # pages themselves, and requiring >=1 record meant a source's
            # LAST listing could never be withdrawn (2026-08-22 bug hunt).
            seen_sources.add(name)
            all_records.extend(valid)
        except Exception as exc:  # per-source isolation: never fail the run
            traceback.print_exc()
            source_results.append(
                {"source": name, "ok": False, "records": 0, "note": str(exc)[:200],
                 "consecutive_failures": prev_failures + 1,
                 "consecutive_zero_runs": prev_zero,
                 "expected_blocked": name in EXPECTED_BLOCKED}
            )

    # kuruma-ex aggregates the Carsensor feed with a 'cc'-prefixed copy of
    # the same id, so the same physical truck arrived twice with clashing
    # prices (2026-08-22 bug hunt: ccAU6253091581 at ¥0 next to
    # AU6253091581 at ¥3.5M). Carsensor is the primary; its twin wins.
    carsensor_ids = {r["source_listing_id"] for r in all_records if r["source"] == "carsensor"}
    listings_path = data_dir / "listings.json"
    if listings_path.exists():
        listing_store = json.loads(listings_path.read_text())
    else:
        listing_store = {"generated_at": today, "listings": []}
    stored_carsensor = {l["source_listing_id"] for l in listing_store["listings"]
                        if l["source"] == "carsensor" and l["status"] == "active"}
    before = len(all_records)
    all_records = [
        r for r in all_records
        if not (r["source"] == "kuruma_ex"
                and r["source_listing_id"].startswith("cc")
                and r["source_listing_id"][2:] in (carsensor_ids | stored_carsensor))
    ]
    if len(all_records) != before:
        print(f"dedupe: dropped {before - len(all_records)} kuruma_ex twin(s) of carsensor listings")

    # Translation pass: best-effort, per PRD never fatal and never blocking.
    for rec in all_records:
        if rec.get("title_translated") is None and translate.needs_translation(rec["title"]):
            rec["title_translated"] = translate.translate(rec["title"])

    listing_store, changes = store_mod.reconcile(listing_store, all_records, seen_sources, today)
    validate(changes, "changes")
    for listing in listing_store["listings"]:
        validate(listing, "listing")

    active = [l for l in listing_store["listings"] if l["status"] == "active"]
    # > 0, not just non-None: a zero price is always a parse artefact and a
    # single one halved the published median for days (2026-08-22 bug hunt).
    gbp_prices = [l["price"]["gbp"] for l in active if l["price"]["gbp"]]
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

    # Titles of new catches go to stdout so the Actions log answers "what
    # did it find?" without opening the data files (the branch live-test
    # workflow never commits them).
    by_id = {l["id"]: l for l in listing_store["listings"]}
    for new_id in changes["new"]:
        l = by_id.get(new_id)
        if l:
            print(f"new: {new_id} | {l['title'][:90]} | "
                  f"{l['price']['amount']} {l['price']['currency']} | {l['url']}")

    # The headline counts only sources that COULD have worked. Two permanent
    # IP bans made every healthy run read as 18/20 and buried the days when
    # something was genuinely wrong.
    reachable = [s for s in source_results if not s.get("expected_blocked")]
    ok = sum(1 for s in reachable if s["ok"])
    blocked = len(source_results) - len(reachable)
    blocked_note = f", {blocked} known blocked" if blocked else ""
    print(
        f"run complete: fx {fx_day['date']}, sources ok {ok}/{len(reachable)}"
        f"{blocked_note}, active {len(active)}, new {len(changes['new'])}, "
        f"price changes {len(changes['price_changed'])}"
    )
    return 0


def run_hilux() -> int:
    """The Hilux run. It follows the Datsun run in the same workflow, so the
    day's rates are normally already in the shared log; fetching again is
    harmless (append_rates dedupes by date) and covers a standalone run."""
    from listings_hilux import SOURCES as HILUX_SOURCES
    return run(DATA_DIR / "hilux", sources=HILUX_SOURCES, fx_path=DATA_DIR / "fx-rates.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=["datsun", "hilux"], default="datsun")
    args = parser.parse_args()
    raise SystemExit(run_hilux() if args.model == "hilux" else run())
