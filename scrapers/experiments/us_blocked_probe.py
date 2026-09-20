"""Probe: can Hemmings and Cars & Bids be reached legitimately at all?

Both have served 403 to GitHub runners for 70 consecutive days. The owner
wants their results, so the question is what LEGITIMATE route exists.

Ground rules, set before any result comes back:
  - Only public surfaces a site offers for consumption: RSS, sitemaps,
    documented/obvious JSON endpoints, structured data.
  - robots.txt is checked with urllib.robotparser and obeyed. A path it
    disallows is not probed further, whatever its status code.
  - No evasion. The existing browser User-Agent stays as it is; no
    Googlebot spoofing, no proxy rotation, no retry-until-through. If a
    site is deliberately keeping us out, the answer is "use their email
    alerts", not "get around it".

Diagnostic order matters. First: is the block IP-level or path-level?
  - robots.txt and the homepage answering 200 while search 403s means
    path-level protection, and another public path may work.
  - Everything 403 means the runner's IP range is banned outright, no
    endpoint will help, and the honest route is Phase C email alerts.

Then, if any door is open, which one carries 620 data. Also checks
classic.com, which aggregates BOTH of these plus the traditional auction
houses — one working aggregator would cover both blocked sources at once.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib import robotparser

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import carsandbids as cab
from listings import hemmings as hem

UA = hem.HEADERS["User-Agent"]
HEADERS = {"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9"}

# (label, url, accept) — accept steers content negotiation only.
HEMMINGS = [
    ("robots.txt",        "https://www.hemmings.com/robots.txt", "text/plain"),
    ("homepage",          "https://www.hemmings.com/", "text/html"),
    ("current collector", hem.URL, "text/html"),
    ("sitemap index",     "https://www.hemmings.com/sitemap.xml", "application/xml"),
    ("classifieds RSS",   "https://www.hemmings.com/classifieds/rss", "application/rss+xml"),
    ("stories RSS",       "https://www.hemmings.com/stories/rss", "application/rss+xml"),
    ("api listings",      "https://www.hemmings.com/api/listings?q=datsun+620", "application/json"),
    ("search query",      "https://www.hemmings.com/classifieds?q=datsun%20620", "text/html"),
]

CARSANDBIDS = [
    ("robots.txt",        "https://carsandbids.com/robots.txt", "text/plain"),
    ("homepage",          "https://carsandbids.com/", "text/html"),
    ("current api",       cab.API_URL, "application/json"),
    ("current page",      cab.PAGE_URL, "text/html"),
    ("sitemap",           "https://carsandbids.com/sitemap.xml", "application/xml"),
    ("past auctions",     "https://carsandbids.com/past-auctions/", "text/html"),
    ("search api v2",     "https://carsandbids.com/v2/search?q=datsun", "application/json"),
]

# One working aggregator covers BOTH blocked sources plus Mecum/RM/BJ.
AGGREGATORS = [
    ("classic.com robots",   "https://www.classic.com/robots.txt", "text/plain"),
    ("classic.com 620 page", "https://www.classic.com/m/nissan/truck/620/", "text/html"),
    ("classic.com sitemap",  "https://www.classic.com/sitemap.xml", "application/xml"),
    ("classic.com search",   "https://www.classic.com/search/?q=datsun+620", "text/html"),
]


def fetch(client, url, accept):
    try:
        resp = client.get(url, headers={**HEADERS, "Accept": accept}, timeout=30,
                          follow_redirects=True)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:90]}"
    return resp, None


def looks_useful(body: str, ctype: str) -> str:
    """Does the body carry data, or is it a challenge/shell page?"""
    low = body[:6000].lower()
    marks = []
    if any(w in low for w in ("captcha", "are you a human", "access denied",
                              "blocked", "cloudflare", "perimeterx", "datadome",
                              "incapsula", "just a moment")):
        marks.append("CHALLENGE")
    if "json" in ctype and body.strip()[:1] in "{[":
        marks.append("json")
    if "<rss" in low or "<feed" in low:
        marks.append("RSS")
    if "<urlset" in low or "<sitemapindex" in low:
        marks.append("sitemap")
    if re.search(r"\b620\b", body):
        marks.append("mentions-620")
    if re.search(r"datsun", body, re.I):
        marks.append("mentions-datsun")
    return ",".join(marks) or "-"


def run_group(client, title, rows, robots_text_holder):
    print(f"\n=== {title} ===", flush=True)
    for label, url, accept in rows:
        resp, err = fetch(client, url, accept)
        if err:
            print(f"  {label:<20} {err}", flush=True)
            continue
        ctype = resp.headers.get("content-type", "")[:40]
        body = resp.text if "image" not in ctype else ""
        # Keep the robots body for the permission verdicts below.
        if label.endswith("robots.txt") and resp.status_code == 200:
            robots_text_holder[title] = body
        print(f"  {label:<20} HTTP {resp.status_code:<4} {len(body):>8}B "
              f"{ctype:<28} {looks_useful(body, ctype)}", flush=True)
        if resp.status_code == 200 and "sitemap" in looks_useful(body, ctype):
            locs = re.findall(r"<loc>([^<]+)</loc>", body)[:6]
            for loc in locs:
                print(f"        {loc[:100]}", flush=True)


def verdicts(robots_text: str, base: str, paths: list[str]) -> None:
    if not robots_text:
        print("    (no robots.txt retrieved — treat as unknown, do not assume)",
              flush=True)
        return
    parser = robotparser.RobotFileParser()
    parser.parse(robots_text.split("\n"))
    for path in paths:
        ok = parser.can_fetch("*", base + path)
        print(f"    {path:<46} {'ALLOWED' if ok else 'DISALLOWED'}", flush=True)


def main() -> int:
    holder: dict[str, str] = {}
    with httpx.Client() as client:
        run_group(client, "Hemmings", HEMMINGS, holder)
        run_group(client, "Cars & Bids", CARSANDBIDS, holder)
        run_group(client, "Aggregator: classic.com", AGGREGATORS, holder)

        print("\n=== robots.txt verdicts for the paths that matter ===",
              flush=True)
        print("  Hemmings:", flush=True)
        verdicts(holder.get("Hemmings", ""), "https://www.hemmings.com",
                 ["/classifieds/cars-for-sale/datsun/620", "/classifieds/rss",
                  "/sitemap.xml", "/api/listings"])
        print("  Cars & Bids:", flush=True)
        verdicts(holder.get("Cars & Bids", ""), "https://carsandbids.com",
                 ["/v2/autos/auctions", "/search/datsun%20620",
                  "/past-auctions/", "/sitemap.xml"])
        print("  classic.com:", flush=True)
        verdicts(holder.get("Aggregator: classic.com", ""),
                 "https://www.classic.com",
                 ["/m/nissan/truck/620/", "/sitemap.xml", "/search/"])

        print("\n=== read this as ===", flush=True)
        print("  robots+homepage 200 but search 403 -> path-level, another "
              "public path may work", flush=True)
        print("  everything 403                     -> runner IP banned; no "
              "endpoint helps, use Phase C email alerts", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
