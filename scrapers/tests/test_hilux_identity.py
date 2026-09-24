"""Hilux identity rules (common/hilux.py): which titles are a 3rd-gen
petrol Hilux, and which of those look like the owner's reference RN30."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux


def test_reference_truck():
    # The owner's reference listing on Car & Classic, as titled there.
    r = hilux.classify("1980 Toyota Hilux RN30",
                       "Original 12R engine. Upgraded to 5-speed gearbox.")
    assert r and r["year"] == 1980
    assert r["variant"] == {"chassis_code": "RN30", "drive": "2WD", "target_match": True,
                            "target_reasons": ["chassis code RN30", "12R engine"]}, r
    assert r["king_cab"]["matched"] is False
    print("ok test_reference_truck")


def test_us_naming():
    # North America never used the Hilux name.
    r = hilux.classify("1981 Toyota Pickup SR5 Long Bed", "20R, 5 speed")
    assert r and r["year"] == 1981 and r["variant"]["target_match"] is False
    r = hilux.classify("1982 Toyota SR5 4x4 Truck", None)
    assert r and r["variant"]["drive"] == "4WD"
    # Same name, wrong generation.
    assert hilux.classify("1986 Toyota Pickup SR5 Xtracab", None) is None
    assert hilux.classify("1975 Toyota Hi-Lux", None) is None
    print("ok test_us_naming")


def test_year_rules():
    # No year and no code: a modern Hilux is far more likely.
    assert hilux.classify("Toyota Hilux Invincible", None) is None
    # A code vouches for an undated listing.
    r = hilux.classify("Toyota Hilux RN34 long bed project", None)
    assert r and r["year"] is None and r["variant"]["chassis_code"] == "RN34"
    # 1984 only with a 3rd-gen code (UK/AU stock registrations).
    assert hilux.classify("1984 Toyota Hilux pickup", None) is None
    assert hilux.classify("1984 Toyota Hilux RN30", None)["year"] == 1984
    # Prices are not years.
    assert hilux.classify("Toyota Hilux RN30 £1980 ono", None)["year"] is None
    # Showa-era Japanese dating: 昭和55年 = 1980.
    assert hilux.classify("ハイラックス 昭和55年 ガソリン", None)["year"] == 1980
    print("ok test_year_rules")


def test_diesel_and_other_models():
    assert hilux.classify("1981 Toyota Hilux LN40 diesel", None) is None
    assert hilux.classify("1982 Toyota Hilux 2.2 diesel", None) is None
    assert hilux.classify("1980 Toyota Hilux", "Runs on diesel, 2L engine") is None
    # Petrol stated beats a stray "diesel" mention in the description.
    assert hilux.classify("1980 Toyota Hilux", "petrol, not the diesel") is not None
    # Wrong generation codes.
    assert hilux.classify("1977 Toyota Hilux RN25", None) is None
    assert hilux.classify("Toyota Hilux RN65 1983 Xtracab", None) is None
    # Other Toyota trucks.
    assert hilux.classify("1983 Toyota Land Cruiser pickup", None) is None
    assert hilux.classify("1984 Toyota 4Runner", None) is None
    print("ok test_diesel_and_other_models")


def test_target_and_extended_cab():
    r = hilux.classify("1979 Toyota Hilux 1600", "1.6 litre petrol, 4 speed")
    assert r["variant"]["target_match"] and r["variant"]["target_reasons"] == ["1.6 litre engine"]
    # A 4WD is never "like the reference truck".
    r = hilux.classify("1981 Toyota Hilux RN30 4x4 conversion", None)
    assert r["variant"]["drive"] == "4WD" and r["variant"]["target_match"] is False
    r = hilux.classify("1983 Toyota Hilux Xtracab RN44", None)
    assert r["king_cab"]["matched"] and r["king_cab"]["matched_terms"] == ["xtracab"]
    r = hilux.classify("1983 Toyota Hilux extra cab", None, body_style="Regular Cab")
    assert r["king_cab"]["matched"] is False
    print("ok test_target_and_extended_cab")


def test_real_misfires_2026_09_24():
    # Real titles from the first Hilux fixtures that the first rules kept.
    assert hilux.classify("1978 Toyota Hilux/Pickup (N20 1972-1978)", None) is None
    assert hilux.classify("52k-Mile Survivor: 1990 Toyota Pickup 4×4",
                          "a truck from the 1980s, bought new in 1980") is None
    assert hilux.classify("1977-1983 Toyota Pickup Tail Light Lenses", None) is None
    assert hilux.classify("1980 Toyota Hilux 'Minitrek' Hot Wheels", None) is None
    assert hilux.extract_year("built in the 1980s") is None
    # Still fine: a manual gearbox, and a decade-free description year.
    assert hilux.classify("1980 Toyota Hilux manual 4 speed", None) is not None
    assert hilux.classify("Toyota Hilux RN30", "first registered 1980")["year"] == 1980
    print("ok test_real_misfires_2026_09_24")


def test_code_table():
    # Last digit 6/7/8 = 4WD, whatever the text says.
    assert hilux.classify("1980 Toyota Hilux RN36", None)["variant"]["drive"] == "4WD"
    assert hilux.classify("1982 Toyota Hilux RN41", None)["variant"]["drive"] == "2WD"
    # Japan's 12R-J short body counts as the reference truck; the long
    # body 1.6 (RN40) doesn't.
    assert hilux.classify("ハイラックス RN35 1981", None)["variant"]["target_match"]
    assert not hilux.classify("1980 Toyota Hilux RN40 1600", None)["variant"]["target_match"]
    # Popular Series RN35 to 1988 in Japan; a codeless 1987 stays out.
    assert hilux.classify("1987 ハイラックス RN35", None)["year"] == 1987
    assert hilux.classify("1987 Toyota Hilux 1600", None) is None
    # US model year 1978 is the 2nd gen; a Hilux-named 1978 is fine.
    assert hilux.classify("1978 Toyota Pickup SR5", None) is None
    assert hilux.classify("1978 Toyota Hilux", None) is not None
    # 22R-E is the 4th gen's injected engine.
    assert hilux.classify("1983 Toyota Pickup 22RE", None) is None
    print("ok test_code_table")


if __name__ == "__main__":
    test_reference_truck()
    test_us_naming()
    test_year_rules()
    test_diesel_and_other_models()
    test_target_and_extended_cab()
    test_real_misfires_2026_09_24()
    test_code_table()
