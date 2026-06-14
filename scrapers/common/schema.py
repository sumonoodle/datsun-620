"""Shared schema loading and validation.

This is the contract every other agent codes against. JSON Schema files live in
schema/ so both the Python scrapers and the TypeScript site validate against the
same definitions. Keep this thin: it loads a schema and validates data against it.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
DATA_DIR = REPO_ROOT / "data"


def load_schema(name: str) -> dict:
    """Load a JSON Schema by file stem, e.g. load_schema('listing')."""
    path = SCHEMA_DIR / f"{name}.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_data(filename: str):
    """Load a data file by name, e.g. load_data('listings.json')."""
    path = DATA_DIR / filename
    return json.loads(path.read_text(encoding="utf-8"))


def validate(instance, schema_name: str) -> list[str]:
    """Validate an instance against a named schema. Returns a list of error
    messages (empty list means valid)."""
    validator = Draft202012Validator(load_schema(schema_name))
    return [
        f"{list(e.absolute_path)}: {e.message}"
        for e in validator.iter_errors(instance)
    ]
