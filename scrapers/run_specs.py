"""Orchestrate a specs refresh.

Loads the variant registry, runs every collector (a blocked or failing source
is skipped and flagged, not fatal), reconciles all observations against any
recorded decisions, and writes:
  data/specs.json            reconciled specs (the site reads this)
  data/specs-conflicts.json  open conflicts for review
  data/specs-report.json     per-source status + counts (audit + site panel)

Run from the repo root:  python scrapers/run_specs.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.specs_reconcile import reconcile  # noqa: E402
from specs import datsuntrucks, fastestlaps, manual_seed, wikipedia  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
COLLECTORS = [wikipedia, datsuntrucks, fastestlaps, manual_seed]


def main() -> int:
    registry = json.loads((DATA / "variant-registry.json").read_text(encoding="utf-8"))
    decisions = json.loads((DATA / "specs-decisions.json").read_text(encoding="utf-8"))

    observations = []
    sources = []
    for mod in COLLECTORS:
        result = mod.collect(registry)
        sources.append({"source": result.source, "ok": result.ok, "note": result.note, "facts": len(result.observations)})
        status = "ok" if result.ok else "SKIPPED"
        print(f"  [{status}] {result.source}: {len(result.observations)} facts {('- ' + result.note) if result.note else ''}")
        observations.extend(result.observations)

    variants, conflicts = reconcile(observations, registry, decisions)

    (DATA / "specs.json").write_text(json.dumps(variants, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (DATA / "specs-conflicts.json").write_text(json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = {
        "generated_at": date.today().isoformat(),
        "variant_count": len(variants),
        "markets": sorted({v["market"] for v in variants}),
        "conflict_count": len(conflicts),
        "sources": sources,
    }
    (DATA / "specs-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"\n{len(variants)} variants across {len(report['markets'])} markets; {len(conflicts)} open conflicts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
