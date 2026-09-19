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


def test_trovit_de_parser():
    """German edition: same markup, EUR with dot-thousands, and a page
    padded with unrelated cars when no Datsun matches (the real Dacia card
    in the fixture is that padding)."""
    records = trovit.parse_page((FIXTURES / "trovit_de_page.html").read_text(), FX_DAY,
                                country="DE", currency="EUR")
    ids = [r["id"] for r in records]
    assert ids == ["trovit:de-synth-620kc"], ids
    kc = records[0]
    assert kc["price"]["amount"] == 13500 and kc["price"]["currency"] == "EUR"
    assert kc["price"]["gbp"] == round(13500 / FX_DAY["rates"]["EUR"], 2)
    assert kc["country"] == "DE"
    assert kc["king_cab"]["matched"] is True
    validate(_full(kc), "listing")
    print("ok test_trovit_de_parser")


def test_kleinanzeigen_parser():
    """Against the 2026-09-19 redesign markup: no <h2>, no 'aditem' class.

    The old parser scored 0 on this page while 28 real Datsun cars sat in
    the results, so every assertion here is about reading the page the
    site actually serves now.
    """
    records = kleinanzeigen.parse_page(
        (FIXTURES / "kleinanzeigen_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # The 280 ZX, the 240z and the Cherry are all real Datsun cars and all
    # wrong; only the 620 King Cab belongs.
    assert ids == ["kleinanzeigen:3510009911"], ids
    kc = records[0]
    assert kc["title"] == "Datsun 620 King Cab Pick Up H-Zulassung"
    assert kc["king_cab"]["matched"] is True
    assert kc["price"]["amount"] == 18500 and kc["price"]["currency"] == "EUR"
    assert kc["price"]["gbp"] == round(18500 / FX_DAY["rates"]["EUR"], 2)
    assert kc["country"] == "DE" and kc["drive_side"] == "LHD"
    # "EZ 03/1978" is a registration date, and a better year than any
    # guess from the title.
    assert kc["year"] == 1978, kc["year"]
    assert kc["region"] == "94072 Bad Füssing", kc["region"]
    assert kc["url"].endswith("/3510009911-216-3312")
    assert kc["images"] and kc["images"][0].startswith("https://img.kleinanzeigen.de/")
    assert kc["description_snippet"].startswith("Seltener Datsun 620")
    validate(_full(kc), "listing")
    print("ok test_kleinanzeigen_parser")


def test_kleinanzeigen_german_thousands_dot():
    """A 6.620 € Cherry is not a 620 (the bug this rewrite uncovered)."""
    records = kleinanzeigen.parse_page(
        (FIXTURES / "kleinanzeigen_page.html").read_text(), FX_DAY)
    assert "kleinanzeigen:3400000001" not in {r["id"] for r in records}, \
        "German thousands dot read as a model reference"


def test_kleinanzeigen_blindness_guard():
    """A heading promising results with no cards parsed MUST raise.

    The old guard only fired when the page held no ads AND no 'datsun' —
    but the search term is echoed in the chrome, so an unreadable page
    returned [] and reported success for months. Never again: 'cannot
    see' and 'nothing there' must not share an outcome.
    """
    blind = ('<html><body><h1>Autos 1 - 25 von 28 Gebrauchtwagen für '
             '„datsun“ in Deutschland</h1><div>datsun</div></body></html>')
    try:
        kleinanzeigen.parse_page(blind, FX_DAY)
    except ValueError as exc:
        assert "28" in str(exc)
    else:
        raise AssertionError("unreadable page returned quietly")

    # A genuinely empty market is NOT an error: no cards, no claimed count.
    empty = ('<html><body><h1>Autos: 0 Gebrauchtwagen für „datsun“</h1>'
             '</body></html>')
    assert kleinanzeigen.parse_page(empty, FX_DAY) == []
    print("ok test_kleinanzeigen_blindness_guard")


if __name__ == "__main__":
    test_pistonheads_parser()
    test_ratsun_parser()
    test_retrorides_parser()
    test_trovit_parser()
    test_trovit_de_parser()
    test_kleinanzeigen_parser()
    test_kleinanzeigen_german_thousands_dot()
    test_kleinanzeigen_blindness_guard()
    print("all gap-sweep tests passed")
