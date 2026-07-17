# Asia source expansion: research record and decision table

Date of record: 2026-07-17. Desk research (four parallel research passes:
Japan export portals, Japan domestic classifieds, Thailand/SEA classifieds,
and Thai/SEA manufacturing history) plus a live reachability probe from
GitHub-hosted runners (`scrapers/experiments/asia_probe.py`, raw results in
`data/research/asia-probe.json`, Actions run 29568829902).

Extends `japan-sources.md`, which recorded the v1 finding that Buyee blocks
GitHub's IP ranges outright (Playwright-proven) and that Goo-net Exchange
404-walled the path v1 used. The probe shows the current Goo-net Exchange
model index path answers 200 with full content, so that block was
path-specific, not IP-wide.

## Why

The 620 is rare in the West; most surviving examples and most turnover are
in Asia. v1's coverage (eBay, BaT, Cars & Bids, Hemmings, plus two blocked
Japan collectors) sees almost none of that market. Research scope was
"everything": export-facing AND domestic sites.

## Manufacturing findings (now in specs)

- **Thailand: confirmed.** Nissan's first overseas assembly operation, Siam
  Motors & Nissan Co., founded 1962; a dedicated pickups-only plant, Siam
  Nissan Automobile Co., opened 1977. Thai 620s were badged **Datsun 1300 /
  Datsun 1500** (J13/J15 engines), never "620", and carry the nickname
  **ช้างเหยียบ** ("chang yiap"). Added to `data/specs.json` v1.4 as market TH.
- Taiwan: confirmed (Yulon YLN-752/753, 1973-79). Philippines: confirmed
  (Universal Motors Corp). Malaysia: probable CKD. Indonesia: unconfirmed.
  Recorded here for reference; not added to specs (no listing sources
  identified for these markets yet).

## Search-term notes for Asian collectors

- Japan: ダットサントラック (Datsun Truck), ダットサン 620, キングキャブ (King Cab).
  Domestic sites file the 620 under "Nissan Datsun Truck" as a model line.
- Thailand: ดัทสัน (Datsun), ช้างเหยียบ ("chang yiap"), "Datsun 1300",
  "Datsun 1500". Years appear in Buddhist Era (BE 2515-2522 = 1972-1979)
  and BE/CE conversion mistakes are routine: never hard-filter on year.
- Thai listings rarely say "620"; a Thai collector must match on the badge
  names and nickname instead.

## Candidate sources

Evidence = did desk research find actual 620-family listings (current or
recently sold) on the site. Reachability = HTTP status from a GitHub runner
(the daily pipeline's IP space) on the site's search/model index page,
2026-07-17. "Challenge (202)" means a ~2 KB bot-check page instead of
content. `mentions_datsun` on a 403 page is just the error page echoing the
URL, so it is ignored.

### Japan, export-facing (English, built to sell abroad)

| Site | 620 evidence | Reachability | Email alerts | Route |
|---|---|---|---|---|
| Goo-net Exchange | Strong (1973 Datsun Truck indexed) | **200, full page (315 KB)** | No | Scrape |
| TCV (tc-v.com) | Strong | **200 (135 KB)** | Saved search + alerts | Scrape |
| jdmexport.com | Strong | **200 (322 KB)** | No | Scrape (small inventory, low priority) |
| SBT Japan | Moderate | **200 (772 KB)** | Enquiry-based | Hold (moderate evidence) |
| Japan Partner | Moderate | **200 (107 KB)** | No | Hold |
| CAR FROM JAPAN | Strong (1972 620 indexed) | Challenge (202, 2 KB) | Alerts on saved search | Email alerts |
| BE FORWARD | Moderate | Challenge (202, 2 KB) | Saved search alerts | Email alerts |
| JapaneseCarTrade | Moderate | 403 | Stock alerts | Email alerts |

### Japan, domestic (Japanese-language)

| Site | 620 evidence | Reachability | Email alerts | Route |
|---|---|---|---|---|
| Carsensor | Strong | **200 (696 KB)** | Yes (saved search mail) | Scrape |
| Goo-net (domestic) | Strong | **200 (1.1 MB)** | Yes | Scrape |
| Yahoo Auctions | Strong, highest volume | **200 (816 KB)** | Via alert services | Scrape |
| Yahoo closedsearch (sold prices) | Strong | **200 (784 KB)** | n/a | Scrape (price history) |
| Jimoty | Light listings, easy pages | **200 (330 KB)** | No | Scrape (low priority) |
| NOSWEB ucar (dealer) | Occasional | 200 but 15 KB, JS-rendered or wrong params | No | Skip for now |
| Rocky Auto (dealer stock) | Occasional | TLS certificate error from runner | No | Skip (their misconfig) |
| japan-vintage.com (dealer) | Occasional | TLS certificate error from runner | No | Skip |
| Mercari | Some | not probed: hostile SPA | No | Skip |
| Buyee | (proxy for Yahoo) | 403 (v1, Playwright-proven) | No | Superseded: Yahoo direct is 200 |

### Thailand and wider SEA

| Site | 620 evidence | Reachability | Email alerts | Route |
|---|---|---|---|---|
| Truck2Hand | Strong, live 620s (35k-220k THB) | **200 (1.8 MB)** | No | Scrape |
| Kaidee / rod.kaidee | Strong | **200 (663 KB)** | Saved search alerts | Scrape |
| Chobrod | Strong (dedicated 620 page) | Connect timeout from runner | No | Retry later; likely geo-blocking |
| One2car | Strong | 403 | Yes | Email alerts |
| Bahtsold | Weak | Root 200, search URL guess 404 | No | Skip (weak evidence) |
| Facebook groups (TH) | Highest volume of all | not scrapable | No | Skip (terms prohibit) |
| mudah.my (MY) | Strong | **200 (317 KB)** | Yes | Scrape (phase 2) |
| carlist.my (MY) | Moderate | 403 | Yes | Email alerts |
| carmudi.co.id (ID) | Moderate | 403 | Yes | Email alerts |

## Conclusion

**A paid proxy is not needed.** Every strong-evidence source is either
directly reachable from the free runners (Goo-net x2, Carsensor, Yahoo
Auctions, TCV, Truck2Hand, Kaidee, mudah) or offers saved-search email
alerts as a fallback (CAR FROM JAPAN, One2car, carlist, carmudi). The paid
route stays on the shelf per `japan-sources.md`.

### Build plan (status 2026-07-17)

- **Phase A (Japan): SHIPPED.** Goo-net Exchange, Carsensor and Yahoo
  Auctions (open + closed/sold search) collectors, built against real
  fetched pages. The old goonet and yahoo_buyee collectors are retired:
  Yahoo direct supersedes Buyee, and the Exchange path supersedes the
  dead domestic path. Key filter learned from the real pages: "Datsun
  Truck" stayed a JDM model name until 2002, so Japanese sources demand
  King Cab term AND a 1971-1980 year; Yahoo sold items additionally
  require the 中古車・新車 (whole vehicle) category tree.
- **Phase B (Thailand): Kaidee SHIPPED** with the Thai-badge rules
  (Datsun marker + คิงแค็บ/king cab, 520/720 generation exclusions with
  digit boundaries so BE years like ปี 2520 survive, no year filtering).
  **Truck2Hand DEFERRED:** four fetch rounds proved its search is fully
  client-side (SSR and the _next/data route both ignore the keyword; the
  API endpoint is not visible in any shipped JS chunk). Follow-up angles
  if wanted: the categories-pickup sitemap + category pages, Playwright
  from a runner, or manual browsing.
- **Phase C (email alerts): NEXT, blocked on owner.** Dedicated
  alerts-only Gmail account, saved searches on CAR FROM JAPAN /
  BE FORWARD / One2car / TCV / Carsensor as belt-and-braces, IMAP reader
  in the daily run, one parser per alert format, built only against real
  received samples.

A 200 today is not a contract: every new collector keeps the degradable
per-source pattern (failures logged, digest health line, 7-day escalation),
so any of these sites starting to block just re-runs this decision with
evidence in hand.
