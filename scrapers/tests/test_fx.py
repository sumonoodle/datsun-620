"""FX module tests. Offline: uses a saved Frankfurter response, no network."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.schema import validate

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "frankfurter.json").read_text())


def test_parse_rates():
    day = fx.parse_rates(FIXTURE)
    assert day["base"] == "GBP"
    assert day["date"] == FIXTURE["date"]
    assert set(day["rates"]) == set(fx.SYMBOLS)
    print("ok test_parse_rates")


def test_parse_rates_rejects_missing_symbol():
    broken = {"date": "2026-07-14", "rates": {"USD": 1.3}}
    try:
        fx.parse_rates(broken)
    except ValueError:
        print("ok test_parse_rates_rejects_missing_symbol")
    else:
        raise AssertionError("expected ValueError for missing symbols")


def test_append_and_validate_log():
    day = fx.parse_rates(FIXTURE)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fx-rates.json"
        fx.append_rates(path, day)
        # Same date twice must not duplicate.
        log = fx.append_rates(path, day)
    assert len(log["history"]) == 1
    assert log["latest"]["date"] == day["date"]
    validate(log, "fx-rates")
    print("ok test_append_and_validate_log")


def test_to_gbp():
    day = fx.parse_rates(FIXTURE)
    usd_rate = day["rates"]["USD"]
    assert fx.to_gbp(1000, "USD", day) == round(1000 / usd_rate, 2)
    assert fx.to_gbp(500, "GBP", day) == 500
    assert fx.to_gbp(None, "USD", day) is None
    print("ok test_to_gbp")


if __name__ == "__main__":
    test_parse_rates()
    test_parse_rates_rejects_missing_symbol()
    test_append_and_validate_log()
    test_to_gbp()
    print("all fx tests passed")
