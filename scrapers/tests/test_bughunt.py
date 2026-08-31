"""Regressions from the 2026-08-22 bug hunt: every case here was a verified
live defect (real trucks filtered away, wrong trucks admitted, prices
mangled, state machine misbehaving)."""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx, normalize, store
from common.patterns import RE_620, RE_OTHER_GEN
from listings import ebay, kaidee, kuruma_ex

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def test_shared_patterns():
    # Comma-grouped numbers are not model references.
    assert not RE_620.search("1984 Nissan 720 King Cab 6,620 Original Miles")
    assert not RE_620.search("only 76,620 km")
    assert RE_620.search("Datsun 620, restored")
    # Prices, phone digits and the 620's own SD22 diesel survive the
    # cross-generation rule; real other-generation names still trip it.
    for ok in ["1975 Datsun 620 - $6,520 obo", "spent £720 on new brakes",
               "ダットサン620 ワンオーナー 720,000円即決",
               "1979 Datsun 620 pickup SD22 diesel", "ปี 2520 สภาพสวย"]:
        assert not RE_OTHER_GEN.search(ok), ok
    for bad in ["1984 Nissan 720 King Cab", "Datsun 520 pickup",
                "Nissan D21 Hardbody", "Y720 King Cab",
                "1971 521, sale or trade for 620 ext cab"]:
        assert RE_OTHER_GEN.search(bad), bad
    print("ok test_shared_patterns")


def test_ebay_filter_spares_real_trucks():
    base = {"itemId": "x", "legacyItemId": "1", "itemWebUrl": "https://ebay.com/itm/1",
            "price": {"value": "9500", "currency": "USD"},
            "buyingOptions": ["FIXED_PRICE"], "itemLocation": {"country": "US"},
            "categories": [{"categoryName": "Cars & Trucks"}]}
    real_titles = [
        "1975 Datsun 620 King Cab 4-Speed Manual L20B",      # transmission != owner's manual
        "1977 Datsun 620 Pickup - Toyota 22R swap",          # Toyota != toy
        "1978 Datsun 620 King Cab partial restoration project",
        "1976 Datsun 620 new clutch and brakes, many photos",
        "1979 Datsun 620 consignment sale",
    ]
    for i, t in enumerate(real_titles):
        payload = {"itemSummaries": [base | {"legacyItemId": str(100 + i), "title": t}]}
        recs = ebay.parse_items(payload, "US", FX_DAY)
        assert len(recs) == 1, f"real truck filtered away: {t}"
    # Memorabilia still held back.
    junk = [
        ("Datsun 620 print ad 1975 original", [{"categoryName": "Collectibles"}]),
        ("Tomica Datsun 620 truck toy", [{"categoryName": "Diecast & Toy Vehicles"}]),
        ("Datsun 620 owners manual 1977", [{"categoryName": "Cars & Trucks"}]),
    ]
    for i, (t, cats) in enumerate(junk):
        payload = {"itemSummaries": [base | {"legacyItemId": str(200 + i), "title": t,
                                             "categories": cats}]}
        assert not ebay.parse_items(payload, "US", FX_DAY), f"junk leaked: {t}"
    # Localized (DE) vehicle category is not treated as memorabilia.
    payload = {"itemSummaries": [base | {
        "legacyItemId": "300", "title": "Datsun 620 King Cab Pick Up H-Zulassung",
        "price": {"value": "12000", "currency": "EUR"},
        "categories": [{"categoryName": "Auto & Motorrad: Fahrzeuge"}],
        "itemLocation": {"country": "DE"}}]}
    assert len(ebay.parse_items(payload, "DE", FX_DAY)) == 1, "DE-categorized truck dropped"
    # A 720 whose mileage contains 620 stays out.
    payload = {"itemSummaries": [base | {
        "legacyItemId": "400", "title": "1984 Nissan 720 King Cab 6,620 Original Miles"}]}
    assert not ebay.parse_items(payload, "US", FX_DAY), "720 ingested via mileage 6,620"
    print("ok test_ebay_filter_spares_real_trucks")


def test_kaidee_wanted_edges():
    assert kaidee._wanted("Datsun 620 คิงแค็บ SD22 กระบะ"), "SD22 killed a real 620"
    assert not kaidee._wanted("Datsun Bluebird 1300 SSS ปี 2515"), "saloon admitted"
    assert not kaidee._wanted("Datsun Sunny 1500 sedan สวยมาก"), "saloon admitted"
    assert kaidee._wanted("ดัทสัน 1500 ช้างเหยียบ กระบะสั้น ปี 2519")
    print("ok test_kaidee_wanted_edges")


def test_kuruma_ex_split_price():
    records = kuruma_ex.parse_page((FIXTURES / "kuruma_ex_page.html").read_text(), FX_DAY)
    # The synthetic 1978 cards clone the real card whose price renders as
    # <b>130.</b><b>5</b>万円 with value="1305000": the value attribute is
    # authoritative (the old text regex read this as ¥50,000).
    golden = records[0]
    assert golden["price"]["amount"] == 1_305_000, golden["price"]
    print("ok test_kuruma_ex_split_price")


def test_extract_year_edges():
    assert normalize.extract_year("Registered 1969, 1974 Datsun 620") == 1974
    assert normalize.extract_year("Datsun 620 pickup project £1975") is None
    assert normalize.extract_year("1978 Datsun 620") == 1978
    print("ok test_extract_year_edges")


def _rec(rid, status="active", amount=5000.0):
    price = normalize.make_price(amount, "USD", FX_DAY)
    return {
        "id": rid, "source": rid.split(":")[0], "source_listing_id": rid.split(":")[1],
        "url": f"https://example.com/{rid.split(':')[1]}", "title": f"1975 Datsun 620 {rid}",
        "title_translated": None, "description_snippet": None, "year": 1975,
        "country": "US", "region": None, "drive_side": "LHD",
        "king_cab": {"matched": False, "matched_terms": [], "body_style_check": "unavailable"},
        "price": price, "images": [], "status": status,
    }


def test_store_outage_does_not_age():
    s = {"generated_at": "", "listings": []}
    s, _ = store.reconcile(s, [_rec("ebay:1"), _rec("ebay:2")], {"ebay"}, "2026-08-01")
    # Three days of source outage: not seen, no ageing.
    for day in ["2026-08-02", "2026-08-03", "2026-08-04"]:
        s, ch = store.reconcile(s, [], set(), day)
        assert not ch["status_changed"], "outage aged a listing"
    # Source recovers with only listing 1: listing 2 has missed ONE healthy
    # run, not four days — it must survive.
    s, ch = store.reconcile(s, [_rec("ebay:1")], {"ebay"}, "2026-08-05")
    assert not ch["status_changed"], "first healthy miss withdrew a listing"
    # Two more healthy misses withdraw it.
    s, ch = store.reconcile(s, [_rec("ebay:1")], {"ebay"}, "2026-08-06")
    assert not ch["status_changed"]
    s, ch = store.reconcile(s, [_rec("ebay:1")], {"ebay"}, "2026-08-07")
    assert [c["id"] for c in ch["status_changed"]] == ["ebay:2"]
    assert next(l for l in s["listings"] if l["id"] == "ebay:2")["status"] == "withdrawn"
    # A sighting resets the streak.
    l1 = next(l for l in s["listings"] if l["id"] == "ebay:1")
    assert "missed_runs" not in l1
    print("ok test_store_outage_does_not_age")


def test_store_same_day_relist_not_paired():
    a = _rec("yahoo_auctions:a1", status="sold")
    b = copy.deepcopy(a) | {"id": "yahoo_auctions:a2", "source_listing_id": "a2",
                            "url": "https://example.com/a2"}
    s = {"generated_at": "", "listings": []}
    s, ch = store.reconcile(s, [a, b], {"yahoo_auctions"}, "2026-08-01")
    assert not ch["possible_relists"], "same-day records paired as relists of each other"
    print("ok test_store_same_day_relist_not_paired")


def test_store_price_block_fx_stable():
    s = {"generated_at": "", "listings": []}
    s, _ = store.reconcile(s, [_rec("ebay:1")], {"ebay"}, "2026-08-01")
    stored = s["listings"][0]
    original_gbp = stored["price"]["gbp"]
    # Same amount, different day's rate: the stored conversion must not move.
    moved_fx = copy.deepcopy(FX_DAY)
    moved_fx["rates"]["USD"] = FX_DAY["rates"]["USD"] * 1.1
    moved_fx["date"] = "2026-08-02"
    rec = _rec("ebay:1")
    rec["price"] = normalize.make_price(5000.0, "USD", moved_fx)
    s, ch = store.reconcile(s, [rec], {"ebay"}, "2026-08-02")
    assert not ch["price_changed"]
    assert s["listings"][0]["price"]["gbp"] == original_gbp, "gbp silently recomputed"
    print("ok test_store_price_block_fx_stable")


if __name__ == "__main__":
    test_shared_patterns()
    test_ebay_filter_spares_real_trucks()
    test_kaidee_wanted_edges()
    test_kuruma_ex_split_price()
    test_extract_year_edges()
    test_store_outage_does_not_age()
    test_store_same_day_relist_not_paired()
    test_store_price_block_fx_stable()
    print("all bug-hunt regression tests passed")
