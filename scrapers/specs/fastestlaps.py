"""Collector: fastestlaps.com Datsun 620 page.

Describes the L20B 620. Specs are in the static HTML, reachable with a browser
user-agent. Body dimensions and weight go to each market's base-body variant;
the L20B engine goes to US variants only (rest-of-world used the J15).
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from common.observations import CollectorResult, Observation

URL = "https://fastestlaps.com/models/datsun-620"
SOURCE = "FastestLaps (620, L20B)"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"


def collect(registry: dict) -> CollectorResult:
    try:
        r = httpx.get(URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return CollectorResult(SOURCE, ok=False, note=f"fetch failed: {e}")

    text = re.sub(r"\s+", " ", BeautifulSoup(r.text, "html.parser").get_text(" "))

    def grab(pattern, conv=lambda x: x, idx=1):
        m = re.search(pattern, text)
        return (conv(m.group(idx)), m.group(0)) if m else (None, "")

    dims_weights = {
        "dimensions.length_mm": grab(r"([\d.]+)\s*m \(\d+ in\) long", lambda x: round(float(x) * 1000)),
        "dimensions.width_mm": grab(r"([\d.]+)\s*m \(\d+ in\) wide", lambda x: round(float(x) * 1000)),
        "dimensions.height_mm": grab(r"([\d.]+)\s*m \(\d+ in\) high", lambda x: round(float(x) * 1000)),
        "dimensions.wheelbase_mm": grab(r"Wheelbase\s+([\d.]+)\s*m", lambda x: round(float(x) * 1000)),
        "weights.kerb_kg": grab(r"Curb weight\s+(\d+)\s*kg", int),
    }
    engine = {
        "engine.code": ("L20B", "L20B"),
        "engine.displacement_cc": grab(r"(\d+)\s*cc\)", int),
        "engine.power_hp": grab(r"Power\s+\d+\s*ps\s*\((\d+)\s*bhp", int),
        "engine.torque_nm": grab(r"Torque\s+(\d+)\s*Nm", int),
    }

    base_targets = [v["id"] for v in registry["variants"] if v.get("base_body")]
    us_targets = [v["id"] for v in registry["variants"] if v["market"] == "US"]

    obs: list[Observation] = []
    for field, (value, raw) in dims_weights.items():
        if value is None:
            continue
        for vid in base_targets:
            obs.append(Observation(vid, field, value, SOURCE, URL, raw.strip()))
    for field, (value, raw) in engine.items():
        if value is None:
            continue
        for vid in us_targets:
            obs.append(Observation(vid, field, value, SOURCE, URL, raw.strip()))

    if not obs:
        return CollectorResult(SOURCE, ok=False, note="page reached but no specs parsed (layout changed?)")
    return CollectorResult(SOURCE, ok=True, observations=obs)
