# Hilux sources: what is scraped, what is blocked, and why

Built 2026-09-24 for the 3rd-generation petrol Hilux (1978-83, RN30 and
relatives). Every URL below was fetched by a GitHub runner (the probe rounds
in `data/research/pages-hilux/`) before a collector was written against it,
and robots.txt was obeyed throughout: a disallowed URL was never fetched.
Identity is decided in one place, `scrapers/common/hilux.py`.

## Scraped daily (24)

| Source | Market | What it polls | Notes |
|---|---|---|---|
| eBay (Browse API) | US, UK, DE, AU | Whole-vehicle categories, year-led queries 1978-84 ("1980 toyota hilux", "1981 toyota pickup") plus RN30/RN34/RN40/12R | A plain "hilux" query drowns in modern trucks past the 200-item cap |
| Bring a Trailer | US | `/toyota/pickup/` (live + completed) | Hilux page 404s |
| ClassicCars.com | US | 1978-84 Toyota pickup and all-years Hilux pages | |
| Kijiji | CA | Cars & Trucks "toyota hilux" / "toyota pickup", Classic Cars Toyota | Three real 1980-83 trucks on probe day |
| Barn Finds | US | toyota-hilux, toyota-pickup, toyota tag feeds | Editorial; old posts stay "active" as on the 620 side |
| PistonHeads | UK | `/buy/search` with the Hilux model and a 1984 year cap | The model page ignores `?yearTo`; the search form's cap is verified |
| Retro Rides | UK | Board 57 (cars for sale, 1985 and older) | |
| Trovit | US, UK, DE | toyota-hilux pages | UK's `max_year` is ignored by the site; US carried 6 real trucks on probe day |
| Kleinanzeigen | DE | `/s-autos/hilux/`, up to 6 pages | Want-ads ("Suche") skipped |
| Gumtree UK | UK | "toyota hilux" newest first, and "toyota hilux rn30" | Sees only the newest ~26 ads each day; the petrol filter and every other filter are under the robots-disallowed `/search` |
| Classic Trader | UK/EU | Toyota Hilux model search | Classics only; low volume, no modern flood |
| Gumtree ZA | ZA | Hilux, petrol filter (about 73 ads) | Reads every petrol Hilux in South Africa daily |
| Marktplaats | NL | Cars category, "toyota hilux" | First real catch: a 1981 petrol US import, titled only "Toyota 1981" |
| Hagerty | US | Toyota make (the Pickup/Truck model names return nothing) | Server-rendered after all |
| Goo-net Exchange | JP | HILUX and HILUX_PICK_UP | |
| Goo-net (domestic) | JP | The "other" Hilux model facet and HILUX_PICK_UP | Old Hiluxes (a 1970 on probe day) are filed under "other" |
| Carsensor | JP | Freeword ハイラックス capped at the site's 1989 floor | Raises if the cap is ignored |
| Yahoo Auctions | JP | ハイラックス + RN30 / 12R, and the vehicle category via `/carsearch` JSON | The category search changed format silently; see below |
| FLEX | JP | Freeword ハイラックス, oldest first | |
| kuruma-ex | JP | Model S112 capped at 1989 | |
| EVERY | JP | Toyota Hilux model pages | |
| TCV | JP export | Hilux, registration years 1978-84 | The filter is echoed in the page title; raises if absent |
| CAR FROM JAPAN | JP export | Hilux, maxYear 1985 | The sort parameter is ignored; the year cap is applied |
| Truck2Hand | TH | "hilux" and ไฮลักซ์ searches | Thailand is overwhelmingly modern diesel |

## Blocked from GitHub's servers (the email-alert route)

These return 403 (or similar) to datacentre IPs, confirmed again for the
Hilux on 2026-09-24. No evasion is attempted; the route is the saved-search
email alerts already planned for the 620 (Phase C in
`docs/sources-deep-dive.md`), which needs the dedicated Gmail account.

| Source | Why it matters for the Hilux |
|---|---|
| **Car & Classic** | Where the owner's reference RN30 was listed; the best UK classic inventory |
| AutoTrader UK | Largest UK marketplace |
| Gumtree AU, carsales.com.au, CarsGuide | Australia is a major Hilux market |
| Trade Me (NZ) | 406 on the web; the API needs OAuth |
| Classics on Autotrader, Cars.com | US classic and used inventory |
| One2car (TH), DoneDeal (IE), BE FORWARD | Blocked or JavaScript challenge |
| Hemmings, Cars & Bids | Settled as blocked for the 620 (2026-09-20) |

## Probed and not built

- **Kaidee (TH)**: the site is now a client-rendered app with no listing
  data in the page. This is also why the 620's Kaidee collector fails daily.
- **Craigslist, Mecum**: no listing data in the server-rendered page.
- **IH8MUD**: classifieds moved to a Land Cruiser-only app.
- **Ratsun**: a Datsun-only community.
- **classiccarsforsale.co.uk, JustCars, YotaTech**: 404 on the search URL.
