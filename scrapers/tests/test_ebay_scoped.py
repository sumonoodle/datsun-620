"""Regressions from the 2026-09-14 eBay diagnosis.

The collector had returned zero records every day since it shipped. Four
rounds of live probing found two stacked causes, both about the SHAPE of
the query rather than the filters:

1. The search was unscoped, so "datsun 620" matched ~8,800 items on
   EBAY_US — bumpers, Hot Wheels cars, vintage adverts — and the API caps
   a page at 200. Not one whole vehicle appeared in ~1,800 items sampled
   across four marketplaces. No filter change could have helped.
2. Scoped to the vehicle category the payload is sane (28 Datsun vehicles
   on EBAY_US, 3 on EBAY_AU), but q="datsun 620" inside that category
   returns total=0 everywhere: Motors composes titles from year/make/
   model fields, and a 620 often reads "1978 Datsun Pickup".

These tests pin both halves of the fix, and pin the unscoped path too so
the parts-era defences cannot be deleted while fixtures still use them.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from listings import ebay

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))

# Shaped like a real Motors vehicle summary: the whole-vehicle category,
# a year-led composed title, a four-figure price.
VEHICLE = {"itemId": "v|1|0", "legacyItemId": "1",
           "itemWebUrl": "https://www.ebay.com/itm/1",
           "price": {"value": "9500", "currency": "USD"},
           "buyingOptions": ["FIXED_PRICE"], "itemLocation": {"country": "US"},
           "categories": [{"categoryName": "Cars & Trucks"}]}


def _scoped(title, **over):
    payload = {"itemSummaries": [VEHICLE | {"title": title} | over]}
    return ebay.parse_items(payload, "US", FX_DAY, vehicle_scoped=True)


def test_scoped_admits_modelless_pickup():
    """The listing shape that a month of zeros was hiding."""
    for title in ["1978 Datsun Pickup",
                  "1976 Datsun Pick Up long bed",
                  "1975 Datsun Truck project, no reserve",
                  "1979 DATSUN PICKUP KING CAB"]:
        assert _scoped(title), f"model-less 620-vintage pickup dropped: {title}"
    # The same titles unscoped stay out: that payload is parts and
    # brochures, where "1978 Datsun Pickup" is as likely a magazine cover.
    for title in ["1978 Datsun Pickup", "1975 Datsun Truck project, no reserve"]:
        payload = {"itemSummaries": [VEHICLE | {"title": title}]}
        assert not ebay.parse_items(payload, "US", FX_DAY), \
            f"model-less title admitted on the unscoped path: {title}"


def test_scoped_still_rejects_other_datsuns():
    """The vehicle category is the whole marque, not just trucks."""
    wrong = [
        "1978 Datsun 280Z 2 seater",          # Z-car, the bulk of the category
        "1973 Datsun 240Z",
        "1969 Datsun Roadster",
        "1975 Datsun 260C GL Sedan Car",
        "1970 Datsun 521 Pickup",             # neighbouring generation
        "1975 Datsun 521 Pickup",             # ...and one inside the year window,
        "1976 Datsun 720 pickup",             # so the cross-gen gate must run first
        "1984 Nissan 720 King Cab",
        "1971 Datsun 1200 Truck",             # Sunny truck, not a 620
        "1968 Datsun 520 Pickup",
        "1992 Nissan Hardbody D21 pickup",
        "2004 Nissan Navara pickup",
    ]
    for title in wrong:
        assert not _scoped(title), f"non-620 vehicle admitted: {title}"


def test_scoped_year_window():
    """Model-less admission is bounded by 620 production, not open season."""
    assert not _scoped("1962 Datsun Pickup"), "pre-620 pickup admitted"
    assert not _scoped("1995 Datsun Pickup"), "post-620 pickup admitted"
    assert not _scoped("Datsun Pickup, needs work"), "yearless pickup admitted"
    assert not _scoped("1977 Datsun, runs and drives"), "non-pickup Datsun admitted"
    assert _scoped("1972 Datsun Pickup"), "first production year dropped"
    assert _scoped("1979 Datsun Pickup"), "last production year dropped"


def test_scoped_keeps_explicit_620s():
    """An explicit 620 is admitted however it is titled or priced."""
    recs = _scoped("1975 Datsun 620 King Cab")
    assert len(recs) == 1
    assert recs[0]["king_cab"]["matched"], "King Cab not flagged"
    assert recs[0]["year"] == 1975
    # The parts word list and the $500 floor are the unscoped path's job;
    # inside the vehicle category they only cost real trucks.
    assert _scoped("1977 Datsun 620 with new grille and tail light lenses"), \
        "parts vocabulary killed a scoped truck"
    assert _scoped("1976 Datsun 620 King Cab", price={"value": "1", "currency": "USD"},
                   buyingOptions=["AUCTION"]), "£1 opening bid killed a scoped truck"
    assert _scoped("1974 Datsun 620", price={"value": "100", "currency": "USD"}), \
        "price floor applied on the scoped path"


def test_unscoped_path_unchanged():
    """The fixtures and the parts-era defences still agree."""
    payload = json.loads((FIXTURES / "ebay_browse.json").read_text())
    ids = {r["id"] for r in ebay.parse_items(payload, "US", FX_DAY)}
    assert "ebay:256001001001" in ids and "ebay:256001001003" not in ids
    # Default argument must stay unscoped: every existing caller relies on it.
    assert ebay.parse_items(payload, "US", FX_DAY) == \
        ebay.parse_items(payload, "US", FX_DAY, vehicle_scoped=False)


def test_marketplaces_carry_categories():
    """Guard the fix itself: an unscoped query is what caused the outage."""
    assert all(len(m) == 3 and m[2].isdigit() for m in ebay.MARKETPLACES)
    assert "620" not in " ".join(ebay.QUERIES), \
        "model-code query returns total=0 inside the vehicle category"


if __name__ == "__main__":
    test_scoped_admits_modelless_pickup()
    test_scoped_still_rejects_other_datsuns()
    test_scoped_year_window()
    test_scoped_keeps_explicit_620s()
    test_unscoped_path_unchanged()
    test_marketplaces_carry_categories()
    print("all ebay scoped tests passed")
