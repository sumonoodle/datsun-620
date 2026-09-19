"""Probe round 2: may we scrape Kleinanzeigen at all, and if so, what
does the results markup look like now?

Round 1 returned two things that have to be taken in order.

FIRST, a permission question. robots.txt contains a bare "Disallow: /",
but round 1 printed matching lines without the User-agent block each
belongs to, so it is unknown whether that rule binds us. If the "*" group
disallows the search paths, the correct outcome is to retire the
collector and move Kleinanzeigen to its Suchauftrag email alerts - not to
repair a parser we should not be running. No parser work happens until
this is answered, which is why this probe answers it first and plainly.

SECOND, a blindness question, only worth acting on if the answer above
permits. All five candidate searches returned HTTP 200 with ZERO
article.aditem elements - including the marque alone across every
category, in 810KB of HTML, with no challenge words. Germany always has
some Datsun listing, so "the market is empty" does not explain this; the
selector is the likelier suspect. Round 1 also confirmed the collector's
emptiness guard never fires (guard_would_raise=False on every page), so
it has been returning [] quietly on pages it cannot read - the eBay
failure mode exactly.

Prints the robots.txt groups verbatim, then counts a spread of plausible
card selectors and looks for an embedded JSON payload, which would mean
the page went client-rendered.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib import robotparser

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import kleinanzeigen as kz

TARGET_PATHS = ["/s-autos/datsun-pickup/k0c216", "/s-autos/datsun/k0c216",
                "/s-datsun/k0"]


def robots_groups(text: str) -> list[tuple[list[str], list[str]]]:
    """robots.txt as [(user-agents, rules)], preserving which rule is whose."""
    groups: list[tuple[list[str], list[str]]] = []
    agents: list[str] = []
    rules: list[str] = []
    last_was_agent = False
    for raw in text.split("\n"):
        line = raw.split("#")[0].strip()
        if not line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if rules:                      # a new group starts here
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value)
            last_was_agent = True
        else:
            rules.append(f"{field}: {value}")
            last_was_agent = False
    if agents or rules:
        groups.append((agents, rules))
    return groups


# The verdict comes from the standard library's robots parser, not a
# hand-rolled matcher: the first attempt at one crashed on a rule
# containing regex metacharacters, and a permission check is exactly the
# wrong place to trust my own parsing.
def allows(robots_text: str, path: str, agent: str = "*") -> bool:
    parser = robotparser.RobotFileParser()
    parser.parse(robots_text.split("\n"))
    return parser.can_fetch(agent, kz.BASE + path)


def main() -> int:
    with httpx.Client() as client:
        print("=== A. robots.txt, grouped by user-agent ===")
        r = client.get(f"{kz.BASE}/robots.txt", headers=kz.HEADERS, timeout=30)
        groups = robots_groups(r.text)
        print(f"  {len(groups)} group(s)")
        star_rules: list[str] = []
        for agents, rules in groups:
            blanket = any(rule.strip() == "disallow: /" for rule in rules)
            mark = "   <<< BLANKET DISALLOW" if blanket else ""
            print(f"    user-agents={agents}  rules={len(rules)}{mark}")
            if "*" in agents:
                star_rules = rules
        print(f"\n  Rules for user-agent '*' ({len(star_rules)} of them); "
              f"the non-pagination ones:", flush=True)
        for rule in star_rules:
            # Hundreds of /*/seite:NN* pagination rules would bury the rest.
            if re.search(r"seite:\d+", rule):
                continue
            print(f"    {rule}", flush=True)
        print(f"    ({sum(1 for r in star_rules if re.search(r'seite:.d+', r))} "
              f"pagination rules omitted)", flush=True)
        print("\n  Verdict for the paths we fetch (stdlib robotparser):",
              flush=True)
        for path in TARGET_PATHS:
            ok = allows(r.text, path)
            print(f"    {path}: {'ALLOWED' if ok else 'DISALLOWED'}", flush=True)

        print("\n=== B. what the results page actually contains ===")
        url = f"{kz.BASE}/s-autos/datsun/k0c216"
        resp = client.get(url, headers=kz.HEADERS, timeout=30,
                          follow_redirects=True)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        print(f"  {url}\n      HTTP {resp.status_code}  {len(html)}B  "
              f"final={str(resp.url)[:80]}")
        selectors = [
            "article.aditem", "article", "[data-adid]", "li.ad-listitem",
            ".ad-listitem", "#srchrslt-adtable", ".aditem-main",
            "[data-testid]", "main", "noscript",
        ]
        for sel in selectors:
            try:
                print(f"      {sel:<22} {len(soup.select(sel))}")
            except Exception as exc:
                print(f"      {sel:<22} selector error: {exc}")
        # Client-rendered pages ship their data as JSON instead of markup.
        for needle in ["__NEXT_DATA__", "application/ld+json", "window.__",
                       "adId", "\"ads\"", "Datsun", "datsun"]:
            print(f"      contains {needle!r}: {needle in html}")
        title = soup.title.get_text(strip=True) if soup.title else "(none)"
        print(f"      <title> {title[:100]}")
        for tag in soup.find_all(["h1", "h2"])[:6]:
            text = tag.get_text(" ", strip=True)
            if text:
                print(f"      {tag.name}: {text[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
