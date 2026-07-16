# Datsun 620 Tracker

A reference site for Datsun 620 pickup specs (1972 to 1979) and a daily tracker
of King Cab listings worldwide. Runs autonomously on GitHub Actions, hosted free
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
data/                pipeline output + curated specs + legacy v1.0 archive
scrapers/            Python: run_daily.py, per-source collectors, common/, tests/
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
4. Digest rendered (and emailed once `DIGEST_LIVE=1`); data committed; site
   rebuilt and deployed.

## Working locally

See [docs/OPS.md](docs/OPS.md). Short version: `pip install -r
scrapers/requirements.txt`, run any test in `scrapers/tests/`, and
`cd site && npm install && npm run dev`.
