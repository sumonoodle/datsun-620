"""Probe round 3: the two live leads.

Round 2 produced one dead end, one near-miss and one genuine opening.

DEAD END — Hemmings' other sitemaps carry only category pages
(classic-cars-for-sale-alabama, metro-search/st-louis-mo, and so on). No
individual ads anywhere, so there is no "link to the listing" route from
those.

NEAR MISS — sitemap_makes.xml (1034 entries) includes
/sitemap_makes/datsun.xml, but the probe followed only the first three
nested files alphabetically (aar, abarth, abbott_detroit) and never
reached it. That cap was mine, not the site's. If datsun.xml enumerates
individual ads then the degraded-but-real route stands: report that a 620
is listed and link to it. If it holds category pages like its siblings,
Hemmings is closed and the answer is their email alerts.

OPENING — AutoTempest answered HTTP 200 with 236KB, robots ALLOWS the
search path, and the body mentions both datsun and 620. It is a
meta-search across eBay, Craigslist, Cars.com, CarGurus, Autotrader and
others, so it could reach inventory we cannot. The catch: meta-search
sites usually fetch each partner by XHR after page load, in which case
that 236KB is a shell and "620" is just the query echoed back. This round
settles that by counting real listing markup rather than trusting a
keyword match.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib import robotparser

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import hemmings as hem

HEADERS = {"User-Agent": hem.HEADERS["User-Agent"],
           "Accept-Language": "en-GB,en;q=0.9"}
DATSUN_SITEMAP = "https://www.hemmings.com/sitemap_makes/datsun.xml"
AT_BASE = "https://www.autotempest.com"
AT_SEARCH = f"{AT_BASE}/results?make=datsun&model=620"


def get(client, url, accept="*/*"):
    try:
        return client.get(url, headers={**HEADERS, "Accept": accept},
                          timeout=40, follow_redirects=True), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:90]}"


def main() -> int:
    with httpx.Client() as client:
        print("=== A. Hemmings: the datsun sub-sitemap ===", flush=True)
        resp, err = get(client, DATSUN_SITEMAP, "application/xml")
        if err:
            print(f"  {err}", flush=True)
        else:
            body = resp.text
            print(f"  HTTP {resp.status_code}  {len(body)}B", flush=True)
            if resp.status_code == 200:
                locs = re.findall(r"<loc>([^<]+)</loc>", body)
                # An individual ad ends in a long numeric id; a category page
                # does not. That distinction is the whole question.
                ads = [l for l in locs if re.search(r"/\d{6,}/?$", l)]
                six20 = [l for l in locs if re.search(r"/620(?:/|$)|620", l)]
                nested = [l for l in locs if "sitemap" in l.lower()]
                print(f"  locs={len(locs)} individual-ad-like={len(ads)} "
                      f"mentioning-620={len(six20)} nested={len(nested)}",
                      flush=True)
                for label, group in (("ad-like", ads), ("620", six20),
                                     ("nested", nested), ("any", locs)):
                    if group:
                        print(f"  sample {label}:", flush=True)
                        for s in group[:8]:
                            print(f"      {s[:110]}", flush=True)
                        break
                # lastmod would tell us when a listing appeared.
                lastmods = re.findall(r"<lastmod>([^<]+)</lastmod>", body)
                print(f"  lastmod entries: {len(lastmods)}"
                      + (f"  newest={max(lastmods)[:10]}" if lastmods else ""),
                      flush=True)

        print("\n=== B. AutoTempest: real listings, or a shell? ===", flush=True)
        r, rerr = get(client, f"{AT_BASE}/robots.txt", "text/plain")
        if rerr or r.status_code != 200:
            print(f"  robots: {rerr or r.status_code} — stopping, "
                  f"permission unknown", flush=True)
            return 0
        parser = robotparser.RobotFileParser()
        parser.parse(r.text.split("\n"))
        allowed = parser.can_fetch("*", AT_SEARCH)
        print(f"  robots allows /results: {allowed}", flush=True)
        if not allowed:
            print("  -> not probed further, robots says no", flush=True)
            return 0

        resp, err = get(client, AT_SEARCH, "text/html")
        if err:
            print(f"  {err}", flush=True)
            return 0
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        print(f"  HTTP {resp.status_code}  {len(html)}B", flush=True)
        # Count plausible result containers. A shell has none of these.
        for sel in ["div.result", "div.listing", "li.result", "[data-listing]",
                    "article", ".result-list-item", ".srp-item", "a[href*='/go/']"]:
            try:
                print(f"    {sel:<24} {len(soup.select(sel))}", flush=True)
            except Exception as exc:
                print(f"    {sel:<24} selector error {exc}", flush=True)
        # Does any partner-site name appear next to a price? That is what a
        # real result row looks like.
        prices = re.findall(r"\$[\d,]{4,}", html)
        print(f"    price-like strings: {len(prices)} "
              f"{prices[:8]}", flush=True)
        for word in ["ebay", "craigslist", "cars.com", "cargurus", "autotrader",
                     "hemmings", "__NEXT_DATA__", "window.__", "application/ld+json"]:
            print(f"    mentions {word:<20} {word.lower() in html.lower()}",
                  flush=True)
        # If it ships JSON, that is the parse target.
        for tag in soup.find_all("script", type="application/ld+json")[:2]:
            raw = (tag.string or "").strip()
            print(f"    ld+json block {len(raw)}B: {raw[:200]}", flush=True)
        title = soup.title.get_text(strip=True) if soup.title else "(none)"
        print(f"    <title> {title[:90]}", flush=True)
        # Headline text tells us whether it rendered results server-side.
        for tag in soup.find_all(["h1", "h2"])[:6]:
            t = tag.get_text(" ", strip=True)
            if t:
                print(f"    {tag.name}: {t[:90]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
