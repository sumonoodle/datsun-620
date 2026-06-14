"""The shared currency between spec collectors and the reconciler.

A collector turns a source into a flat list of Observations. An Observation is
one fact, about one variant, from one source, normalised to canonical units,
with the original text kept for the citation.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any


@dataclass
class Observation:
    variant_id: str
    field: str  # dotted leaf path, e.g. "dimensions.length_mm" or "engine.power_hp"
    value: Any  # canonical units (mm, kg, cc, hp, Nm) or string/list
    source_name: str
    source_url: str
    raw: str = ""  # the value as the source stated it, for the citation

    def as_dict(self) -> dict:
        return {
            "variant_id": self.variant_id,
            "field": self.field,
            "value": self.value,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "raw": self.raw,
        }


@dataclass
class CollectorResult:
    """What a collector returns: its observations plus whether it succeeded.
    A blocked or errored source reports ok=False with a note, so the run can
    continue and flag the skip rather than failing silently."""

    source: str
    ok: bool
    observations: list[Observation] = dc_field(default_factory=list)
    note: str = ""
