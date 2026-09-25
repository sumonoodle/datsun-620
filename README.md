# Datsun 620 Tracker (and Hilux RN30)

A reference site for Datsun 620 pickup specs (1972 to 1979) and a daily tracker
of King Cab listings worldwide. Since 2026-09-24 it tracks a second truck the
same way: the 3rd-generation petrol Toyota Hilux (1978 to 1983, RN30 and
relatives, 2WD and 4WD), with listings like the owner's reference RN30 (12R
1.6, 2WD, short bed) flagged first. Runs autonomously on GitHub Actions, hosted free
on GitHub Pages. Zero recurring cost. Full product spec: [prd.md](prd.md) (v1.1).

**Live site: https://sumonoodle.github.io/datsun-620/**

## What it does

- **Specs**: curated reference for every 620 variant across six markets
  (US, UK, Australia, Japan, South Africa, Europe), every variant cited,
  disagreements recorded openly with confidence ratings.
- **Listings**: daily sweep for King Cab listings across eBay (US/UK/DE/AU),
  Bring a Trailer, Cars & Bids, Hemmings, Goo-net and Yahoo Japan (Buyee),
  with GBP conversion, price/status history per vehicle, and best-effort
  relisted detection. Sources that block scraping degrade gracefully and
  report themselves ([docs/japan-sources.md](docs/japan-sources.md)).
- **Hilux**: the same pipeline for the 3rd-gen petrol Hilux, at
  [/hilux/](https://sumonoodle.github.io/datsun-620/hilux/): 17+ sources
  (every reachable 620 source plus Gumtree UK/ZA, Classic Trader, TCV,
  CAR FROM JAPAN, Goo-net). Identity rules live in one place,
  `scrapers/common/hilux.py`; diesels (LN codes) are excluded; any extended
  cab is flagged (none is known to exist in this generation, see
  [docs/hilux-identification.md](docs/hilux-identification.md)).
- **Digest**: a morning email summarising new listings, price changes,
  possible relists, status changes, source health and stats. Dry-run digests
  publish to [/digest.html](https://sumonoodle.github.io/datsun-620/digest.html).

## Status

v1 complete (M1 scaffolding through M6 polish). Operational levers and
troubleshooting: [docs/OPS.md](docs/OPS.md).

## Layout

```
.github/workflows/   daily-scrape (04:17 UTC cron), deploy (Pages), branch test
schema/              the data contract (JSON Schema). Edit here first.
data/                pipeline output + curated specs + legacy v1.0 archive;
                     data/hilux/ holds the Hilux equivalents
scrapers/            Python: run_daily.py, listings/ (620) and listings_hilux/
                     collectors, common/ (shared + hilux.py identity), tests/
site/                Astro site, mobile-first at 390px
emailer/             digest builder + Gmail SMTP send
docs/                ops notes, Japan source outcomes
```

## Daily flow

1. Cron fires; FX fetched once from Frankfurter (base GBP), logged.
2. Six collectors run in isolation; a blocked or broken source is recorded,
   never fatal.
3. Results reconcile into `data/listings.json`: new listings, price moves,
   status changes, possible relists.
4. The Hilux run follows (`run_daily.py --model hilux`) into `data/hilux/`,
   isolated so a Hilux failure never costs the 620 its data.
5. One digest covers both trucks, rendered (and emailed once
   `DIGEST_LIVE=1`); data committed; site rebuilt and deployed.

## Working locally

See [docs/OPS.md](docs/OPS.md). Short version: `pip install -r
scrapers/requirements.txt`, run any test in `scrapers/tests/`, and
`cd site && npm install && npm run dev`.
