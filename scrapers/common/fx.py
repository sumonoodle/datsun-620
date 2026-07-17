"""Daily FX rates from Frankfurter (ECB reference rates), base GBP.

Fetched once per run and appended to data/fx-rates.json. Each listing stores
the rate it was converted at, so historical GBP values never drift when rates
move later.

Frankfurter needs no API key. The PRD named exchangerate.host, which has since
moved behind a key; Frankfurter is the agreed replacement.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import httpx

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
SYMBOLS = ["USD", "EUR", "JPY", "AUD", "ZAR", "THB", "CAD", "MXN"]
BASE = "GBP"


def fetch_rates(client: httpx.Client | None = None) -> dict:
    """Fetch today's rates. Returns a day entry per schema/fx-rates.schema.json."""
    own_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        resp = client.get(
            FRANKFURTER_URL, params={"base": BASE, "symbols": ",".join(SYMBOLS)}
        )
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if own_client:
            client.close()
    return parse_rates(payload)


def parse_rates(payload: dict) -> dict:
    """Turn a Frankfurter response into a day entry. Split out for testing."""
    missing = [s for s in SYMBOLS if s not in payload.get("rates", {})]
    if missing:
        raise ValueError(f"FX response missing symbols: {missing}")
    return {
        "date": payload["date"],
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "base": BASE,
        "rates": {s: payload["rates"][s] for s in SYMBOLS},
    }


def append_rates(path: Path, day: dict) -> dict:
    """Merge a day entry into the FX log at `path`, deduping by date."""
    if path.exists():
        log = json.loads(path.read_text())
    else:
        log = {"latest": day, "history": []}
    history = [d for d in log.get("history", []) if d["date"] != day["date"]]
    history.append(day)
    history.sort(key=lambda d: d["date"])
    log = {"latest": history[-1], "history": history}
    path.write_text(json.dumps(log, indent=2) + "\n")
    return log


def to_gbp(amount: float | None, currency: str, day: dict) -> float | None:
    """Convert an amount in `currency` to GBP using a day entry's rates."""
    if amount is None:
        return None
    if currency == BASE:
        return round(amount, 2)
    rate = day["rates"].get(currency)
    if not rate:
        return None
    return round(amount / rate, 2)
