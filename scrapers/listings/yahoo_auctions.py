"""Collector: Yahoo Auctions Japan, direct (no Buyee proxy).

The 2026-07-17 probe showed auctions.yahoo.co.jp serves full pages to
GitHub runners even though Buyee 403s them, so this replaces the blocked
yahoo_buyee collector. Two surfaces:

- Open search (server-rendered li.Product cards with data-auction-*
  attributes): active auctions.
- Closed search (__NEXT_DATA__ JSON): recently sold items, which carry a
  full categoryPath, letting us require the 中古車・新車 (whole vehicle)
  category structurally instead of by word list.

Open results are overwhelmingly parts, so the filter chain mirrors eBay's
layered approach: King Cab terms, a 620 that is not part of a longer
number, the Japanese parts word list, and a fixed-price floor (a Buy It
Now-only King Cab item under ¥100,000 is a part or a toy, never a truck;
auctions are exempt because real trucks start at ¥1).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize

SOURCE = "yahoo_auctions"
OPEN_URL = "https://auctions.yahoo.co.jp/search/search?p={}"
CLOSED_URL = "https://auctions.yahoo.co.jp/closedsearch/closedsearch?p={}"
# Targeted King Cab query plus the broad 620 query (also the canary: parts
# hits for "ダットサン 620" always exist, so zero raw items = broken/blocked).
QUERIES = ["ダットサン キングキャブ", "ダットサン 620"]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "ja,en;q=0.8",
}

# "620" not embedded in a longer number (part numbers, "1620", "S620x" SKUs).
_620_RE = re.compile(r"(?<![\dA-Za-z])620(?!\d)")
_FIXED_PRICE_FLOOR_JPY = 100_000

# Parts/memorabilia words, extended from the retired Buyee collector's list.
# 用 = "for (use with)": a "キングキャブ用テールランプ" is a lamp FOR a King Cab.
_PARTS_WORDS = [
    "用", "パーツ", "部品", "テールランプ", "ヘッドライト", "フェンダー", "グリル",
    "エンブレム", "バンパー", "マフラー", "ミラー", "カタログ", "ミニカー",
    "トミカ", "ステッカー", "キーホルダー", "シート", "ホイール", "キャブレター",
    "ブロックキット", "ローダウン", "リーフ", "サスペンション", "デカール",
    "ポスター", "雑誌", "広告", "プラモ", "模型", "ラジエーター", "ドアハンドル",
    "レンズ", "ガスケット", "ブレーキ", "クラッチ", "ワイパー", "ベアリング",
    "テールゲート", "ボンネット", "荷台", "メーター", "ウインカー", "ランプ",
    "ガラス", "モール", "ノベルティ", "パンフレット", "取扱説明書",
]


def _looks_like_part(title: str) -> bool:
    return any(w in title for w in _PARTS_WORDS)


def _record(auction_id: str, title: str, amount: float | None, image: str | None,
            fx_day: dict, status: str) -> dict:
    return {
        "id": f"yahoo_auctions:{auction_id}",
        "source": SOURCE,
        "source_listing_id": auction_id,
        "url": normalize.safe_url(f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}"),
        "title": title,
        "title_translated": None,
        "description_snippet": None,
        "year": normalize.extract_year_jp(title),
        "country": "JP",
        "region": None,
        "drive_side": normalize.infer_drive_side("JP", title),
        "king_cab": king_cab.check(title),
        "price": normalize.make_price(amount, "JPY", fx_day),
        "images": [image] if image else [],
        "status": status,
    }


def _passes_filters(title: str) -> bool:
    if not king_cab.check(title)["matched"]:
        return False
    if not _620_RE.search(title):
        return False  # D21/D22 King Cabs and unrelated trucks must not leak
    if _looks_like_part(title):
        return False
    return True


def parse_open(html: str, fx_day: dict) -> tuple[list[dict], int]:
    """Active auctions from the server-rendered open search page.
    Returns (records, raw_item_count) — the raw count feeds the canary."""
    soup = BeautifulSoup(html, "html.parser")
    products = soup.select("li.Product")
    records = []
    for p in products:
        a = p.select_one("a.Product__titleLink")
        if a is None:
            continue
        auction_id = a.get("data-auction-id", "")
        title = a.get("data-auction-title") or a.get_text(" ", strip=True)
        if not auction_id or not _passes_filters(title):
            continue

        raw_price = a.get("data-auction-price")
        amount = float(raw_price) if raw_price and raw_price.isdigit() else None
        # 現在 = current bid (auction running); 即決 only = fixed price.
        labels = {el.get_text(strip=True) for el in p.select(".Product__label")}
        is_fixed_only = "即決" in labels and "現在" not in labels
        if is_fixed_only and amount is not None and amount < _FIXED_PRICE_FLOOR_JPY:
            continue

        records.append(_record(auction_id, title, amount,
                               a.get("data-auction-img"), fx_day, "active"))
    return records, len(products)


def parse_closed(html: str, fx_day: dict) -> tuple[list[dict], int]:
    """Sold items from the closed search's __NEXT_DATA__ JSON. The full
    categoryPath is available here, so besides the title filters a sold item
    must sit in the 中古車・新車 (whole vehicle) category tree."""
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
                  html, re.S)
    if not m:
        raise ValueError("closed search __NEXT_DATA__ missing (page layout changed?)")
    data = json.loads(m.group(1))
    try:
        items = data["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]["items"]
    except (KeyError, TypeError):
        items = []

    records = []
    for it in items:
        title = it.get("title", "")
        auction_id = it.get("auctionId", "")
        path_names = [c.get("name", "") for c in it.get("categoryPath") or []]
        if not auction_id or not _passes_filters(title):
            continue
        if not any("中古車" in n for n in path_names):
            continue  # parts, toys and literature live in other trees
        amount = float(it["price"]) if it.get("price") is not None else None
        records.append(_record(auction_id, title, amount, it.get("imageUrl"), fx_day, "sold"))
    return records, len(items)


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    failures: list[str] = []
    fetches = 0
    raw_total = 0
    with httpx.Client(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for template, parser in ((OPEN_URL, parse_open), (CLOSED_URL, parse_closed)):
            for query in QUERIES:
                fetches += 1
                try:
                    resp = client.get(template.format(quote(query)))
                    resp.raise_for_status()
                    recs, raw = parser(resp.text, fx_day)
                    raw_total += raw
                    for rec in recs:
                        if rec["id"] not in seen:  # sold and active never collide;
                            seen.add(rec["id"])   # queries do
                            records.append(rec)
                except Exception as exc:
                    failures.append(f"{query}: {exc}")
    if failures and len(failures) == fetches:
        raise RuntimeError(f"all Yahoo fetches failed ({failures[0]})")
    if failures:
        print(f"yahoo_auctions: partial failure, continuing without {failures}")
    if raw_total == 0:
        # "ダットサン 620" always has parts hits; zero raw items everywhere
        # means blocked or a layout change pretending to be an empty market.
        raise RuntimeError("canary: zero raw items across all Yahoo queries")
    return records
