"""Strict King Cab filter per PRD 4.2.

Title or description must contain one of the King Cab terms (case-insensitive).
Where the source exposes a body-style field, it is used as a sanity check to
catch unrelated mentions (e.g. a standard cab whose description says
"looks like a King Cab"): a body style that clearly names a different cab
vetoes the match.
"""

from __future__ import annotations

# คิงแค็บ is the Thai rendering of King Cab (แค็บ pickups are a Thai staple);
# คิงแคป and คิงเเค็บ are common listing misspellings. "cabina y media"
# (cab and a half) is the Mexican term for the extended cab.
TERMS = ["king cab", "kingcab", "king-cab", "extended cab", "キングキャブ",
         "คิงแค็บ", "คิงแคป", "คิงเเค็บ", "cabina y media"]

# Body styles that positively confirm an extended cab.
_BODY_POSITIVE = ["king", "extended", "extra cab", "xtracab"]
# Body styles that veto: a different cab type explicitly stated.
_BODY_NEGATIVE = ["standard cab", "regular cab", "single cab", "crew cab", "double cab"]


def check(title: str, description: str | None = None, body_style: str | None = None) -> dict:
    """Returns the king_cab block per schema/listing.schema.json."""
    text = " ".join(t for t in (title, description) if t).lower()
    matched_terms = [t for t in TERMS if t in text]
    matched = bool(matched_terms)

    if body_style:
        body = body_style.lower()
        if any(p in body for p in _BODY_POSITIVE):
            body_check = "pass"
        elif any(n in body for n in _BODY_NEGATIVE):
            body_check = "fail"
            matched = False  # explicit different cab type overrides text mentions
        else:
            body_check = "unavailable"
    else:
        body_check = "unavailable"

    return {"matched": matched, "matched_terms": matched_terms, "body_style_check": body_check}
