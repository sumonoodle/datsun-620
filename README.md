# Datsun 620 Tracker

A reference site for Datsun 620 pickup specs (1972 to 1979) and a daily tracker
of King Cab listings worldwide. Runs autonomously on GitHub Actions, hosted free
on GitHub Pages. Full product spec: [prd.md](prd.md) (v1.1).

Live site: https://sumonoodle.github.io/datsun-620/

## Status

**M1 (scaffolding).** Schema contract in place, daily pipeline running (FX only,
no scrapers yet), placeholder site deploying to Pages. This is a ground-up
rebuild against PRD v1.1; the previous build's collected data is preserved in
`data/legacy/` and gets imported when listings go live in M3.

Milestones: M2 curated specs, M3 tier 1 listings (eBay, Bring a Trailer),
M4 tier 2 + email digest, M5 Japan experiments, M6 polish.

## Layout

```
.github/workflows/   daily-scrape (cron pipeline), deploy (site to Pages)
schema/              the data contract, as JSON Schema. Edit here first.
data/                pipeline output: listings, changes, run log, FX log
data/legacy/         frozen data from the v1.0 build, imported in M3
scrapers/            Python: run_daily.py orchestrator, common/, listings/, tests/
site/                Astro site, mobile-first (390px primary viewport)
emailer/             daily digest sender (built in M4)
```

## Daily flow

1. Cron fires at 05:17 UTC (digest must land before ~08:00 Jersey time).
2. FX fetched once from Frankfurter, appended to `data/fx-rates.json`.
3. Listing scrapers run, each isolated: a failed source is logged, never fatal.
4. Results reconciled into `data/listings.json`; changes and run health written.
5. Data committed, site rebuilt and deployed.
6. Digest emailed (from M4; dry-run to `data/digest-latest.html` until sign-off).

## Working locally

```
pip install -r scrapers/requirements.txt
python scrapers/tests/test_fx.py        # offline tests
python scrapers/tests/test_schema.py
python scrapers/run_daily.py            # real run (fetches FX)

cd site
npm install
npm run build                           # outputs site/dist
npm run dev                             # http://localhost:4321/datsun-620
```

## Secrets (GitHub Actions)

Needed from M3/M4, none needed yet: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`,
`GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DEEPL_API_KEY`. Email stays in dry-run
until the repo variable `DIGEST_LIVE` is set to `1`.
