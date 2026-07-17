"""Thailand collector tests: Kaidee parse contract (offline fixture trimmed
from the real 2026-07-17 c11-auto-car search) and the Thai naming rules.

Thai listings never say "620": Thai-built trucks were badged Datsun
1300/1500 and are nicknamed ช้างเหยียบ, King Cab is คิงแค็บ, and years are
Buddhist Era (ปี 2521 = 1978) — which is why year is informational only and
the 520/720 exclusions need digit boundaries.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx, king_cab
from common.schema import validate
from listings import kaidee

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_thai_king_cab_terms():
    assert king_cab.check("Datsun 620 คิงแค็บ ปี 2521")["matched"]
    assert king_cab.check("ดัทสัน 1500 คิงแคป ช้างเหยียบ")["matched"]
    assert not king_cab.check("ดัทสัน 1500 ช้างเหยียบ กระบะสั้น")["matched"]
    print("ok test_thai_king_cab_terms")


def test_kaidee_parser():
    records = kaidee.parse_page((FIXTURES / "kaidee_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The real Datsun 520 (other generation, no King Cab), the promoted
    # Honda, and the 720 คิงแค็บ are all excluded; the Thai-badged and the
    # English-badged 620 King Cabs both pass.
    assert ids == ["kaidee:900000001", "kaidee:900000002"], ids

    thai = records[0]
    assert thai["country"] == "TH" and thai["drive_side"] == "RHD"
    assert thai["price"]["amount"] == 185000 and thai["price"]["currency"] == "THB"
    assert thai["price"]["gbp"] == round(185000 / FX_DAY["rates"]["THB"], 2)
    # ปี 2521 is BE 1978; the collector must NOT misread it as a CE year.
    assert thai["year"] is None
    validate(_full(thai), "listing")

    en = records[1]
    assert en["images"] == []
    validate(_full(en), "listing")
    print("ok test_kaidee_parser")


def test_be_year_does_not_trip_generation_filter():
    # "ปี 2520" (= 1977) contains the substring 520; it must not be excluded.
    assert kaidee._wanted("Datsun คิงแค็บ ช้างเหยียบ ปี 2520 สภาพสวย")
    assert not kaidee._wanted("Datsun 520 คิงแค็บ")   # a real 520 must be
    assert not kaidee._wanted("Datsun 720 คิงแค็บ")   # a real 720 must be
    print("ok test_be_year_does_not_trip_generation_filter")


if __name__ == "__main__":
    test_thai_king_cab_terms()
    test_kaidee_parser()
    test_be_year_does_not_trip_generation_filter()
    print("all thailand tests passed")
