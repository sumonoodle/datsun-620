"""Daily exchange rates from Frankfurter (ECB-backed, no key required).

Rates are quoted with GBP as the base. We fetch once per run and store the
snapshot so historical GBP conversions stay consistent.
"""

from __future__ import annotations

from datetime import date

import httpx

URL = "https://api.frankfurter.dev/v1/latest"
SOURCE = "Frankfurter (ECB)"
SYMBOLS = ["USD", "JPY", "EUR", "AUD", "CAD", "ZAR", "NZD"]


def fetch_rates() -> dict:
    """Return an fx-rate record: {date, base: GBP, rates: {CUR: per-GBP}, source}."""
    try:
        r = httpx.get(URL, params={"base": "GBP", "symbols": ",".join(SYMBOLS)}, timeout=30)
        r.raise_for_status()
        data = r.json()
        rates = {"GBP": 1.0, **data["rates"]}
        return {"date": data.get("date", date.today().isoformat()), "base": "GBP", "rates": rates, "source": SOURCE}
    except Exception as e:  # noqa: BLE001
        # Fail soft: no rates means we keep original prices and skip GBP conversion.
        return {"date": date.today().isoformat(), "base": "GBP", "rates": {"GBP": 1.0}, "source": f"{SOURCE} (unavailable: {e})"}


def to_gbp(amount: float | None, currency: str | None, fx: dict) -> float | None:
    """Convert an amount in `currency` to GBP using the fetched rates.
    Rates are per-GBP (e.g. USD 1.34 means 1 GBP = 1.34 USD), so GBP = amount / rate."""
    if amount is None or not currency:
        return None
    rate = fx.get("rates", {}).get(currency.upper())
    if not rate:
        return None
    return round(amount / rate, 2)
