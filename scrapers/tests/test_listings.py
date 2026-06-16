"""Listings pipeline tests: normalisation, FX, change detection, schema, digest.

Uses fixtures (real BaT field shape) so the data path is verified even when live
620 inventory is momentarily empty.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "emailer"))

from common.listings_common import build_listing  # noqa: E402
from common.listings_store import merge  # noqa: E402
from common.schema import validate  # noqa: E402
import send_notification  # noqa: E402

FX = {"date": "2026-06-15", "base": "GBP", "rates": {"GBP": 1.0, "USD": 1.34, "JPY": 215.0}}

# Real BaT field shape, set to a 620 King Cab for the test.
RAW_BAT = {
    "source": "bringatrailer", "source_url": "https://bringatrailer.com/listing/1978-datsun-620-king-cab-1/",
    "title": "1978 Datsun 620 King Cab 5-Speed", "price_original": 12000, "currency": "USD",
    "country_code": "US", "year": 1978, "photo_urls": ["https://example.com/a.jpg"], "status": "active",
}
RAW_JP = {
    "source": "goonet", "source_url": "https://example.com/jp/620-1",
    "title": "ダットサン 620 キングキャブ", "price_original": 1500000, "currency": "JPY",
    "country_code": "JP", "status": "active",
}


def test_build_listing_normalises_and_scores():
    rec = build_listing(RAW_BAT, FX, "2026-06-15")
    assert rec["price_gbp"] == round(12000 / 1.34, 2)
    assert rec["drive_side"] == "LHD" and rec["drive_side_inferred"] is True
    assert rec["king_cab_score"] >= 0.9
    assert rec["country"] == "United States" and rec["year"] == 1978


def test_build_listing_rhd_and_schema_valid():
    rec = build_listing(RAW_JP, FX, "2026-06-15")
    assert rec["drive_side"] == "RHD"
    assert validate(rec, "listing") == []  # conforms to the contract


def test_merge_detects_new_then_price_change():
    today = "2026-06-15"
    a = build_listing(RAW_BAT, FX, today)
    merged, changes = merge([], [a], {"bringatrailer"}, today)
    assert len(changes["new"]) == 1 and len(merged) == 1

    cheaper = build_listing({**RAW_BAT, "price_original": 9000}, FX, "2026-06-16")
    merged2, changes2 = merge(merged, [cheaper], {"bringatrailer"}, "2026-06-16")
    assert len(changes2["price_changed"]) == 1
    assert changes2["price_changed"][0]["old"] == 12000 and changes2["price_changed"][0]["new"] == 9000
    assert len(merged2[0]["price_history"]) == 2  # original + the change


def test_merge_marks_withdrawn_when_disappeared():
    today = "2026-06-15"
    a = build_listing(RAW_BAT, FX, today)
    merged, _ = merge([], [a], {"bringatrailer"}, today)
    # next run: source scraped OK but listing gone
    merged2, changes = merge(merged, [], {"bringatrailer"}, "2026-06-16")
    assert len(changes["withdrawn"]) == 1 and merged2[0]["status"] == "withdrawn"


def test_digest_only_has_content_when_changes():
    assert send_notification.has_changes({"new": [], "price_changed": [], "status_changed": [], "withdrawn": []}) is False
    changes = {"new": [build_listing(RAW_BAT, FX)], "price_changed": [], "status_changed": [], "withdrawn": []}
    assert send_notification.has_changes(changes) is True
    html = send_notification.build_html(changes, {"active": 1, "by_country": {"United States": 1}, "sources": []})
    assert "King Cab" in html and "1978 Datsun 620 King Cab" in html


def _run():
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  PASS {name}")
            except AssertionError as e:
                fails.append(f"{name}: {e}"); print(f"  FAIL {name}: {e}")
    return fails


if __name__ == "__main__":
    if _run():
        sys.exit(1)
    print("OK: listings pipeline (normalise / FX / changes / schema / digest) works.")
