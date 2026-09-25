"""Hilux collector: Hagerty Marketplace (US), every Toyota for sale.

Earlier notes called Hagerty client-rendered. It is not: the Next.js page
runs the marketplace search server-side and ships the answer in the
Apollo cache (__NEXT_DATA__ -> pageProps.__APOLLO_STATE__). ROOT_QUERY
holds marketplaceExplore:{filters} -> paginated:{page,limit:33} with
totalCount and edges, and each edge points at an AuctionVehicleSearchNode
(year, make, model, auctionTitle, currentHighestBid in cents, status,
hasBeenSold, location) or a ListingVehicleSearchNode (year, make, model,
askedPrice in cents, listingStatus, location).

Why the whole make. The first probe asked for make=Toyota&model=Pickup and
the server answered totalCount 0; round 3 (2026-09-24) found model=Truck
also 0, while make=Toyota returned all 14 Toyotas for sale (3 auctions and
11 classifieds: Land Cruisers, a 4Runner, Crowns, a Supra, a 1998 Hilux, a
1997 Hilux Surf). Hagerty's model names are the seller's, so a 1981 truck
could be "Pickup", "SR5" or "Hilux"; the make page sees it whichever, and
at ~14 cars it is one page (limit 33). classify() does the rest on
"<year> Toyota <model>" / the auction title, with the US-name rule
catching "Toyota Pickup".

Guard: no ROOT_QUERY search raises; totalCount > 0 with no node raises;
a total above one page is reported (hasNextPage) rather than paged.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "hagerty"
BASE = "https://www.hagerty.com"
URL = f"{BASE}/marketplace/search?make=Toyota"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-US,en;q=0.9",
}

_NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_HREF_RE = re.compile(r'href="(/marketplace/(?:auction|classified)/[^"]+/([0-9a-f-]{36}))"')


def _connection(apollo: dict) -> dict:
    root = apollo.get("ROOT_QUERY") or {}
    search = ((root.get("marketplaceSearch") or {}).get("search") or {})
    for key, val in search.items():
        if key.startswith("marketplaceExplore") and isinstance(val, dict):
            for pkey, conn in val.items():
                if pkey.startswith("paginated") and isinstance(conn, dict):
                    return conn
    raise ValueError("marketplaceExplore search missing from the Apollo cache (payload moved?)")


def parse_page(html: str, fx_day: dict) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        raise ValueError("__NEXT_DATA__ missing (page layout changed or blocked?)")
    data = json.loads(m.group(1))
    apollo = ((data.get("props") or {}).get("pageProps") or {}).get("__APOLLO_STATE__") or {}
    conn = _connection(apollo)
    total = conn.get("totalCount")
    refs = [((e or {}).get("node") or {}).get("__ref") for e in conn.get("edges") or []]
    nodes = [apollo[r] for r in refs if r in apollo]
    if not nodes:
        if total:
            raise ValueError(f"search reports {total} vehicles but no node was parsed")
        return []
    if (conn.get("pageInfo") or {}).get("hasNextPage"):
        print(f"hagerty (hilux): {total} Toyotas, only the first page is read")
    hrefs = {vid: path for path, vid in _HREF_RE.findall(html)}

    records = []
    for node in nodes:
        vid = str(node.get("id") or "")
        if not vid or str(node.get("make") or "").lower() != "toyota":
            continue
        year_raw = str(node.get("year") or "")
        year = int(year_raw) if year_raw.isdigit() else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        model = str(node.get("model") or "")
        is_auction = node.get("__typename") == "AuctionVehicleSearchNode"
        title = node.get("auctionTitle") or f"{year_raw} Toyota {model}".strip()
        # The model field is structured; append it so "Toyota" + "Pickup"
        # reads as the US name even when the auction title is creative.
        ident = hilux.classify(title, f"Toyota {model}", year=year)
        if ident is None:
            continue

        if is_auction:
            money = node.get("currentHighestBid") or {}
            status = "sold" if node.get("hasBeenSold") or node.get("hasBeenSoldAfter") else "active"
        else:
            money = node.get("askedPrice") or {}
            status = "active"
        cents = money.get("amount")
        amount = round(cents / 100, 2) if isinstance(cents, (int, float)) and cents > 0 else None
        loc = node.get("location") or {}
        region = ", ".join(x for x in [loc.get("city"), loc.get("state")] if x) or None
        path = hrefs.get(vid) or (f"/marketplace/{'auction' if is_auction else 'classified'}/"
                                  f"{year_raw}-Toyota-{model.replace(' ', '%20')}/{vid}")
        photo = (node.get("mainPhoto") or {}).get("url")

        records.append({
            "id": f"hagerty:{vid}",
            "source": SOURCE,
            "source_listing_id": vid,
            "url": normalize.safe_url(f"{BASE}{path}"),
            "title": title,
            "title_translated": None,
            "description_snippet": None,
            "year": ident["year"],
            "country": "US",
            "region": region,
            "drive_side": normalize.infer_drive_side("US", title),
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [photo] if photo else [],
            "status": status,
        })
    return records


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return parse_page(resp.text, fx_day)
