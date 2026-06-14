"""Collector: manually captured facts from sources that block scraping.

Reads data/specs-manual.json. This is the PRD's documented fallback for sources
like CarsGuide that return HTTP 403 to scripts: the value is captured by hand
but keeps a real citation, so it participates in reconciliation like any source.
"""

from __future__ import annotations

import json
from pathlib import Path

from common.observations import CollectorResult, Observation

SOURCE = "manual seed (blocked sources)"
PATH = Path(__file__).resolve().parents[2] / "data" / "specs-manual.json"


def collect(registry: dict) -> CollectorResult:
    try:
        data = json.loads(PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return CollectorResult(SOURCE, ok=False, note=f"could not read specs-manual.json: {e}")

    valid_ids = {v["id"] for v in registry["variants"]}
    obs: list[Observation] = []
    for o in data.get("observations", []):
        if o["variant_id"] not in valid_ids:
            continue
        obs.append(
            Observation(
                o["variant_id"], o["field"], o["value"],
                o.get("source_name", SOURCE), o.get("source_url", ""), o.get("raw", ""),
            )
        )
    return CollectorResult(SOURCE, ok=True, observations=obs)
