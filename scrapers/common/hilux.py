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
import unicodedata

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
# The last digit carries engine and drive (docs/hilux-identification.md):
# 0/3/5 = 12R 1.6 2WD (3 and 5 are Japan's 12R-J), 1 = 18R 2WD, 2 = 20R
# 2WD, 4 = 22R 2WD, 6/7/8 = the 4WD versions. 3x is the short body on the
# 2585 mm wheelbase, 4x the long one on 2800 mm.
_4WD_CODES = {f"RN{b}{d}" for b in (3, 4) for d in (6, 7, 8)}
# Short-body 1.6 12R codes: the owner's reference configuration.
_TARGET_CODES = {"RN30", "RN33", "RN35"}
# Codes sold past the 1983 generation change: Japan's 12R-J "Popular
# Series" RN35/RN45 ran to 1988, and Thai RN30/RN40s are listed as
# 1979-1989. With one of these codes, a later year is not a 4th gen.
_LATE_CODES = {"RN30", "RN35", "RN40", "RN45"}
LATE_YEAR_MAX = 1989

RE_DIESEL = re.compile(r"diesel|ディーゼル|ดีเซล|\b2\.2\s*d\b|\b[23]L\s*(?:engine|motor)", re.I)
RE_PETROL = re.compile(r"petrol|gasoline|\bgas\b|ガソリン|เบนซิน|benzin", re.I)
RE_4WD = re.compile(r"4\s?[wx×]\s?d|4\s?x\s?4|4×4|four[\s-]wheel[\s-]drive|四駆|4駆|ヨンク|ขับ\s?4", re.I)
RE_2WD = re.compile(r"2\s?wd|4\s?x\s?2|4×2|two[\s-]wheel[\s-]drive|二駆|2駆", re.I)
# 12R is the 1.6 litre engine of the reference truck. "1600" and "1.6"
# count only as displacements (not "£1,600", not "1600 miles").
RE_12R = re.compile(r"(?<![A-Za-z0-9])12\s?-?R(?![A-Za-z0-9])", re.I)
RE_16L = re.compile(r"(?<![\d.,£$€¥])(?:1\.6\s?(?:l\b|litre|liter|ltr)|1,?600\s?cc|1\.6\s?(?:petrol|gas)|1600(?=\s*(?:engine|motor)))", re.I)

# Other Toyota trucks / later generations named in a title. A listing for
# one of these that merely mentions "Hilux" is not our truck.
RE_OTHER_MODEL = re.compile(
    r"4[\s-]?runner|tacoma|tundra|land\s?cruiser|hiace|dyna|stout|surf\b|"
    r"\bT100\b|\bv6\b|\b3vz|\b22r-?e\b|"
    # Toyota cars that share the SR5 trim name (Kijiji 2026-09-24: a
    # "1982 Toyota Corolla SR5" matched the US-name rule).
    r"corolla|celica|corona|cressida|supra|camry|tercel|starlet|carina|crown", re.I)
# Later Hilux sub-models that carry the Hilux name itself, so they reject
# even when "Hilux" is in the title: the Surf (late 1983 on) and Thailand's
# Hero/Mighty-X/Tiger/Sport Rider/Vigo/Champ/Revo line.
RE_SUBMODEL = re.compile(
    r"surf|サーフ|vigo|revo|\bchamp\b|\bmighty[\s-]?x|\btiger\b|\bhero\b|"
    r"sport\s?rider|ไทเกอร์|วีโก้|รีโว่|ไมตี้|ฮีโร่", re.I)

# Extended cab terms for the Hilux. Toyota's name was Xtracab; the others
# are how sellers describe it. Checked through common.king_cab so the flag
# lands in the same schema block the site already highlights.
EXT_CAB_TERMS = ["xtracab", "xtra cab", "xtra-cab", "extra cab", "extracab",
                 "extended cab", "king cab", "エクストラキャブ", "エクストラ キャブ"]

# Toyota's generation codes. N30/N40 is ours; a title naming another
# (2026-09-24 Trovit US: "1978 Toyota Hilux/Pickup (N20 1972-1978)") is a
# different truck, or a fitment list.
RE_OTHER_GEN = re.compile(r"(?<![A-Za-z0-9])N[1-26-9]0(?![0-9])")
# Fitment year spans ("1977-1983 Toyota Pickup Tail Light Lenses", Kijiji
# 2026-09-24) are parts, never a vehicle's own year.
RE_YEAR_SPAN = re.compile(r"(?<!\d)(?:19|20)\d{2}\s*(?:-|–|to)\s*(?:19|20)?\d{2}(?!\d)")
# Toys, models and parts that classify's name/year rules would otherwise
# admit (Kijiji 2026-09-24: a 1980 Hilux "Minitrek" Hot Wheels car).
RE_NOT_VEHICLE = re.compile(
    r"hot\s?wheels|matchbox|die[\s-]?cast|tomica|\b1\s?[:/]\s?(?:18|24|43|64)\b|"
    r"model\s?kit|brochure|\btail\s?lights?\b|\bheadlights?\b|\blenses\b|\bgrille\b|"
    r"\bmanual\b(?!\s*(?:gear|trans|box|4|5))|\bposter\b|\bkeyring\b|\bemblems?\b|\bbadges?\b", re.I)
# Any full year in the title, used to stop a title year outside the window
# from being overridden by a description year.
_ANY_YEAR = re.compile(r"(?<![\d£$€¥,.])(19[5-9]\d|20[0-2]\d)(?![\d'’]|s\b)")

_SHOWA_RE = re.compile(r"昭和\s*(5[3-9])年")


def extract_year(text: str | None) -> int | None:
    """First year in the Hilux window (1978-1984), skipping prices."""
    text = text or ""
    # Not a decade: "the 1980s" (Barn Finds 2026-09-24, on a 1990 truck).
    for m in re.finditer(r"(?<!\d)(19(?:7[89]|8[0-9]))(?![\d'’]|s\b)", text):
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
    # NFKC folds full-width forms (Goo-net writes ＲＮ３０, １２Ｒ, 昭和５５年).
    title = unicodedata.normalize("NFKC", title or "")
    description = unicodedata.normalize("NFKC", description) if description else description
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
    if RE_SUBMODEL.search(title):
        return None
    # Codes from another generation and none from ours: wrong generation.
    if other_rn and not gen3_rn:
        return None
    if RE_OTHER_GEN.search(title) or RE_YEAR_SPAN.search(title) or RE_NOT_VEHICLE.search(title):
        return None

    # Diesel: an LN code with no RN code, or diesel named with no petrol
    # counter-signal and no RN code. A title-level diesel always rejects.
    if not code:
        if ln or (RE_DIESEL.search(text) and not RE_PETROL.search(text)):
            return None
    if RE_DIESEL.search(title) and not RE_PETROL.search(title):
        return None

    year_max = LATE_YEAR_MAX if code in _LATE_CODES else YEAR_SLOP
    if year is not None and not (YEAR_MIN <= year <= year_max):
        # A structured year from the source (Japanese 年式, a Motors year
        # field) is more reliable than anything in the text.
        return None
    if year is None:
        title_year = _ANY_YEAR.search(title)
        if title_year and not (YEAR_MIN <= int(title_year.group(1)) <= year_max):
            # The title states the year and it's out of window: the
            # description can't overrule it (a 1990 truck whose write-up
            # mentions "1980" must stay out).
            return None
        year = extract_year(title) or extract_year(description)
    if year is None:
        # No year at all: only a 3rd-gen chassis code can vouch for it
        # (an undated "Toyota Hilux" is far more likely a modern one).
        if not code:
            return None
    elif year == YEAR_SLOP and not code:
        return None
    elif not (YEAR_MIN <= year <= year_max):
        return None
    elif year == YEAR_MIN and not code and not RE_HILUX.search(text):
        # A US-named 1978 is the 2nd gen: North America's 3rd gen began
        # with model year 1979.
        return None

    if code in _4WD_CODES or RE_4WD.search(text):
        drive = "4WD"
    elif RE_2WD.search(text) or code:
        drive = "2WD"
    else:
        drive = "unknown"

    reasons = []
    if code in _TARGET_CODES:
        reasons.append(f"chassis code {code}")
    if RE_12R.search(text):
        reasons.append("12R engine")
    elif RE_16L.search(text):
        reasons.append("1.6 litre engine")
    # A long-body code (RN40/43/45) is a 1.6 but not the short truck.
    long_body = bool(code) and code[2] == "4"
    target = drive != "4WD" and not long_body and (code in _TARGET_CODES or (
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
