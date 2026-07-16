"""Best-effort relisted detection per PRD 4.2.

Within the same source only: price proximity, title similarity, location.
Output is only ever framed as "possible relist"; never asserted as fact.
"""

from __future__ import annotations

from difflib import SequenceMatcher

TITLE_SIMILARITY_MIN = 0.75
PRICE_PROXIMITY_PCT = 15.0


def detect(new_listing: dict, existing: list[dict]) -> dict:
    """Returns the relist block for a newly seen listing."""
    best = None
    for old in existing:
        if old["source"] != new_listing["source"] or old["id"] == new_listing["id"]:
            continue
        if old["status"] == "active":
            continue  # a live listing can't have been relisted yet
        reasons = []

        sim = SequenceMatcher(
            None, (old["title"] or "").lower(), (new_listing["title"] or "").lower()
        ).ratio()
        if sim < TITLE_SIMILARITY_MIN:
            continue
        reasons.append(f"title similarity {sim:.2f}")

        if old["country"] != "XX" and old["country"] == new_listing["country"]:
            reasons.append(f"same country ({old['country']})")

        old_amt = (old.get("price") or {}).get("amount")
        new_amt = (new_listing.get("price") or {}).get("amount")
        if old_amt and new_amt:
            delta_pct = abs(new_amt - old_amt) / old_amt * 100
            if delta_pct <= PRICE_PROXIMITY_PCT:
                reasons.append(f"price within {delta_pct:.0f}%")

        # Title similarity alone is not enough: require a second signal.
        if len(reasons) >= 2 and (best is None or sim > best[0]):
            best = (sim, old["id"], reasons)

    if best:
        return {"possible": True, "prior_id": best[1], "reasons": best[2]}
    return {"possible": False, "prior_id": None, "reasons": []}
