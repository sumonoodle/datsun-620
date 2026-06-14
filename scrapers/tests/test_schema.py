"""Validate the placeholder data files against the schema contract.

Run from the repo root:
    python -m pytest scrapers/tests
or without pytest:
    python scrapers/tests/test_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common.schema import load_data, validate  # noqa: E402


def check(data_file: str, schema_name: str, *, each: bool) -> list[str]:
    data = load_data(data_file)
    errors: list[str] = []
    if each:
        for i, item in enumerate(data):
            for msg in validate(item, schema_name):
                errors.append(f"{data_file}[{i}] {msg}")
    else:
        for msg in validate(data, schema_name):
            errors.append(f"{data_file} {msg}")
    return errors


CASES = [
    ("listings.json", "listing", True),
    ("specs.json", "spec-variant", True),
    ("fx-rates.json", "fx-rate", True),
    ("specs-conflicts.json", "spec-conflict", True),
    ("specs-decisions.json", "spec-decision", True),
]


def test_placeholder_data_matches_schema():
    all_errors: list[str] = []
    for data_file, schema_name, each in CASES:
        all_errors.extend(check(data_file, schema_name, each=each))
    assert not all_errors, "Schema validation failed:\n" + "\n".join(all_errors)


if __name__ == "__main__":
    errors: list[str] = []
    for data_file, schema_name, each in CASES:
        errors.extend(check(data_file, schema_name, each=each))
    if errors:
        print("FAIL: schema validation errors:")
        for e in errors:
            print("  -", e)
        sys.exit(1)
    print("OK: all placeholder data validates against the schema contract.")
