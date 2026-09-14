"""eBay OAuth for the Browse API (client-credentials grant).

Mints an application access token from EBAY_CLIENT_ID / EBAY_CLIENT_SECRET.
Used by the M3 eBay collector; `--self-test` mints a token and walks the
collector's own route — each marketplace's vehicle category — to prove both
the credentials and the categories work, printing only statuses, counts and
matched titles (never the token or keys).
"""

from __future__ import annotations

import base64
import os
import sys

import httpx

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"


def mint_token(client: httpx.Client | None = None) -> str:
    client_id = os.environ.get("EBAY_CLIENT_ID", "")
    client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("EBAY_CLIENT_ID / EBAY_CLIENT_SECRET not set")
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    own_client = client is None
    client = client or httpx.Client(timeout=20)
    try:
        resp = client.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": SCOPE},
        )
    finally:
        if own_client:
            client.close()
    if resp.status_code != 200:
        raise RuntimeError(
            f"token mint failed: HTTP {resp.status_code} "
            f"(error={resp.json().get('error', 'unknown') if resp.headers.get('content-type','').startswith('application/json') else 'non-json'})"
        )
    return resp.json()["access_token"]


def self_test() -> int:
    """Prove the credentials AND the route the collector actually uses.

    It used to search q="datsun 620" unscoped and report a healthy-looking
    total of ~9,000 — every one of them a part. That reassuring number was
    part of why the collector's month of zero records went unexamined, so
    the self-test now walks each marketplace's vehicle category exactly as
    collect() does and reports the count that matters.
    """
    from listings import ebay  # local: ebay imports mint_token from here

    token = mint_token()
    print("token mint: OK")
    bad = 0
    with httpx.Client(timeout=20) as client:
        for marketplace, _country, category in ebay.MARKETPLACES:
            resp = client.get(
                BROWSE_SEARCH_URL,
                params={"q": ebay.QUERIES[0], "limit": 50,
                        "category_ids": category},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-EBAY-C-MARKETPLACE-ID": marketplace,
                },
            )
            if resp.status_code != 200:
                print(f"{marketplace} cat {category}: HTTP {resp.status_code} "
                      f"{resp.text[:200]}")
                bad += 1
                continue
            payload = resp.json()
            items = payload.get("itemSummaries") or []
            hits = [i for i in items
                    if ebay.is_620_title(i.get("title", ""), vehicle_scoped=True)]
            print(f"{marketplace} cat {category}: HTTP 200 "
                  f"total={payload.get('total', 0)} fetched={len(items)} "
                  f"620s={len(hits)}")
            for hit in hits:
                print(f"    {hit.get('title', '')[:70]}")
    return 1 if bad == len(ebay.MARKETPLACES) else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print("module: use mint_token() from the eBay collector, or run with --self-test")
