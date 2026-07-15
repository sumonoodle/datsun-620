"""Validation helpers for the shared schema contract in schema/."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schema"
DATA_DIR = REPO_ROOT / "data"


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text())


def validate(instance: dict, schema_name: str) -> None:
    """Raise jsonschema.ValidationError if `instance` breaks the contract."""
    jsonschema.validate(
        instance,
        load_schema(schema_name),
        format_checker=jsonschema.FormatChecker(),
    )


def validate_data_file(filename: str, schema_name: str) -> None:
    validate(json.loads((DATA_DIR / filename).read_text()), schema_name)
