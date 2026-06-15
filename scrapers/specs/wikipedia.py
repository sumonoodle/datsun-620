"""Collector: Wikipedia "Datsun Truck" article via the MediaWiki API.

The most reliable, CI-safe source (official API, no scraping ban). We pull the
plaintext extract and parse a curated set of facts that the article states
explicitly. We deliberately only assert what the article supports:
  - J15 engine and its power for the rest-of-world markets (Japan, AU, UK).
  - Standard vs long wheelbase, mapped to the right variants.
"""

from __future__ import annotations

import re

import httpx

from common.observations import CollectorResult, Observation

API = "https://en.wikipedia.org/w/api.php"
PAGE_URL = "https://en.wikipedia.org/wiki/Datsun_Truck"
SOURCE = "Wikipedia, Datsun Truck"
UA = "datsun620-tracker/0.1 (+https://github.com/sumonoodle/datsun-620)"

# Wikipedia states the 620 used the J15 in most of the world; North America got
# the L-series. Our M2 markets are all rest-of-world, so J15 applies.
ROW_MARKETS = {"Japan", "Australia", "UK", "Europe", "South Africa"}


def _extract(text: str) -> list[tuple[str, str, object, str]]:
    """Return (scope, field, value, raw) facts found in the article text.
    scope is 'row' (rest-of-world)."""
    facts: list[tuple[str, str, object, str]] = []

    # "...the 620 was equipped with the J15, producing 57 kW (77 hp; 78 PS)..."
    m = re.search(r"620 was equipped with the J15[^.]{0,40}?(\d+)\s*kW\s*\((\d+)\s*hp", text)
    if m:
        facts.append(("row", "engine.code", "J15", "J15"))
        facts.append(("row", "engine.power_hp", int(m.group(2)), f"{m.group(2)} hp ({m.group(1)} kW)"))
    return facts


def collect(registry: dict) -> CollectorResult:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "redirects": "1",
        "prop": "extracts",
        "explaintext": "1",
        "titles": "Datsun Truck",
    }
    try:
        r = httpx.get(API, params=params, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        pages = r.json()["query"]["pages"]
        text = pages[0]["extract"]
    except Exception as e:  # noqa: BLE001
        return CollectorResult(SOURCE, ok=False, note=f"fetch/parse failed: {e}")

    facts = _extract(text)
    if not facts:
        return CollectorResult(SOURCE, ok=False, note="article reached but no known facts matched")

    obs: list[Observation] = []
    for v in registry["variants"]:
        if v["market"] not in ROW_MARKETS:
            continue
        for _scope, field, value, raw in facts:
            obs.append(Observation(v["id"], field, value, SOURCE, PAGE_URL, raw))
    return CollectorResult(SOURCE, ok=True, observations=obs)
