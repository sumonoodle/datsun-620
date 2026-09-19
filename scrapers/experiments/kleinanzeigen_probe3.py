"""Probe round 3: capture Kleinanzeigen's CURRENT card markup.

Rounds 1-2 settled both prior questions:

  - robots.txt ALLOWS the paths we fetch; the bare "Disallow: /" belongs
    to other named user-agents, not "*".
  - The collector is blind, and precisely why: the page reports
    "Autos 1 - 25 von 28 Gebrauchtwagen für „datsun“" — 28 real Datsun
    cars in Germany — while article.aditem matches 0 and .aditem-main
    matches 0. The "aditem" class is gone; 25 <article> elements each
    carrying data-adid are there instead. So every inner selector the
    parser uses (.aditem-main--middle h2 a, .aditem-main--middle p,
    .aditem-main--top--left) is dead too, and must be re-derived from
    what the page actually ships now.

This round dumps what the parser needs and nothing else: the ld+json
blocks (structured data is a far more stable parse target than CSS
classes, and the page has some), then the trimmed HTML of the first few
article[data-adid] cards. From that the collector can be rewritten
against real markup and pinned with a trimmed fixture, as every other
collector here was.

Scaffolding: delete once the collector is fixed.
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

from listings import kleinanzeigen as kz

URL = f"{kz.BASE}/s-autos/datsun/k0c216"


def main() -> int:
    with httpx.Client() as client:
        resp = client.get(URL, headers=kz.HEADERS, timeout=30,
                          follow_redirects=True)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        print(f"HTTP {resp.status_code}  {len(html)}B", flush=True)

        print("\n=== A. ld+json structured data ===", flush=True)
        for i, tag in enumerate(soup.find_all("script",
                                              type="application/ld+json")[:4]):
            raw = tag.string or ""
            print(f"  block {i}: {len(raw)}B", flush=True)
            try:
                data = json.loads(raw)
            except Exception as exc:
                print(f"    unparseable: {exc}", flush=True)
                continue
            # Print the shape rather than the whole payload: top-level keys,
            # and the first item if it is a list of offers.
            def shape(obj, depth=0):
                pad = "    " + "  " * depth
                if isinstance(obj, dict):
                    print(f"{pad}keys: {list(obj)[:12]}", flush=True)
                    for k in ("itemListElement", "offers", "mainEntity"):
                        if k in obj:
                            v = obj[k]
                            print(f"{pad}{k}: {type(v).__name__} "
                                  f"len={len(v) if isinstance(v, list) else '-'}",
                                  flush=True)
                            if isinstance(v, list) and v and depth < 2:
                                shape(v[0], depth + 1)
                elif isinstance(obj, list):
                    print(f"{pad}list len={len(obj)}", flush=True)
                    if obj and depth < 2:
                        shape(obj[0], depth + 1)
            shape(data)
            if len(raw) < 1200:
                print(f"    raw: {raw.strip()[:1100]}", flush=True)

        print("\n=== B. first article[data-adid] cards, trimmed ===", flush=True)
        cards = soup.select("article[data-adid]")
        print(f"  {len(cards)} card(s)", flush=True)
        for card in cards[:3]:
            print("\n  " + "-" * 66, flush=True)
            print(f"  data-adid={card.get('data-adid')} "
                  f"data-href={card.get('data-href')}", flush=True)
            print(f"  classes={card.get('class')}", flush=True)
            # Which descendants carry the fields we need?
            for label, sel in [("h2", "h2"), ("h2 a", "h2 a"),
                               ("any a[href]", "a[href]"), ("img", "img")]:
                el = card.select_one(sel)
                if el is None:
                    print(f"    {label:<12} (none)", flush=True)
                elif el.name == "img":
                    print(f"    {label:<12} src={el.get('src')} "
                          f"data-src={el.get('data-src')}", flush=True)
                else:
                    print(f"    {label:<12} href={el.get('href')} "
                          f"text={el.get_text(' ', strip=True)[:60]!r}", flush=True)
            # Class names of every child div/p/span, which is what a new
            # parser would key on.
            named = []
            for el in card.find_all(["div", "p", "span"], class_=True):
                cls = " ".join(el.get("class"))
                text = el.get_text(" ", strip=True)[:45]
                if text:
                    named.append(f"{cls} :: {text}")
            for line in named[:18]:
                print(f"      {line}", flush=True)
            print(f"    full text: {card.get_text(' ', strip=True)[:170]!r}",
                  flush=True)

        print("\n=== C. is page 2 allowed? (28 results, 25 per page) ===",
              flush=True)
        r = client.get(f"{kz.BASE}/robots.txt", headers=kz.HEADERS, timeout=30)
        parser = robotparser.RobotFileParser()
        parser.parse(r.text.split("\n"))
        for path in ["/s-autos/datsun/seite:2/k0c216", "/s-autos/datsun/seite:48/k0c216"]:
            ok = parser.can_fetch("*", kz.BASE + path)
            print(f"  {path}: {'ALLOWED' if ok else 'DISALLOWED'}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
