"""eBay OAuth for the Browse API (client-credentials grant).

Mints an application access token from EBAY_CLIENT_ID / EBAY_CLIENT_SECRET.
Used by the M3 eBay collector; `--self-test` mints a token and makes one
Browse API search to prove the credentials work, printing only statuses and
counts (never the token or keys).
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
    token = mint_token()
    print("token mint: OK")
    with httpx.Client(timeout=20) as client:
        resp = client.get(
            BROWSE_SEARCH_URL,
            params={"q": "datsun 620", "limit": 3},
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            },
        )
    print(f"browse search: HTTP {resp.status_code}")
    if resp.status_code != 200:
        print(resp.text[:500])
        return 1
    payload = resp.json()
    print(f"browse search: total={payload.get('total', 0)} items for 'datsun 620' on EBAY_US")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(self_test())
    print("module: use mint_token() from the eBay collector, or run with --self-test")
