"""Probe: is Kleinanzeigen returning 0 because the market is empty, or
because the collector cannot see?

Context. It threw one 403 on 2026-09-15 and has run clean for the four
days since, so the block was a blip rather than a wall. The open question
is the other one: it has reported "ok, 0 listings" every single day of
its life, which is the exact profile eBay had while structurally blind.

Two specific suspicions, both from the eBay diagnosis:

1. The query may be too narrow. The URL searches the keyword phrase
   "datsun-pickup", so an ad titled "Datsun 620" or "Datsun Kleinlaster"
   with no "Pickup" in it would never appear.
2. The blocked-page guard is nearly inert. parse_page only raises when
   there are NO ads AND the word "datsun" is absent — but the search term
   is echoed back in the page chrome, so "datsun" is present even on an
   empty or challenged page. A broken fetch therefore returns [] quietly,
   which is precisely how a month of eBay zeros hid.

So: how many ads does each candidate query actually return, and what are
they? Also reads robots.txt first — whatever is disallowed there is off
limits, as it was for everycar.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import fx
from common.patterns import RE_620, RE_OTHER_GEN
from listings import kleinanzeigen as kz

# c216 = Autos. Both the phrase search the collector uses and broader
# terms a real 620 might actually be titled with.
CANDIDATES = [
    ("collector's current URL", kz.URL),
    ("marque only",            f"{kz.BASE}/s-autos/datsun/k0c216"),
    ("model code",             f"{kz.BASE}/s-autos/datsun-620/k0c216"),
    ("marque, all categories", f"{kz.BASE}/s-datsun/k0"),
    ("oldtimer category",      f"{kz.BASE}/s-autos/datsun/k0c216+autos.art_s:oldtimer"),
]


def summarise(client: httpx.Client, label: str, url: str, fx_day: dict) -> None:
    try:
        resp = client.get(url, headers=kz.HEADERS, timeout=30,
                          follow_redirects=True)
    except Exception as exc:
        print(f"  {label}\n      {type(exc).__name__}: {str(exc)[:110]}")
        return
    html = resp.text
    soup = BeautifulSoup(html, "html.parser")
    ads = soup.find_all("article", class_=re.compile(r"\baditem\b"))
    with_id = [a for a in ads if a.get("data-adid")]
    # Does the collector's own emptiness guard even fire on this page?
    guard_would_raise = not ads and "datsun" not in html.lower()
    challenge = any(w in html.lower() for w in
                    ("akamai", "captcha", "are you a human", "zugriff verweigert"))
    print(f"  {label}\n      {url}")
    print(f"      HTTP {resp.status_code}  {len(html)}B  ads={len(ads)} "
          f"with_adid={len(with_id)}  challenge_words={challenge}  "
          f"guard_would_raise={guard_would_raise}")
    if resp.status_code != 200:
        return
    try:
        recs = kz.parse_page(html, fx_day)
        print(f"      parse_page -> {len(recs)} record(s)")
    except Exception as exc:
        print(f"      parse_page raised: {type(exc).__name__}: {str(exc)[:80]}")
    # Every ad title, with the model gates applied, so we can see exactly
    # what is being dropped and why.
    for ad in ads[:25]:
        t_el = ad.select_one(".aditem-main--middle h2 a") or ad.find("h2")
        title = t_el.get_text(" ", strip=True) if t_el else "(no title)"
        d_el = ad.select_one(".aditem-main--middle p")
        desc = d_el.get_text(" ", strip=True) if d_el else ""
        text = f"{title} {desc}"
        is620 = bool(RE_620.search(text))
        other = bool(RE_OTHER_GEN.search(text))
        verdict = "KEPT" if (is620 and not other) else (
            "drop:other-gen" if other else "drop:not-620")
        print(f"        [{verdict:<14}] {title[:72]}")


def main() -> int:
    fx_day = {"date": "2026-09-19", "base": "GBP",
              "rates": {"EUR": 1.17, "USD": 1.27, "JPY": 190.0, "THB": 43.0}}
    with httpx.Client() as client:
        print("=== robots.txt (what we may not touch) ===")
        try:
            r = client.get(f"{kz.BASE}/robots.txt", headers=kz.HEADERS, timeout=30)
            lines = [l for l in r.text.split("\n") if l.strip()]
            print(f"  HTTP {r.status_code}, {len(lines)} lines; "
                  f"Disallow entries mentioning our paths:")
            for l in lines:
                if re.search(r"s-autos|/s-|disallow:\s*/\s*$", l, re.I):
                    print(f"    {l[:100]}")
        except Exception as exc:
            print(f"  {type(exc).__name__}: {str(exc)[:80]}")

        print("\n=== candidate searches ===")
        for label, url in CANDIDATES:
            summarise(client, label, url, fx_day)
    return 0


if __name__ == "__main__":
    sys.exit(main())
