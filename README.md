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

**M2 (specs v1) complete.** Specs are live for UK, Japan, and Australia, collected
from multiple sources, reconciled, with a citation per value and a conflicts queue
for fields where sources disagree. Remaining markets come in M3; real listings in
M4 to M5.

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
