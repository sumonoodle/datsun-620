"""Collector: Kleinanzeigen.de (ex-eBay Kleinanzeigen), Datsun cars.

Germany's dominant classifieds; research found real 620s passing through
(about 1-3 a year) amid Hot Wheels noise, which the cars category (c216)
strips.

Rewritten 2026-09-19 after the site's redesign left this collector blind.
It had reported "ok, 0 listings" every day of its life while the results
page carried 28 real Datsun cars, because Kleinanzeigen dropped the
"aditem" class: article.aditem matched 0, .aditem-main matched 0, and
there is no <h2> in a card any more. The old emptiness guard could not
catch it either — it only raised when the page held no ads AND no
"datsun", but the search term is echoed in the page chrome, so a page it
could not read still looked fine. Both failures are the eBay pattern:
a collector reporting success while seeing nothing.

So this version keys on what the redesign kept and what the site
maintains deliberately, not on presentation:

- article[data-adid] and its data-href are data attributes that survived
  the redesign intact, and give identity and URL.
- Title and description come from the ld+json ImageObject blocks the page
  publishes per ad for search engines — semantic data, joined to each
  card by image id. The surrounding classes are Tailwind utilities
  ("mb-xsmall text-bodyRegular text-onSurfaceSubdued") that will not
  survive the next restyle, so they are never selected on.
- Price, registration year and location are read from the card's text.
  "EZ 07/1979" is a better year than anything guessable from a title.

The guard now compares the result count in the heading against the cards
parsed: a heading promising results with no cards parsed means the markup
moved again and MUST raise, while a heading of zero results is simply an
empty market and returns nothing. That is the everycar lesson — never let
"cannot see" and "nothing there" share an outcome.

robots.txt permits these paths for user-agent "*" (checked 2026-09-19;
the bare "Disallow: /" in that file belongs to other named agents). It
disallows ?keyword= style endpoints, which this does not use.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import king_cab, normalize
from common.patterns import RE_620, RE_OTHER_GEN

SOURCE = "kleinanzeigen"
BASE = "https://www.kleinanzeigen.de"
# The marque alone, not "datsun-pickup": a 620 advertised as "Datsun 620"
# with no "Pickup" in it never matched the old phrase search. The whole
# marque is only ~28 cars nationwide, which the 620 gate handles easily.
SEARCH = "/s-autos/datsun/k0c216"
# "seite:N" sits between the category and the keyword. Putting it after the
# keyword (the first guess here) redirect-loops, which the live branch test
# caught; the shapes are probed in that order and the first that answers
# with cards wins, so a future move costs page 2, never page 1.
PAGE_SEARCH = ["/s-autos/seite:{page}/datsun/k0c216",
               "/s-autos/datsun/k0c216/seite:{page}"]
MAX_PAGES = 3  # 28 results at 25/page; a cap keeps a runaway paginator honest
PER_PAGE = 25
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    "Accept-Language": "de,en;q=0.8",
}

# "19.990 €" — German thousands dot. RE_620's dot guard (added the same
# day as this rewrite) stops such figures reading as model references.
_EUR_RE = re.compile(r"([\d.]+)\s*€")
# "EZ 07/1979" = Erstzulassung, the first-registration date.
_EZ_RE = re.compile(r"EZ\s*(\d{1,2})/((?:19|20)\d{2})")
# "31275 Lehrte 18.06.2026" / "94072 Bad Füssing Heute, 08:34"
_PLACE_RE = re.compile(
    r"(\d{5}\s+\D+?)\s+(?:Heute|Gestern|\d{2}\.\d{2}\.\d{4})")
# "Autos 1 - 25 von 28 Gebrauchtwagen für „datsun“"
_COUNT_RE = re.compile(r"von\s+([\d.]+)\s+\w", re.I)
_IMAGE_KEY_RE = re.compile(r"/images/([^?\s]+)")


def _image_key(url: str) -> str:
    """The stable part of an image URL, shared by card and ld+json.

    The card serves "...?rule=$_2.AUTO" and the ld+json "...?rule=$_59.AUTO"
    for the same picture, so the path before the query joins them.
    """
    m = _IMAGE_KEY_RE.search(url or "")
    return m.group(1) if m else ""


def _ld_text(soup: BeautifulSoup) -> dict[str, tuple[str, str]]:
    """(title, description) per ad, keyed by image id, from ld+json."""
    out: dict[str, tuple[str, str]] = {}
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue  # one malformed block must not cost the whole page
        if not isinstance(data, dict) or data.get("@type") != "ImageObject":
            continue
        key = _image_key(data.get("contentUrl", ""))
        if key:
            out[key] = (data.get("title") or "", data.get("description") or "")
    return out


def _title_from_href(href: str) -> str:
    """Fallback title from the ad slug, e.g. /s-anzeige/datsun-620-pickup/...

    Used only when a card has no ld+json twin. Lossy, but derived from a
    stable attribute, and good enough for the model gate and for the owner
    to recognise the truck.
    """
    m = re.search(r"/s-anzeige/([^/]+)/", href or "")
    return m.group(1).replace("-", " ").strip().title() if m else ""


def _result_count(soup: BeautifulSoup) -> int | None:
    """How many results the page says it has, or None if it does not say."""
    heading = soup.find("h1")
    if not heading:
        return None
    m = _COUNT_RE.search(heading.get_text(" ", strip=True))
    return int(m.group(1).replace(".", "")) if m else None


def parse_page(html: str, fx_day: dict) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("article[data-adid]")
    claimed = _result_count(soup)
    # The guard that the old inert one should have been: the heading and
    # the cards must agree. Results promised but none parsed means the
    # markup moved and we are blind again — raise, never return [].
    if not cards and claimed:
        raise ValueError(
            f"heading claims {claimed} result(s) but no article[data-adid] "
            f"parsed — card markup changed again?")

    ld = _ld_text(soup)
    records = []
    seen: set[str] = set()
    for card in cards:
        ad_id = card.get("data-adid") or ""
        if not ad_id or ad_id in seen:
            continue
        href = card.get("data-href") or ""
        img = card.find("img")
        image = img.get("src") if img else None
        title, desc = ld.get(_image_key(image or ""), ("", ""))
        if not title:
            title = _title_from_href(href)
        text = f"{title} {desc}"

        # The cars category carries every Datsun generation; only 620-era
        # trucks belong. Title AND description are searched because German
        # ads routinely put the model in the body ("Datsun Pick Up, Typ
        # 620"), unlike eBay where a description mentioning the 620 is
        # usually a different truck citing it.
        if not RE_620.search(text):
            continue
        if RE_OTHER_GEN.search(text):
            continue
        seen.add(ad_id)

        card_text = card.get_text(" ", strip=True)
        pm = _EUR_RE.search(card_text)
        amount = float(pm.group(1).replace(".", "")) if pm else None
        ez = _EZ_RE.search(card_text)
        year = int(ez.group(2)) if ez else normalize.extract_year(text)
        place = _PLACE_RE.search(card_text)
        region = place.group(1).strip() if place else None

        records.append({
            "id": f"kleinanzeigen:{ad_id}",
            "source": SOURCE,
            "source_listing_id": ad_id,
            "url": normalize.safe_url(BASE + href if href.startswith("/") else href),
            "title": title,
            "title_translated": None,
            "description_snippet": (desc[:500] or None),
            "year": year,
            "country": "DE",
            "region": region,
            "drive_side": normalize.infer_drive_side("DE", text),
            "king_cab": king_cab.check(title, desc),
            "price": normalize.make_price(amount, "EUR", fx_day),
            "images": [image] if image else [],
            "status": "active",
        })
    return records


def _fetch_page(client: httpx.Client, page: int) -> str | None:
    """One results page, or None if this page number cannot be reached.

    Page 1 has a single known URL. Later pages try the known pagination
    shapes in turn: a wrong one redirect-loops rather than 404ing, so a
    guess must never be fatal.
    """
    if page == 1:
        resp = client.get(BASE + SEARCH)
        resp.raise_for_status()
        return resp.text
    for shape in PAGE_SEARCH:
        try:
            resp = client.get(BASE + shape.format(page=page))
            resp.raise_for_status()
        except Exception:
            continue
        if BeautifulSoup(resp.text, "html.parser").select("article[data-adid]"):
            return resp.text
    return None


def collect(fx_day: dict) -> list[dict]:
    records: list[dict] = []
    seen: set[str] = set()
    # max_redirects low and explicit: a malformed pagination URL loops, and
    # 20 pointless round-trips at someone else's expense is not acceptable.
    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS,
                      max_redirects=5) as client:
        for page in range(1, MAX_PAGES + 1):
            try:
                html = _fetch_page(client, page)
            except Exception:
                if page == 1:
                    raise  # page 1 failing IS the source failing
                break
            if html is None:
                # Pagination unreachable. Page 1 holds 25 of ~28 results, so
                # this is a small gap, not a failure — say so and keep them.
                print(f"kleinanzeigen: page {page} unreachable, "
                      f"continuing with {len(records)} record(s) from page 1")
                break
            for rec in parse_page(html, fx_day):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    records.append(rec)
            # A short page is the last page; nothing to paginate into.
            if len(BeautifulSoup(html, "html.parser")
                   .select("article[data-adid]")) < PER_PAGE:
                break
    return records
