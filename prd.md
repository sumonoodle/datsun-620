# PRD: Datsun 620 Reference and King Cab Listings Tracker

**Version:** 1.1
**Owner:** Matt
**Status:** Ready for Claude Code kickoff

**Amendments agreed during the build (owner sign-off, July 2026):** storage is
JSON files rather than SQLite (diffable in git, readable from GitHub mobile,
matches the legacy data format); FX comes from Frankfurter rather than
exchangerate.host (which now requires an API key). eBay credentials are a
client ID + secret pair (`EBAY_CLIENT_ID`/`EBAY_CLIENT_SECRET`), not a single
app ID as the section 11 checklist assumed.

**Changes from v1.0:** public repo decision made explicit; spec scrapers replaced with a one-off research and curation milestone; listing sources resequenced by scraping reliability; Japan sources defined as degradable experiments; relisted detection scoped as best-effort heuristic; mobile-first requirements added for the site, the digest, and the build process itself.

**As-built amendments (agreed during the build; the body below is kept as
written, these notes override it where they conflict):**

- Storage is JSON files (`data/listings.json`), not SQLite: readable diffs in
  git are the owner's review surface. References to `listings.db` and the
  SQLite risk row read accordingly.
- FX comes from Frankfurter (ECB rates, no key), not exchangerate.host, which
  now requires an API key.
- Section 11 secrets as implemented: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`,
  `GMAIL_USER`, `GMAIL_APP_PASSWORD`, `DEEPL_API_KEY` (optional), plus the
  optional `HEALTHCHECK_PING_URL` heartbeat.
- The 4.2 King Cab filter also matches the katakana term キングキャブ, needed
  for Japanese listings, with a Japanese parts-word exclusion.
- The 5.3 daily order as run: data written, digest built and sent, data
  committed, site deployed last. Deploy after digest is deliberate: the
  digest must not wait on a Pages build.
- Section 9's "translation spot-checked on three Japanese listings" is
  satisfied by a fixture-based test of the DeepL path (three realistic
  Japanese titles), because both Japan sources block GitHub's IP ranges and
  provide no live listings; see docs/japan-sources.md.
- The site is installable as a web app (manifest, icon, offline fallback),
  an owner-requested addition beyond section 6.
- Scope change (owner decision, July 2026): the tracker follows ALL Datsun
  620 variants, not King Cabs only — the truck's rarity plus poorly-worded
  listings made the strict King Cab gate too likely to filter out real King
  Cabs. Confirmed King Cabs are highlighted (site chips, digest tags,
  King Cab-first ordering, a body filter) rather than being the entry bar.
  Section 4.2's filter is recorded per listing, not used to exclude.
- Asia expansion (owner-requested, July 2026): the section 4.4 Japan
  experiments concluded and were replaced by working collectors — Goo-net
  Exchange, Carsensor and Yahoo Auctions direct (reachable from GitHub
  runners, probe-proven), retiring the blocked goonet/yahoo_buyee pair.
  Thailand added: Kaidee collector with Thai matching rules (Datsun
  1300/1500 badges, คิงแค็บ, ช้างเหยียบ, Buddhist-Era year caution) and a
  TH market in specs (Thai assembly confirmed: Siam Motors & Nissan 1962,
  Siam Nissan Automobile 1977). FX gains THB. See docs/asia-sources.md.

## 1. Purpose

A single web app with two views:

1. **Specs**: a reference overview of every Datsun 620 pickup variant across major markets (1972 to 1979), with dimensions and specifications. Data is researched and curated once, stored as versioned JSON with source citations. Specs for a truck out of production since 1979 do not change; there is no refresh pipeline.
2. **Listings**: a daily-refreshed feed of Datsun 620 King Cab listings globally, with price (original currency and GBP), location, LHD/RHD, and price history. A daily email digest summarises new and changed listings.

The build runs autonomously via GitHub Actions on a free tier, with no paid infrastructure. The owner operates entirely from mobile devices; every review, sign-off, and verification step must work from a phone.

## 2. Goals and non-goals

### Goals
- Accurate, cited spec sheet for every 620 market variant.
- Daily King Cab listing sweep, prioritised by source reliability.
- Strict King Cab filtering (no false positives from standard cabs).
- Price and listing history per vehicle, with best-effort relisted detection.
- Daily email digest, readable in a mobile mail client.
- Mobile-first site design.
- Zero recurring cost.

### Non-goals
- Real-time alerts (daily is fine).
- Buying or bidding on the owner's behalf.
- Guaranteed Japan source coverage in v1 (they are experiments, see 4.4).
- Cross-source relisted matching (v1 matches within a source only).
- A spec refresh pipeline.
- A mobile app (the site is mobile-first web).

## 3. Users

One user: the owner. The repo and site are public. Accepted tradeoff: GitHub Pages on a free personal account requires a public repository, and Pages URLs are guessable, so privacy is not achievable at zero cost. Nothing sensitive lives in the repo; credentials are GitHub Actions secrets only. Public repos also get unlimited Actions minutes.

## 4. Scope

### 4.1 Specs view

Coverage: all major markets where the 620 was sold.

- **US**: 1972 to 1979, including King Cab from 1977.
- **UK**: limited official import; document what exists.
- **Australia**: locally assembled variants, including utes with tray bodies.
- **Japan (JDM)**: home-market variants, including double cab and King Cab.
- **South Africa**: locally assembled variants under Datsun and Nissan branding.
- **Europe**: continental variants where they differed from UK.

Data model: one JSON file (`data/specs.json`), versioned in git, with a citation (URL or publication reference) per variant. Populated by a research and curation milestone (M2), not by scrapers. Corrections are made by editing the JSON and rebuilding.

### 4.2 Listings view

Sources, in build order by reliability:

| Tier | Source | Method | Expectation |
|---|---|---|---|
| 1 | eBay (US/UK/DE/AU) | Official Browse API | Reliable |
| 1 | Bring a Trailer | HTML scrape | Reliable |
| 2 | Cars & Bids | HTML scrape | Likely reliable |
| 2 | Hemmings | HTML scrape | Likely reliable |
| 3 | Goo-net Exchange | HTML scrape | Experiment (see 4.4) |
| 3 | Yahoo Japan via Buyee or ZenMarket | HTML scrape, Playwright if needed | Experiment (see 4.4) |

**King Cab filter**: title or description must contain "King Cab", "Kingcab", "King-Cab", or "extended cab" (case-insensitive), with a sanity check on body style fields where present to catch unrelated mentions.

**FX**: a daily fixed rate fetched once per run from exchangerate.host (no key required). Stored alongside each listing snapshot so historical GBP values remain consistent.

**Relisted detection (best-effort heuristic)**: within the same source only, match on price proximity, title similarity, and location. Flagged as "possible relist" in the UI and digest, never asserted as fact. VINs are rarely listed; cross-source matching is out of scope for v1.

**Translation**: DeepL free API (key stored as a secret) for Japanese listings, with the deep-translator library as unofficial fallback. If both fail, show original text; never fail the run over translation.

### 4.3 Daily email digest

Sent via Gmail SMTP from a Google account using an app password, stored as a GitHub Actions secret.

Contents:
- New listings since last run (thumbnail, price in original + GBP, country, LHD/RHD, link)
- Price changes (old to new, percentage delta)
- Possible relists (with link to prior listing)
- Status changes (sold, withdrawn)
- Source health: which sources succeeded, which were skipped and why
- Summary stats: total active, count by country, median GBP price

Plain HTML, no tracking pixels, single column, large tap targets, tested against mobile mail rendering (Gmail and Apple Mail on phone).

### 4.4 Japan sources are degradable experiments

Goo-net and Yahoo Japan proxies are JS-heavy and likely to block GitHub Actions datacenter IPs. Rules:

- Each scraper runs in isolation; a blocked or failed source never fails the daily run.
- A skipped source is reported in the digest's source health section.
- If a Japan source is blocked for 7 consecutive days, Claude Code proposes options (alternative source, proxy, or dropping it) rather than silently retrying forever.
- v1 success does not depend on Japan sources working.

## 5. Architecture

### 5.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Site framework | Astro (static) | Fast static output, GitHub Pages friendly |
| Site hosting | GitHub Pages (public repo) | Free, same repo as scrapers |
| Scrape runner | GitHub Actions cron | Free and unlimited on public repos |
| Storage | SQLite committed to repo | Simple, version-controlled, right for this volume. Known tradeoff: slow git history growth from binary churn; acceptable for years at this scale |
| Language | Python 3.12 scrapers, TypeScript site | Best scraping ecosystem; Astro uses TS |
| Scraping | httpx, BeautifulSoup, Playwright only where required | Playwright is slow; use sparingly |
| Translation | DeepL free API, deep-translator fallback | See 4.2 |
| Email | Gmail SMTP via smtplib | Free, no third party |
| FX | exchangerate.host | Free, no key |

### 5.2 Repo layout

```
datsun-620/
├── .github/workflows/
│   └── daily-scrape.yml          # cron: daily, timed so the digest lands before ~08:00 Jersey time
├── scrapers/
│   ├── listings/                 # one module per source, isolated failures
│   ├── common/                   # FX, dedup, translation, schema, relist heuristic
│   └── tests/                    # fixtures + golden listings
├── data/
│   ├── specs.json                # curated spec database with citations
│   ├── listings.db               # SQLite listing history
│   └── fx-rates.json             # daily FX log
├── site/                         # Astro app (mobile-first)
├── emailer/
│   └── send_digest.py
├── prd.md
└── README.md
```

(specs-refresh.yml and scrapers/specs/ from v1.0 are deleted: no spec pipeline.)

### 5.3 Daily flow

1. Cron triggers (schedule set so the digest arrives before the owner's working day in Jersey; mind UTC vs local offset).
2. FX rate fetched once, written to `fx-rates.json`.
3. Listing scrapers run with per-source isolation; failures are logged, not fatal.
4. Results normalised, deduped against `listings.db`.
5. Changes computed: new, price changed, status changed, possible relists.
6. Database updated, site rebuilt, deployed.
7. Digest generated and sent, including source health.
8. Run summary committed for audit trail.

## 6. Mobile-first requirements

The owner reviews everything on a phone. This binds the product and the build process.

**Site**: single-column layouts, readable without zooming, filters usable with a thumb, listing cards over dense tables, images lazy-loaded. Test viewport 390px width as primary.

**Digest**: renders correctly in Gmail and Apple Mail mobile clients.

**Build process**: plans and summaries short enough to read on a phone; one sign-off question at a time; verification via things checkable from a phone (deploy URL, email in inbox, green tick on an Actions run in the GitHub mobile app); clear, descriptive commit messages since review happens in GitHub mobile.

## 7. Multi-agent build plan

| Agent | Responsibility |
|---|---|
| **Architect** | Repo scaffolding, workflow, shared schema, FX module, SMTP module |
| **Researcher** | M2 specs research: gather, verify, and cite spec data across six markets into specs.json |
| **Listings scraper** | Per-source scrapers, normalisation, King Cab filter, LHD/RHD inference, relist heuristic, failure isolation |
| **Frontend** | Astro site, mobile-first Specs and Listings views, vehicle history pages |
| **Emailer** | Digest template, change detection, source health, Gmail SMTP send |
| **QA** | Fixture tests, golden listings, FX sanity checks, King Cab filter regression, mobile rendering checks |
| **Product (owner, plain language)** | Reviews at each milestone; Claude Code flags tradeoffs rather than guessing |

Architect first; everything else parallelises against the shared schema.

## 8. Milestones

| # | Milestone | Definition of done |
|---|---|---|
| M1 | Scaffolding | Repo created, workflow defined (not yet scraping), schema in place, placeholder site deploys to GitHub Pages |
| M2 | Specs curated | specs.json populated for all six markets with citations, specs view renders mobile-first, owner spot-checks five variants |
| M3 | Listings tier 1 | eBay API + BaT scraping, listings view renders, FX working, daily cron runs end to end, failure isolation proven by test |
| M4 | Listings tier 2 + digest | Cars & Bids + Hemmings live; digest in dry-run mode (written to repo for review), then live send after sign-off |
| M5 | Japan experiments | Goo-net and Yahoo Japan attempted under the 4.4 rules; outcome documented either way |
| M6 | Polish | Filters (country, LHD/RHD, year, price), per-vehicle history pages, mobile QA pass, README and ops notes |

## 9. Verification

Before any scraper is done:
- Unit tests against saved HTML fixtures.
- One golden listing per source (known King Cab) checked end to end.
- FX verified against the exchangerate.host response.
- Translation spot-checked on three Japanese listings.

Before the digest goes live:
- Dry-run digest written to the repo for owner review on a phone.
- Live send only after sign-off.

Every milestone's proof must be checkable from a phone.

## 10. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Japan sources block Actions IPs | Moderate to high | Degradable design (4.4); v1 success does not depend on them |
| Any scraper breaks on site redesign | Certain, eventually | Fixture tests catch it; source health in digest surfaces it same day |
| eBay API approval friction | Low to moderate | Owner starts signup before M3 (see checklist) |
| Gmail app password revoked or rate limited | Low | Digest failure alerts via Actions failure email |
| SQLite git history bloat | Low, slow burn | Accepted; revisit if repo passes ~500MB |
| Relist heuristic false positives | Moderate | Framed as "possible relist", never asserted |

## 11. Owner checklist (all doable from a mobile browser)

Before M1:
- [ ] GitHub account ready; confirm repo name.

Before M3:
- [ ] eBay developer account signup started (approval can take days).
- [ ] Gmail app password created (requires 2FA on the Google account).
- [ ] DeepL free API key created.
- [ ] All three stored as GitHub Actions secrets: `EBAY_APP_ID`, `GMAIL_APP_PASSWORD`, `DEEPL_API_KEY`.

## 12. v1 success criteria

- Site live on GitHub Pages, mobile-first, with Specs and Listings views.
- Daily cron scraping all tier 1 and 2 sources reliably; Japan sources attempted and their status documented.
- Curated, cited specs for all six markets.
- Strict King Cab filtering with zero obvious false positives in a sample of 20 listings.
- Digest arrives each morning before the owner starts work in Jersey, readable on a phone.
- Total cost: zero.
