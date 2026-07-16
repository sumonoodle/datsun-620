"""Collector: Goo-net Exchange (tier 3 Japan experiment, PRD 4.4).

Targets the English-language export site, which exists to be browsed from
abroad and may tolerate datacenter traffic better than goo-net.com proper.
The v1.0 build was blocked (404 walls); a block here raises and is absorbed
by per-source isolation and reported in the digest.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "goonet"
URL = "https://www.goo-net-exchange.com/usedcars/DATSUN/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.5",
}

_USD_RE = re.compile(r"(?:US\$|USD\s?)\s?([\d,]+)")
_JPY_RE = re.compile(r"[¥￥]\s?([\d,]+)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/usedcars/" not in href or not re.search(r"/\d{6,}", href):
            continue  # detail links carry a numeric stock id
        title = a.get_text(" ", strip=True)
        if "620" not in title:
            continue
        kc = king_cab.check(title)
        if not kc["matched"]:
            continue

        stock_id = re.search(r"/(\d{6,})", href).group(1)
        if stock_id in seen:
            continue
        seen.add(stock_id)
        url = href if href.startswith("http") else f"https://www.goo-net-exchange.com{href}"

        card = a.find_parent(["li", "article", "div", "section"]) or a
        text = card.get_text(" ", strip=True)
        m_usd, m_jpy = _USD_RE.search(text), _JPY_RE.search(text)
        if m_usd:
            amount, currency = float(m_usd.group(1).replace(",", "")), "USD"
        elif m_jpy:
            amount, currency = float(m_jpy.group(1).replace(",", "")), "JPY"
        else:
            amount, currency = None, "JPY"
        img = card.find("img")

        records.append({
            "id": f"goonet:{stock_id}",
            "source": SOURCE,
            "source_listing_id": stock_id,
            "url": url,
            "title": title,
            "title_translated": None,  # filled by the translation pass
            "description_snippet": None,
            "year": normalize.extract_year(title),
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", title),
            "king_cab": kc,
            "price": normalize.make_price(amount, currency, fx_day),
            "images": [img["src"]] if img and str(img.get("src", "")).startswith("http") else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    if resp.status_code in (403, 404, 429, 503):
        raise RuntimeError(f"HTTP {resp.status_code} (bot protection / blocked)")
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
