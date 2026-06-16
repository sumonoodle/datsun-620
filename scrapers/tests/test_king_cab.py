"""King Cab scoring tests: recall-first, multilingual, with signal trails."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab  # noqa: E402


def test_english_king_cab_scores_high():
    s, sig = king_cab.score("1978 Datsun 620 King Cab 5-Speed")
    assert s >= 0.9
    assert "en:king cab" in sig


def test_japanese_kingcab_scores_high():
    s, sig = king_cab.score("ダットサン 620 キングキャブ 1977")
    assert s >= 0.9
    assert "ja:キングキャブ" in sig


def test_extended_cab_is_medium():
    s, sig = king_cab.score("Datsun 620 extended cab project")
    assert 0.6 <= s < 0.9
    assert "en:extended cab" in sig


def test_plain_620_kept_but_low():
    s, sig = king_cab.score("Datsun 620 pickup, runs great")
    assert s == 0.3  # recall-first: kept, ranked low
    assert sig == []


def test_explicit_other_cab_scores_lowest():
    s, sig = king_cab.score("Datsun 620 standard cab long bed")
    assert s <= 0.15
    assert "-en:standard cab" in sig


def _run():
    fails = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print(f"  PASS {name}")
            except AssertionError as e:
                fails.append(f"{name}: {e}"); print(f"  FAIL {name}: {e}")
    return fails


if __name__ == "__main__":
    if _run():
        sys.exit(1)
    print("OK: King Cab scoring behaves correctly.")
