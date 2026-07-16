"""King Cab filter regression tests. Zero false positives is a v1 success
criterion; every miss found in the wild becomes a case here."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab

POSITIVES = [
    ("1978 Datsun 620 King Cab Deluxe", None),
    ("Datsun 620 KINGCAB 1977", None),
    ("Datsun 620 King-Cab pickup", None),
    ("1979 Datsun 620 extended cab", None),
    ("Datsun pickup", "restored king cab with new interior"),
]

NEGATIVES = [
    ("1975 Datsun 620 Pickup standard cab", None),
    ("Datsun 620 long bed", "clean short bed truck"),
    ("1972 Datsun 240Z", None),
    ("Datsun 620 regular cab", "often mistaken for a King Cab"),  # needs body veto
]


def test_positives():
    for title, desc in POSITIVES:
        result = king_cab.check(title, desc)
        assert result["matched"], f"false negative: {title!r}"
        assert result["matched_terms"], title
    print("ok test_positives")


def test_negatives():
    for title, desc in NEGATIVES[:3]:
        result = king_cab.check(title, desc)
        assert not result["matched"], f"false positive: {title!r}"
    print("ok test_negatives")


def test_body_style_veto():
    # Description mentions King Cab, but the body-style field says otherwise.
    result = king_cab.check(
        "Datsun 620 regular cab", "often mistaken for a King Cab", body_style="Regular Cab"
    )
    assert result["body_style_check"] == "fail"
    assert not result["matched"], "body-style veto did not override text mention"

    confirmed = king_cab.check("1977 Datsun 620 King Cab", body_style="Extended Cab Pickup")
    assert confirmed["body_style_check"] == "pass"
    assert confirmed["matched"]
    print("ok test_body_style_veto")


if __name__ == "__main__":
    test_positives()
    test_negatives()
    test_body_style_veto()
    print("all king cab tests passed")
