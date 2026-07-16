"""Japan experiment tests: parse contracts for Goo-net and Buyee (offline
fixtures) and the never-fail translation module."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx, translate
from common.schema import validate
from listings import goonet, yahoo_buyee

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _full(rec, day="2026-07-14"):
    return rec | {"first_seen": day, "last_seen": day,
                  "history": [{"date": day, "status": rec["status"], "price": rec["price"]}]}


def test_goonet_parser():
    records = goonet.parse_page((FIXTURES / "goonet_page.html").read_text(), FX_DAY)
    assert len(records) == 1, [r["id"] for r in records]
    golden = records[0]
    assert golden["id"] == "goonet:700123456"
    assert golden["price"]["amount"] == 15800 and golden["price"]["currency"] == "USD"
    assert golden["country"] == "JP" and golden["drive_side"] == "RHD"
    validate(_full(golden), "listing")
    print("ok test_goonet_parser")


def test_buyee_parser():
    records = yahoo_buyee.parse_page((FIXTURES / "buyee_page.html").read_text(), FX_DAY)
    ids = [r["id"] for r in records]
    assert ids == ["yahoo_buyee:x1234567890"], ids
    # katakana King Cab matched; standard cab skipped; the tail lamp sold
    # FOR a King Cab (King Cab 用) excluded by the Japanese parts filter.
    golden = next(r for r in records if r["id"] == "yahoo_buyee:x1234567890")
    assert golden["price"]["amount"] == 550000 and golden["price"]["currency"] == "JPY"
    assert golden["price"]["gbp"] == round(550000 / FX_DAY["rates"]["JPY"], 2)
    assert golden["images"] == ["https://auctions.c.yimg.jp/images/x1234567890.jpg"]
    validate(_full(golden), "listing")
    print("ok test_buyee_parser")


def test_translation_spot_check():
    """PRD 9 asks for translation spot-checked on three Japanese listings.
    With both Japan sources IP-blocked there are no live listings to use, so
    this pins the mechanism against a canned DeepL response instead: three
    realistic titles must round-trip through the DeepL code path."""
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
    test_goonet_parser()
    test_buyee_parser()
    test_translation_spot_check()
    test_translate_never_fails()
    print("all japan tests passed")
