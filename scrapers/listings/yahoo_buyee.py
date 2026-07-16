"""Collector: Yahoo Japan Auctions via Buyee (tier 3 Japan experiment, PRD 4.4).

Buyee is the proxy-bidding front for Yahoo Auctions with a crawlable search
page. The v1.0 build was blocked (404 walls); a block raises and is absorbed
by per-source isolation and reported in the digest.

Search term: ダットサン 620 (Datsun 620). The King Cab filter handles both the
Japanese キングキャブ and English spellings.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "yahoo_buyee"
QUERY = "ダットサン 620"
URL = f"https://buyee.jp/item/search/query/{quote(QUERY)}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
                  "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9,ja;q=0.5",
}

_YEN_RE = re.compile(r"([\d,]+)\s*(?:yen|円)", re.I)

# Auction titles for parts, not trucks. 用 = "for (use with)"; a title like
# "King Cab 用 tail lamp" is a part being sold FOR a King Cab.
_PARTS_WORDS = [
    "用", "パーツ", "部品", "テールランプ", "ヘッドライト", "フェンダー", "グリル",
    "エンブレム", "バンパー", "マフラー", "ミラー", "カタログ", "ミニカー",
    "トミカ", "ステッカー", "キーホルダー", "シート", "ホイール", "キャブレター",
]


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    records = []
    seen = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r"/item/(?:yahoo/auction/|jdirectitems/auction/)?([a-z]\d{8,})", a["href"])
        if not m:
            continue
        auction_id = m.group(1)
        card = a.find_parent(["li", "article", "div", "section"]) or a
        title_el = card.find(class_=re.compile("itemCard__itemName|item-name|title", re.I)) or a
        title = title_el.get_text(" ", strip=True)
        if "620" not in title:
            continue
        kc = king_cab.check(title)
        if not kc["matched"]:
            continue
        if any(w in title for w in _PARTS_WORDS):
            continue
        if auction_id in seen:
            continue
        seen.add(auction_id)

        text = card.get_text(" ", strip=True)
        m_price = _YEN_RE.search(text)
        amount = float(m_price.group(1).replace(",", "")) if m_price else None
        img = card.find("img")
        img_src = img.get("data-src") or img.get("src") if img else None

        records.append({
            "id": f"yahoo_buyee:{auction_id}",
            "source": SOURCE,
            "source_listing_id": auction_id,
            "url": f"https://buyee.jp/item/yahoo/auction/{auction_id}",
            "title": title,
            "title_translated": None,  # filled by the translation pass
            "description_snippet": None,
            "year": normalize.extract_year(title),
            "country": "JP",
            "region": None,
            "drive_side": normalize.infer_drive_side("JP", title),
            "king_cab": kc,
            "price": normalize.make_price(amount, "JPY", fx_day),
            "images": [img_src] if img_src and str(img_src).startswith("http") else [],
            "status": "active",
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    if resp.status_code in (403, 404, 429, 503):
        raise RuntimeError(f"HTTP {resp.status_code} (bot protection / blocked)")
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
