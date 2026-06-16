# Datsun 620 Tracker

A reference site for Datsun 620 specs and a worldwide King Cab listings tracker.
Runs autonomously on GitHub Actions, hosted free on GitHub Pages. See
[datsun_620_prd_v1.1.md](datsun_620_prd_v1.1.md) for the full product spec.

Two views:

- **Specs**: comparative reference of every 620 variant across markets, collected
  automatically with a human-in-the-loop where sources disagree.
- **Listings**: King Cab listings worldwide, cast as a wide net then ranked by
  likelihood, with email notification only when something new or changed appears.

## Status

**Specs complete (M3)** for all six markets, reconciled with citations and a
conflicts queue.

**Listings complete (M5).** Daily sweep across six sources: eBay (Browse API) and
Bring a Trailer as the core, plus Cars & Bids, Hemmings, Goo-net, and Yahoo/Buyee
as best-effort (skipped and flagged when blocked). Recall-first multilingual King
Cab scoring, GBP conversion (Frankfurter), full price/status history, fuzzy
relisted detection, and a notify-on-change email digest.

Two things need your input to switch fully on:
- **eBay**: add `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` as repo secrets (pending
  developer approval). Until then eBay skips and flags itself.
- **Email go-live**: add `GMAIL_USER` / `GMAIL_APP_PASSWORD` secrets, review
  `data/digest-sample.html`, then set repo variable `NOTIFY_LIVE=1`. Until then
  the digest is written to `data/digest-latest.html` (dry-run) and not emailed.

**Polish (M6).** Listings view has filters (country, drive side, year, price,
King Cab likelihood) and per-vehicle history pages with the full price timeline.

See [docs/OPS.md](docs/OPS.md) for how to turn on eBay and email, resolve spec
conflicts, and run things locally.

Run a listings refresh locally:

```
python scrapers/run_listings.py
```

Refresh specs locally:

```
python scrapers/run_specs.py     # collect, reconcile, write data/specs*.json
```

In CI, run the "Specs refresh" workflow manually from the Actions tab.

## Layout

```
.github/workflows/   deploy (site to Pages), scrape (scheduled), specs-refresh (manual)
schema/              the data contract, as JSON Schema. Edit here first.
data/                JSON data files (placeholder in M1)
scrapers/            Python scrapers + shared schema helper + tests
site/                Astro site (the front end)
emailer/             notification sender (M5)
```

## Working locally

Build the site:

```
cd site
npm install
npm run build      # outputs to site/dist
npm run dev        # local preview at http://localhost:4321/datsun-620
```

Validate the data files against the schema contract:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r scrapers/requirements.txt
python scrapers/tests/test_schema.py
```

## How it deploys

Any push to `main` triggers `.github/workflows/deploy.yml`, which builds the Astro
site and publishes it to GitHub Pages. The scheduled `scrape.yml` runs daily and
(from M4) updates the listings data, which the next build renders.
