"""Orchestrate a listings refresh.

FX once, then every collector (a blocked source or missing credentials is
skipped and flagged), normalise + score recall-first, merge into the store with
change detection, write data files and a snapshot, and hand the changes to the
notifier (dry-run unless Gmail credentials are set).

Run from the repo root:  python scrapers/run_listings.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import listings_store  # noqa: E402
from common.fx import fetch_rates  # noqa: E402
from common.listings_common import build_listing  # noqa: E402
from listings import bat, best_effort, ebay  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "emailer"))
import send_notification  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
# Core sources first (eBay, BaT), then best-effort sources that often block.
COLLECTORS = [
    ebay.collect, bat.collect,
    best_effort.cars_and_bids, best_effort.hemmings, best_effort.goonet, best_effort.yahoo_buyee,
]


def _load(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return fallback


def _compact(rec: dict) -> dict:
    return {k: rec.get(k) for k in ("id", "title", "source", "source_url", "price_gbp", "currency",
                                    "price_original", "country", "drive_side", "king_cab_score", "status")}


def main() -> int:
    today = date.today().isoformat()

    fx = fetch_rates()
    fx_log = [r for r in _load(DATA / "fx-rates.json", []) if r.get("date") != fx["date"]] + [fx]
    (DATA / "fx-rates.json").write_text(json.dumps(fx_log, indent=2) + "\n", encoding="utf-8")

    incoming, scraped, sources = [], set(), []
    for collect in COLLECTORS:
        res = collect()
        sources.append({"source": res.source, "ok": res.ok, "note": res.note, "records": len(res.records)})
        print(f"  [{'ok' if res.ok else 'SKIPPED'}] {res.source}: {len(res.records)} records {('- ' + res.note) if res.note else ''}")
        if res.ok:
            scraped.add(res.source)
            incoming.extend(build_listing(r, fx, today) for r in res.records)

    existing = _load(DATA / "listings.json", [])
    merged, changes = listings_store.merge(existing, incoming, scraped, today)

    (DATA / "listings.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DATA / "snapshots").mkdir(exist_ok=True)
    (DATA / "snapshots" / f"listings-{today}.json").write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    changes_out = {
        "generated_at": today,
        "new": [_compact(r) for r in changes["new"]],
        "price_changed": [{**_compact(c["listing"]), "old": c["old"], "new": c["new"]} for c in changes["price_changed"]],
        "status_changed": [{**_compact(c["listing"]), "old": c["old"], "new": c["new"]} for c in changes["status_changed"]],
        "withdrawn": [_compact(c["listing"]) for c in changes["withdrawn"]],
        "relisted": [{**_compact(c["listing"]), "relisted_from": c["relisted_from"]} for c in changes["relisted"]],
    }
    (DATA / "listings-changes.json").write_text(json.dumps(changes_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    active = sum(1 for r in merged if r.get("status") == "active")
    report = {
        "generated_at": today, "total": len(merged), "active": active,
        "by_country": _counts(merged, "country"), "sources": sources,
    }
    (DATA / "listings-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    n_changes = sum(len(changes_out[k]) for k in ("new", "price_changed", "status_changed", "withdrawn", "relisted"))
    print(f"\n{len(merged)} listings ({active} active); {n_changes} changes this run.")
    send_notification.notify(changes_out, report)
    return 0


def _counts(rows, key):
    out: dict[str, int] = {}
    for r in rows:
        if r.get("status") == "active":
            out[r.get(key) or "?"] = out.get(r.get(key) or "?", 0) + 1
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    raise SystemExit(main())
