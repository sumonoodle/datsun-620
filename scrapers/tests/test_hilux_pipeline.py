"""Hilux pipeline: the eBay Hilux collector's filtering, and a full
run_daily run with --model hilux shape (own data dir, shared FX log)."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_daily
from common import fx
from common.schema import validate
from listings_hilux import ebay

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))

VEHICLE = {"itemWebUrl": "https://www.ebay.co.uk/itm/1",
           "price": {"value": "9995", "currency": "GBP"},
           "itemLocation": {"country": "GB"},
           "categories": [{"categoryName": "Cars"}]}


def _items(*titles):
    return {"itemSummaries": [VEHICLE | {"title": t, "legacyItemId": str(i)}
                              for i, t in enumerate(titles)]}


def test_ebay_hilux_filter():
    recs = ebay.parse_items(_items(
        "1980 Toyota Hilux RN30 12R restored",      # the reference truck
        "2019 Toyota Hilux Invincible X",           # modern: the flood the query avoids
        "1982 Toyota Hilux 2.2 diesel pickup",      # diesel
        "1981 Toyota Pickup SR5 4x4",               # US naming, 4WD
        "1986 Toyota Hilux Xtracab",                # 4th generation
    ), "GB", FX_DAY)
    assert [r["source_listing_id"] for r in recs] == ["0", "3"], recs
    ref, us4 = recs
    assert ref["variant"]["target_match"] and ref["variant"]["chassis_code"] == "RN30"
    assert ref["price"]["gbp"] == 9995 and ref["drive_side"] == "RHD"
    assert us4["variant"]["drive"] == "4WD" and not us4["variant"]["target_match"]
    for r in recs:
        validate(r | {"first_seen": "2026-09-24", "last_seen": "2026-09-24",
                      "history": [{"date": "2026-09-24", "status": "active"}]}, "listing")
    print("ok test_ebay_hilux_filter")


def test_hilux_run_uses_own_dir_and_shared_fx():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        hilux_dir = root / "hilux"
        rec = ebay.parse_items(_items("1980 Toyota Hilux RN30"), "GB", FX_DAY)[0]

        def broken(_fx):
            raise RuntimeError("HTTP 403")

        run_daily.run(hilux_dir, fx_fetch=lambda: FX_DAY,
                      sources=[("ebay", lambda _fx: [dict(rec)]), ("gumtree_uk", broken)],
                      fx_path=root / "fx-rates.json")
        assert (root / "fx-rates.json").exists() and not (hilux_dir / "fx-rates.json").exists()
        store = json.loads((hilux_dir / "listings.json").read_text())
        assert [l["id"] for l in store["listings"]] == ["ebay:0"]
        assert store["listings"][0]["variant"]["target_match"] is True
        log = json.loads((hilux_dir / "run-log.json").read_text())
        assert [(s["source"], s["ok"]) for s in log["sources"]] == [("ebay", True), ("gumtree_uk", False)]
        changes = json.loads((hilux_dir / "changes-latest.json").read_text())
        assert changes["new"] == ["ebay:0"]
    print("ok test_hilux_run_uses_own_dir_and_shared_fx")


if __name__ == "__main__":
    test_ebay_hilux_filter()
    test_hilux_run_uses_own_dir_and_shared_fx()
