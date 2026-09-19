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
        assert by_source["bringatrailer"]["ok"] and by_source["bringatrailer"]["records"] == 3
        assert not by_source["hemmings"]["ok"]
        assert "simulated source outage" in by_source["hemmings"]["note"]
        assert by_source["hemmings"]["consecutive_failures"] == 1

        # Healthy source's records made it into the store despite the crash.
        listings = json.loads((data_dir / "listings.json").read_text())["listings"]
        assert len(listings) == 3

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


def _quiet(fx_day):
    """Completes cleanly and finds nothing — eBay's month in one function."""
    return []


def test_quiet_streak_counts_and_resets():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        run = lambda srcs: run_daily.run(data_dir=data_dir,
                                         fx_fetch=lambda: dict(FX_DAY), sources=srcs)

        def streak(name):
            log = json.loads((data_dir / "run-log.json").read_text())
            return next(s for s in log["sources"]
                        if s["source"] == name)["consecutive_zero_runs"]

        # An "ok but empty" source accumulates a quiet streak; a producing
        # one never does. This is the signal that did not exist while eBay
        # reported ok/0 for a month.
        for expected in (1, 2, 3):
            assert run([("ebay", _quiet), ("bringatrailer", _healthy)]) == 0
            assert streak("ebay") == expected
            assert streak("bringatrailer") == 0

        # One find clears it: the source is demonstrably still seeing stock.
        assert run([("ebay", _healthy), ("bringatrailer", _healthy)]) == 0
        assert streak("ebay") == 0

        # A FAILING run carries the count forward rather than adding to it —
        # everycar's five 404 days were a failure, not five quiet days, and
        # conflating them would have double-counted one problem as two.
        assert run([("ebay", _quiet), ("bringatrailer", _healthy)]) == 0
        assert streak("ebay") == 1
        for _ in range(3):
            assert run([("ebay", _crashing), ("bringatrailer", _healthy)]) == 0
            assert streak("ebay") == 1
        # ...and resumes from where it left off once the source answers again.
        assert run([("ebay", _quiet), ("bringatrailer", _healthy)]) == 0
        assert streak("ebay") == 2
    print("ok test_quiet_streak_counts_and_resets")


if __name__ == "__main__":
    test_crashing_source_never_fails_the_run()
    test_quiet_streak_counts_and_resets()
    print("all isolation tests passed")
