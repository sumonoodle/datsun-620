# Ops notes

Everything here is doable from a phone browser. The daily pipeline runs
itself; these are the levers when something needs a human.

## Daily rhythm

- Cron fires at 04:17 UTC (GitHub can add up to ~2h delay; digest still lands
  before 07:30 Jersey). Green tick: Actions tab, "daily-scrape".
- Each run commits a `data: daily run YYYY-MM-DD` commit. The diff is the
  audit trail: FX rates, listings, changes, run log, digest.
- The site redeploys automatically after every run.
- Latest digest, rendered: https://sumonoodle.github.io/datsun-620/digest.html

## Turning email on (and off)

Prerequisites: `GMAIL_USER` and `GMAIL_APP_PASSWORD` secrets (set 2026-07-16).

- ON: repo Settings → Secrets and variables → Actions → Variables tab →
  New repository variable: name `DIGEST_LIVE`, value `1`.
- OFF: set `DIGEST_LIVE` to `0` (or delete it). Dry-run digests keep being
  written to the repo and site regardless.
- Compromised app password: revoke at https://myaccount.google.com/apppasswords,
  create a new one, update the secret. Nothing else changes.

## When a source breaks

The digest's Source health section shows every source daily. Expected states:

- **eBay, Bring a Trailer**: normally green. A parse failure here usually
  means a site redesign; the fixture tests in `scrapers/tests/` pin the
  expected format, so ask Claude Code to refresh the fixture and parser.
- **Cars & Bids, Hemmings, Goo-net, Yahoo (Buyee)**: blocked (403/404) most
  days; that is documented, not broken. See `docs/japan-sources.md` for the
  evidence and the options if coverage matters later.
- Any source blocked 7+ days shows "decision needed" in the digest.

A failing source NEVER fails the run; if the daily-scrape tick itself goes
red, the problem is elsewhere (FX API, GitHub, or a code bug) and the Actions
log for the failed step is the place to look.

## Secrets inventory

| Secret | Used by | Rotate how |
|---|---|---|
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | eBay collector | developer.ebay.com → Application Keys |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | digest send | Google app passwords page |
| `DEEPL_API_KEY` (optional) | Japanese translation | deepl.com account; without it the fallback translator is used |

## Local development

```
pip install -r scrapers/requirements.txt
python scrapers/tests/test_schema.py      # run any/all test files the same way
python scrapers/run_daily.py              # real run, writes into data/

cd site && npm install && npm run dev     # http://localhost:4321/datsun-620
```

## Data files

| File | What |
|---|---|
| `data/listings.json` | every listing ever seen, with per-listing history |
| `data/changes-latest.json` | what changed in the last run (digest input) |
| `data/run-log.json` | last run's source health and totals |
| `data/fx-rates.json` | daily GBP rates log (each listing stores its own rate) |
| `data/specs.json` | curated specs, edit by hand + rebuild to correct |
| `data/legacy/` | frozen v1.0 build data (history preserved, already imported) |

## Known limits

- eBay Browse API results for vehicles vary by marketplace; a genuine King
  Cab listing that the daily run misses should be reported so the query or
  filter can be tuned (`scrapers/listings/ebay.py`).
- Relist detection is a heuristic and always labelled "possible".
- Withdrawn = missing from a healthy source for 3+ days; auction sites report
  sold explicitly.
