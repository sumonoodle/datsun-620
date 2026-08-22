"""Gap-sweep collector tests: PistonHeads, Ratsun, Retro Rides, Trovit and
Kleinanzeigen parse contracts, against fixtures built from real 2026-08-14
pages (several contain REAL live 620s) plus synthetic edge cases."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings import kleinanzeigen, pistonheads, ratsun, retrorides, trovit

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-08-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_pistonheads_parser():
    records = pistonheads.parse_page((FIXTURES / "pistonheads_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # Real 240Z out; 620 King Cab in (flagged); era Pickup with no "620" in
    # the title in via the structural body/era rule; 1984 720 out.
    assert sorted(ids) == ["pistonheads:99000001", "pistonheads:99000002"], ids
    kc = next(r for r in records if r["id"] == "pistonheads:99000001")
    assert kc["king_cab"]["matched"] is True
    assert kc["price"]["amount"] == 18995 and kc["price"]["currency"] == "GBP"
    assert kc["price"]["gbp"] == 18995  # native GBP needs no conversion
    assert kc["drive_side"] == "LHD"  # title says LHD US import
    validate(_full(kc), "listing")
    struct = next(r for r in records if r["id"] == "pistonheads:99000002")
    assert struct["king_cab"]["matched"] is False
    assert struct["year"] == 1975
    validate(_full(struct), "listing")
    print("ok test_pistonheads_parser")


def test_ratsun_parser():
    records = ratsun.parse_page((FIXTURES / "ratsun_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The real 510 card and the REAL "521, trade for 620 ext cab" title
    # (cross-generation rule) are out; the 620 King Cab is in and the
    # COMPLETED 620 longbed arrives as sold.
    assert ids == ["ratsun:9901", "ratsun:9902"], ids
    kc = records[0]
    assert kc["king_cab"]["matched"] is True
    assert kc["price"]["amount"] == 8500
    assert kc["status"] == "active"
    validate(_full(kc), "listing")
    sold = records[1]
    assert sold["status"] == "sold"
    validate(_full(sold), "listing")
    print("ok test_ratsun_parser")


def test_retrorides_parser():
    records = retrorides.parse_page((FIXTURES / "retrorides_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The REAL live board 620 (£8995 Sussex) is in; the Viva, the 521 and
    # the "620 miles" Micra are out; the SOLD! King Cab arrives as sold.
    assert len(ids) == 2, ids
    live = next(r for r in records if "8995" in str(r["price"]["amount"]))
    assert live["price"]["currency"] == "GBP" and live["year"] == 1978
    assert live["status"] == "active"
    validate(_full(live), "listing")
    sold = next(r for r in records if r["id"] == "retrorides:999001")
    assert sold["status"] == "sold"
    assert sold["king_cab"]["matched"] is True
    assert sold["price"]["amount"] == 7500
    validate(_full(sold), "listing")
    print("ok test_retrorides_parser")


def test_trovit_parser():
    records = trovit.parse_page((FIXTURES / "trovit_page.html").read_text(), FX_DAY)
    # Real page: 7 cards, one a "See Video at" stub whose 620 only lives in
    # the description — title-only matching drops it.
    assert len(records) == 6, [r["title"] for r in records]
    kcs = [r for r in records if r["king_cab"]["matched"]]
    assert len(kcs) == 2, "the two real King Cabs must be flagged"
    priced = next(r for r in records if r["price"]["amount"] == 9940)
    assert priced["king_cab"]["matched"] is True
    for r in records:
        validate(_full(r), "listing")
    print("ok test_trovit_parser")


def test_kleinanzeigen_parser():
    records = kleinanzeigen.parse_page((FIXTURES / "kleinanzeigen_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The three real ads (incl. the live Y720 King Cab) are all excluded;
    # only the synthetic 620 King Cab passes, in EUR.
    assert ids == ["kleinanzeigen:9990000001"], ids
    kc = records[0]
    assert kc["king_cab"]["matched"] is True
    assert kc["price"]["amount"] == 9500 and kc["price"]["currency"] == "EUR"
    assert kc["price"]["gbp"] == round(9500 / FX_DAY["rates"]["EUR"], 2)
    assert kc["country"] == "DE" and kc["drive_side"] == "LHD"
    validate(_full(kc), "listing")
    print("ok test_kleinanzeigen_parser")


if __name__ == "__main__":
    test_pistonheads_parser()
    test_ratsun_parser()
    test_retrorides_parser()
    test_trovit_parser()
    test_kleinanzeigen_parser()
    print("all gap-sweep tests passed")
