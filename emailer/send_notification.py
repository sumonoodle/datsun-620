"""Notify-on-change email digest.

Builds a plain HTML digest from the change sets and:
  - always writes it to data/digest-latest.html (the dry-run artifact to review);
  - sends it via Gmail SMTP only if there is something to report AND credentials
    (GMAIL_USER, GMAIL_APP_PASSWORD) are set. No changes => no email. No creds =>
    dry-run only (the PRD's review-before-go-live gate).
"""

from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data"


def _section(title: str, rows: list[dict], render) -> str:
    if not rows:
        return ""
    items = "".join(f"<li>{render(r)}</li>" for r in rows)
    return f"<h3>{title} ({len(rows)})</h3><ul>{items}</ul>"


def _gbp(r: dict) -> str:
    g = r.get("price_gbp")
    o = r.get("price_original")
    cur = r.get("currency")
    parts = []
    if g is not None:
        parts.append(f"£{g:,.0f}")
    if o is not None and cur:
        parts.append(f"{o:,.0f} {cur}")
    return " / ".join(parts) if parts else "price n/a"


def _line(r: dict) -> str:
    pct = round(r.get("king_cab_score", 0) * 100)
    return (f'<a href="{r.get("source_url")}">{r.get("title")}</a> &mdash; {_gbp(r)} &middot; '
            f'{r.get("country") or "?"} &middot; {r.get("drive_side")} &middot; King Cab {pct}% &middot; {r.get("source")}')


def build_html(changes: dict, report: dict) -> str:
    body = [
        _section("New listings", changes.get("new", []), _line),
        _section("Price changes", changes.get("price_changed", []),
                 lambda r: f'{_line(r)}<br><small>{r.get("old")} &rarr; {r.get("new")}</small>'),
        _section("Status changes", changes.get("status_changed", []),
                 lambda r: f'{_line(r)}<br><small>{r.get("old")} &rarr; {r.get("new")}</small>'),
        _section("Relisted", changes.get("relisted", []),
                 lambda r: f'{_line(r)}<br><small>relisted from {r.get("relisted_from")}</small>'),
        _section("Withdrawn", changes.get("withdrawn", []), _line),
    ]
    skipped = [s for s in report.get("sources", []) if not s["ok"]]
    if skipped:
        body.append("<h3>Sources skipped</h3><ul>" +
                    "".join(f'<li>{s["source"]}: {s["note"]}</li>' for s in skipped) + "</ul>")
    summary = (f'<p><small>{report.get("active", 0)} active listings. '
               f'Counts by country: {report.get("by_country", {})}.</small></p>')
    return f"<html><body><h2>Datsun 620 King Cab digest</h2>{''.join(body)}{summary}</body></html>"


def has_changes(changes: dict) -> bool:
    return any(changes.get(k) for k in ("new", "price_changed", "status_changed", "withdrawn", "relisted"))


def notify(changes: dict, report: dict) -> None:
    html = build_html(changes, report)
    (DATA / "digest-latest.html").write_text(html, encoding="utf-8")

    if not has_changes(changes):
        print("  notify: no changes, no email.")
        return

    user = os.environ.get("GMAIL_USER")
    pw = os.environ.get("GMAIL_APP_PASSWORD")
    if not user or not pw:
        print("  notify: changes present, but no Gmail credentials -> dry-run only (data/digest-latest.html).")
        return
    if os.environ.get("NOTIFY_LIVE") != "1":
        print("  notify: credentials present but NOTIFY_LIVE!=1 -> dry-run only (review data/digest-latest.html, then enable).")
        return

    msg = MIMEText(html, "html")
    msg["Subject"] = "Datsun 620 King Cab digest"
    msg["From"] = user
    msg["To"] = user
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pw)
        s.send_message(msg)
    print(f"  notify: digest emailed to {user}.")
