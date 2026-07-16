"""Failure isolation proof, required by PRD M3: a crashing source must never
fail the daily run. Runs the real orchestrator with one healthy source and one
that raises, in a temp data dir with stubbed FX."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
import run_daily

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def _healthy(fx_day):
    from listings import bat
    return bat.parse_page((FIXTURES / "bat_page.html").read_text(), fx_day)


def _crashing(fx_day):
    raise RuntimeError("simulated source outage (HTTP 403)")


def test_crashing_source_never_fails_the_run():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        rc = run_daily.run(
            data_dir=data_dir,
            fx_fetch=lambda: dict(FX_DAY),
            sources=[("bringatrailer", _healthy), ("hemmings", _crashing)],
        )
        assert rc == 0, "run failed despite per-source isolation"

        run_log = json.loads((data_dir / "run-log.json").read_text())
        by_source = {s["source"]: s for s in run_log["sources"]}
        assert by_source["bringatrailer"]["ok"] and by_source["bringatrailer"]["records"] == 2
        assert not by_source["hemmings"]["ok"]
        assert "simulated source outage" in by_source["hemmings"]["note"]
        assert by_source["hemmings"]["consecutive_failures"] == 1

        # Healthy source's records made it into the store despite the crash.
        listings = json.loads((data_dir / "listings.json").read_text())["listings"]
        assert len(listings) == 2

        # Second run: failure counter must accumulate (drives the 7-day rule).
        rc = run_daily.run(
            data_dir=data_dir,
            fx_fetch=lambda: dict(FX_DAY),
            sources=[("bringatrailer", _healthy), ("hemmings", _crashing)],
        )
        assert rc == 0
        run_log = json.loads((data_dir / "run-log.json").read_text())
        hemmings = next(s for s in run_log["sources"] if s["source"] == "hemmings")
        assert hemmings["consecutive_failures"] == 2
    print("ok test_crashing_source_never_fails_the_run")


if __name__ == "__main__":
    test_crashing_source_never_fails_the_run()
    print("all isolation tests passed")
