"""Hilux collector: TCV (tc-v.com, formerly tradecarview), Japanese exporter.

TCV lists dealer export stock, mostly in Japan but also Thai, UK and
other yards. Its model page is server-rendered: each car is a
<div class="vehicle__car-item" data-car-id=...> with the registration
year, a title (year/make/model), the chassis prefix ("YN107-0001***" --
a 3rd-gen truck would read "RN30-..."), FOB price in US$, option tags
(RHD, Gasoline/Diesel, 2WD/4WD, MT/AT) and the stock country as an ISO
numeric flag id (#392 is Japan).

Why the year filter. The 2026-09-24 probe of /used_car/toyota/hilux/ held
872 Hiluxes, 25 a page; page 1 was 23 GUN125/GUN226 trucks of 2018-2026
plus a 2001 and a 1994. The page's own search form has
"Registration Year From/To" selects named fid/jid, and its "Older Model"
link is /used_car/all/all/?jid=1989, so ?fid=1978&jid=1984 scopes the
query server-side to the generation. That URL is the site's own filter
and round 3 (2026-09-24) confirmed it server-side: the page title reads
"Toyota Hilux & Year 1978-1984" and the result-id list is empty (no
1978-84 Hilux in TCV stock that day). Because every card would be
rejected on its year anyway, a silently dropped filter would look just
like an empty market, so collect() also requires that title echo.

Guard: the page lists its result ids in data-search-car-ids-value. A
missing attribute raises (layout change or block page); ids promised but
no card parsed raises; an empty list is an empty market.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import hilux, normalize

SOURCE = "tcv"
BASE = "https://www.tc-v.com"
URL = f"{BASE}/used_car/toyota/hilux/?fid=1978&jid=1984"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "en-GB,en;q=0.9",
}

_IDS_RE = re.compile(r'data-search-car-ids-value="\[([^\]]*)\]"')
_USD_RE = re.compile(r"US\$\s*([\d,]+)")
_FLAG_RE = re.compile(r"\.svg\?#(\d{1,3})\b")
# ISO 3166 numeric codes of the stock yards TCV shows (its flag sprite is
# keyed by them). Unknown codes fall back to XX rather than a guess.
_ISO_NUMERIC = {"392": "JP", "764": "TH", "826": "GB", "410": "KR", "702": "SG",
                "158": "TW", "840": "US", "404": "KE", "894": "ZM", "36": "AU",
                "554": "NZ", "710": "ZA", "458": "MY", "784": "AE", "124": "CA"}


def _promised_ids(html: str) -> list[str]:
    m = _IDS_RE.search(html)
    if not m:
        raise ValueError("data-search-car-ids-value missing (page layout changed or blocked?)")
    return [x.strip() for x in m.group(1).split(",") if x.strip()]


def parse_page(html: str, fx_day: dict) -> list[dict]:
    promised = _promised_ids(html)
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.vehicle__car-item[data-car-id]")
    if promised and not cards:
        raise ValueError(f"page lists {len(promised)} cars but no card was parsed")

    records = []
    for card in cards:
        car_id = card.get("data-car-id", "")
        link = card.select_one("a.title-wrap__title") or card.select_one("a.info__area--ttl")
        if not car_id or link is None:
            continue
        title = " ".join(link.get_text(" ", strip=True).split())
        chassis_el = card.select_one("div.title-wrap__sub")
        chassis = chassis_el.get_text(strip=True) if chassis_el else ""
        boxes = {}
        for box in card.select("div.car-item__info-area div.main-info__box"):
            k, v = box.select_one("div.box__title"), box.select_one("div.box__body")
            if k and v:
                boxes[k.get_text(" ", strip=True)] = v.get_text(" ", strip=True)
        tags = [t.get_text(strip=True) for t in card.select("div.inner__opption-tag")]

        year_raw = boxes.get("Registration Year", "")
        year = int(year_raw) if year_raw.isdigit() else None
        if year is not None and not hilux.YEAR_MIN <= year <= hilux.YEAR_SLOP:
            continue
        # Chassis prefix and option tags ride along as the description:
        # "RN30-..." names the generation, "Diesel" rejects.
        detail = " ".join([chassis, boxes.get("Engine Capacity", "")] + tags)
        ident = hilux.classify(title, detail, year=year)
        if ident is None:
            continue

        m = _USD_RE.search(boxes.get("FOB Price", ""))
        amount = float(m.group(1).replace(",", "")) if m else None
        flag = card.select_one("span.icon-flag-wrap use")
        fm = _FLAG_RE.search((flag.get("xlink:href") or flag.get("href") or "") if flag else "")
        country = _ISO_NUMERIC.get(fm.group(1), "XX") if fm else "XX"
        drive = "RHD" if "RHD" in tags else ("LHD" if "LHD" in tags else
                                              normalize.infer_drive_side(country, detail))
        img = card.select_one("div.pic-area__main-pic img")
        image = img.get("src") if img else None
        dealer = card.select_one("span.dealer-name")

        records.append({
            "id": f"tcv:{car_id}",
            "source": SOURCE,
            "source_listing_id": car_id,
            "url": normalize.safe_url(f"{BASE}/used_car/toyota/hilux/{car_id}/"),
            "title": title,
            "title_translated": None,
            "description_snippet": (" | ".join(x for x in [
                chassis, dealer.get_text(strip=True) if dealer else ""] + tags if x)[:500] or None),
            "year": ident["year"],
            "country": country,
            "region": None,
            "drive_side": drive,
            "king_cab": ident["king_cab"],
            "variant": ident["variant"],
            "price": normalize.make_price(amount, "USD", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


_FILTER_ECHO_RE = re.compile(r"<title>[^<]*Year 1978-1984", re.I)


def collect(fx_day: dict) -> list[dict]:
    resp = httpx.get(URL, headers=HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    if not _FILTER_ECHO_RE.search(resp.text):
        raise ValueError("year filter not echoed in the page title (fid/jid ignored?)")
    return parse_page(resp.text, fx_day)
