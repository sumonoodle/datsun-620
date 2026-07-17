"""Collector parser tests against saved fixtures (offline), the store's
change detection, and the relist heuristic."""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx, relist, store
from common.schema import validate
from listings import bat, ebay

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}],
                  "relist": {"possible": False, "prior_id": None, "reasons": []}}


def test_ebay_parser():
    payload = json.loads((FIXTURES / "ebay_browse.json").read_text())
    records = ebay.parse_items(payload, "US", FX_DAY)
    ids = [r["id"] for r in records]
    assert "ebay:256001001001" in ids, "golden King Cab missed"
    assert "ebay:256001001002" not in ids, "standard cab leaked through"
    assert "ebay:256001001003" not in ids, "parts listing leaked through"
    assert "ebay:256001001004" in ids, "Kingcab spelling missed"
    # The 2026-07-17 memorabilia flood: ads, toys and non-620 trucks must not pass.
    assert "ebay:256001001005" not in ids, "print ad leaked through"
    assert "ebay:256001001006" not in ids, "toy model leaked through"
    assert "ebay:256001001007" not in ids, "non-620 truck leaked through"

    golden = next(r for r in records if r["id"] == "ebay:256001001001")
    assert golden["year"] == 1978
    assert golden["drive_side"] == "LHD"
    assert golden["price"]["gbp"] == round(14500 / FX_DAY["rates"]["USD"], 2)
    validate(_full(golden), "listing")

    rhd = next(r for r in records if r["id"] == "ebay:256001001004")
    assert rhd["drive_side"] == "RHD"
    assert rhd["price"]["gbp"] == 5250.0  # GBP listing needs no conversion
    validate(_full(rhd), "listing")
    print("ok test_ebay_parser")


def test_bat_parser():
    html = (FIXTURES / "bat_page.html").read_text()
    records = bat.parse_page(html, FX_DAY)
    ids = [r["id"] for r in records]
    assert ids == ["bringatrailer:1978-datsun-620-3", "bringatrailer:1977-datsun-620-kc"], ids
    golden = records[0]
    assert golden["status"] == "sold"
    assert golden["year"] == 1978
    validate(_full(golden), "listing")
    print("ok test_bat_parser")


def test_store_change_detection():
    html = (FIXTURES / "bat_page.html").read_text()
    day1 = bat.parse_page(html, FX_DAY)
    s = {"generated_at": "", "listings": []}
    s, changes = store.reconcile(s, copy.deepcopy(day1), {"bringatrailer"}, "2026-07-14")
    assert len(changes["new"]) == 2

    # Day 2: price moves on the active auction.
    day2 = copy.deepcopy(day1)
    active = next(r for r in day2 if r["status"] == "active")
    active["price"]["amount"] = 12000
    active["price"]["gbp"] = round(12000 / FX_DAY["rates"]["USD"], 2)
    s, changes = store.reconcile(s, day2, {"bringatrailer"}, "2026-07-15")
    assert len(changes["new"]) == 0
    assert len(changes["price_changed"]) == 1
    assert changes["price_changed"][0]["id"] == active["id"]
    stored = next(l for l in s["listings"] if l["id"] == active["id"])
    assert len(stored["history"]) == 2

    # Day 5+: the active listing disappears from a healthy source -> withdrawn.
    s, changes = store.reconcile(s, [], {"bringatrailer"}, "2026-07-19")
    assert any(c["new_status"] == "withdrawn" for c in changes["status_changed"])

    # A failed source must NOT trigger withdrawals.
    s2 = {"generated_at": "", "listings": []}
    s2, _ = store.reconcile(s2, copy.deepcopy(day1), {"bringatrailer"}, "2026-07-14")
    s2, changes2 = store.reconcile(s2, [], set(), "2026-07-19")
    assert not changes2["status_changed"], "withdrawal fired for a skipped source"
    print("ok test_store_change_detection")


def test_relist_heuristic():
    html = (FIXTURES / "bat_page.html").read_text()
    day1 = bat.parse_page(html, FX_DAY)
    s = {"generated_at": "", "listings": []}
    s, _ = store.reconcile(s, copy.deepcopy(day1), {"bringatrailer"}, "2026-07-14")

    # The sold golden listing reappears under a new slug at a similar price.
    reborn = copy.deepcopy(next(r for r in day1 if r["status"] == "sold"))
    reborn["id"] = "bringatrailer:1978-datsun-620-4"
    reborn["source_listing_id"] = "1978-datsun-620-4"
    reborn["status"] = "active"
    reborn["price"]["amount"] = 12900
    block = relist.detect(reborn, s["listings"])
    assert block["possible"], "relist heuristic missed a near-identical resale"
    assert block["prior_id"] == "bringatrailer:1978-datsun-620-3"

    # A different truck must not be flagged.
    other = copy.deepcopy(reborn)
    other["id"] = "bringatrailer:1971-random"
    other["title"] = "1971 Datsun 521 Bulletside"
    assert not relist.detect(other, s["listings"])["possible"]
    print("ok test_relist_heuristic")


if __name__ == "__main__":
    test_ebay_parser()
    test_bat_parser()
    test_store_change_detection()
    test_relist_heuristic()
    print("all listings tests passed")
