"""Reconcile observations from many sources into one spec per variant.

Per leaf field, across all sources:
  - if a recorded human decision exists, use it (conflict stays resolved);
  - else if sources agree (numbers within tolerance, others exact), auto-accept
    with all citations;
  - else open a conflict: the leaf is left empty and the candidates are listed
    for review.
Fields no source covered are simply absent (a gap).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from common.observations import Observation

# Numbers from different sources agree if within this relative tolerance.
TOLERANCE = 0.02

# Output groups assembled from dotted "group.leaf" observation fields.
GROUPS = ("engine", "dimensions", "weights", "wheels_tyres", "trim_levels", "production_changes", "transmission")

# Identity fields copied from the registry into each output variant.
IDENTITY = ("id", "market", "years", "body_style", "bed_length")


def _numbers_agree(values: list[float]) -> bool:
    lo, hi = min(values), max(values)
    if hi == 0:
        return True
    return (hi - lo) / abs(hi) <= TOLERANCE


def _agree(values: list[Any]) -> bool:
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
        return _numbers_agree([float(v) for v in values])
    return len(set(map(str, values))) == 1


def _citation(o: Observation) -> dict:
    return {"value": o.raw or o.value, "source_url": o.source_url, "source_name": o.source_name}


def reconcile(
    observations: list[Observation], registry: dict, decisions: list[dict]
) -> tuple[list[dict], list[dict]]:
    decision_map = {(d["variant_id"], d["field"]): d for d in decisions}

    # variant_id -> leaf field -> list[Observation]
    by_variant: dict[str, dict[str, list[Observation]]] = defaultdict(lambda: defaultdict(list))
    for o in observations:
        by_variant[o.variant_id][o.field].append(o)

    variants_out: list[dict] = []
    conflicts_out: list[dict] = []

    for v in registry["variants"]:
        vid = v["id"]
        out = {k: v[k] for k in IDENTITY if k in v}
        groups: dict[str, dict] = {}

        for field, obs in by_variant.get(vid, {}).items():
            group, _, leaf = field.partition(".")
            if not leaf:
                group, leaf = field, "value"  # bare fields land under a single leaf
            grp = groups.setdefault(group, {"value": {}, "citations": []})

            decision = decision_map.get((vid, field))
            if decision is not None:
                grp["value"][leaf] = decision["chosen_value"]
                grp["citations"].extend(_citation(o) for o in obs if str(o.value) == str(decision["chosen_value"]))
                continue

            values = [o.value for o in obs]
            if _agree(values):
                grp["value"][leaf] = obs[0].value
                grp["citations"].extend(_citation(o) for o in obs)
            else:
                # distinct candidates, grouping sources that share a value
                cand: dict[str, list[str]] = defaultdict(list)
                for o in obs:
                    cand[str(o.value)].append(o.source_name)
                conflicts_out.append({
                    "variant_id": vid,
                    "field": field,
                    "candidates": [
                        {"value": obs_value(obs, k), "source": ", ".join(sorted(set(srcs)))}
                        for k, srcs in cand.items()
                    ],
                    "status": "open",
                })

        # attach only non-empty groups, in the canonical order
        for group in GROUPS:
            g = groups.get(group)
            if g and g["value"]:
                # de-dup citations
                seen, uniq = set(), []
                for c in g["citations"]:
                    key = (c["source_url"], str(c["value"]))
                    if key not in seen:
                        seen.add(key)
                        uniq.append(c)
                out[group] = {"value": g["value"], "citations": uniq}

        variants_out.append(out)

    return variants_out, conflicts_out


def obs_value(obs: list[Observation], value_key: str):
    """Return the original-typed value for a stringified candidate key."""
    for o in obs:
        if str(o.value) == value_key:
            return o.value
    return value_key
