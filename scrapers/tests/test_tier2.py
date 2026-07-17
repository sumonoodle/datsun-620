"""Tier 2 collector parse contracts (offline fixtures). These sources are
degradable: the network path may be blocked, but the parsing must be proven
so a future unblock needs no code changes."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate
from listings import carsandbids, hemmings

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_hemmings_parser():
    records = hemmings.parse_page((FIXTURES / "hemmings_page.html").read_text(), FX_DAY)
    # All-620s policy: the 1973 standard cab is included too, unflagged.
    assert [r["id"] for r in records] == ["hemmings:2789001", "hemmings:2789002"]
    assert records[1]["king_cab"]["matched"] is False
    golden = records[0]
    assert golden["id"] == "hemmings:2789001"
    assert golden["price"]["amount"] == 13995
    assert golden["year"] == 1979
    assert golden["king_cab"]["matched"]
    validate(_full(golden), "listing")
    print("ok test_hemmings_parser")


def test_carsandbids_parser():
    payload = json.loads((FIXTURES / "carsandbids_api.json").read_text())
    records = carsandbids.parse_auctions(payload, FX_DAY)
    # All-620s policy: the 1976 standard cab is included too, unflagged.
    assert [r["id"] for r in records] == ["carsandbids:abc123-1978-datsun-620-king-cab",
                                          "carsandbids:def456-1976-datsun-620-pickup"]
    assert records[1]["king_cab"]["matched"] is False
    golden = records[0]
    assert golden["id"] == "carsandbids:abc123-1978-datsun-620-king-cab"
    assert golden["price"]["amount"] == 7200
    assert golden["region"] == "CA"
    assert golden["status"] == "active"
    validate(_full(golden), "listing")
    print("ok test_carsandbids_parser")


if __name__ == "__main__":
    test_hemmings_parser()
    test_carsandbids_parser()
    print("all tier2 tests passed")
