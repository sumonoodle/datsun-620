"""Reconcile collector output into the listing store and compute daily changes.

The store is data/listings.json: current state plus per-listing history.
Collectors return partial records (everything except first_seen / last_seen /
history / relist); this module fills those in, detects price and status
changes, and ages out listings that stop appearing.
"""

from __future__ import annotations

import datetime as dt

from . import relist as relist_mod

# An active listing missing from its source's results for this many days is
# considered withdrawn (auction sites report sold explicitly; classifieds just
# remove the page).
MISSING_DAYS_TO_WITHDRAWN = 3


def _history_entry(date: str, status: str, price: dict | None) -> dict:
    entry = {"date": date, "status": status}
    if price is not None:
        entry["price"] = price
    return entry


def reconcile(store: dict, incoming: list[dict], seen_sources: set[str], today: str) -> tuple[dict, dict]:
    """Merge incoming records into the store. Returns (store, changes).

    `seen_sources` are sources that reported successfully AND returned at
    least one record this run; only their listings age toward withdrawal.
    Failed, skipped, and zero-record sources are left untouched, so neither
    an outage nor a silently broken parser can mass-withdraw an inventory.
    """
    changes = {
        "date": today,
        "new": [],
        "price_changed": [],
        "status_changed": [],
        "possible_relists": [],
    }
    by_id = {l["id"]: l for l in store.get("listings", [])}
    incoming_ids = set()

    for rec in incoming:
        incoming_ids.add(rec["id"])
        existing = by_id.get(rec["id"])
        if existing is None:
            rec["first_seen"] = today
            rec["last_seen"] = today
            rec["history"] = [_history_entry(today, rec["status"], rec["price"])]
            rec["relist"] = relist_mod.detect(rec, list(by_id.values()))
            if rec["relist"]["possible"]:
                changes["possible_relists"].append(
                    {"id": rec["id"], "prior_id": rec["relist"]["prior_id"],
                     "reasons": rec["relist"]["reasons"]}
                )
            by_id[rec["id"]] = rec
            changes["new"].append(rec["id"])
            continue

        existing["last_seen"] = today
        old_price, new_price = existing["price"], rec["price"]
        old_status, new_status = existing["status"], rec["status"]
        price_moved = (
            old_price["amount"] != new_price["amount"]
            and not (old_price["amount"] is None and new_price["amount"] is None)
        )
        status_moved = old_status != new_status

        # Refresh volatile fields from the source. Translation may arrive on a
        # later run than the listing (e.g. DeepL key added afterwards).
        existing["title"] = rec["title"]
        if rec.get("title_translated"):
            existing["title_translated"] = rec["title_translated"]
        existing["images"] = rec["images"] or existing["images"]
        existing["price"] = new_price
        existing["status"] = new_status

        if price_moved:
            pct = None
            if old_price["gbp"] and new_price["gbp"]:
                pct = round((new_price["gbp"] - old_price["gbp"]) / old_price["gbp"] * 100, 1)
            changes["price_changed"].append(
                {"id": rec["id"], "old_gbp": old_price["gbp"], "new_gbp": new_price["gbp"], "pct": pct}
            )
        if status_moved:
            changes["status_changed"].append(
                {"id": rec["id"], "old_status": old_status, "new_status": new_status}
            )
        if price_moved or status_moved:
            existing["history"].append(_history_entry(today, new_status, new_price))

    # Age out actives that vanished from a healthy source.
    today_d = dt.date.fromisoformat(today)
    for listing in by_id.values():
        if listing["id"] in incoming_ids or listing["status"] != "active":
            continue
        if listing["source"] not in seen_sources:
            continue
        missing_days = (today_d - dt.date.fromisoformat(listing["last_seen"])).days
        if missing_days >= MISSING_DAYS_TO_WITHDRAWN:
            changes["status_changed"].append(
                {"id": listing["id"], "old_status": "active", "new_status": "withdrawn"}
            )
            listing["status"] = "withdrawn"
            listing["history"].append(_history_entry(today, "withdrawn", None))

    store["listings"] = sorted(by_id.values(), key=lambda l: (l["first_seen"], l["id"]), reverse=True)
    store["generated_at"] = today
    return store, changes
