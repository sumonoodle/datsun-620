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


if __name__ == "__main__":
    test_digest_render()
    print("all digest tests passed")
