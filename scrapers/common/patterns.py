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
# longer number ("6200"), part number ("B620", "A16205"), or comma-grouped
# figure ("6,620 miles").
RE_620 = re.compile(r"(?<![\dA-Za-z,])620(?!\d)")

# Other Datsun/Nissan truck generations. A real 620 for sale never
# name-drops these; a title spanning several generations is a multi-fit
# part (the live Yahoo escapee that taught us this was a 720 diff
# keyword-stuffed with "620 520 521 D21"). Guards: currency symbols and
# comma-grouped digits must not trigger it ("$6,520", "720,000円"), and
# SD22 (the 620's diesel) must survive D22.
RE_OTHER_GEN = re.compile(
    r"(?<![\d.,£$€¥])(?:520|521|720)(?!,?\d)|(?<![A-Za-z])D2[12](?!\d)", re.I)
