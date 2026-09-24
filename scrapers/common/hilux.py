"""Hilux identity: is this listing a 3rd-generation PETROL Toyota Hilux?

The 3rd generation (N30/N40 series) ran from August 1978 to late 1983.
Petrol chassis codes start RN; diesels are LN and are out of scope. Toyota
sold it as "Hilux" in most markets but as the "Toyota Truck" / "Pickup" in
North America, so a US listing usually reads "1981 Toyota Pickup SR5" with
no model name or code at all.

One definition, imported by every Hilux collector (the 620 side learned the
hard way that thirteen drifting per-collector copies of an identity regex
cost real trucks: see common/patterns.py).

The owner's reference truck is a 1980 RN30: 12R 1.6 petrol, 2WD, single
cab, short bed. Listings that look like it are flagged `target_match`.
"""

from __future__ import annotations

import re

from . import king_cab

YEAR_MIN, YEAR_MAX = 1978, 1983
# UK and Australian trucks were still registered from stock into 1984, but
# US model-year 1984 is the 4th generation. A 1984 therefore counts only
# with a 3rd-gen chassis code to back it up.
YEAR_SLOP = 1984

# The name itself, in the languages the sources use. "Hi-Lux" and "Hi Lux"
# are period spellings; ハイラックス (JP) and ไฮลักซ์ (TH) are the local forms.
RE_HILUX = re.compile(r"hi[\s-]?lux|ハイラックス|ไฮลักซ์|ไฮลักษ์", re.I)
# The North American name: "Toyota Pickup", "Toyota Truck", "Toyota SR5".
RE_US_NAME = re.compile(
    r"toyota\b[^|]{0,30}?\b(?:pick[\s-]?up|truck|sr[\s-]?5|sport\s*truck)", re.I)

# Chassis codes. Word-bounded so part numbers ("90915-RN30A") and longer
# alphanumerics don't count. The optional trailing letters are Toyota's
# grade/spec suffixes (RN30-KRS, RN34L).
_CODE = r"(?<![A-Za-z0-9])({p})\s?-?\s?(\d{{2}})(?!\d)"
RE_RN = re.compile(_CODE.format(p="RN"), re.I)
RE_LN = re.compile(_CODE.format(p="LN"), re.I)

# 3rd-gen petrol codes: RN30-RN49. RN2x is the 2nd gen, RN5x/RN6x the 4th.
_GEN3 = range(30, 50)
# 4WD codes of the 3rd generation (RN36 is ambiguous across sources and is
# left to the text; the drive is only asserted from codes that are certain).
_4WD_CODES = {"RN37", "RN38", "RN47", "RN48"}

RE_DIESEL = re.compile(r"diesel|ディーゼル|ดีเซล|\b2\.2\s*d\b|\b[23]L\s*(?:engine|motor)", re.I)
RE_PETROL = re.compile(r"petrol|gasoline|\bgas\b|ガソリン|เบนซิน|benzin", re.I)
RE_4WD = re.compile(r"4\s?[wx×]\s?d|4\s?x\s?4|4×4|four[\s-]wheel[\s-]drive|四駆|4駆|ヨンク|ขับ\s?4", re.I)
RE_2WD = re.compile(r"2\s?wd|4\s?x\s?2|4×2|two[\s-]wheel[\s-]drive|二駆|2駆", re.I)
# 12R is the 1.6 litre engine of the reference truck. "1600" and "1.6"
# count only as displacements (not "£1,600", not "1600 miles").
RE_12R = re.compile(r"(?<![A-Za-z0-9])12\s?-?R(?![A-Za-z0-9])", re.I)
RE_16L = re.compile(r"(?<![\d.,£$€¥])(?:1\.6\s?(?:l\b|litre|liter|ltr)|1600\s?cc|1600(?=\s*(?:engine|motor)))", re.I)

# Other Toyota trucks / later generations named in a title. A listing for
# one of these that merely mentions "Hilux" is not our truck.
RE_OTHER_MODEL = re.compile(
    r"4[\s-]?runner|tacoma|tundra|land\s?cruiser|hiace|dyna|stout|surf\b|"
    r"\bT100\b|vigo|revo|\bmighty[\s-]?x|tiger\b", re.I)

# Extended cab terms for the Hilux. Toyota's name was Xtracab; the others
# are how sellers describe it. Checked through common.king_cab so the flag
# lands in the same schema block the site already highlights.
EXT_CAB_TERMS = ["xtracab", "xtra cab", "xtra-cab", "extra cab", "extracab",
                 "extended cab", "king cab", "エクストラキャブ", "エクストラ キャブ"]

_SHOWA_RE = re.compile(r"昭和\s*(5[3-9])年")


def extract_year(text: str | None) -> int | None:
    """First year in the Hilux window (1978-1984), skipping prices."""
    text = text or ""
    for m in re.finditer(r"(?<!\d)(19(?:7[89]|8[0-4]))(?!\d)", text):
        if m.start() > 0 and text[m.start() - 1] in "£$€¥,.":
            continue
        return int(m.group(1))
    m = _SHOWA_RE.search(text)
    return 1925 + int(m.group(1)) if m else None


def chassis_codes(text: str) -> tuple[list[str], list[str]]:
    """(RN codes, LN codes) stated in the text, normalised to 'RN30' form."""
    rn = [f"RN{n}" for _, n in RE_RN.findall(text)]
    ln = [f"LN{n}" for _, n in RE_LN.findall(text)]
    return rn, ln


def classify(title: str, description: str | None = None, *, year: int | None = None,
             require_name: bool = True, body_style: str | None = None) -> dict | None:
    """Decide whether a listing is a 3rd-gen petrol Hilux.

    Returns None to reject, or {"year", "variant", "king_cab"} to keep.
    `year` is a structured year from the source (preferred over the text).
    `require_name=False` is for sources whose search is already scoped to
    the Hilux model, where titles may omit the name.
    """
    title = title or ""
    text = f"{title} {description or ''}"

    rn, ln = chassis_codes(text)
    gen3_rn = [c for c in rn if int(c[2:]) in _GEN3]
    other_rn = [c for c in rn if int(c[2:]) not in _GEN3]
    code = gen3_rn[0] if gen3_rn else None

    named = bool(RE_HILUX.search(text) or RE_US_NAME.search(title))
    if require_name and not named and not code:
        return None
    # Another Toyota model in the TITLE is a different truck (descriptions
    # routinely mention the Land Cruiser a seller also owns).
    if RE_OTHER_MODEL.search(title) and not RE_HILUX.search(title):
        return None
    # Codes from another generation and none from ours: wrong generation.
    if other_rn and not gen3_rn:
        return None

    # Diesel: an LN code with no RN code, or diesel named with no petrol
    # counter-signal and no RN code. A title-level diesel always rejects.
    if not code:
        if ln or (RE_DIESEL.search(text) and not RE_PETROL.search(text)):
            return None
    if RE_DIESEL.search(title) and not RE_PETROL.search(title):
        return None

    if year is None or not (YEAR_MIN <= year <= YEAR_SLOP):
        year = extract_year(title) or extract_year(description)
    if year is None:
        # No year at all: only a 3rd-gen chassis code can vouch for it
        # (an undated "Toyota Hilux" is far more likely a modern one).
        if not code:
            return None
    elif year == YEAR_SLOP and not code:
        return None
    elif not (YEAR_MIN <= year <= YEAR_SLOP):
        return None

    if code in _4WD_CODES or RE_4WD.search(text):
        drive = "4WD"
    elif RE_2WD.search(text) or (code and code not in _4WD_CODES and code != "RN36"):
        drive = "2WD"
    else:
        drive = "unknown"

    reasons = []
    if code == "RN30":
        reasons.append("chassis code RN30")
    if RE_12R.search(text):
        reasons.append("12R engine")
    elif RE_16L.search(text):
        reasons.append("1.6 litre engine")
    target = drive != "4WD" and ("chassis code RN30" in reasons or (
        bool(reasons) and not RE_DIESEL.search(text)))

    # Same text-plus-body-style logic as the 620's King Cab gate, with the
    # Hilux's own terms; an explicit single/regular cab body style vetoes.
    ext_terms = [t for t in EXT_CAB_TERMS if t in text.lower()]
    body_check = king_cab.check("", None, body_style)["body_style_check"]
    kc = {"matched": bool(ext_terms) and body_check != "fail",
          "matched_terms": ext_terms, "body_style_check": body_check}

    return {
        "year": year,
        "variant": {"chassis_code": code, "drive": drive,
                    "target_match": target, "target_reasons": reasons if target else []},
        "king_cab": kc,
    }
