"""Normalisation helpers shared by all collectors."""

from __future__ import annotations

import re

from . import fx as fx_mod

COUNTRY_NAMES = {
    "united states": "US", "usa": "US", "united kingdom": "GB", "uk": "GB",
    "great britain": "GB", "germany": "DE", "deutschland": "DE", "australia": "AU",
    "japan": "JP", "south africa": "ZA", "canada": "CA", "netherlands": "NL",
    "france": "FR", "new zealand": "NZ", "belgium": "BE", "ireland": "IE",
}

_RHD_COUNTRIES = {"GB", "JP", "AU", "NZ", "ZA", "IE"}
_LHD_COUNTRIES = {"US", "CA", "DE", "FR", "NL", "BE", "IT", "ES", "SE", "CH", "AT", "MX", "PL"}


def to_country_code(value: str | None) -> str:
    """Country name or code to ISO 3166-1 alpha-2; 'XX' when unknown."""
    if not value:
        return "XX"
    v = value.strip()
    if re.fullmatch(r"[A-Za-z]{2}", v):
        return v.upper()
    return COUNTRY_NAMES.get(v.lower(), "XX")


def infer_drive_side(country: str, text: str | None = None) -> str:
    """Explicit mention in the text wins; otherwise infer from country."""
    t = (text or "").lower()
    if re.search(r"\brhd\b|right[ -]hand[ -]drive", t):
        return "RHD"
    if re.search(r"\blhd\b|left[ -]hand[ -]drive", t):
        return "LHD"
    if country in _RHD_COUNTRIES:
        return "RHD"
    if country in _LHD_COUNTRIES:
        return "LHD"
    return "unknown"


def make_price(amount: float | None, currency: str, fx_day: dict) -> dict:
    """Price block per the listing schema, converted at today's captured rate."""
    rate = None if currency == fx_mod.BASE else fx_day["rates"].get(currency)
    return {
        "amount": amount,
        "currency": currency,
        "gbp": fx_mod.to_gbp(amount, currency, fx_day),
        "fx_rate": 1.0 if currency == fx_mod.BASE else rate,
        "fx_date": fx_day["date"],
    }


def safe_url(url: str | None) -> str:
    """Only http(s) URLs may enter the data files: they end up as tappable
    links on the site and in the digest, so no javascript:/data: schemes."""
    if url and url.lower().startswith(("http://", "https://")):
        return url
    return ""


def extract_year(title: str) -> int | None:
    m = re.search(r"\b(19(?:7[0-9]|6[89]|80))\b", title or "")
    if not m:
        return None
    year = int(m.group(1))
    return year if 1971 <= year <= 1980 else None
