"""Merge a fresh scrape into the stored listings and compute what changed.

Produces the change sets the email digest needs: new, price changes, status
changes, and listings that disappeared from a source we successfully scraped
(treated as withdrawn). Full-history price points are appended only when the
price actually moves. Fuzzy relisted-detection is deferred to M5.
"""

from __future__ import annotations

import re
from datetime import date
from difflib import SequenceMatcher


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower())


def find_relisted(rec: dict, candidates: list[dict]) -> dict | None:
    """Find a prior ended (sold/withdrawn) listing that this new one likely is a
    relist of: similar title, same year, and price within 25%. Cross-source is
    allowed. Returns the matched prior, or None."""
    rt = _norm_title(rec.get("title", ""))
    ry, rp = rec.get("year"), rec.get("price_original")
    best, best_ratio = None, 0.0
    for c in candidates:
        if c["id"] == rec.get("id") or c.get("status") not in ("sold", "withdrawn"):
            continue
        if ry and c.get("year") and ry != c["year"]:
            continue
        if rp and c.get("price_original"):
            hi = max(rp, c["price_original"])
            if hi and abs(rp - c["price_original"]) / hi > 0.25:
                continue
        ratio = SequenceMatcher(None, rt, _norm_title(c.get("title", ""))).ratio()
        if ratio > best_ratio:
            best, best_ratio = c, ratio
    return best if best_ratio >= 0.6 else None


def merge(existing: list[dict], incoming: list[dict], scraped_sources: set[str], today: str | None = None):
    today = today or date.today().isoformat()
    by_id = {r["id"]: r for r in existing}
    seen_ids = set()
    changes = {"new": [], "price_changed": [], "status_changed": [], "withdrawn": [], "relisted": []}

    for rec in incoming:
        seen_ids.add(rec["id"])
        prior = by_id.get(rec["id"])
        if prior is None:
            match = find_relisted(rec, list(by_id.values()))
            if match is not None:
                rec["relisted_from"] = match["id"]
                changes["relisted"].append({"listing": rec, "relisted_from": match["id"]})
            by_id[rec["id"]] = rec
            changes["new"].append(rec)
            continue

        prior["last_seen"] = today
        # Price change
        old_price = prior.get("price_original")
        new_price = rec.get("price_original")
        if new_price is not None and new_price != old_price:
            prior["price_original"] = new_price
            prior["price_gbp"] = rec.get("price_gbp")
            prior["currency"] = rec.get("currency")
            prior.setdefault("price_history", []).append(
                {"date": today, "price_original": new_price, "price_gbp": rec.get("price_gbp")}
            )
            changes["price_changed"].append({"listing": prior, "old": old_price, "new": new_price})
        # Status change
        if rec.get("status") and rec["status"] != prior.get("status"):
            old_status = prior.get("status")
            prior["status"] = rec["status"]
            changes["status_changed"].append({"listing": prior, "old": old_status, "new": rec["status"]})

    # Listings from a successfully-scraped source that we did not see this run -> withdrawn.
    for rec in by_id.values():
        if rec["id"] in seen_ids:
            continue
        if rec.get("source") in scraped_sources and rec.get("status") == "active":
            rec["status"] = "withdrawn"
            rec["last_seen"] = rec.get("last_seen", today)
            changes["withdrawn"].append({"listing": rec, "old": "active", "new": "withdrawn"})

    merged = sorted(by_id.values(), key=lambda r: (-r.get("king_cab_score", 0), r.get("id", "")))
    return merged, changes
