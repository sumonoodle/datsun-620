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

**Build outcome (2026-07-17):** five of the nine shipped — ClassicCars.com,
Kijiji, Barn Finds, FLEX and kuruma-ex. Three demoted on close inspection:
MercadoLibre's 200 was a bot-challenge shell ("suspicious-traffic"
frontend) — alert route, official API a future option; JUST CARS and
TokyoCarZ render results client-side (empty SSR) — JUST CARS to the alert
route, TokyoCarZ to manual. Car & Classic was always alert-route.

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

## Gap sweep (2026-08-14, owner-prompted by the PistonHeads catch)

Two further research passes (UK/EU/aggregators; Americas/AU/forums) plus a
fetch-probe round. Outcome:

**Five new collectors shipped:** PistonHeads (Apollo cache, native GBP,
structural era-Pickup rule), **Ratsun.net classifieds** (the Datsun truck
community's own market — highest 620 density found anywhere), Retro Rides
forum (a real £8,995 1978 620 was live on the board on build day), Trovit
(aggregator safety net over sites we don't scrape; two King Cabs on its
620 page on build day), Kleinanzeigen.de (real German 620s; Akamai risk
accepted, degrades to its email alerts if blocked).

**Added to the Phase C alert list:** DoneDeal.ie (blocked from runners;
had a live EUR 9,000 620 during research), Gumtree UK (live GBP 12,995
1977 620; toy-heavy search markup made blind scraping unwise), CarsGuide
AU (dedicated 620 ute page + alerts; blocked), Classic Trader (native
"notify me when a 620 lists" — set and forget), Gateway Classic Cars
(arrival alerts), MercadoLibre AR/CL/PE/CO/EC (real 620s in every one,
Peru's badged NL620; same bot wall as MX), Copart + IAAI (live 1976 620
salvage lot found; hard walls, saved-search alerts exist), Trade Unique
Cars AU.

**Manual/watch:** NICOclub Datsun classifieds (estate-sale finds),
datsun.co.nz forum, datsun1200.com, 510 Realm, ClassicZcars, OZDAT,
my105, UK auction houses (Iconic — which sold a 521 pickup — Brightwells,
SWVA, Mathewsons; Glenmarch and CLASSIC.COM cover their results).

**Dead/skip:** Honest John Classics (redirects to drive.co.uk — site
absorbed), CCFS (unreachable on two probe rounds), AutoTempest
(client-side meta-search), CarGurus (no classics vertical), GovDeals,
Bilweb/Bytbil, subito.it, coches.net, seminuevos (NP300-era taxonomy
noise), Adverts.ie (toys only).

## Bug-hunt round + Trovit DE (2026-08-22)

Three parallel audits (core pipeline, all 18 collectors, outputs/ops)
against code AND a month of accumulated live data. Every confirmed finding
is fixed with a pinned regression test in test_bughunt.py; headline items:

- kuruma-ex's split-markup prices read as ¥0/¥50k and had poisoned the
  published median for days (now read from the card's value attribute);
  its records were also duplicating their Carsensor twins — deduped.
- The eBay parts filter was killing real trucks by substring ("Manual"
  transmission, "Toyota" swap, "consignment"); now word-bounded, and the
  category gate understands localized (DE) category names.
- Cross-generation rules fired on prices ("$6,520"), phone digits and the
  620's own SD22 diesel; the 620 rule matched inside "6,620 miles" on a
  720. One shared, guarded pattern set now lives in common/patterns.py.
- Withdrawal ageing counted source-outage days (first scrape after an
  outage could mass-withdraw); now a per-listing healthy-miss counter.
- BaT only parsed COMPLETED auctions — live 620 auctions were invisible.
- Workflow: a thrice-failed data push looked green (day silently lost);
  a digest failure blocked the site deploy.

Expansion: **Trovit DE** added as a second edition of the trovit collector
(markup parity verified live; an edition with no Datsun matches pads with
unrelated cars, which the title gate filters). Trovit UK/ES/AU have no
probeable search paths (two rounds of 404s). **Hagerty confirmed
client-rendered** (empty SSR payload) — stays on the alert route for good.

## Asia round 2 (2026-09-02, owner-prompted: more TH/VN/JP coverage)

**Truck2Hand is IN** — the July "fully client-side" verdict aged out: its
category pages now ship complete listing data server-side, and the brand
page carried FOUR live 620s on build day (฿35,500-฿180,000, two of them
ช้างเหยียบ trucks with no model tag — which is why the brand page, not
the 620 facet, is scraped). ปี years are garbage by observation (a 1974
truck tagged ปี 2020) and stay unused; a ฿10k floor + Thai parts words
keep the ฿450 mudguards out.

**everycar.jp promoted from the bench** — its detail URLs carry model
slug AND year (/nissan/datsun-truck/1978/id/), a clean structural filter;
the model query pads with Civilians when empty, which the slug gate
absorbs. (Corrected 2026-09-15: the model facet does not pad when empty,
it 404s — the padding seen here came from the unfiltered make query. See
the everycar entry below.)

**The rest of the JP bench is re-demoted with evidence:** carused and
picknbuy24 return empty bodies, nikkyo and carjunction hold zero Datsun
stock to pin a parser against, jpauc's past search needs a POST,
cardealpage refused the runner. **Chobrod** (dedicated car-datsun-620
tree, live Thai stock) refused the runner too — watch/alert candidate.
**Taladrod**: dealer stock <15 years old, no 620s ever — skip. Thai
forums (datsun-thailand.com SMF, ThaiScooter Datsun board) and the
Facebook 520/620/720 group: manual list.

**Vietnam is a researched dead end for the 620**: pre-1975 Datsun imports
were sedans and taxis (Sunny B10s and Fairladys are what survives);
Vietnamese searches for a Datsun pickup return only diecast. No collector
built, on evidence rather than neglect.

## eBay: the month of zeros, diagnosed (2026-09-14)

The eBay collector had reported "ok, 0 records" every single day since it
shipped. Four rounds of live probing (the sandbox has no egress, so each
round ran on Actions against the real API) found the cause was the SHAPE
of the query, twice over. The filters were innocent throughout.

**Cause 1 — no category scoping.** `q="datsun 620"` unscoped matched
~8,800 items on EBAY_US, and the Browse API caps a page at 200. Across
four marketplaces and three queries, ~1,800 items were sampled and not
one was a whole vehicle: bumpers, Hot Wheels cars, workshop manuals,
1970s magazine adverts. Every rejection our filters made was a genuine
part. No filter change could ever have helped — the trucks were never in
the payload.

**Cause 2 — the model code is not in the title.** Scoped to the vehicle
category the payload is finally sane (28 Datsun vehicles on EBAY_US, 3 on
EBAY_AU), but `q="datsun 620"` INSIDE that category returns total=0 on
every marketplace. Motors composes a vehicle title from the seller's
year/make/model fields, so a 620 arrives as "1978 Datsun Pickup" as
readily as "1978 Datsun 620". The collector now queries the marque alone
and admits, alongside explicit 620s, a Datsun pickup of 1971-1980 vintage
whose title names no other model — consistent with the standing rule to
show all 620 variants rather than risk filtering a real truck away.

**Category ids are per-site** and are recorded in
`data/research/ebay-categories.json`. US 6001 and AU 29690 returned whole
cars and are proven; GB 9801 and DE 9801 are the sites' car nodes but
held 0 and 3 Datsun items on the day, so they are unproven rather than
wrong. The high-volume alternatives in that file (GB 31853, DE 29690) are
traps: they scored well only because the probe's vehicle heuristic wanted
a year-led title, which is exactly how sales brochures and Hot Wheels
boxes are titled.

**Honest scale of the win.** This fixes a structurally blind collector,
but it is not the large recall gain the earlier notes implied: eBay
US/GB/DE/AU held no 620 vehicle at all on diagnosis day, so the corrected
collector still returns 0 today. What changes is that 0 now means "the
market is empty", the canary fires if auth breaks or a category id moves,
and the next 620 listed will actually be seen.

**Ruled out for good:** the legacy Finding API (findItemsAdvanced), which
historically carried Motors vehicles, answers HTTP 418.

## everycar.jp: a 404 that meant "none in stock" (2026-09-15)

everycar's collector had failed five consecutive daily runs on a 404 from
`?make=nissan&model=datsun-truck`. Three probe rounds found the site had
not moved at all:

- `used-cars.php?make=nissan` still returns 200 with 25 cards, and the
  detail-URL shape the parser keys on is unchanged
  (`/nissan/ud-truck/2012/7958102/`).
- Sibling slugs are formed exactly like ours — `ud-truck`,
  `vanette-truck` — so a rename was never likely.
- The make page's `<select name="model">` offers **25 slugs, all models
  actually in stock** (atlas, civilian, condor, quon, ud-truck …) and no
  Datsun anything. Datsun is not among the site's 50 makes either.
- The 404 body is a plain "Page Not Found" template.

So everycar builds its facet URLs from live inventory: the Datsun Truck
facet answered 200 when the collector was written on 2 September and
404'd once the last one sold. **The collector was treating an ordinary
market condition — no Datsun in stock this week — as a hard failure.**

The fix reads the make page's dropdown instead of assuming a slug. No
Datsun slug offered means an empty market and the collector returns
nothing quietly; an unreadable dropdown still raises, so a genuine layout
change cannot hide behind the same silence. Reading rather than assuming
also means a future `datsun-620` or `datsun-pickup` facet is picked up
with no code change.

`robots.txt` disallows `?keyword=`, `?page=`, `?sort=` and `?ipp=`, so
keyword search and pagination are both off limits here — the model facet
is the only polite way in, which is why its slug mattered so much.

Worth keeping in proportion: everycar has contributed **zero** listings
since promotion. This restores an unproven source rather than recovering
lost coverage, and its 404 never failed the daily run — per-source
isolation held.

## Kleinanzeigen: blind since the redesign (2026-09-19)

Checked after a one-off 403 on 15 September. That block was a blip — four
clean runs followed — but checking it exposed something worse: the
collector had reported "ok, 0 listings" **every day of its life** while
the results page carried real stock.

Three probe rounds, in the order that mattered:

**1. May we scrape it at all?** robots.txt contains a bare `Disallow: /`,
which had to be resolved before any repair: if it bound us, the right
answer was to retire the collector for Kleinanzeigen's Suchauftrag email
alerts, not to fix a parser we should not run. It does not — that rule
belongs to other named user-agents. For `*`, all the paths we fetch are
ALLOWED, pagination included. (The first attempt at this check crashed:
a hand-rolled matcher fed robots paths straight into `re`, and one rule
contains regex metacharacters. The verdict now comes from
`urllib.robotparser`, which is the right tool for a permission question.)

**2. Empty market, or blind?** Blind. The page reads *"Autos 1 - 25 von
**28** Gebrauchtwagen für „datsun“"* while `article.aditem` matches 0 and
`.aditem-main` matches 0. Kleinanzeigen dropped the `aditem` class in a
redesign; cards are now `<article data-adid>` with Tailwind utility
classes and **no `<h2>` at all**, so every selector the parser used was
dead. Worse, the emptiness guard could never fire: it raised only when
the page held no ads AND no "datsun", but the search term is echoed in
the page chrome. Exactly the eBay shape — success reported while seeing
nothing.

**3. What does the page ship now?** `article[data-adid]` and its
`data-href` survived the redesign intact, and the page publishes an
ld+json `ImageObject` per ad carrying the real title and description,
joinable to each card by image id. The rewrite keys on those — semantic
data the site maintains deliberately — and never on the utility classes,
which will not survive the next restyle. `EZ 03/1978` gives a
registration year better than any guess from a title.

The new guard compares the heading's result count against the cards
parsed: results promised but none parsed raises, a heading of zero
results returns nothing. That is the everycar rule — "cannot see" and
"nothing there" must never share an outcome.

**A latent bug fell out of this.** `RE_620` guarded against comma-grouped
figures ("6,620 miles", fixed 2026-08-22) but not dot-grouped ones, so in
German "6.620 €" and "66.620 km" both read as model references.
`RE_OTHER_GEN` already excluded a leading dot; `RE_620`'s guard was
simply incomplete. It was latent only because this collector could not
see — the first German source to actually return cards would have started
ingesting any car priced 6.620 €. Now guarded and pinned.

Query widened from the phrase `datsun-pickup` to the marque alone: a 620
advertised as "Datsun 620" with no "Pickup" in it never matched the old
search. The whole marque is ~28 cars nationwide, which the 620 gate
handles comfortably.
