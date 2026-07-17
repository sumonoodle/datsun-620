"""Daily digest: render changes + source health into a mobile-first HTML email.

Reads data/changes-latest.json, data/run-log.json and data/listings.json,
writes data/digest-latest.html (the dry-run artifact, also published to the
site as /digest.html), and sends via Gmail SMTP ONLY when GMAIL_USER and
GMAIL_APP_PASSWORD are set AND the DIGEST_LIVE env/repo variable is "1".
Until then every run is a dry run per PRD 9.

Layout rules per PRD 4.3: plain HTML, inline styles, single column, large tap
targets, no tracking pixels. Tables are used for structure because mobile mail
clients (Gmail, Apple Mail) ignore most CSS layout.
"""

from __future__ import annotations

import html
import json
import os
import smtplib
import ssl
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scrapers"))

from common.schema import DATA_DIR

SOURCE_NAMES = {
    "ebay": "eBay", "bringatrailer": "Bring a Trailer", "carsandbids": "Cars & Bids",
    "hemmings": "Hemmings", "goonet_exchange": "Goo-net Exchange",
    "carsensor": "Carsensor", "yahoo_auctions": "Yahoo Auctions JP",
    "kaidee": "Kaidee", "classiccars": "ClassicCars.com", "kijiji": "Kijiji",
    "barnfinds": "Barn Finds", "flex": "FLEX (JP)", "kuruma_ex": "Kuruma-EX",
    "mercadolibre": "MercadoLibre MX", "justcars": "JUST CARS", "tokyocarz": "TokyoCarZ",
}
BROWN = "#3b2b1d"
ORANGE = "#b04a1a"
MUTED = "#75634f"


def _money(price: dict) -> str:
    if not price or price.get("amount") is None:
        return "no price shown"
    sym = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "AUD": "A$", "ZAR": "R",
           "THB": "฿", "CAD": "C$", "MXN": "MX$"}
    orig = f"{sym.get(price['currency'], price['currency'] + ' ')}{price['amount']:,.0f}"
    if price["currency"] == "GBP" or price.get("gbp") is None:
        return orig
    return f"{orig} (£{price['gbp']:,.0f})"


def _kc_tag(listing: dict) -> str:
    """All 620 variants flow through the tracker; confirmed King Cabs get
    the orange tag so the owner can screen at a glance."""
    if (listing.get("king_cab") or {}).get("matched"):
        return (f'<span style="background:{ORANGE};color:#fff8ee;font-size:11px;'
                f'font-weight:bold;padding:2px 7px;border-radius:6px;'
                f'letter-spacing:0.4px;">KING CAB</span> ')
    return ""


def _card(listing: dict, extra: str = "") -> str:
    img = ""
    if listing.get("images"):
        img = (f'<img src="{html.escape(listing["images"][0])}" alt="" width="120" '
               f'style="border-radius:6px;display:block;max-width:120px;height:auto;">')
    title = html.escape(listing.get("title_translated") or listing["title"])
    original = ""
    if listing.get("title_translated"):
        original = (f'<br><span style="color:{MUTED};font-size:12px;">'
                    f'{html.escape(listing["title"])}</span>')
    url = html.escape(listing["url"])
    meta = f"{listing['country']} · {listing['drive_side']} · {SOURCE_NAMES.get(listing['source'], listing['source'])}"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border:1px solid #dddddd;border-radius:8px;margin:0 0 12px;">
      <tr>
        {'<td style="padding:12px 0 12px 12px;" valign="top" width="132">' + img + '</td>' if img else ''}
        <td style="padding:12px;" valign="top">
          {_kc_tag(listing)}<a href="{url}" style="color:{ORANGE};font-weight:bold;text-decoration:none;
             font-size:16px;line-height:1.4;display:inline-block;padding:2px 0;">{title}</a>{original}<br>
          <span style="font-size:15px;">{_money(listing["price"])}</span><br>
          <span style="color:{MUTED};font-size:13px;">{meta}</span>
          {extra}
        </td>
      </tr>
    </table>"""


def _section(heading: str, body: str) -> str:
    return (f'<h2 style="font-size:17px;color:{BROWN};border-bottom:2px solid {ORANGE};'
            f'padding-bottom:4px;margin:24px 0 12px;">{heading}</h2>{body}')


def build_html(changes: dict, run_log: dict, listings_by_id: dict, site_url: str) -> str:
    parts = []

    # A brand-new listing flagged as a possible relist shows once, in the
    # relists section, not twice.
    relist_ids = {r["id"] for r in changes["possible_relists"]}
    new_listings = [
        listings_by_id[i] for i in changes["new"]
        if i in listings_by_id and i not in relist_ids
    ]
    # King Cabs lead the section; the tracker carries every 620 variant.
    new_listings.sort(key=lambda l: not (l.get("king_cab") or {}).get("matched"))
    new_cards = [_card(l) for l in new_listings]
    if new_cards:
        n_kc = sum(1 for l in new_listings if (l.get("king_cab") or {}).get("matched"))
        kc_note = f", {n_kc} King Cab" if n_kc else ""
        parts.append(_section(f"New listings ({len(new_cards)}{kc_note})", "".join(new_cards)))

    price_rows = []
    for ch in changes["price_changed"]:
        l = listings_by_id.get(ch["id"])
        if not l:
            continue
        arrow = "▼" if (ch["pct"] or 0) < 0 else "▲"
        old = f"£{ch['old_gbp']:,.0f}" if ch["old_gbp"] is not None else "?"
        new = f"£{ch['new_gbp']:,.0f}" if ch["new_gbp"] is not None else "?"
        pct = f" ({arrow} {abs(ch['pct']):.0f}%)" if ch["pct"] is not None else ""
        extra = (f'<br><span style="font-size:14px;">{old} &rarr; <b>{new}</b>{pct}</span>')
        price_rows.append(_card(l, extra))
    if price_rows:
        parts.append(_section(f"Price changes ({len(price_rows)})", "".join(price_rows)))

    relist_cards = []
    for r in changes["possible_relists"]:
        l = listings_by_id.get(r["id"])
        prior = listings_by_id.get(r["prior_id"])
        if not l:
            continue
        why = html.escape("; ".join(r["reasons"]))
        prior_link = (f' Prior: <a href="{html.escape(prior["url"])}" style="color:{ORANGE};">'
                      f'{html.escape(prior["title"])}</a>.' if prior else "")
        extra = (f'<br><span style="color:#7a5b16;font-size:13px;">Possible relist '
                 f'(not certain): {why}.{prior_link}</span>')
        relist_cards.append(_card(l, extra))
    if relist_cards:
        parts.append(_section(f"Possible relists ({len(relist_cards)})", "".join(relist_cards)))

    status_rows = []
    for ch in changes["status_changed"]:
        l = listings_by_id.get(ch["id"])
        if not l:
            continue
        extra = (f'<br><span style="font-size:14px;">{ch["old_status"]} &rarr; '
                 f'<b>{ch["new_status"]}</b></span>')
        status_rows.append(_card(l, extra))
    if status_rows:
        parts.append(_section(f"Status changes ({len(status_rows)})", "".join(status_rows)))

    if not parts:
        parts.append(f'<p style="font-size:15px;">No new or changed listings today.</p>')

    health_items = []
    if not run_log["sources"]:
        health_items.append('<li style="margin:4px 0;">no sources ran</li>')
    for s in run_log["sources"]:
        name = SOURCE_NAMES.get(s["source"], s["source"])
        if s["ok"]:
            health_items.append(
                f'<li style="margin:4px 0;">&#9989; {name}: {s["records"]} listing(s)</li>')
        else:
            note = html.escape(s.get("note", ""))
            streak = s.get("consecutive_failures", 0)
            streak_txt = f" ({streak} days running)" if streak > 1 else ""
            # PRD 4.4: 7 consecutive blocked days escalates to a decision,
            # never silent retrying forever.
            escalation = (
                f'<br><b style="color:#8a3030;">Blocked {streak} days: decision needed '
                f'(alternative source, proxy, or drop it).</b>' if streak >= 7 else "")
            health_items.append(
                f'<li style="margin:4px 0;">&#10060; {name}: skipped — {note}{streak_txt}{escalation}</li>')
    parts.append(_section("Source health",
                          f'<ul style="padding-left:20px;font-size:14px;">{"".join(health_items)}</ul>'))

    t = run_log["totals"]
    by_country = ", ".join(f"{c}: {n}" for c, n in sorted(t["by_country"].items())) or "none"
    median = f"£{t['median_gbp']:,.0f}" if t["median_gbp"] is not None else "n/a"
    # Run start time surfaces GitHub's cron delay without opening Actions:
    # the digest must keep landing before ~08:00 Jersey.
    started = run_log.get("started_at", "")
    started_line = f"<br>Run started: {started[11:16]} UTC" if len(started) >= 16 else ""
    parts.append(_section("Summary", (
        f'<p style="font-size:14px;">Active listings: <b>{t["active"]}</b><br>'
        f'By country: {by_country}<br>Median price: {median}{started_line}</p>')))

    body = "".join(parts)
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f7f1e3;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="max-width:600px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#33261a;">
      <tr><td style="background:{BROWN};padding:14px 16px;">
        <span style="color:#f7f1e3;font-size:18px;font-weight:bold;">Datsun 620 digest</span>
        <span style="color:#cbb99a;font-size:14px;"> — {changes["date"]}</span>
      </td></tr>
      <tr><td style="padding:16px;">{body}
        <p style="margin-top:28px;">
          <a href="{site_url}/" style="background:{ORANGE};color:#fff8ee;text-decoration:none;
             padding:12px 20px;border-radius:8px;font-size:15px;display:inline-block;">Open the tracker</a>
        </p>
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def main() -> int:
    changes = json.loads((DATA_DIR / "changes-latest.json").read_text())
    run_log = json.loads((DATA_DIR / "run-log.json").read_text())
    listings = json.loads((DATA_DIR / "listings.json").read_text())["listings"]
    listings_by_id = {l["id"]: l for l in listings}

    html_out = build_html(changes, run_log, listings_by_id,
                          "https://sumonoodle.github.io/datsun-620")
    out_path = DATA_DIR / "digest-latest.html"
    out_path.write_text(html_out)
    print(f"digest written to {out_path}")

    user = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    live = os.environ.get("DIGEST_LIVE", "") == "1"
    if not (user and password and live):
        print("dry run: live send disabled "
              f"(credentials {'set' if user and password else 'missing'}, DIGEST_LIVE={live})")
        return 0

    n_new, n_price = len(changes["new"]), len(changes["price_changed"])
    n_kc = sum(1 for i in changes["new"]
               if (listings_by_id.get(i, {}).get("king_cab") or {}).get("matched"))
    if n_kc:
        subject = (f"Datsun 620: {n_kc} KING CAB of {n_new} new, "
                   f"{n_price} price change(s) — {changes['date']}")
    elif n_new or n_price:
        subject = f"Datsun 620: {n_new} new, {n_price} price change(s) — {changes['date']}"
    else:
        subject = f"Datsun 620 digest — {changes['date']}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = os.environ.get("DIGEST_TO") or user  # empty string falls back too
    msg.attach(MIMEText("Your mail client does not display HTML.", "plain"))
    msg.attach(MIMEText(html_out, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)
    print(f"digest sent to {msg['To']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
