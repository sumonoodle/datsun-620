"""One-shot experiment (PRD 4.4): does Buyee serve a real browser what it
refuses to plain HTTP? Run manually / from the branch workflow; never part of
the daily pipeline. Prints evidence for docs/japan-sources.md."""

from __future__ import annotations

from urllib.parse import quote

from playwright.sync_api import sync_playwright

URL = f"https://buyee.jp/item/search/query/{quote('ダットサン 620')}"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            locale="en-GB",
        )
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        status = resp.status if resp else None
        title = page.title()
        item_links = page.locator('a[href*="/item/yahoo/auction/"]').count()
        blocked_markers = page.locator("text=/captcha|access denied|forbidden/i").count()
        print(f"status={status} title={title!r} item_links={item_links} "
              f"blocked_markers={blocked_markers}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
