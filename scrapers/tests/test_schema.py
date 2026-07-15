"""Contract tests: a golden listing must validate, obvious breakage must not,
and the data files in data/ must match their schemas."""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonschema

from common.schema import DATA_DIR, validate

GOLDEN_LISTING = {
    "id": "bringatrailer:datsun-620-example",
    "source": "bringatrailer",
    "source_listing_id": "datsun-620-example",
    "url": "https://bringatrailer.com/listing/datsun-620-example/",
    "title": "1978 Datsun 620 King Cab",
    "title_translated": None,
    "description_snippet": "Restored King Cab with L20B engine.",
    "year": 1978,
    "country": "US",
    "region": "Oregon",
    "drive_side": "LHD",
    "king_cab": {
        "matched": True,
        "matched_terms": ["king cab"],
        "body_style_check": "unavailable"
    },
    "price": {
        "amount": 12500,
        "currency": "USD",
        "gbp": 9315.84,
        "fx_rate": 1.3418,
        "fx_date": "2026-07-14"
    },
    "images": ["https://example.com/thumb.jpg"],
    "status": "active",
    "first_seen": "2026-07-14",
    "last_seen": "2026-07-14",
    "history": [
        {
            "date": "2026-07-14",
            "status": "active",
            "price": {
                "amount": 12500,
                "currency": "USD",
                "gbp": 9315.84,
                "fx_rate": 1.3418,
                "fx_date": "2026-07-14"
            }
        }
    ],
    "relist": {"possible": False, "prior_id": None, "reasons": []}
}


def test_golden_listing_validates():
    validate(GOLDEN_LISTING, "listing")
    print("ok test_golden_listing_validates")


def test_bad_listings_rejected():
    cases = {
        "unknown source": ("source", "craigslist"),
        "bad status": ("status", "pending"),
        "bad drive side": ("drive_side", "left"),
        "bad country": ("country", "USA"),
    }
    for label, (field, value) in cases.items():
        bad = copy.deepcopy(GOLDEN_LISTING)
        bad[field] = value
        try:
            validate(bad, "listing")
        except jsonschema.ValidationError:
            continue
        raise AssertionError(f"schema accepted invalid listing: {label}")
    print("ok test_bad_listings_rejected")


def test_data_files_match_contract():
    for filename, schema_name in [
        ("fx-rates.json", "fx-rates"),
        ("changes-latest.json", "changes"),
        ("run-log.json", "run-log"),
        ("specs.json", "specs"),
    ]:
        path = DATA_DIR / filename
        if path.exists():
            validate(json.loads(path.read_text()), schema_name)
    listings_path = DATA_DIR / "listings.json"
    if listings_path.exists():
        for listing in json.loads(listings_path.read_text())["listings"]:
            validate(listing, "listing")
    print("ok test_data_files_match_contract")


if __name__ == "__main__":
    test_golden_listing_validates()
    test_bad_listings_rejected()
    test_data_files_match_contract()
    print("all schema tests passed")
