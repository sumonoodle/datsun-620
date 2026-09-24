"""Two-truck digest: one email with a Datsun 620 section and a Hilux section.

Checks RN30-like listings lead the Hilux section, extended cabs are flagged,
unknown sources fall back to their id, the subject names both trucks, and a
missing Hilux dataset renders an empty state instead of crashing."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "emailer"))

import send_digest

DATE = "2026-09-24"


def _listing(id_, title, *, target=False, ext=False, code=None, drive="unknown",
             reasons=None, gbp=5000.0, source=None):
    return {
        "id": id_, "source": source or id_.split(":")[0], "url": f"https://example.test/{id_}",
        "title": title, "title_translated": None, "year": 1980, "country": "US",
        "drive_side": "LHD", "images": [],
        "price": {"amount": gbp, "currency": "GBP", "gbp": gbp},
        "king_cab": {"matched": ext, "matched_terms": ["xtracab"] if ext else [],
                     "body_style_check": "unavailable"},
        "status": "active", "first_seen": DATE, "last_seen": DATE, "history": [],
        "variant": {"chassis_code": code, "drive": drive, "target_match": target,
                    "target_reasons": reasons or []},
    }


def _changes(new=(), price=()):
    return {"date": DATE, "new": list(new), "price_changed": list(price),
            "status_changed": [], "possible_relists": []}


def _run_log(sources=()):
    return {"date": DATE, "started_at": f"{DATE}T04:20:00+00:00", "sources": list(sources),
            "totals": {"active": 2, "by_country": {"US": 2}, "median_gbp": 5000.0}}


DATSUN_KC = {
    "id": "ebay:d1", "source": "ebay", "url": "https://example.test/d1",
    "title": "1977 Datsun 620 King Cab", "country": "US", "drive_side": "LHD",
    "images": [], "price": {"amount": 9000, "currency": "USD", "gbp": 6700.0},
    "king_cab": {"matched": True, "matched_terms": ["king cab"], "body_style_check": "unavailable"},
    "status": "active", "first_seen": DATE, "last_seen": DATE, "history": [],
}


def _hilux():
    plain = _listing("ebay:h1", "1981 Toyota Hilux 4x4", code="RN46", drive="4WD")
    rn30 = _listing("newsite:h2", "1980 Toyota Hilux RN30 short bed", target=True,
                    code="RN30", drive="2WD", reasons=["chassis RN30 stated", "2WD"])
    xtra = _listing("ebay:h3", "1983 Hilux Xtracab", ext=True)
    by_id = {l["id"]: l for l in (plain, rn30, xtra)}
    return {
        # Pipeline order puts the plain truck first; the digest must not.
        "changes": _changes(new=["ebay:h1", "newsite:h2", "ebay:h3"],
                            price=[{"id": "ebay:h1", "old_gbp": 6000.0, "new_gbp": 5000.0, "pct": -16.7},
                                   {"id": "newsite:h2", "old_gbp": 5500.0, "new_gbp": 5000.0, "pct": -9.1}]),
        "run_log": _run_log([{"source": "newsite", "ok": True, "records": 1, "note": "",
                              "consecutive_failures": 0, "consecutive_zero_runs": 0}]),
        "listings_by_id": by_id,
    }


def test_two_sections_target_first():
    hilux = _hilux()
    html = send_digest.build_html(_changes(new=["ebay:d1"]), _run_log(), {"ebay:d1": DATSUN_KC},
                                  "https://example.test", hilux=hilux)
    # One email, both trucks, Datsun first.
    assert "Datsun 620 + Hilux digest" in html
    d_at, h_at = html.index(">Datsun 620</div>"), html.index(">Toyota Hilux</div>")
    assert d_at < h_at
    datsun, hil = html[d_at:h_at], html[h_at:]
    assert "KING CAB" in datsun and "1977 Datsun 620 King Cab" in datsun
    assert "https://example.test/hilux/" in hil
    # Target matches lead the Hilux new-listings section, with their reasons.
    assert "New listings (3, 1 matches your RN30 spec, 1 extended cab)" in hil
    new_sec = hil[hil.index("New listings"):hil.index("Price changes")]
    assert new_sec.index("RN30 short bed") < new_sec.index("Xtracab") < new_sec.index("4x4")
    assert "MATCHES YOUR RN30 SPEC" in new_sec
    assert "chassis RN30 stated; 2WD" in new_sec
    # ...and lead price changes too.
    price_sec = hil[hil.index("Price changes"):]
    assert price_sec.index("RN30 short bed") < price_sec.index("4x4")
    # Extended cab labelled as such (never "King Cab") and flagged rare.
    assert "EXTENDED CAB (rare)" in hil
    assert "KING CAB" not in hil
    # Chassis code and drive shown when known.
    assert "· RN46 · 4WD ·" in hil and "· RN30 · 2WD ·" in hil
    # Unknown source falls back to its raw id.
    assert "newsite: 1 listing(s)" in hil and "· newsite</span>" in hil
    # Each truck has its own health and summary.
    assert html.count("Source health") == 2 and html.count("Summary</h2>") == 2
    print("ok test_two_sections_target_first")


def test_subject_mentions_both():
    hilux = _hilux()
    s = send_digest.build_subject(_changes(new=["ebay:d1"]), _run_log(), {"ebay:d1": DATSUN_KC},
                                  hilux=hilux)
    assert s == ("Datsun 620: 1 KING CAB of 1 new, 0 price change(s) | "
                 "Hilux: 1 RN30 MATCH, 1 EXTENDED CAB of 3 new, 2 price change(s) — 2026-09-24"), s
    # Only the Hilux has news: the subject leads with it alone.
    s = send_digest.build_subject(_changes(), _run_log(), {}, hilux=hilux)
    assert s.startswith("Hilux: 1 RN30 MATCH"), s
    assert "Datsun" not in s
    # Neither has news.
    quiet = {"changes": _changes(), "run_log": _run_log(), "listings_by_id": {}}
    assert send_digest.build_subject(_changes(), _run_log(), {}, hilux=quiet) == \
        "Datsun 620 + Hilux digest — 2026-09-24"
    # Datsun-only callers keep the old subject exactly.
    assert send_digest.build_subject(_changes(), _run_log(), {}) == "Datsun 620 digest — 2026-09-24"
    # Quiet-source alerts count across both trucks.
    q = {"source": "x", "ok": True, "records": 0, "note": "", "consecutive_failures": 0,
         "consecutive_zero_runs": send_digest.QUIET_RUNS_ALERT}
    hq = {"changes": _changes(), "run_log": _run_log([q]), "listings_by_id": {}}
    assert send_digest.build_subject(_changes(), _run_log([q]), {}, hilux=hq).endswith(
        "— 2 source(s) quiet")
    print("ok test_subject_mentions_both")


def test_missing_hilux_data():
    """The Hilux pipeline has not run yet: every file is absent."""
    with tempfile.TemporaryDirectory() as tmp:
        hilux = send_digest.load_hilux(Path(tmp))
        # A partial set (changes only) must also load.
        (Path(tmp) / "changes-latest.json").write_text(json.dumps(_changes()))
        partial = send_digest.load_hilux(Path(tmp))
    assert hilux == {"changes": None, "run_log": None, "listings_by_id": {}}
    html = send_digest.build_html(_changes(), _run_log(), {}, "https://example.test", hilux=hilux)
    assert ">Toyota Hilux</div>" in html
    assert "No Hilux results yet" in html
    assert send_digest.build_subject(_changes(), _run_log(), {}, hilux=hilux) == \
        "Datsun 620 + Hilux digest — 2026-09-24"
    html = send_digest.build_html(_changes(), _run_log(), {}, "https://example.test", hilux=partial)
    hil = html[html.index(">Toyota Hilux</div>"):]
    assert "No new or changed listings today." in hil and "no sources ran" in hil
    print("ok test_missing_hilux_data")


def test_hilux_without_variant_block():
    """Older or partial records may lack `variant`; nothing may crash."""
    l = _listing("ebay:h9", "Toyota pickup")
    del l["variant"]
    hilux = {"changes": _changes(new=["ebay:h9"]), "run_log": None, "listings_by_id": {"ebay:h9": l}}
    html = send_digest.build_html(_changes(), _run_log(), {}, "https://example.test", hilux=hilux)
    assert "New listings (1)" in html and "Toyota pickup" in html
    print("ok test_hilux_without_variant_block")


if __name__ == "__main__":
    test_two_sections_target_first()
    test_subject_mentions_both()
    test_missing_hilux_data()
    test_hilux_without_variant_block()
    print("all hilux digest tests passed")
