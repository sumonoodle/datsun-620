# Identifying a 3rd-generation petrol Hilux (N30/N40, 1978-1983)

Date of record: 2026-09-24. This guide is for the scraper engineers. It says
how to decide whether a listing is in scope. It pairs with
`data/hilux/specs.json`, which holds the per-market variants and every
citation. All web research for this round came from search-result snippets,
because the sandbox egress proxy blocked page fetches for every reference
domain (Wikipedia, Toyota, Megazip, drive.com.au, importarchive and others).
Treat a figure marked low-confidence in the specs file as a lead to check, not
as a fact.

**In scope:** third-generation Toyota Hilux / Toyota Truck / Toyota Pickup,
petrol models (chassis codes starting `RN`), 2WD and 4WD, in every body
style. **Out of scope:** diesels (codes starting `LN`), the 2nd generation
(`RN1x`/`RN2x`) and the 4th generation and later (`RN5x` and up, plus `YN`
codes).

---

## 1. Chassis (model) codes

The code format is `RN` + a two-digit number, optionally followed by a
drive-side letter (`L` = left-hand drive, `R` = right-hand drive) and a
grade/spec suffix after a hyphen, for example `RN30R-KD`, `RN46L-KRW` or
`RN35-QRS`. The `R` stands for the R-series petrol engine and the `N` stands
for the Hilux chassis. The tens digit gives the body length: **3x = short
(standard) bed/body on the 2585 mm wheelbase; 4x = long bed/body on the
2800 mm wheelbase.** The units digit gives the engine and drive.

### Petrol codes: accept

| Code | Engine | Drive | Bed | Markets / dates (as documented) |
|---|---|---|---|---|
| **RN30** | 12R / 12R-J 1.6 | 2WD | short | JP Aug 1978-Dec 1979; UK, EU, AU, TH, general export 1978-83. **Owner's truck.** |
| RN40 | 12R / 12R-J 1.6 | 2WD | long | Same markets as RN30 |
| RN33 | 12R-J 1.6 | 2WD | short | Japan, Dec 1979-Oct 1981 |
| RN43 | 12R-J 1.6 | 2WD | long | Japan, Dec 1979-Oct 1981 |
| RN35 | 12R-J 1.6 | 2WD | short | Japan, Oct 1981-Sept **1988** (Popular Series after Nov 1983) |
| RN45 | 12R-J 1.6 | 2WD | long (and probably the double cab) | Japan, Oct 1981-1988 |
| RN31 | 18R 2.0 | 2WD | short | General export (AU, ZA and others) 1978-81 |
| RN41 | 18R 2.0 | 2WD | long; AU dual cab 1982-83 | General export, EU (RN41L), AU 1979-83 |
| RN36 | 18R / 18R-J 2.0 | 4WD | short | JP Oct 1979-; export (rare in AU/EU) |
| RN46 | 18R 2.0 | 4WD | long | UK, EU, AU, general export 1979-83 |
| RN32 | 20R 2.2 | 2WD | short | US/Canada MY1979-80 |
| RN42 | 20R 2.2 | 2WD | long | US/Canada MY1979-80 |
| RN37 | 20R 2.2 | 4WD | short | US/Canada MY1979-80 (from Jan 1979) |
| RN47 | 20R 2.2 | 4WD | long | US/Canada MY1979-80 |
| RN34 | 22R 2.4 | 2WD | short | US/Canada MY1981-83 |
| RN44 | 22R 2.4 | 2WD | long | US/Canada MY1981-83 (incl. 1983 Mojave) |
| RN38 | 22R 2.4 | 4WD | short | US/Canada MY1981-83 |
| RN48 | 22R 2.4 | 4WD | long | US/Canada MY1981-83 |

**Uncertain:** `RN39` appears in Japanese used-car and parts listings as a
"1983 Hilux 2WD 2,000cc" (for example on carfromjapan and nengun). No
catalogue entry confirming its generation or engine was found. Treat it as
**probable** 3rd gen, 2WD, and send it to human review rather than
auto-accepting or rejecting it. No `RN49` was found anywhere.

Regex for the accept set:

```
\bRN(3[0-8]|4[0-8])(?:[LR])?(?:-[A-Z0-9]+)?\b       # accept (RN39 is deliberately outside this set)
\bRN39\b                                           # review
```

`RN3x`/`RN4x` never appears on the 2nd or 4th generation, so the pattern is
clean. Watch for sellers who write the code with a space ("RN 30") or with
lower case ("rn30"). Match case-insensitively and allow an optional space or
hyphen: `\bRN[\s-]?(3[0-8]|4[0-8])\b` (with `RN[\s-]?39` routed to review).

### Neighbouring generations: reject (by code)

| Generation | Years | Petrol codes | Notes |
|---|---|---|---|
| 1st | 1968-72 | RN1x (e.g. RN10) | Hilux name first used |
| 2nd | 1972-78 | **RN20, RN22, RN23, RN25, RN27, RN28** (any RN2x) | Short RN20/22, long RN25/27 per parts sources; RN23/RN28 also exist. The 20R arrived for North America with the 1975 redesign (US MY1975-78 trucks are 2nd gen); which of RN23/RN28 is the 20R code was not verified |
| 4th | 1983-88 | RN5x, RN6x, RN7x (e.g. RN50, RN55, RN56, RN60, RN61, RN66, RN70, RN75), YN5x/YN6x (e.g. YN58), VZN (V6, 1988) | Xtracab, double cab, 4Runner/Hilux Surf |
| 5th+ | 1988- | RN8x-RN11x, YN8x-YN11x, VZN | |

Reject rule: `\bRN(1\d|2\d|[5-9]\d|1\d\d)\b` and `\bYN\d{2,3}\b`.

### Diesel: reject

- Codes: `LN30, LN36, LN40, LN46` (3rd-gen diesels) and all other `LN\d+`.
  Regex: `\bLN\d{2,3}\b`.
- Engines: `L` (2.2 diesel, 2188 cc), `2L` (2.4 diesel, 4th gen onward),
  `2L-T`, `3L`. Regex, applied only in engine context:
  `\b(2L-?T|2L|3L)\b` and a bare `\bL\b` next to the word "engine" or
  "diesel".
- Words: diesel, turbo diesel, TD, D4D, `ดีเซล` (Thai), `ディーゼル` (Japanese),
  Diesel (German). Also `2.2D`, `2.2 D`, `2.2L diesel`, `2200 diesel`.
- **Caveat: engine swaps.** A petrol RN30 fitted with a diesel (a UK example
  is an "RN30 fitted with a 2.8 turbo diesel 3L") is still an RN30 body. The
  owner is looking for original petrol trucks, so mark "RN30 + diesel swap" as
  a match with a flag, not a silent reject. The same applies to petrol-engine
  swaps (18R-G, 3S-GE, V8) in RN bodies.

### Petrol engine codes to accept

`12R`, `12R-J`, `12RJ`, `18R`, `18R-J`, `20R`, `22R` (carburetted only for
1981-83; a `22R-E`/`22RE` badge points to MY1984 or later, so treat it as
4th gen unless the listing also gives a 3rd-gen code). The `21R` and the `2Y`
were never factory fitments in the N30/N40; the 1.8 `2Y` arrived with the 4th
gen (YN codes), so `2Y` points to 4th gen. The `16R` belongs to other
models.

Displacements to accept: 1587/1588 cc, "1600", "1.6"; 1968 cc, "2000",
"2.0"; 2189 cc, "2.2" petrol; 2366/2367 cc, "2.4" petrol. Be careful with
"2.2": the 2.2 L diesel has the same capacity, so "2.2" alone is not
evidence of petrol.

---

## 2. Year windows

| Market | 3rd gen on sale | Earliest in scope | Latest in scope | Slop rules |
|---|---|---|---|---|
| Japan | Sept 1978 | 1978 | **1988** for RN35/RN45 2WD (Popular Series to Sept 1988); 1983 for 4WD | A JDM 1984-88 Hilux with 12R and an RN35/RN45 code is 3rd gen. The same year without a code is ambiguous, because the 4th gen launched in Nov 1983. |
| US / Canada | MY1979 (production from Aug 1978) | **MY1979** | **MY1983** | **US MY1984 is always 4th gen** (August 1983 redesign, the Xtracab year). A US "1978" is 2nd gen (RN28 and others). A few 1978-built trucks may be titled as MY1979, which is fine. |
| UK | 1979 | 1978 (only as a late-1978 import) | 1983 build | UK listings give the **registration year**. 1984 registrations ('A' or 'B' plates) can be runout N30/N40 stock. Accept a 1984 UK listing when there is an RN3x/RN4x code or the round-headlight 3rd-gen body; otherwise send it to review. |
| Australia | late 1978 / early 1979 | 1978 | 1983 | Registration-date slop is the same as the UK: a 1984 listing is possible runout. Accept on code, review otherwise. |
| Europe | 1979 import | 1979 | 1983 | First-registration (Erstzulassung) slop as in the UK. |
| South Africa | 1979 | 1979 | 1983 | An SA "1984 Hilux 2000 4x4" with the 18R exists; it may be runout or an early 4th gen, so send it to review. |
| Thailand | 1979 | 1978 | 1983 (possibly later) | Thai parts shops label RN30-40 "1979-1989". Local production may have continued, so accept an RN30/RN40 at any year. |

Global production of the N30/N40 stopped in July 1983 (4WD). The 4th gen
launched in November 1983 in Japan and as MY1984 in the US.

**Generation-number trap:** do not trust "3rd gen" or "4th gen" text in a
listing. Toyota USA's newsroom files 1979-83 as the "Fourth Generation"
Toyota Truck and 1984-88 as the "Fifth". LC Engineering calls 1979-83 the
"2nd generation" Pickup. Global Hilux numbering calls it the 3rd. In a US
listing, "4th gen Toyota pickup" usually **means our truck**, while "3rd gen"
may mean the 1975-78 truck. Decide on year, code and body, not on the
generation number.

---

## 3. Names listings use

| Market / language | Names for the 3rd-gen petrol truck |
|---|---|
| US / Canada | "Toyota Pickup", "Toyota Truck", "Toyota SR5", "SR5 Sport Truck", "Long Bed", "Deluxe", "Mojave" (1983). "Hilux" is rare in US listings but appears on imports and in auction copy ("1979 Toyota Hilux SR5"). "4x4", "4WD". |
| UK | "Toyota Hilux", "Hi-Lux", "Hilux pick-up", "Hilux 1.6", "Hilux 4WD", "Hilux 4x4", "RN30", "Mk3 Hilux". |
| Australia | "Toyota HiLux", "Hilux ute", "HiLux 4x4", "cab chassis", "tray back", "dual cab" (1982-83), "SR5" (2.0 RWD). |
| Japan | ハイラックス (Hilux), トヨタ ハイラックス, 3代目, 30系, 40系, 30/40系, RN30/RN40/RN36 and others, ピックアップ, ロングボデー (long body), ダブルキャブ (double cab), ポピュラーシリーズ (Popular Series), 4WD ハイリフト. |
| Thailand | ไฮลักซ์ (Hilux), โตโยต้า ไฮลักซ์, "ม้ากระโดด" (jumping horse, the Thai nickname for RN30/RN40), "Hilux Super Star" / ซูเปอร์สตาร์, "4 ขอ" (short bed) / "5 ขอ" (long bed), กระบะ (pickup). |
| Germany / Austria / Switzerland | "Toyota Hilux", "Pritsche", "Pritschenwagen", "Pick-up", "Allrad" (4WD), "Oldtimer", "H-Kennzeichen". |
| Netherlands / Belgium | "Toyota Hilux pick-up", "Hilux 4x4", "oldtimer". |
| France | "Toyota Hilux pick-up", "plateau", "4x4", "essence" (petrol) versus "diesel". |
| South Africa | "Toyota Hilux bakkie", "Hilux 1600", "Hilux 2000", "Hilux 4x4". |

Search-query spellings to cover: `hilux`, `hi-lux`, `hi lux`, `hylux`,
`ハイラックス`, `ไฮลักซ์`, `ไฮลักซ`.

---

## 4. Telling 3rd gen from its neighbours in a title

**Code or year first.** A listing that gives a code decides the question on
the code alone. With no code, use the year window above, then body cues.

- **2nd gen (1972-78, RN2x):** squarer, slab-sided cab with single round
  headlamps. US MY1975-78 trucks are similar in size to the 3rd gen, so a US
  "1977" or "1978 Toyota SR5" is 2nd gen and is settled by the year.
- **3rd gen (1978-83, RN3x/4x):** rounder nose with a wide horizontal grille.
  Toyota's Japanese history describes the launch model as having "round
  4-light headlights" (丸型4灯). A facelift came in October 1981 in Japan
  (and correspondingly for MY1982 elsewhere). Its exact headlamp change by
  market was **not verified** in this round, so do not use headlamp shape as
  a hard rule. Front torsion-bar IFS on 2WD; solid front axle and leaf
  springs on 4WD.
- **4th gen (1983/84-88, RN5x/6x/7x, YN):** squarer, flatter body; Xtracab /
  Xtra Cab; fuel-injected 22R-E ("22RE") from MY1984/85; 4Runner and Hilux
  Surf; independent front suspension on 4WD from MY1986. **Any mention of
  Xtracab, Xtra Cab, Xtra-Cab or 22RE/22R-E means not 3rd gen** (unless a
  3rd-gen code is also given, which would indicate a swapped part).

Title keywords that point to the wrong generation: `xtracab`, `xtra cab`,
`extra cab`, `22re`, `22r-e`, `efi`, `4runner`, `surf`, `ifs 4x4` (IFS 4WD
arrived in 1986), `v6`, `3vze`, `turbo` (the 22R-TE arrived in 1985).

---

## 5. Did any extended cab exist in the 3rd generation? (Xtracab question)

**Verdict: No Xtracab or equivalent extended cab (a cab with storage space or
jump seats behind the seat, sold under an extended-cab name) was offered on
the third-generation N30/N40 in any market. The Xtracab first appeared with
the fourth generation: the August 1983 redesign, sold in North America as
MY1984. Confidence: high.**

Evidence:

- English Wikipedia (Toyota Hilux) says the August 1983 redesign, sold as
  MY1984 in North America, introduced the Xtracab, with about 150 mm (6 in) of
  space behind the seat.
- LC Engineering's chassis-code table lists only regular-cab codes for
  1979-83 (RN32/34/37/38/42/44/47/48). The first Xtracab codes are 4th-gen
  (RN55 and others). IMCDb and auction data show "1986 Toyota Truck Xtracab
  [RN55]" and a "1984 Pickup Xtracab RN56".
- Stoapfälzer-4Wheelers (a German club) says the 3rd gen was always a single
  cab, and XtraCab and DoubleCab reached Europe with the 4th gen.
- Toyota's own Japanese and UK histories list the 3rd-gen bodies as standard
  body, long body and (from Oct 1981) double cab. None is an extended cab.

**The discrepancy, resolved:** the claim "RN34 ... with Xtracab, 1979-1983"
is wrong. RN34 is the US 1981-83 22R 2WD **short-bed regular cab**
(LC Engineering; the Megazip EPC lists RN34 for the USA region 1980-83; a
1983 "PICKUP 1/2 TON RN34" is on Copart). The error most likely mixes up US
generation numbering (Toyota USA calls 1984-88 the 5th gen and 1979-83 the
4th) with global numbering (in which the Xtracab is "4th gen"). A search for
"RN34" together with "Xtracab" found no primary or catalogue source pairing
them.

**One real near-miss to know about:** the Japanese-market 3rd-gen **Super
Deluxe** had a single cab **90 mm longer** than standard, which gave more
interior room (Toyota global history; Toyota UK magazine: "its extended cab
was 90mm longer than standard"). That wording is probably the source of the
confusion. It is a longer single cab on the same two-seat layout, it was not
called Xtracab, and it has no separate chassis code. A listing that says
"Super Deluxe" or "extended cab" on a JDM RN30/RN40 is still in scope.

---

## 6. "Like the owner's reference truck"

Reference: **1980 Hilux RN30, original 12R 1.6, single cab, short bed, 2WD,
UK (right-hand drive).**

Score a listing as a **close match** when all of these hold:

1. Code `RN30` (or JDM `RN33`/`RN35`, which are 12R-J short-body 2WD
   equivalents), **or**, with no code: 1.6 / 1600 / 12R, 2WD, short bed or
   short wheelbase, year 1978-1983 (JDM up to 1988).
2. Engine is 12R (not swapped). Flag swaps.
3. Single cab (not the double cab / ダブルキャブ / dual cab).
4. Not 4WD (reject `4x4`, `4WD`, `Allrad`, `RN36`/`RN46`).
5. Bonus: right-hand drive (UK, AU, JP, TH, ZA). Thai-origin RN30s imported to
   the UK are genuine matches.

**Near match:** RN40 (same engine, long bed), RN31 (18R, short bed), or an
RN30 with an engine swap.

**No US-market truck can be a close match**, because the 12R was never sold
in the US. The nearest US equivalent is an RN32 (MY1979-80, 20R) or an RN34
(MY1981-83, 22R) standard bed 2WD.

---

## 7. Compact rule list (for regexes)

```
ACCEPT_CODE   = \bRN[\s-]?(3[0-8]|4[0-8])[LR]?\b                  (case-insensitive)
REVIEW_CODE   = \bRN[\s-]?39\b
REJECT_CODE   = \bRN[\s-]?(1\d|2\d|[5-9]\d|1\d\d)\b | \bYN\d{2,3}\b | \bLN\d{2,3}\b | \bVZN\d+\b
PETROL_ENGINE = \b(12R(-?J)?|18R(-?J)?|20R|22R(?!-?E\b))\b             (22R-E/22RE => 4th gen; do not let "22R engine" trip it)
DIESEL        = diesel|ディーゼル|ดีเซล|\b(2L-?T|2L|3L)\b|\bTD\b
NEXT_GEN      = xtra[\s-]?cab|extra[\s-]?cab|\b22r-?e\b|4runner|hilux surf|\bv6\b|3vz
NAME          = hilux|hi-?lux|hylux|toyota (pickup|truck)|ハイラックス|ไฮลักซ์|ม้ากระโดด
YEAR_US       = 1979-1983 model year only (1984 => reject)
YEAR_ROW      = 1978-1983 build; 1984 registration => accept only with code/body evidence
YEAR_JP       = 1978-1983 any code; 1984-1988 only RN35/RN45/12R Popular Series
OWNER_MATCH   = RN30|RN33|RN35, or (12R|1600|1.6) & 2WD & short bed & single cab
```
