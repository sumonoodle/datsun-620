"""Reconcile collector output into the listing store and compute daily changes.

The store is data/listings.json: current state plus per-listing history.
Collectors return partial records (everything except first_seen / last_seen /
history / relist); this module fills those in, detects price and status
changes, and ages out listings that stop appearing.
"""

from __future__ import annotations

from . import relist as relist_mod

# An active listing missing from its source's HEALTHY results for this many
# consecutive healthy runs is considered withdrawn (auction sites report sold
# explicitly; classifieds just remove the page). 2026-08-22 bug hunt: this
# used to be a CALENDAR-day gap measured from last_seen, so outage days
# counted toward withdrawal and the first scrape after a three-day outage
# instantly mass-withdrew everything not on that day's page. Now each
# healthy-but-absent run increments a per-listing counter that a sighting
# resets, so only genuine absences age a listing.
MISSED_RUNS_TO_WITHDRAWN = 3


def _history_entry(date: str, status: str, price: dict | None) -> dict:
    entry = {"date": date, "status": status}
    if price is not None:
        entry["price"] = price
    return entry


def reconcile(store: dict, incoming: list[dict], seen_sources: set[str], today: str) -> tuple[dict, dict]:
    """Merge incoming records into the store. Returns (store, changes).

    `seen_sources` are sources whose collector completed without raising this
    run; only their listings age toward withdrawal. Failed and skipped
    sources are left untouched, so an outage can never mass-withdraw an
    inventory (collectors guard their own "empty page that shouldn't be"
    cases by raising).
    """
    changes = {
        "date": today,
        "new": [],
        "price_changed": [],
        "status_changed": [],
        "possible_relists": [],
    }
    by_id = {l["id"]: l for l in store.get("listings", [])}
    # Relist candidates are listings that existed BEFORE this run: two
    # records first seen together must not pair with each other (2026-08-22
    # bug: same-day sold auctions were flagged as relists of one another).
    prior_listings = list(by_id.values())
    incoming_ids = set()

    for rec in incoming:
        incoming_ids.add(rec["id"])
        existing = by_id.get(rec["id"])
        if existing is None:
            rec["first_seen"] = today
            rec["last_seen"] = today
            rec["history"] = [_history_entry(today, rec["status"], rec["price"])]
            rec["relist"] = relist_mod.detect(rec, prior_listings)
            if rec["relist"]["possible"]:
                changes["possible_relists"].append(
                    {"id": rec["id"], "prior_id": rec["relist"]["prior_id"],
                     "reasons": rec["relist"]["reasons"]}
                )
            by_id[rec["id"]] = rec
            changes["new"].append(rec["id"])
            continue

        existing["last_seen"] = today
        existing.pop("missed_runs", None)  # sighted: absence streak over
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
        # Schema contract: gbp/fx_rate are captured at conversion time and
        # never recomputed. Only replace the price block when the price
        # itself (or its currency) actually changed — otherwise the stored
        # conversion silently drifted with every day's FX (2026-08-22 bug).
        if price_moved or old_price["currency"] != new_price["currency"]:
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

    # Age out actives that vanished from a healthy source: one missed-run
    # tick per healthy run in which the listing was absent.
    for listing in by_id.values():
        if listing["id"] in incoming_ids or listing["status"] != "active":
            continue
        if listing["source"] not in seen_sources:
            continue
        missed = listing.get("missed_runs", 0) + 1
        if missed >= MISSED_RUNS_TO_WITHDRAWN:
            listing.pop("missed_runs", None)
            changes["status_changed"].append(
                {"id": listing["id"], "old_status": "active", "new_status": "withdrawn"}
            )
            listing["status"] = "withdrawn"
            listing["history"].append(_history_entry(today, "withdrawn", None))
        else:
            listing["missed_runs"] = missed

    store["listings"] = sorted(by_id.values(), key=lambda l: (l["first_seen"], l["id"]), reverse=True)
    store["generated_at"] = today
    return store, changes
