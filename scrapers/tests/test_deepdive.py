"""Deep-dive collector tests: ClassicCars.com, Kijiji, Barn Finds, FLEX and
kuruma-ex parse contracts, against fixtures trimmed from real 2026-07-17
pages with synthetic golden King Cabs (the live pages held no King Cab
620s on fetch day, correctly yielding zero records)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings import barnfinds, classiccars, flex, kijiji, kuruma_ex

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_classiccars_parser():
    records = classiccars.parse_page((FIXTURES / "classiccars_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # All-620s policy: the real 1979 standard cab is included (unflagged)
    # alongside the King Cab.
    assert ids == ["classiccars:CC-2079740", "classiccars:CC-9990001"], ids
    assert records[0]["king_cab"]["matched"] is False
    golden = records[1]
    assert golden["year"] == 1978
    assert golden["price"]["amount"] == 21500 and golden["price"]["currency"] == "USD"
    assert golden["region"] == "Portland Oregon"
    assert golden["url"].startswith("https://classiccars.com/listings/view/")
    validate(_full(golden), "listing")
    print("ok test_classiccars_parser")


def test_kijiji_parser():
    records = kijiji.parse_page((FIXTURES / "kijiji_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # Real Hot Wheels ad (toys path), the 720 King Cab (no 620) and the
    # gated toy lot (620+King Cab words but /v-toys-games/ URL) are all out.
    assert ids == ["kijiji:9990000001"], ids
    golden = records[0]
    assert golden["price"]["amount"] == 18500.0  # cents -> dollars
    assert golden["price"]["currency"] == "CAD"
    assert golden["price"]["gbp"] == round(18500 / FX_DAY["rates"]["CAD"], 2)
    assert golden["country"] == "CA" and golden["region"] == "Vancouver"
    assert golden["year"] == 1977
    validate(_full(golden), "listing")
    print("ok test_kijiji_parser")


def test_barnfinds_parser():
    records = barnfinds.parse_feed((FIXTURES / "barnfinds_feed.xml").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # All-620s policy: every 620 write-up is tracked; only the King Cab
    # project is flagged.
    assert ids == ["barnfinds:king-cab-project-1977-datsun-620",
                   "barnfinds:dealer-modified-1979-datsun-620-4x4-pickup",
                   "barnfinds:compact-work-truck-1977-datsun-620"], ids
    assert [r["king_cab"]["matched"] for r in records] == [True, False, False]
    golden = records[0]
    assert golden["title"] == "King Cab Project: 1977 Datsun 620"
    assert golden["year"] == 1977
    assert golden["price"]["amount"] == 8500
    assert golden["images"] and golden["images"][0].endswith("1977-620-kc.jpg")
    validate(_full(golden), "listing")
    print("ok test_barnfinds_parser")


def test_flex_parser():
    records = flex.parse_page((FIXTURES / "flex_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The real 1994 Sunny Truck (no King Cab) and the 1990 D21 King Cab
    # (era gate) are out; the 1978 620 King Cab passes at 398万円.
    assert ids == ["flex:888000001"], ids
    golden = records[0]
    assert golden["year"] == 1978
    assert golden["price"]["amount"] == 3_980_000
    assert golden["price"]["gbp"] == round(3_980_000 / FX_DAY["rates"]["JPY"], 2)
    assert golden["status"] == "active"
    validate(_full(golden), "listing")
    print("ok test_flex_parser")


def test_kuruma_ex_parser():
    records = kuruma_ex.parse_page((FIXTURES / "kuruma_ex_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The real 1987 pickup (era) and the real D21 SEV6 King Cab Hardbody
    # (era) are out; the synthetic 1978 620 King Cab passes, as does the
    # 応談 (negotiable, no-price) 1977 card.
    assert ids == ["kuruma_ex:ccZZ9000000001", "kuruma_ex:ccZZ9000000002"], ids
    golden = records[0]
    assert golden["year"] == 1978
    assert golden["country"] == "JP" and golden["drive_side"] == "RHD"
    assert golden["price"]["currency"] == "JPY"
    validate(_full(golden), "listing")

    ondan = records[1]
    # A negotiable-price card must not swallow the spec table into the
    # title (the pre-fix behaviour when 支払総額 was absent).
    assert ondan["price"]["amount"] is None
    assert "年式" not in ondan["title"] and "走行距離" not in ondan["title"], ondan["title"]
    validate(_full(ondan), "listing")
    print("ok test_kuruma_ex_parser")


if __name__ == "__main__":
    test_classiccars_parser()
    test_kijiji_parser()
    test_barnfinds_parser()
    test_flex_parser()
    test_kuruma_ex_parser()
    print("all deep-dive tests passed")
