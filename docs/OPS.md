# Operations notes

Plain-language guide to running the Datsun 620 Tracker. Nothing here needs daily
attention; it runs itself. This is for when you want to turn something on or
figure out why a source is empty.

## What runs automatically

- **Listings check** (`.github/workflows/scrape.yml`): daily at 06:00 UTC
  (07:00 Jersey in summer). Fetches exchange rates, checks all six sources,
  updates the data, rebuilds the site, and emails you only if something changed.
- **Site deploy** (`deploy.yml`): runs whenever data or code changes, publishing
  to https://sumonoodle.github.io/datsun-620/.
- **Specs refresh** (`specs-refresh.yml`): manual only. Run it from the GitHub
  Actions tab when you want to re-pull specs.

You can trigger any workflow by hand: GitHub repo → Actions → pick the workflow →
"Run workflow".

## Turning on eBay

eBay is the most important listings source and needs your developer credentials.

1. Once eBay approves your developer account, generate **Production** keys
   (App ID / Client ID and Cert ID / Client Secret) for the Browse API.
2. In the GitHub repo: Settings → Secrets and variables → Actions → New
   repository secret. Add two secrets:
   - `EBAY_CLIENT_ID`
   - `EBAY_CLIENT_SECRET`
3. That's it. The next daily run (or a manual run) will include eBay. Until then
   it shows as "skipped (awaiting credentials)" on the Listings page.

Open risk to confirm: that the Browse API actually returns vintage 620 listings.
The first run with credentials is the test. If eBay returns nothing, we revisit.

## Turning on email (go-live)

Email is built but kept in dry-run until you approve it, so it can't surprise you.

1. In your Google account: turn on 2-step verification, then create an **app
   password** (Google Account → Security → App passwords).
2. Add two repo secrets:
   - `GMAIL_USER` (your Gmail address)
   - `GMAIL_APP_PASSWORD` (the 16-character app password)
3. Review what an email will look like: open `data/digest-sample.html` in the
   repo (or `data/digest-latest.html` after a run).
4. When happy, add a repo **variable** (not secret): Settings → Secrets and
   variables → Actions → Variables tab → New variable: `NOTIFY_LIVE` = `1`.
5. From then on you get an email only when a listing is new, changed, relisted,
   or withdrawn. Quiet days send nothing.

To pause emails, set `NOTIFY_LIVE` to `0` (or delete it).

## Why a source shows "skipped"

The Listings page lists each source's status every run.

- **eBay**: skipped until credentials are added (see above).
- **Cars & Bids, Hemmings, Goo-net, Yahoo/Buyee**: these block automated access
  from datacenter IPs (the GitHub runners), so they usually skip with an
  HTTP 403/404/429 note. This is expected and does not break the run. Making them
  reliable would need a paid residential proxy, which breaks the zero-cost goal,
  so they are best-effort for now.
- **Bring a Trailer**: works from the runner. Returns 620 auctions when present.

An empty Listings page is normal: the 620 King Cab is rare and often nothing is
for sale.

## Resolving spec conflicts

When sources disagree on a spec, it appears under "Needs review" on the Specs
page and in `data/specs-conflicts.json`. To resolve one, add an entry to
`data/specs-decisions.json`:

```json
{ "variant_id": "au-620-ute", "field": "dimensions.length_mm", "chosen_value": 4609, "decided_on": "2026-06-15" }
```

Then run the Specs refresh workflow. The conflict clears and your chosen value
shows with its citation. (A click-to-resolve UI is a possible future addition.)

## Running things locally

```
# Python tools
python3 -m venv .venv && source .venv/bin/activate
pip install -r scrapers/requirements.txt
python scrapers/run_specs.py        # refresh specs
python scrapers/run_listings.py     # refresh listings (eBay/email use env vars if set)
python scrapers/tests/test_listings.py   # and the other test_*.py

# Site
cd site && npm install && npm run build   # output in site/dist
npm run dev                               # local preview
```

## Cost

Everything runs on free tiers: GitHub Actions (public repo), GitHub Pages,
Frankfurter FX (no key), Gmail SMTP. The only thing that would cost money is a
residential proxy for the blocked sources, which we have not added.
