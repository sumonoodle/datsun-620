"""Reconciler behaviour tests.

Proves the three paths the conflicts feature depends on:
  1. sources agree -> value auto-accepted, no conflict
  2. sources disagree -> conflict raised, leaf left empty
  3. a recorded decision -> conflict resolved to the chosen value
Run:  python scrapers/tests/test_reconcile.py   (or via pytest)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.observations import Observation  # noqa: E402
from common.specs_reconcile import reconcile  # noqa: E402

REGISTRY = {"variants": [{"id": "t1", "market": "Japan", "years": "1972 to 1979", "body_style": "standard cab", "bed_length": "short"}]}


def _obs(field, value, src):
    return Observation("t1", field, value, src, f"https://example.com/{src}", str(value))


def test_agreement_accepts():
    obs = [_obs("dimensions.length_mm", 4298, "a"), _obs("dimensions.length_mm", 4300, "b")]  # within tolerance
    variants, conflicts = reconcile(obs, REGISTRY, [])
    assert conflicts == []
    assert variants[0]["dimensions"]["value"]["length_mm"] in (4298, 4300)
    assert len(variants[0]["dimensions"]["citations"]) == 2


def test_disagreement_conflicts():
    obs = [_obs("dimensions.length_mm", 4298, "a"), _obs("dimensions.length_mm", 4609, "b")]  # far apart
    variants, conflicts = reconcile(obs, REGISTRY, [])
    assert len(conflicts) == 1
    assert conflicts[0]["field"] == "dimensions.length_mm"
    assert {c["value"] for c in conflicts[0]["candidates"]} == {4298, 4609}
    assert "length_mm" not in variants[0].get("dimensions", {}).get("value", {})


def test_decision_resolves():
    obs = [_obs("dimensions.length_mm", 4298, "a"), _obs("dimensions.length_mm", 4609, "b")]
    decisions = [{"variant_id": "t1", "field": "dimensions.length_mm", "chosen_value": 4609, "decided_on": "2026-06-14"}]
    variants, conflicts = reconcile(obs, REGISTRY, decisions)
    assert conflicts == []
    assert variants[0]["dimensions"]["value"]["length_mm"] == 4609


def _run():
    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as e:
                failures.append(f"{name}: {e}")
                print(f"  FAIL {name}: {e}")
    return failures


if __name__ == "__main__":
    fails = _run()
    if fails:
        sys.exit(1)
    print("OK: reconciler behaves correctly (agree / conflict / decision).")
