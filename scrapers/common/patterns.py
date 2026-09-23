"""Shared 620-identity regexes. One definition, imported by every collector.

History (2026-08-22 bug hunt): thirteen per-collector copies of these
patterns had drifted, and the loose forms cost real trucks and admitted
wrong ones:

- "\\b620\\b" and "(?<![\\dA-Za-z])620(?!\\d)" both matched inside
  comma-grouped numbers, so "1984 Nissan 720 King Cab 6,620 Original
  Miles" was ingested as a 620 and "only 76,620 km" in a description
  counted as a model reference. The comma joined the lookbehind class.
- The cross-generation rule matched inside prices and phone numbers:
  "$6,520 obo", "£720 spent on brakes" and "720,000円即決" all read as
  other-generation trucks and killed legitimate 620 titles (forum boards
  put prices in titles by convention). Currency symbols and comma-grouped
  digits now block the match.
- "D2[12]" matched inside SD22 — the 620's own factory diesel engine, a
  routine spec mention in Japanese and Thai ads. A letter lookbehind
  fixes it.
"""

from __future__ import annotations

import re

# The truck itself: "620" as a standalone model reference — not part of a
# longer number ("6200"), part number ("B620", "A16205"), or grouped
# figure ("6,620 miles", "6.620 €").
#
# The DOT guard was added 2026-09-19, when the Kleinanzeigen rewrite first
# gave us a German-language source that could actually see: Germany groups
# thousands with a dot, so "6.620 €" and "66.620 km" both read as model
# references here while RE_OTHER_GEN — which already excluded a leading
# dot — was unaffected. Same bug as the 2026-08-22 comma guard, one
# separator later. The lookbehind is (?<!\d\.) rather than (?<!\.) so that
# a 620 after a sentence full stop still counts.
RE_620 = re.compile(r"(?<![\dA-Za-z,])(?<!\d\.)620(?!\d)")

# Other Datsun/Nissan truck generations. A real 620 for sale never
# name-drops these; a title spanning several generations is a multi-fit
# part (the live Yahoo escapee that taught us this was a 720 diff
# keyword-stuffed with "620 520 521 D21"). Guards: currency symbols and
# comma-grouped digits must not trigger it ("$6,520", "720,000円"), and
# SD22 (the 620's diesel) must survive D22.
RE_OTHER_GEN = re.compile(
    r"(?<![\d.,£$€¥])(?:520|521|720)(?!,?\d)|(?<![A-Za-z])D2[12](?!\d)", re.I)

# Datsun/Nissan nameplates that are not this truck at all — saloons, coupes,
# vans and later pickups. A "datsun" query returns these everywhere, and
# era gating alone cannot tell them apart: a 1974 Bluebird sits inside the
# 620 production window just as neatly as a 620 does.
#
# Added 2026-09-23 after the owner asked about two live false positives. The
# Japanese collectors gated on registration year ONLY, with no model check
# of any kind, which let in a UN521 (a 521-generation truck, admitted twice)
# and a ダットサンブルーバード1600 saloon. Kaidee already carried this list
# privately; it belongs here so thirteen collectors cannot drift again — the
# same lesson as the 620 and cross-generation rules above.
RE_NOT_620_MODEL = re.compile(
    r"bluebird|ブルーバード|sunny|サニー|ซันนี่|cedric|セドリック|gloria"
    r"|laurel|ローレル|skyline|スカイライン|fairlady|フェアレディ|violet"
    r"|cherry|チェリー|stanza|maxima|silvia|シルビア|vanette|バネット"
    r"|caravan|キャラバン|civilian|シビリアン|patrol|パトロール|safari"
    r"|cabstar|キャブスター|homer|ホーマー|junior|ジュニア|navara|frontier"
    r"|hardbody|big[ -]?m|atlas|アトラス|condor|コンドル|\bsedan\b|セダン"
    r"|ซีดาน|เก๋ง|\d{3}ZX?\b|\bZ\d{3}\b|roadster|ロードスター", re.I)


def is_other_generation(text: str) -> bool:
    """Not a 620: a neighbouring truck generation, or a different model.

    One call so a collector cannot remember the numeric rule and forget the
    nameplate one, which is exactly how the UN521 and the Bluebird got in.
    """
    return bool(RE_OTHER_GEN.search(text) or RE_NOT_620_MODEL.search(text))


# Accessories and parts sold FOR a 620 rather than a 620 itself. The live
# case (2026-09-20, ratsun:2463) was "Datsun 620 Sunline Camper" at $500 —
# a camper shell that mounts on a 620 bed, ingested as a truck.
#
# Deliberately conservative, because the standing rule since 2026-07-17 is
# to show every 620 variant rather than risk filtering a real truck away.
# All three conditions must hold: an accessory word, NO word implying a
# whole vehicle, and a known price below the floor. An unpriced listing is
# never dropped on suspicion — it goes through for the owner to screen.
RE_ACCESSORY = re.compile(
    r"\bcamper\b|\bcanopy\b|\btopper\b|\bshell\b|\bcap\b|bed liner|bedliner"
    r"|\btailgate\b|\bbumper\b|\bfender\b|\bgrille\b|\bhood\b|\bbonnet\b"
    r"|\bseats?\b|\bwheels?\b|\btyres?\b|\btires?\b|\bengine\b|\bgearbox\b"
    r"|\btransmission\b|\bdiff\b|\baxle\b|\bmanual\b|\bbrochure\b|\bdecal\b",
    re.I)
RE_WHOLE_VEHICLE = re.compile(
    r"pick[ -]?up|\btruck\b|\bute\b|\bcab\b|\bproject\b|\brunning\b|\bdrives?\b"
    r"|\brestored\b|\brestoration\b|\bbarn find\b|\btitle\b|\bmiles\b|\bkm\b"
    r"|\bregistered\b|\bmot\b|\btax\b|\bvehicle\b|\bcar\b", re.I)
ACCESSORY_PRICE_FLOOR_GBP = 1500.0


def looks_like_accessory(title: str, price_gbp: float | None) -> bool:
    """A part sold for a 620, not a 620 — on all three signals, or not at all."""
    if price_gbp is None or price_gbp >= ACCESSORY_PRICE_FLOOR_GBP:
        return False
    if RE_WHOLE_VEHICLE.search(title or ""):
        return False
    return bool(RE_ACCESSORY.search(title or ""))
