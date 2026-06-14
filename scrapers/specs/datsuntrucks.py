"""Collector: datsuntrucks.com 620 specifications page.

Reachable from a plain script (HTTP 200). The page presents specs as a flat
"Label: value unit." list, which we parse by label. These are the general 620
(US-oriented) figures; because the 620 shared a body globally, we attach the
body dimensions to the base-body variant of each market and let the reconciler
flag any disagreement with market-specific sources.
"""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from common.observations import CollectorResult, Observation
from common.units import inch_to_mm, lb_to_kg

URL = "https://datsuntrucks.com/620-specifications/"
SOURCE = "datsuntrucks.com (620 general specs)"
UA = "datsun620-tracker/0.1 (+https://github.com/sumonoodle/datsun-620)"

# label in page text -> (canonical field, converter)
DIMENSION_FIELDS = {
    r"Length, overall:\s*([\d.]+)\s*in": ("dimensions.length_mm", inch_to_mm),
    r"Width, overall:\s*([\d.]+)\s*in": ("dimensions.width_mm", inch_to_mm),
    r"Height, overall:\s*([\d.]+)\s*in": ("dimensions.height_mm", inch_to_mm),
    r"Wheelbase:\s*([\d.]+)\s*in": ("dimensions.wheelbase_mm", inch_to_mm),
    r"Road clearance:\s*([\d.]+)\s*in": ("dimensions.ground_clearance_mm", inch_to_mm),
    r"Weight:\s*([\d.]+)\s*lbs": ("weights.kerb_kg", lb_to_kg),
    r"Gross vehicle payload:\s*([\d.]+)\s*lbs": ("weights.payload_kg", lb_to_kg),
}


def collect(registry: dict) -> CollectorResult:
    targets = [v["id"] for v in registry["variants"] if v.get("base_body")]
    try:
        r = httpx.get(URL, headers={"User-Agent": UA}, timeout=30, follow_redirects=True)
        r.raise_for_status()
    except Exception as e:  # noqa: BLE001 - any network/HTTP failure is a skip
        return CollectorResult(SOURCE, ok=False, note=f"fetch failed: {e}")

    text = re.sub(r"\s+", " ", BeautifulSoup(r.text, "html.parser").get_text(" "))
    obs: list[Observation] = []
    for pattern, (field, conv) in DIMENSION_FIELDS.items():
        m = re.search(pattern, text)
        if not m:
            continue
        raw = m.group(0).split(":", 1)[1].strip()
        value = conv(float(m.group(1)))
        for vid in targets:
            obs.append(Observation(vid, field, value, SOURCE, URL, raw))

    if not obs:
        return CollectorResult(SOURCE, ok=False, note="page reached but no fields parsed (layout changed?)")
    return CollectorResult(SOURCE, ok=True, observations=obs)
