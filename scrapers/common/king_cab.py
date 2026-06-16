"""Recall-first King Cab scoring.

Listings are already scoped to the Datsun 620. This scores how likely a given
listing is specifically a King Cab (the extended cab), across languages, and
returns the signals behind the score so a human can judge borderline cases.

The design favours recall: we never drop a listing, we rank it. A 620 with no
cab indicator still scores low-but-present so it shows up for review.
"""

from __future__ import annotations

# Strong, unambiguous King Cab terms, tagged by locale for the signal trail.
STRONG = [
    ("en", "king cab"),
    ("en", "kingcab"),
    ("en", "king-cab"),
    ("ja", "キングキャブ"),
    ("ja", "キング・キャブ"),
]
# Generic extended-cab wording: likely a King Cab on a 620, but less certain.
MEDIUM = [
    ("en", "extended cab"),
    ("en", "extended-cab"),
    ("en", "extra cab"),
    ("en", "ext cab"),
    ("en", "extracab"),
    ("ja", "エクステンデッドキャブ"),
]
# Signals it is NOT a King Cab (pull the score down).
STANDARD = [
    ("en", "standard cab"),
    ("en", "regular cab"),
    ("en", "single cab"),
    ("ja", "シングルキャブ"),
    ("en", "double cab"),
    ("ja", "ダブルキャブ"),
]


def score(*texts: str) -> tuple[float, list[str]]:
    """Score the listing from its title/description text.
    Returns (score in 0..1, list of signal strings like 'en:king cab')."""
    blob = " ".join(t for t in texts if t)
    low = blob.lower()
    signals: list[str] = []

    def present(term: str) -> bool:
        # Latin terms are matched case-insensitively; Japanese as-is.
        return (term in low) if term.isascii() else (term in blob)

    strong = [f"{loc}:{t}" for loc, t in STRONG if present(t)]
    medium = [f"{loc}:{t}" for loc, t in MEDIUM if present(t)]
    standard = [f"{loc}:{t}" for loc, t in STANDARD if present(t)]
    signals = strong + medium + [f"-{s}" for s in standard]

    if strong:
        base = 0.95
    elif medium:
        base = 0.7
    else:
        base = 0.3  # a 620 with no cab cue: keep it, rank it low
    if standard and not strong:
        base = min(base, 0.15)  # contradicted by an explicit other-cab term
    return base, signals
