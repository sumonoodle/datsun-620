"""Best-effort listing sources.

These four (Cars & Bids, Hemmings, Goo-net Exchange, Yahoo Auctions via Buyee)
defend aggressively against automated access and typically return 403/429 to
GitHub Actions' datacenter IPs. Each tries politely and, when blocked, skips and
flags itself so the run continues and the digest reports the gap. They will
populate if reached from an allowed IP (e.g. a future residential proxy).

Marked best-effort and unverified against live data by design.
"""

from __future__ import annotations

import re

import httpx

from common.listings_common import ListingResult

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15"


def _fetch(url: str) -> tuple[bool, str]:
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=25, follow_redirects=True)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code} (bot protection / blocked)"
        return True, r.text
    except Exception as e:  # noqa: BLE001
        return False, f"unreachable: {e}"


def _anchor_620(html: str, base: str, source: str) -> list[dict]:
    """Generic fallback: pull anchors whose text mentions a Datsun 620.
    Conservative; recall-first scoring runs downstream."""
    out = []
    for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        flat = re.sub(r"<[^>]+>", " ", text)
        if re.search(r"\b620\b", flat) and "datsun" in flat.lower():
            url = href if href.startswith("http") else base.rstrip("/") + "/" + href.lstrip("/")
            out.append({"source": source, "source_url": url, "title": re.sub(r"\s+", " ", flat).strip(), "status": "active"})
    return out


def _collector(source: str, url: str, base: str):
    def collect() -> ListingResult:
        ok, payload = _fetch(url)
        if not ok:
            return ListingResult(source, ok=False, note=payload)
        return ListingResult(source, ok=True, records=_anchor_620(payload, base, source))
    return collect


cars_and_bids = _collector("carsandbids", "https://carsandbids.com/search/datsun", "https://carsandbids.com")
hemmings = _collector("hemmings", "https://www.hemmings.com/classifieds/cars-for-sale/datsun/620", "https://www.hemmings.com")
goonet = _collector("goonet", "https://www.goo-net-exchange.com/usedcars/DATSUN/index.html", "https://www.goo-net-exchange.com")
yahoo_buyee = _collector("yahoo_buyee", "https://buyee.jp/yahoo/auction/search?query=%E3%83%80%E3%83%83%E3%83%88%E3%82%B5%E3%83%B3620", "https://buyee.jp")
