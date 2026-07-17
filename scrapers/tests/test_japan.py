"""Japan collector tests: Goo-net Exchange, Carsensor and Yahoo Auctions
parse contracts (offline fixtures trimmed from real 2026-07-17 pages) plus
the never-fail translation module.

The retired goonet/yahoo_buyee collectors' lessons carry over: fixtures
include a King Cab of the WRONG era (D21/D22 trucks kept the Datsun Truck
name until 2002 and had King Cab grades of their own) and Japanese parts
titled with King Cab terms.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx, translate
from common.schema import validate
from listings import carsensor, goonet_exchange, yahoo_auctions

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_goonet_exchange_parser():
    records = goonet_exchange.parse_page(
        (FIXTURES / "goonet_exchange_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # All-620s policy: the era gate does the work — the 1996 LONG and the
    # 1990 D21 KING CAB stay out, the 1978 King Cab AND the 1975 standard
    # DX both come in (only the former KC-flagged).
    assert ids == ["goonet_exchange:988000000000000000001",
                   "goonet_exchange:988000000000000000003"], ids
    golden = records[0]
    assert golden["year"] == 1978
    assert golden["price"]["amount"] == 2850000 and golden["price"]["currency"] == "JPY"
    assert golden["price"]["gbp"] == round(2850000 / FX_DAY["rates"]["JPY"], 2)
    assert golden["country"] == "JP" and golden["drive_side"] == "RHD"
    assert golden["king_cab"]["matched"] is True
    validate(_full(golden), "listing")

    std = records[1]
    assert std["year"] == 1975
    assert std["king_cab"]["matched"] is False
    validate(_full(std), "listing")
    print("ok test_goonet_exchange_parser")


def test_carsensor_parser():
    records = carsensor.parse_page((FIXTURES / "carsensor_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    # 2001 double cab out (era), 1990 D21 King Cab out (era), 1978 620 in.
    assert ids == ["carsensor:AU0000000001"], ids
    golden = records[0]
    assert golden["year"] == 1978
    assert golden["price"]["amount"] == 3_500_000, golden["price"]  # 350万円
    validate(_full(golden), "listing")
    print("ok test_carsensor_parser")


def test_yahoo_open_parser():
    records, raw = yahoo_auctions.parse_open(
        (FIXTURES / "yahoo_open_page.html").read_text(), FX_DAY)
    assert raw == 6, raw
    ids = [r["id"] for r in records]
    # Excluded: the real lowering-block part, the cheap fixed-price item
    # (price floor), the 720 King Cab, the A16205 part number, and the
    # first live run's escapee — a 720 diff keyword-stuffed with
    # "620 520 521 D21" (cross-generation rule).
    assert ids == ["yahoo_auctions:x9000000001"], ids
    assert "yahoo_auctions:d1234126705" not in ids, "keyword-stuffed part leaked"
    golden = records[0]
    assert golden["year"] == 1978  # 昭和53年
    assert golden["price"]["amount"] == 1_500_000
    assert golden["status"] == "active"
    validate(_full(golden), "listing")
    print("ok test_yahoo_open_parser")


def test_yahoo_vehicle_scoped_parser():
    """Category-scoped (auccat=26360) queries trust the vehicle category:
    no word list, no floor, and an era-dated ダットサントラック counts
    without a literal 620 — but other generations still never pass."""
    def product(pid, title, price):
        return (f'<li class="Product"><a class="Product__titleLink" '
                f'data-auction-id="{pid}" data-auction-title="{title}" '
                f'data-auction-price="{price}" '
                f'href="https://auctions.yahoo.co.jp/jp/auction/{pid}">{title}</a>'
                f'<span class="Product__price"><span class="Product__label">現在</span>'
                f'<span class="Product__priceValue">{price}円</span></span></li>')
    html = "<ul>" + "".join([
        product("v9000000001", "昭和53年 ダットサントラック 実働 新品ホイール付", 350000),
        product("v9000000002", "日産 ダットサントラック DX 平成8年", 800000),   # D21 era
        product("v9000000003", "ダットサン 620 キングキャブ レストアベース", 90000),
    ]) + "</ul>"
    records, raw = yahoo_auctions.parse_open(html, FX_DAY, vehicle_scoped=True)
    ids = [r["id"] for r in records]
    assert raw == 3, raw
    # The era-dated truck passes despite the parts word ホイール and no "620";
    # the 平成8年 (1996) truck is out; the cheap 620 KC passes (no floor in
    # the vehicle category — real trucks can sit at low bids).
    assert ids == ["yahoo_auctions:v9000000001", "yahoo_auctions:v9000000003"], ids
    validate(_full(records[0]), "listing")
    print("ok test_yahoo_vehicle_scoped_parser")


def test_yahoo_closed_parser():
    records, raw = yahoo_auctions.parse_closed(
        (FIXTURES / "yahoo_closed_page.html").read_text(), FX_DAY)
    assert raw == 3, raw
    ids = [r["id"] for r in records]
    # The real fender mirror (parts tree) and the door panel sold from the
    # parts tree despite its truck-like title must both be excluded: only
    # the 中古車・新車 (whole vehicle) category item survives.
    assert ids == ["yahoo_auctions:c9000000010"], ids
    golden = records[0]
    assert golden["status"] == "sold"
    assert golden["year"] == 1977  # 昭和52年
    assert golden["price"]["amount"] == 820000
    validate(_full(golden), "listing")
    print("ok test_yahoo_closed_parser")


def test_translation_spot_check():
    """PRD 9 asks for translation spot-checked on three Japanese listings.
    Pins the mechanism against a canned DeepL response: three realistic
    titles must round-trip through the DeepL code path."""
    import os
    from unittest.mock import patch

    titles = {
        "ダットサン 620 キングキャブ 1978年 レストア済": "Datsun 620 King Cab 1978, restored",
        "ダットサントラック カスタム 昭和52年": "Datsun Truck Custom, 1977",
        "日産 ダットサン 620 ピックアップ 実働": "Nissan Datsun 620 pickup, running",
    }

    class FakeResponse:
        status_code = 200
        def __init__(self, text):
            self._text = text
        def json(self):
            return {"translations": [{"text": self._text}]}

    def fake_post(url, headers=None, data=None, timeout=None):
        return FakeResponse(titles[data["text"]])

    with patch.dict(os.environ, {"DEEPL_API_KEY": "test-key"}), \
         patch.object(translate.httpx, "post", fake_post):
        for ja, en in titles.items():
            assert translate.translate(ja) == en, f"spot check failed for {ja!r}"
    print("ok test_translation_spot_check (3 titles)")


def test_translate_never_fails():
    assert translate.needs_translation("ダットサン 620 キングキャブ")
    assert not translate.needs_translation("1978 Datsun 620 King Cab")
    assert translate.translate("plain english") is None
    # With no API key and no network, the fallback fails quietly -> None.
    result = translate.translate("ダットサン 620")
    assert result is None or isinstance(result, str)
    print("ok test_translate_never_fails")


if __name__ == "__main__":
    test_goonet_exchange_parser()
    test_carsensor_parser()
    test_yahoo_open_parser()
    test_yahoo_vehicle_scoped_parser()
    test_yahoo_closed_parser()
    test_translation_spot_check()
    test_translate_never_fails()
    print("all japan tests passed")
