"""Probe round 3: did Kaidee's car search move to www.kaidee.com?

Round 2 settled what the 5KB response is, and it is NOT a block. It is a
genuine Vite SPA shell: <div id="app"></div>, /assets/index-*.js, hashed
CSS bundles, Google Tag Manager. Kaidee replaced the server-rendered
Next.js site, so the __NEXT_DATA__ route this collector used is gone for
good rather than temporarily moved.

Two findings from round 2 drive this round.

FIRST, a correction to round 1. It reported "robots 200; search path
allowed: True", and that was meaningless: rod.kaidee.com serves the same
5,077-byte SPA shell for EVERY path including /robots.txt, so
RobotFileParser was handed an HTML document, found no directives, and
defaulted to permissive. There is currently no readable robots.txt on that
host, which means permission for any new endpoint is unestablished — and
that has to be fixed before, not after, choosing a parse target.

SECOND, a lead. Fetching /assets/index-*.js from rod.kaidee.com redirected
to www.kaidee.com and returned 728 bytes — too small to be a real bundle,
so that asset path is falling through to a stub as well. Combined with
root and search page being byte-identical, it looks like rod.kaidee.com is
now a legacy host and the live site is www.kaidee.com.

So: does www.kaidee.com serve a readable robots.txt and real
server-rendered car listings? If yes, the collector moves host and is
fixed. If it is the same SPA shell, then Kaidee has gone client-rendered
everywhere and the honest answer is that it leaves the scrape layer.

Scaffolding: delete once the finding is acted on.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib import robotparser
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from listings import kaidee as kd

WWW = "https://www.kaidee.com"
CANDIDATES = [
    ("www root",          f"{WWW}/"),
    ("www old car path",  f"{WWW}/c11-auto-car?q={quote('datsun')}"),
    ("www search",        f"{WWW}/search?q={quote('datsun')}"),
    ("www category cars", f"{WWW}/category/c11-auto-car"),
    ("www thai query",    f"{WWW}/search?q={quote('ดัทสัน')}"),
]


def get(client, url, accept="*/*"):
    try:
        return client.get(url, headers={**kd.HEADERS, "Accept": accept},
                          timeout=40, follow_redirects=True), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {str(exc)[:100]}"


def main() -> int:
    with httpx.Client() as client:
        print("=== A. is there a READABLE robots.txt anywhere? ===", flush=True)
        for host in [WWW, kd.BASE]:
            r, err = get(client, f"{host}/robots.txt", "text/plain")
            if err:
                print(f"  {host}: {err}", flush=True)
                continue
            body = r.text
            # A real robots.txt is plain text with directives, not HTML.
            is_real = ("<!doctype" not in body[:200].lower()
                       and re.search(r"(?im)^\s*(user-agent|disallow|allow)\s*:",
                                     body) is not None)
            print(f"  {host}/robots.txt HTTP {r.status_code} {len(body)}B "
                  f"real-robots={is_real}", flush=True)
            if is_real:
                p = robotparser.RobotFileParser()
                p.parse(body.split("\n"))
                for path in ["/c11-auto-car", "/search", "/api/"]:
                    print(f"      {path:<16} "
                          f"{'ALLOWED' if p.can_fetch('*', host + path) else 'DISALLOWED'}",
                          flush=True)
                for line in body.splitlines()[:14]:
                    if line.strip():
                        print(f"      {line[:90]}", flush=True)

        print("\n=== B. does www serve real listings? ===", flush=True)
        shell_len = None
        for label, url in CANDIDATES:
            resp, err = get(client, url, "text/html")
            if err:
                print(f"  {label:<20} {err}", flush=True)
                continue
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            prod = soup.select("a[href*='/product-'], a[href*='/ad/']")
            has_data = any(m in html for m in
                           ("__NEXT_DATA__", "self.__next_f", "__NUXT__",
                            "application/ld+json"))
            mentions = "datsun" in html.lower() or "ดัทสัน" in html
            if shell_len is None and label == "www root":
                shell_len = len(html)
            same_as_root = (shell_len is not None and len(html) == shell_len)
            print(f"  {label:<20} HTTP {resp.status_code} {len(html):>8}B "
                  f"product-links={len(prod)} payload={has_data} "
                  f"mentions-datsun={mentions} same-size-as-root={same_as_root}",
                  flush=True)
            for a in prod[:4]:
                print(f"        {a.get('href')[:80]} :: "
                      f"{a.get_text(' ', strip=True)[:45]!r}", flush=True)

        print("\n=== C. the real JS bundle, if we can reach it ===", flush=True)
        resp, err = get(client, f"{WWW}/", "text/html")
        if not err and resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            srcs = [s.get("src") for s in soup.find_all("script", src=True)]
            print(f"  script srcs: {srcs[:6]}", flush=True)
            api_pat = re.compile(
                r"https://[a-z0-9.\-]*kaidee\.com/[A-Za-z0-9/_\-.]{3,}"
                r"|/api/v?\d?/[A-Za-z0-9/_\-.]+|graphql", re.I)
            for s in srcs[:3]:
                url = urljoin(f"{WWW}/", s)
                r2, e2 = get(client, url, "application/javascript")
                if e2 or r2.status_code != 200:
                    print(f"  {url[:70]}: {e2 or r2.status_code}", flush=True)
                    continue
                hits = sorted(set(api_pat.findall(r2.text)))
                print(f"  {url[:70]}: {len(r2.text)}B "
                      f"api-like={len(hits)}", flush=True)
                for h in hits[:20]:
                    print(f"      {h[:95]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
