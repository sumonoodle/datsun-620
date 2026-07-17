# Source deep dive: the full market map and integration routes

Date of record: 2026-07-17. Second research round ("this isn't searching all
possible sources"), four parallel research passes: the Japan auction access
layer, Japanese export portals and Western JDM importers, Japan's domestic
kyusha (classic) market, and global auctions/classifieds. Every promising
candidate was then probed live from GitHub runners (root AND search URL;
raw results in `data/research/deep-probe.json`). Extends
`asia-sources.md`, which holds round one and the already-shipped collectors.

Routes: **SCRAPE** = build a collector (site answers runners with real
content). **ALERT** = Phase C email-alert route (site blocks runners or has
no scrapeable surface, but offers saved-search email alerts the dedicated
Gmail can receive). **MANUAL** = worth an occasional human look, no
automation path. **SKIP** = not worth covering, with reason.

## Key discoveries

- **A live 620 exists right now** at Duncan Imports (US): 1975 Datsun 620,
  17,719 mi, $32,790. Duncan 403s runners; it needs the alert/manual route.
- **CLASSIC.COM has a dedicated 620 market page** (classic.com/m/nissan/
  truck/620/) aggregating BaT, Hemmings auctions, Cars & Bids and dealers,
  with per-model email alerts. One alert there covers most of the US
  auction world, including the two sources we can't scrape (Cars & Bids,
  Hemmings) and the traditional houses (Mecum, Barrett-Jackson, RM).
- **Car & Classic (UK) is the strongest non-US classifieds**: a dedicated
  620 list page with ~8 concurrent UK/PT listings. Blocked from runners;
  saved-search email exists.
- **FLEX (flexnet.co.jp) is Japan's strongest classic dealer** for this
  truck (two documented 620s incl. an L18-swapped 1974) and its kyusha
  stock search answers runners fully.
- The consumer Yahoo proxies (Buyee, ZenMarket, Jauce...) are parts
  channels: whole cars cannot ship through them. Whole 620s in Japan move
  through dealer auctions (USS/JU), whose data layer is login-gated; the
  free tap into that world is Prestige Motorsport's per-model auction
  alert emails.

## Route: SCRAPE (reachable, evidence-backed — build order proposal)

| # | Site | Why | Probe |
|---|---|---|---|
| 1 | ClassicCars.com | Dedicated 620 search, 2 live 620s, 1979 King Cab history | 200, 112 KB |
| 2 | Car & Classic — via alerts instead, see below | | 403 |
| 3 | Kijiji (CA) | 37 "datsun 620" ads incl. restored 1976 | 200, 375 KB |
| 4 | Barn Finds tag feed | Human-curated 620 write-ups linking live eBay/CL/dealer ads; RSS | 200, 44 KB |
| 5 | FLEX kyusha search (JP) | Documented 620 seller, full pages to runners | 200, 341 KB |
| 6 | kuruma-ex.jp (JP) | Aggregates Carsensor+Goo feeds; hosted a real 1974 620 (SR20 swap, Good Motors) — covers Goo DOMESTIC inventory our Exchange collector misses | 200, 256 KB |
| 7 | MercadoLibre MX | 620 sold new in Mexico ("estaquitas"); official API exists too | 200 |
| 8 | JUST CARS (AU) | Classic-specialist AU classifieds, 620 facet | 200, 106 KB |
| 9 | TokyoCarZ (JP export) | Indexed page claims a 620 in stock | 200, 464 KB |

Reachable but deferred (thin 620 value today, cheap to add later):
Japanese Classics (200, sold-archive diffing), JDM Expo (200), everycar.jp /
Nikkyo / Carused / Car Junction / CardealPage / PicknBuy24 (all 200 —
D21/D22 "Datsun Truck" model feeds where a 620 would appear under the same
key), jpauc.com + aaajapan.com (public auction viewers, no 620 seen),
kurumaerabi / kakaku / webcartop / carview (portal duplicates of
Carsensor/Goo feeds — hold in reserve as fallback surfaces if the primary
sources ever block), Craigslist (200 on probe, but per-metro model and a
notorious blocker: alerts are the honest route), Hagerty (200 but search
appears JS-rendered; needs a markup check before committing).

## Route: ALERT (Phase C — saved-search emails into the dedicated Gmail)

| Priority | Site | What the alert covers | Blocked how |
|---|---|---|---|
| 1 | CLASSIC.COM | Per-model 620 alert: BaT, Hemmings auctions, C&B, dealers, trad houses | 403 |
| 2 | Car & Classic (UK) | Best non-US 620 inventory (~8 live) | 403 |
| 3 | Classics on Autotrader | Dedicated 620 pages, US | 403 |
| 4 | Gumtree Australia | Live 620 results (AU utes) | 403 |
| 5 | Duncan Imports | THE live 1975 620 seller; new-arrival notification if offered, else manual | 403 |
| 6 | Craigslist | Per-search email alerts (few key metros: LA, SF, Seattle, Phoenix) | blocks scrapers |
| 7 | carsales.com.au | 620 ute page | 403 (Kasada) |
| 8 | Trade Me NZ | Favourite-search email; official public API is the better long-term route | 406 |
| 9 | The Parking | EU aggregator covering leboncoin/mobile.de/Marktplaats without their bot walls | 403 |
| 10 | Prestige Motorsport | Japan DEALER-AUCTION layer per-model email (where whole 620s actually trade); free trial, may become paid — flag before relying | n/a |

Round-one alert candidates still stand: CAR FROM JAPAN, BE FORWARD,
One2car, carlist.my, carmudi.co.id, TCV, Carsensor (belt-and-braces).
Buyee's saved-search email is redundant now Yahoo is scraped directly.

## Route: MANUAL (no automation path, occasional look)

- Facebook Marketplace + the "Datsun 620" group: highest raw volume
  anywhere, login-walled, terms prohibit scraping.
- Glenmarch (403, no alerts): quarterly look catches traditional-auction
  620 lots (it logged the RM Sotheby's and Hampson sales).
- SEIYAA (JP hobbyist BBS), minkara / CARTUNE owner communities: where
  private JP 620s surface before hitting the market.
- MONKY'S INC (Osaka vintage exporter): contact-form dealer, markets
  vintage Datsun sourcing to the US.

## Route: SKIP (with reason)

- Collecting Cars, PCARMARKET, Bonhams (all arms), H&H, Historics, Clasiq:
  zero 620 history in their archives.
- Mercari, PayPay Flea Market, Rakuma, OfferUp: parts/goods or app-walled.
- Yahoo-proxy layer (ZenMarket, Jauce, Neokyo, Remambo, FromJapan, Doorzo):
  parts only, whole cars unshippable; Yahoo itself already scraped.
- aucfree (403) and aucfan (login-gated): Yahoo sold data already covered
  by our closedsearch collector.
- ts-export (marketing says open, probe says 403), aleado (broken TLS),
  SAT Japan (403), Toprank US (bot challenge), mobile.de / leboncoin /
  Milanuncios / KSL / Marktplaats / Blocket / Hotrodhotline / Gumtree ZA:
  hard walls and/or no 620 evidence; The Parking covers the EU tail.
- BH Auction (wrong price class), auction agents (Japan Car Direct, Brave
  Auto, Integrity: quote-gated services, nothing to poll), Nissan U-Car,
  qsha-oh (buying service; /result/datsun/ useful for price comps only).

## Coverage picture once built

Scrape layer: eBay x4 markets, BaT, Goo-net Exchange, Carsensor,
Yahoo Auctions (live+sold), Kaidee, + ClassicCars.com, Kijiji, Barn Finds,
FLEX, kuruma-ex, MercadoLibre MX, JUST CARS, TokyoCarZ.
Alert layer: CLASSIC.COM (US auctions incl. C&B/Hemmings/trad houses),
Car & Classic (UK/EU), Autotrader Classics, Gumtree AU, Craigslist metros,
Duncan, carsales, Trade Me, The Parking, Prestige (JP dealer auctions),
CFJ/BE FORWARD/One2car/MY/ID.
That is every layer where a 620 realistically surfaces except Facebook,
which stays manual by its terms.
