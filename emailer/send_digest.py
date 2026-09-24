"""Daily digest: render changes + source health into a mobile-first HTML email.

ONE email covers every tracked truck: a Datsun 620 section (data/*.json) and
a Hilux section (data/hilux/*.json). Reads each model's changes-latest.json,
run-log.json and listings.json (every Hilux file is optional: until the Hilux
pipeline first runs its section shows an empty state), writes data/digest-latest.html (the dry-run artifact, also published to the
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
    "kaidee": "Kaidee", "truck2hand": "Truck2Hand", "everycar": "EVERY (JP)", "classiccars": "ClassicCars.com", "kijiji": "Kijiji",
    "barnfinds": "Barn Finds", "flex": "FLEX (JP)", "kuruma_ex": "Kuruma-EX",
    "pistonheads": "PistonHeads", "ratsun": "Ratsun", "retrorides": "Retro Rides",
    "trovit": "Trovit", "kleinanzeigen": "Kleinanzeigen",
    # Hilux sources
    "gumtree_uk": "Gumtree UK",
    "classic_trader": "Classic Trader",
    "gumtree_za": "Gumtree ZA",
    "marktplaats": "Marktplaats",
    "goonet": "Goo-net",
    "carfromjapan": "CarFromJapan",
    "tcv": "TCV",
    "hagerty": "Hagerty",
    "mecum": "Mecum",
    "craigslist": "Craigslist",
    "ih8mud": "IH8MUD",
}
BROWN = "#3b2b1d"
ORANGE = "#b04a1a"
MUTED = "#75634f"
WARN = "#8a3030"
TARGET_BG = "#ffdbc9"
TARGET_FG = "#380d00"

# Per-truck presentation. The listing's `king_cab` block means "King Cab" on
# the 620 and "extended cab" (Xtracab) on the Hilux, where none are known for
# this generation, so a match is flagged as rare.
DATSUN = {
    "key": "datsun", "name": "Datsun 620", "path": "",
    "ext_tag": "KING CAB", "ext_label": "King Cab", "ext_rare": False,
    "target": False,
}
HILUX = {
    "key": "hilux", "name": "Toyota Hilux", "short": "Hilux", "path": "/hilux",
    "ext_tag": "EXTENDED CAB (rare)", "ext_label": "extended cab", "ext_rare": True,
    # target_match = like the owner's reference truck (1980 RN30, 12R, 2WD).
    "target": True, "target_label": "MATCHES YOUR RN30 SPEC",
    # Most Hilux sources hold no 1978-83 petrol truck for months (the
    # Japanese and Thai portals are wall-to-wall modern diesels), so the
    # 620's 21 days would nag weekly about a dozen healthy sources. The
    # Hilux collectors also guard harder against blindness (year-cap and
    # result-count checks raise), so the quiet alert is a later backstop.
    "quiet_after": 60,
}

# Silent-source alert. eBay reported "ok, 0 listings" every day for a month
# while an unscoped query drowned in parts, and the only reason it surfaced
# was someone reading logs by hand (2026-09-14). A long quiet streak is not
# proof of a bug — most sources hold no 620 most weeks — so this is phrased
# as "worth a look", not "broken".
#
# 21 days: longer than any legitimate gap observed for a source that
# produces at all, and it would have caught eBay nine days sooner. After the
# first nudge it repeats weekly rather than daily, because a line that
# appears every morning stops being read — which is the failure this alert
# exists to prevent.
QUIET_RUNS_ALERT = 21
QUIET_REPEAT_EVERY = 7
# Streaks shorter than the alert still show inline, so the number is visible
# before it becomes a problem.
QUIET_RUNS_SHOW = 5


def quiet_alerts(sources: list[dict], alert_after: int = QUIET_RUNS_ALERT) -> list[dict]:
    """Sources quiet long enough to be worth checking today."""
    out = []
    for s in sources:
        streak = s.get("consecutive_zero_runs", 0)
        if not s.get("ok") or streak < alert_after:
            continue
        since = streak - alert_after
        if since == 0 or since % QUIET_REPEAT_EVERY == 0:
            out.append(s)
    return out


def _money(price: dict) -> str:
    if not price or price.get("amount") is None:
        return "no price shown"
    sym = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "AUD": "A$", "ZAR": "R",
           "THB": "฿", "CAD": "C$", "MXN": "MX$"}
    orig = f"{sym.get(price['currency'], price['currency'] + ' ')}{price['amount']:,.0f}"
    if price["currency"] == "GBP" or price.get("gbp") is None:
        return orig
    return f"{orig} (£{price['gbp']:,.0f})"


def _is_target(listing: dict) -> bool:
    return bool((listing.get("variant") or {}).get("target_match"))


def _is_ext(listing: dict) -> bool:
    return bool((listing.get("king_cab") or {}).get("matched"))


def _kc_tag(listing: dict, model: dict = DATSUN) -> str:
    """All variants flow through the tracker; confirmed King Cabs (Hilux:
    extended cabs) get the orange tag so the owner can screen at a glance."""
    if _is_ext(listing):
        return (f'<span style="background:{ORANGE};color:#fff8ee;font-size:11px;'
                f'font-weight:bold;padding:2px 7px;border-radius:6px;'
                f'letter-spacing:0.4px;">{model["ext_tag"]}</span> ')
    return ""


def _target_banner(listing: dict, model: dict) -> str:
    """Hilux: a listing like the owner's RN30 leads with a banner and why."""
    if not (model.get("target") and _is_target(listing)):
        return ""
    reasons = "; ".join((listing.get("variant") or {}).get("target_reasons") or [])
    why = (f'<br><span style="font-size:12px;font-weight:normal;">'
           f'{html.escape(reasons)}</span>' if reasons else "")
    return (f'<div style="background:{TARGET_BG};color:{TARGET_FG};font-size:13px;'
            f'font-weight:bold;padding:6px 10px;border-radius:6px;margin:0;">'
            f'&#9733; {model["target_label"]}{why}</div>')


def _variant_meta(listing: dict) -> str:
    """Chassis code and 2WD/4WD when the listing states them."""
    v = listing.get("variant") or {}
    bits = [v.get("chassis_code"), v.get("drive") if v.get("drive") in ("2WD", "4WD") else None]
    return "".join(f" · {html.escape(b)}" for b in bits if b)


def _target_first(items: list, key) -> list:
    """Stable sort: RN30-like listings lead, everything else keeps its order."""
    return sorted(items, key=lambda it: not _is_target(key(it) or {}))


def _card(listing: dict, extra: str = "", model: dict = DATSUN) -> str:
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
    meta = (f"{listing['country']} · {listing['drive_side']}{_variant_meta(listing)} · "
            f"{html.escape(_source_name(listing.get('source')))}")
    banner = _target_banner(listing, model)
    # Full width above the photo so the match is the first thing read.
    banner_row = (f'<tr><td colspan="{2 if img else 1}" style="padding:12px 12px 0;">'
                  f'{banner}</td></tr>' if banner else "")
    border = f"2px solid {ORANGE}" if model.get("target") and _is_target(listing) else "1px solid #dddddd"
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="border:{border};border-radius:8px;margin:0 0 12px;">
      {banner_row}<tr>
        {'<td style="padding:12px 0 12px 12px;" valign="top" width="132">' + img + '</td>' if img else ''}
        <td style="padding:12px;" valign="top">
          {_kc_tag(listing, model)}<a href="{url}" style="color:{ORANGE};font-weight:bold;text-decoration:none;
             font-size:16px;line-height:1.4;display:inline-block;padding:2px 0;">{title}</a>{original}<br>
          <span style="font-size:15px;">{_money(listing["price"])}</span><br>
          <span style="color:{MUTED};font-size:13px;">{meta}</span>
          {extra}
        </td>
      </tr>
    </table>"""


def _source_name(source: str | None) -> str:
    """Display name; a source added after this map was written shows its id."""
    if not source:
        return "unknown source"
    return SOURCE_NAMES.get(source, source)


def _section(heading: str, body: str) -> str:
    return (f'<h2 style="font-size:17px;color:{BROWN};border-bottom:2px solid {ORANGE};'
            f'padding-bottom:4px;margin:24px 0 12px;">{heading}</h2>{body}')


def _model_sections(changes: dict, run_log: dict, listings_by_id: dict,
                    model: dict = DATSUN) -> list[str]:
    """New / price / relist / status / health / summary sections for one truck."""
    parts = []
    run_log = run_log or {}
    sources = run_log.get("sources") or []
    target = model.get("target", False)

    # A brand-new listing flagged as a possible relist shows once, in the
    # relists section, not twice.
    relist_ids = {r["id"] for r in changes["possible_relists"]}
    new_listings = [
        listings_by_id[i] for i in changes["new"]
        if i in listings_by_id and i not in relist_ids
    ]
    # King Cabs lead the section; the tracker carries every 620 variant.
    # Hilux: trucks like the owner's RN30 lead, then extended cabs.
    new_listings.sort(key=lambda l: (not (target and _is_target(l)), not _is_ext(l)))
    new_cards = [_card(l, model=model) for l in new_listings]
    if new_cards:
        notes = []
        n_target = sum(1 for l in new_listings if target and _is_target(l))
        if n_target:
            notes.append(f"{n_target} {'matches' if n_target == 1 else 'match'} your RN30 spec")
        n_kc = sum(1 for l in new_listings if _is_ext(l))
        if n_kc:
            notes.append(f"{n_kc} {model['ext_label']}")
        kc_note = "".join(f", {n}" for n in notes)
        parts.append(_section(f"New listings ({len(new_cards)}{kc_note})", "".join(new_cards)))

    price_changed = changes["price_changed"]
    if target:
        price_changed = _target_first(price_changed, lambda ch: listings_by_id.get(ch["id"]))
    price_rows = []
    for ch in price_changed:
        l = listings_by_id.get(ch["id"])
        if not l:
            continue
        arrow = "▼" if (ch["pct"] or 0) < 0 else "▲"
        old = f"£{ch['old_gbp']:,.0f}" if ch["old_gbp"] is not None else "?"
        new = f"£{ch['new_gbp']:,.0f}" if ch["new_gbp"] is not None else "?"
        pct = f" ({arrow} {abs(ch['pct']):.0f}%)" if ch["pct"] is not None else ""
        extra = (f'<br><span style="font-size:14px;">{old} &rarr; <b>{new}</b>{pct}</span>')
        price_rows.append(_card(l, extra, model))
    if price_rows:
        parts.append(_section(f"Price changes ({len(price_rows)})", "".join(price_rows)))

    relists = changes["possible_relists"]
    if target:
        relists = _target_first(relists, lambda r: listings_by_id.get(r["id"]))
    relist_cards = []
    for r in relists:
        l = listings_by_id.get(r["id"])
        prior = listings_by_id.get(r["prior_id"])
        if not l:
            continue
        why = html.escape("; ".join(r["reasons"]))
        prior_link = (f' Prior: <a href="{html.escape(prior["url"])}" style="color:{ORANGE};">'
                      f'{html.escape(prior["title"])}</a>.' if prior else "")
        extra = (f'<br><span style="color:#7a5b16;font-size:13px;">Possible relist '
                 f'(not certain): {why}.{prior_link}</span>')
        relist_cards.append(_card(l, extra, model))
    if relist_cards:
        parts.append(_section(f"Possible relists ({len(relist_cards)})", "".join(relist_cards)))

    status_changed = changes["status_changed"]
    if target:
        status_changed = _target_first(status_changed, lambda ch: listings_by_id.get(ch["id"]))
    status_rows = []
    for ch in status_changed:
        l = listings_by_id.get(ch["id"])
        if not l:
            continue
        extra = (f'<br><span style="font-size:14px;">{ch["old_status"]} &rarr; '
                 f'<b>{ch["new_status"]}</b></span>')
        status_rows.append(_card(l, extra, model))
    if status_rows:
        parts.append(_section(f"Status changes ({len(status_rows)})", "".join(status_rows)))

    if not parts:
        parts.append(f'<p style="font-size:15px;">No new or changed listings today.</p>')

    # Above Source health on purpose: the whole failure mode being fixed is
    # a true-but-useless "ok" that nobody scrolls down to question.
    quiet = quiet_alerts(sources, model.get("quiet_after", QUIET_RUNS_ALERT))
    if quiet:
        rows = "".join(
            f'<li style="margin:4px 0;"><b>{html.escape(_source_name(s["source"]))}</b>'
            f' — no listings for {s["consecutive_zero_runs"]} days running</li>'
            for s in quiet)
        parts.append(_section("Worth a look", (
            f'<p style="font-size:14px;margin:0 0 8px;">These sources are '
            f'reporting success but have found nothing for a long time. That '
            f'may simply be an empty market — or a collector that has quietly '
            f'stopped seeing listings, which is how eBay went a month without '
            f'anyone noticing.</p>'
            f'<ul style="padding-left:20px;font-size:14px;color:{WARN};">{rows}</ul>')))

    health_items = []
    if not sources:
        health_items.append('<li style="margin:4px 0;">no sources ran</li>')
    for s in sources:
        name = html.escape(_source_name(s.get("source")))
        if s.get("ok"):
            quiet = s.get("consecutive_zero_runs", 0)
            quiet_txt = (f' <span style="color:{MUTED};">(quiet {quiet} days)</span>'
                         if quiet >= QUIET_RUNS_SHOW else "")
            health_items.append(
                f'<li style="margin:4px 0;">&#9989; {name}: {s.get("records", 0)} listing(s)'
                f'{quiet_txt}</li>')
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

    t = run_log.get("totals") or {}
    by_country = ", ".join(f"{c}: {n}" for c, n in sorted((t.get("by_country") or {}).items())) or "none"
    median = f"£{t['median_gbp']:,.0f}" if t.get("median_gbp") is not None else "n/a"
    # Run start time surfaces GitHub's cron delay without opening Actions:
    # the digest must keep landing before ~08:00 Jersey.
    started = run_log.get("started_at", "")
    started_line = f"<br>Run started: {started[11:16]} UTC" if len(started) >= 16 else ""
    parts.append(_section("Summary", (
        f'<p style="font-size:14px;">Active listings: <b>{t.get("active", 0)}</b><br>'
        f'By country: {by_country}<br>Median price: {median}{started_line}</p>')))
    return parts


def _model_band(model: dict) -> str:
    """Full-width heading that starts one truck's part of the email."""
    return (f'<div style="background:{BROWN};color:#f7f1e3;font-size:19px;font-weight:bold;'
            f'padding:10px 12px;border-radius:8px;margin:28px 0 4px;">{model["name"]}</div>')


def _button(href: str, label: str) -> str:
    return (f'<p style="margin-top:28px;">'
            f'<a href="{href}" style="background:{ORANGE};color:#fff8ee;text-decoration:none;'
            f'padding:12px 20px;border-radius:8px;font-size:15px;display:inline-block;">{label}</a></p>')


def _empty_changes(date: str = "") -> dict:
    return {"date": date, "new": [], "price_changed": [], "status_changed": [],
            "possible_relists": []}


def build_html(changes: dict, run_log: dict, listings_by_id: dict, site_url: str,
               hilux: dict | None = None) -> str:
    """The whole email. `changes`/`run_log`/`listings_by_id` are the Datsun's.

    `hilux` adds the Hilux section: {"changes", "run_log", "listings_by_id"},
    any of which may be None (the Hilux pipeline has not run yet). Omitted
    entirely, the email is the Datsun-only digest it always was.
    """
    datsun_parts = _model_sections(changes, run_log, listings_by_id, DATSUN)

    if hilux is None:
        body = "".join(datsun_parts) + _button(f"{site_url}/", "Open the tracker")
        title = "Datsun 620 digest"
    else:
        h_changes = hilux.get("changes")
        if h_changes:
            h_parts = _model_sections(h_changes, hilux.get("run_log") or {},
                                      hilux.get("listings_by_id") or {}, HILUX)
        else:
            h_parts = [f'<p style="font-size:15px;">No Hilux results yet. This section '
                       f'fills in once the daily Hilux search has run.</p>']
        h_date = (h_changes or {}).get("date")
        date_note = (f'<p style="color:{MUTED};font-size:13px;margin:0;">Hilux sweep for {h_date}</p>'
                     if h_date and h_date != changes["date"] else "")
        body = (_model_band(DATSUN) + "".join(datsun_parts)
                + _button(f"{site_url}/", "Open the Datsun 620 tracker")
                + _model_band(HILUX) + date_note + "".join(h_parts)
                + _button(f"{site_url}{HILUX['path']}/", "Open the Hilux tracker"))
        title = "Datsun 620 + Hilux digest"

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f7f1e3;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="max-width:600px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#33261a;">
      <tr><td style="background:{BROWN};padding:14px 16px;">
        <span style="color:#f7f1e3;font-size:18px;font-weight:bold;">{title}</span>
        <span style="color:#cbb99a;font-size:14px;"> — {changes["date"]}</span>
      </td></tr>
      <tr><td style="padding:16px;">{body}
      </td></tr>
    </table>
  </td></tr></table>
</body></html>"""


def _news_counts(changes: dict | None, listings_by_id: dict | None) -> dict:
    """Counts for the subject line. They must match the body: a new listing
    that is also a possible relist renders under Relists, not New (2026-08-22
    bug hunt: the subject once promised more new listings than the body)."""
    if not changes:
        return {"new": 0, "price": 0, "ext": 0, "target": 0}
    listings_by_id = listings_by_id or {}
    relist_ids = {r["id"] for r in changes["possible_relists"]}
    new_ids = [i for i in changes["new"] if i not in relist_ids]
    new = [listings_by_id.get(i, {}) for i in new_ids]
    return {
        "new": len(new_ids),
        "price": len(changes["price_changed"]),
        "ext": sum(1 for l in new if _is_ext(l)),
        "target": sum(1 for l in new if _is_target(l)),
    }


def build_subject(changes: dict, run_log: dict, listings_by_id: dict,
                  hilux: dict | None = None) -> str:
    date = changes["date"]
    d = _news_counts(changes, listings_by_id)
    if d["ext"]:
        datsun = (f"Datsun 620: {d['ext']} KING CAB of {d['new']} new, "
                  f"{d['price']} price change(s)")
    elif d["new"] or d["price"]:
        datsun = f"Datsun 620: {d['new']} new, {d['price']} price change(s)"
    else:
        datsun = ""

    h_part = ""
    n_quiet = len(quiet_alerts(list(run_log.get("sources") or [])))
    if hilux is not None:
        h = _news_counts(hilux.get("changes"), hilux.get("listings_by_id"))
        if h["new"] or h["price"]:
            flags = []
            if h["target"]:
                flags.append(f"{h['target']} RN30 MATCH")
            if h["ext"]:
                flags.append(f"{h['ext']} EXTENDED CAB")
            lead = f"{', '.join(flags)} of " if flags else ""
            h_part = f"Hilux: {lead}{h['new']} new, {h['price']} price change(s)"
        n_quiet += len(quiet_alerts(list((hilux.get("run_log") or {}).get("sources") or []),
                                    HILUX["quiet_after"]))

    news = [p for p in (datsun, h_part) if p]
    if news:
        subject = f"{' | '.join(news)} — {date}"
    elif hilux is not None:
        subject = f"Datsun 620 + Hilux digest — {date}"
    else:
        subject = f"Datsun 620 digest — {date}"
    # An alert nobody opens the mail to see is not an alert. Same function as
    # the body section, so the subject cannot promise what the body omits.
    if n_quiet:
        subject += f" — {n_quiet} source(s) quiet"
    return subject


def _load_optional(path: Path):
    """Parsed JSON, or None when the file is missing or unreadable. Every
    Hilux file is optional until the Hilux pipeline has run."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        if path.exists():
            print(f"warning: could not read {path}: {exc}")
        return None


def load_hilux(data_dir: Path) -> dict:
    changes = _load_optional(data_dir / "changes-latest.json")
    run_log = _load_optional(data_dir / "run-log.json")
    listings = (_load_optional(data_dir / "listings.json") or {}).get("listings") or []
    return {"changes": changes, "run_log": run_log,
            "listings_by_id": {l["id"]: l for l in listings}}


def main() -> int:
    changes = json.loads((DATA_DIR / "changes-latest.json").read_text())
    run_log = json.loads((DATA_DIR / "run-log.json").read_text())
    listings = json.loads((DATA_DIR / "listings.json").read_text())["listings"]
    listings_by_id = {l["id"]: l for l in listings}
    hilux = load_hilux(DATA_DIR / "hilux")

    html_out = build_html(changes, run_log, listings_by_id,
                          "https://sumonoodle.github.io/datsun-620", hilux=hilux)
    out_path = DATA_DIR / "digest-latest.html"
    out_path.write_text(html_out)
    print(f"digest written to {out_path}")

    subject = build_subject(changes, run_log, listings_by_id, hilux=hilux)
    user = os.environ.get("GMAIL_USER", "")
    password = os.environ.get("GMAIL_APP_PASSWORD", "")
    live = os.environ.get("DIGEST_LIVE", "") == "1"
    if not (user and password and live):
        print("dry run: live send disabled "
              f"(credentials {'set' if user and password else 'missing'}, DIGEST_LIVE={live})")
        print(f"subject would be: {subject}")
        return 0

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
