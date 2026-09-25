"""Digest rendering test: build the HTML from synthetic changes and check the
sections, links and health lines land where they should."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "emailer"))

from common import fx
from listings import bat
import send_digest

FIXTURES = Path(__file__).parent / "fixtures"
FX_DAY = fx.parse_rates(json.loads((FIXTURES / "frankfurter.json").read_text()))


def test_digest_render():
    records = bat.parse_page((FIXTURES / "bat_page.html").read_text(), FX_DAY)
    for r in records:
        r["first_seen"] = r["last_seen"] = "2026-07-14"
        r["history"] = []
    by_id = {r["id"]: r for r in records}
    active_id = next(r["id"] for r in records
                     if r["status"] == "active" and r["king_cab"]["matched"])
    sold = next(r for r in records if r["status"] == "sold")

    changes = {
        "date": "2026-07-14",
        "new": [active_id],
        "price_changed": [{"id": active_id, "old_gbp": 8000.0, "new_gbp": 8944.0, "pct": 11.8}],
        "status_changed": [{"id": sold["id"], "old_status": "active", "new_status": "sold"}],
        "possible_relists": [{"id": active_id, "prior_id": sold["id"],
                              "reasons": ["title similarity 0.88", "same country (US)"]}],
    }
    run_log = {
        "date": "2026-07-14", "started_at": "2026-07-14T05:20:00+00:00",
        "sources": [
            {"source": "bringatrailer", "ok": True, "records": 2, "note": "", "consecutive_failures": 0},
            {"source": "hemmings", "ok": False, "records": 0,
             "note": "HTTP 403 (bot protection / blocked)", "consecutive_failures": 3},
        ],
        "totals": {"active": 1, "by_country": {"US": 1}, "median_gbp": 8199.0},
    }

    html = send_digest.build_html(changes, run_log, by_id, "https://example.test")
    # The new listing is also flagged as a possible relist, so it must appear
    # ONLY in the relists section, not duplicated under "New listings".
    assert "New listings" not in html
    for expected in [
        "Price changes (1)", "Possible relists (1)",
        "Status changes (1)", "Source health", "Summary",
        "1977 Datsun 620 King Cab",          # new listing card
        "£8,000 &rarr; <b>£8,944</b>",       # price movement
        "Possible relist (not certain)",     # heuristic framing
        "3 days running",                    # failure streak
        "Median price: £8,199",
        "https://example.test/",
        "KING CAB",                          # all-620s policy: KCs are tagged
    ]:
        assert expected in html, f"digest missing: {expected!r}"
    assert "tracking" not in html.lower()
    print("ok test_digest_render")


def _src(name, streak, ok=True, records=0):
    return {"source": name, "ok": ok, "records": records, "note": "",
            "consecutive_failures": 0, "consecutive_zero_runs": streak}


def test_quiet_alert_thresholds():
    """The eBay failure mode: 'ok, 0 listings' forever, and nobody notices."""
    A = send_digest.QUIET_RUNS_ALERT
    fired = lambda srcs: [s["source"] for s in send_digest.quiet_alerts(srcs)]

    # Below the threshold nothing fires: most sources hold no 620 most weeks
    # and a daily cry-wolf is exactly what makes an alert stop being read.
    assert fired([_src("ebay", A - 1)]) == []
    assert fired([_src("ebay", A)]) == ["ebay"]

    # Then weekly, not daily — a line that appears every morning is wallpaper.
    R = send_digest.QUIET_REPEAT_EVERY
    assert fired([_src("ebay", A + 1)]) == []
    assert fired([_src("ebay", A + R)]) == ["ebay"]
    assert fired([_src("ebay", A + R + 1)]) == []
    assert fired([_src("ebay", A + 2 * R)]) == ["ebay"]

    # A source that found something is not quiet, whatever its old streak.
    assert fired([_src("trovit", 0, records=3)]) == []
    # A FAILING source is already reported as failing; it must not also be
    # dressed up as a silent one (everycar's five 404 days, 2026-09-15).
    assert fired([_src("everycar", A + 99, ok=False)]) == []
    print("ok test_quiet_alert_thresholds")


def test_quiet_alert_in_digest():
    changes = {"date": "2026-10-06", "new": [], "price_changed": [],
               "status_changed": [], "possible_relists": []}
    run_log = {
        "date": "2026-10-06", "started_at": "2026-10-06T04:20:00+00:00",
        "sources": [
            _src("ebay", send_digest.QUIET_RUNS_ALERT),   # alerts
            _src("kijiji", 6),                            # shows inline only
            _src("trovit", 0, records=3),                 # healthy
        ],
        "totals": {"active": 3, "by_country": {"US": 3}, "median_gbp": 7000.0},
    }
    html = send_digest.build_html(changes, run_log, {}, "https://example.test")
    assert "Worth a look" in html
    assert f"no listings for {send_digest.QUIET_RUNS_ALERT} days running" in html
    # The alert sits ABOVE source health — the failure being fixed is an "ok"
    # nobody scrolls down to question.
    assert html.index("Worth a look") < html.index("Source health")
    # Sub-threshold streaks are still visible, just not alarming.
    assert "quiet 6 days" in html
    assert "Kijiji" in html and "Worth a look</h2>" in html
    # Trovit found something today, so it carries no quiet note at all.
    assert "Trovit: 3 listing(s)</li>" in html
    print("ok test_quiet_alert_in_digest")


def test_known_blocked_is_muted_not_escalated():
    """Blocked by design must not read as broken by accident.

    Cars & Bids and Hemmings are IP-banned; the 7-day escalation already
    fired and the decision was made (email alerts). A banner that never
    changes stops being read, so these render muted and stay out of the
    'sources ok' headline.
    """
    changes = {"date": "2026-09-23", "new": [], "price_changed": [],
               "status_changed": [], "possible_relists": []}
    run_log = {
        "date": "2026-09-23", "started_at": "2026-09-23T00:20:00+00:00",
        "sources": [
            {"source": "carsandbids", "ok": False, "records": 0,
             "note": "HTTP 403 (bot protection / blocked)",
             "consecutive_failures": 73, "consecutive_zero_runs": 0,
             "expected_blocked": True},
            {"source": "kaidee", "ok": False, "records": 0,
             "note": "__NEXT_DATA__ missing", "consecutive_failures": 9,
             "consecutive_zero_runs": 0},
        ],
        "totals": {"active": 23, "by_country": {"US": 12}, "median_gbp": 8995.0},
    }
    out = send_digest.build_html(changes, run_log, {}, "https://example.test")
    assert "blocked 73 days (known" in out
    # The escalation banner belongs to genuinely new breakage only.
    assert "Blocked 73 days: decision needed" not in out
    # A real, unexplained failure still shouts.
    assert "Kaidee" in out and "skipped" in out
    print("ok test_known_blocked_is_muted_not_escalated")


if __name__ == "__main__":
    test_digest_render()
    test_quiet_alert_thresholds()
    test_quiet_alert_in_digest()
    test_known_blocked_is_muted_not_escalated()
    print("all digest tests passed")
