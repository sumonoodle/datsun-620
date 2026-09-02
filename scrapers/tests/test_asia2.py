"""Asia round-2 collector tests: Truck2Hand (real 2026-09-02 page data —
four LIVE Thai 620s were on the brand page on build day) and everycar."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings import everycar, truck2hand

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-09-02"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_truck2hand_parser():
    records = truck2hand.parse_page((FIXTURES / "truck2hand_page.html").read_text(), FX_DAY)
    ids = {r["id"] for r in records}
    # The four real 620s pass (incl. two ช้างเหยียบ trucks with NO model tag);
    # the real 521s, 720s and 520 are excluded by generation; the real ฿450
    # mudguard (cross-generation title AND parts word AND under floor) too.
    assert ids == {"truck2hand:APNdadvglg", "truck2hand:Y9l6V20mlb",
                   "truck2hand:d1RDEPwnNr", "truck2hand:nol5D1pJNQ"}, ids
    big = next(r for r in records if r["id"] == "truck2hand:nol5D1pJNQ")
    assert big["price"]["amount"] == 180000 and big["price"]["currency"] == "THB"
    assert big["price"]["gbp"] == round(180000 / FX_DAY["rates"]["THB"], 2)
    assert big["country"] == "TH" and big["region"] == "กรุงเทพ"
    assert big["year"] is None  # ปี values are garbage by design
    assert big["status"] == "active"
    for r in records:
        validate(_full(r), "listing")
    print("ok test_truck2hand_parser")


def test_everycar_parser():
    records = everycar.parse_page((FIXTURES / "everycar_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The real Civilian bus padding (non-Datsun slug) and the 1990
    # Datsun-badged truck (era gate via URL year) are out; the 1978 King
    # Cab passes with its USD FOB price.
    assert ids == ["everycar:9990001"], ids
    golden = records[0]
    assert golden["year"] == 1978
    assert golden["price"]["amount"] == 9800 and golden["price"]["currency"] == "USD"
    assert golden["king_cab"]["matched"] is True
    assert not golden["title"].startswith("2609")  # stock-number prefix stripped
    validate(_full(golden), "listing")
    print("ok test_everycar_parser")


if __name__ == "__main__":
    test_truck2hand_parser()
    test_everycar_parser()
    print("all asia2 tests passed")
