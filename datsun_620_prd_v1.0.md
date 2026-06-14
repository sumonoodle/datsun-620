# PRD: Datsun 620 Reference and King Cab Listings Tracker

**Version:** 1.0
**Owner:** Matt
**Status:** Draft for Claude Code kickoff

## 1. Purpose

A single web app with two views:

1. **Specs**: a reference overview of every Datsun 620 pickup variant across major markets (1972 to 1979), with dimensions and specifications, scraped on demand from public sources.
2. **Listings**: a daily-refreshed feed of Datsun 620 King Cab listings globally, with price (original currency and GBP), location, LHD/RHD, and full history (price changes, time on market, relisted detection). A daily email digest summarises new and changed listings.

The build runs autonomously via GitHub Actions on a free tier, with no paid infrastructure.

## 2. Goals and non-goals

### Goals
- Comprehensive, accurate spec sheet for every 620 market variant.
- Daily King Cab listing sweep across the highest signal-to-noise global sources.
- Strict King Cab filtering (no false positives from standard cabs).
- Full price and listing history per vehicle, so I can spot trends and relisted cars.
- Daily email digest summarising new, changed, and relisted listings.
- Zero recurring cost.

### Non-goals
- Real-time alerts (daily is fine).
- Buying or bidding on my behalf.
- Coverage of every possible listing source on day one (Facebook Marketplace, Craigslist, niche regional sites deferred).
- A mobile app.

## 3. Users

One user: me. The site is private (unlisted URL is sufficient; no auth needed for v1).

## 4. Scope

### 4.1 Specs view

Coverage: all major markets where the 620 was sold.

- **US**: 1972 to 1979, including King Cab from 1977.
- **UK**: limited official import; document what exists.
- **Australia**: locally assembled variants, including utes with tray bodies.
- **Japan (JDM)**: home-market variants, including double cab and King Cab.
- **South Africa**: locally assembled variants under Datsun and Nissan branding.
- **Europe**: continental variants where they differed from UK.

Per-variant data fields:
- Market and years sold
- Body style (standard cab, King Cab, double cab, chassis cab)
- Bed length (short, long, where applicable)
- Engine code, displacement, power, torque
- Transmission options
- Dimensions: overall length, width, height, wheelbase, track, ground clearance, bed dimensions
- Weights: kerb, GVM, payload
- Wheels and tyres (factory)
- Trim levels
- Notable production changes year by year
- Source citations per fact

Data is scraped on demand (manual trigger), not on a schedule, and committed to the repo as structured JSON.

### 4.2 Listings view

Daily scrape across the v1 source list:

| Source | Method | Coverage |
|---|---|---|
| eBay (US, UK, DE, AU) | Official API | Multi-country |
| Bring a Trailer | HTML scrape | US auctions |
| Cars & Bids | HTML scrape | US auctions |
| Hemmings | HTML scrape | US classifieds |
| Goo-net Exchange | HTML scrape, auto-translated | Japan |
| Yahoo Auctions Japan (via Buyee or ZenMarket) | HTML scrape of proxy | Japan |

Per-listing data captured:
- Title, source, source URL
- Asking or current bid price (original currency)
- Price converted to GBP using daily fixed rate
- Currency code
- Country and region (where available)
- LHD or RHD (inferred from country and listing details; flagged as inferred where not explicit)
- Year, model trim
- Mileage
- Condition notes (extracted text)
- Photos (URL only, not stored)
- First seen date, last seen date
- Price history (timestamped)
- Status: active, sold, withdrawn, relisted
- Relisted-from reference (if matched to a prior listing by VIN, photos, or fuzzy match)

**King Cab filter**: strict. Title or description must contain "King Cab", "Kingcab", "King-Cab", or "extended cab" (case-insensitive). Listings that mention these terms only in unrelated context (e.g. "compare to King Cab") should be caught by a sanity check on body style fields where present.

**FX**: a daily fixed rate fetched once per run from exchangerate.host (no key required). Stored alongside each listing snapshot so historical GBP values remain consistent.

### 4.3 Daily email digest

Sent via Gmail SMTP from a Google account using an app password. Stored as a GitHub Actions secret.

Digest contents:
- New listings since last run (with thumbnail, price in original + GBP, country, LHD/RHD, link)
- Price changes (old → new, percentage delta)
- Relisted detections (with link to prior listing in history)
- Status changes (sold, withdrawn)
- Summary stats: total active listings, count by country, median GBP price

Plain HTML email, no tracking pixels.

## 5. Architecture

### 5.1 Stack recommendation

| Layer | Choice | Why |
|---|---|---|
| Site framework | Astro (static site generator) | Fast static output, easy to host on GitHub Pages, good for content-heavy sites |
| Site hosting | GitHub Pages | Free, in the same repo as scrapers |
| Scrape runner | GitHub Actions, scheduled (cron) | Free for public repos, 2,000 free minutes/month for private |
| Storage | SQLite file committed to repo | Simple, version-controlled, no external service, perfect for this volume |
| Language | Python 3.12 for scrapers, TypeScript for site | Python has the best scraping ecosystem; Astro uses TS |
| Scraping libraries | httpx, BeautifulSoup, Playwright for JS-heavy sites | Playwright only where necessary, since it's slower |
| Translation | DeepL free tier or Google Translate via deep-translator library | Japanese listings |
| Email | Gmail SMTP via Python smtplib | Free, no third-party service |
| FX | exchangerate.host | Free, no key |

### 5.2 Repo layout (proposed)

```
datsun-620/
├── .github/
│   └── workflows/
│       ├── daily-scrape.yml      # cron: daily at 06:00 UTC
│       └── specs-refresh.yml     # manual trigger
├── scrapers/
│   ├── specs/                    # one module per spec source
│   ├── listings/                 # one module per listing source
│   ├── common/                   # FX, dedup, translation, schema
│   └── tests/
├── data/
│   ├── specs.json                # spec database
│   ├── listings.db               # SQLite, listing history
│   └── fx-rates.json             # daily FX log
├── site/                         # Astro app
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.astro       # landing
│   │   │   ├── specs/            # specs view
│   │   │   └── listings/         # listings view
│   │   └── components/
│   └── astro.config.mjs
├── emailer/
│   └── send_digest.py
├── prd.md
└── README.md
```

### 5.3 Daily flow

1. GitHub Actions cron triggers at 06:00 UTC.
2. FX rate fetched once; written to `fx-rates.json`.
3. Scrapers run in parallel per source.
4. Results normalised to common schema, deduped against `listings.db`.
5. Changes computed: new, price changed, status changed, relisted matches.
6. Database updated; site rebuilt; deployed to GitHub Pages.
7. Email digest generated and sent via Gmail SMTP.
8. Run summary committed back to repo for audit trail.

### 5.4 Specs refresh flow

Manually triggered via GitHub Actions UI button. Runs all spec scrapers, writes `specs.json`, rebuilds site. No email.

## 6. Multi-agent build plan for Claude Code

The repo supports a clean multi-agent split. Proposed structure:

| Agent | Responsibility |
|---|---|
| **Architect** | Repo scaffolding, GitHub Actions workflows, shared schema definitions, FX module, SMTP module |
| **Specs scraper** | Six per-market scraper modules, normalisation to common spec schema, source citation tracking |
| **Listings scraper** | Six per-source listing scrapers, common normalisation, strict King Cab filter, LHD/RHD inference, relisted detection |
| **Frontend** | Astro site, Specs view, Listings view with filters, vehicle history pages |
| **Emailer** | Digest template, change detection, Gmail SMTP send |
| **QA** | Schema validation, end-to-end test against fixtures, sanity checks on FX, regression tests for King Cab filter |
| **Product (me, in plain language)** | I'll review output at each milestone and steer scope; Claude Code should flag tradeoffs rather than guess |

Agents work in parallel where possible. Architect goes first, then everything else can run concurrently with shared schema as the contract.

## 7. Milestones

| # | Milestone | Definition of done |
|---|---|---|
| M1 | Scaffolding | Repo created, workflows defined (not yet running real scrapers), schema files in place, deploy pipeline confirmed with a placeholder site |
| M2 | Specs v1 | At least three of six markets scraped, specs view renders, source citations visible |
| M3 | Specs complete | All six markets, manual refresh works |
| M4 | Listings v1 | eBay + BaT + one Japan source scraping, listings view renders, FX working, daily cron runs end to end |
| M5 | Listings complete | All six sources, full history, relisted detection, email digest sending |
| M6 | Polish | Filters on listings view (country, LHD/RHD, year, price range), per-vehicle history pages, README and ops notes |

## 8. Verification approach

Before any scraper is "done":
- Unit tests against saved HTML fixtures, so I can re-run them when sites change.
- One golden listing per source (known King Cab) checked end to end.
- FX conversion verified against the exchangerate.host response.
- Translation spot-checked on three Japanese listings.

Before the email goes live:
- Dry-run mode that writes the digest to a file in the repo for me to review.
- Once I sign off, switch to live send.

## 9. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Source sites change HTML and break scrapers | High over time | Fixtures + clear error logs; each scraper isolated so one failure doesn't kill the run |
| Goo-net or Yahoo proxy blocks scraping | Moderate | Polite rate limits, rotating user agent, fall back to manual refresh; flag in digest if a source was skipped |
| King Cab filter false positives | Moderate | Strict keyword filter + manual spot check during M5; I can tighten rules from the data |
| LHD/RHD inference wrong | Low to moderate | Default by country, flag as inferred, allow manual override per listing |
| GitHub Actions free minutes exceeded | Low | Estimate < 10 min per daily run; well within 2,000/month |
| Gmail SMTP flagged as spam | Low | Send to myself only; whitelist sender |
| Translation API rate limits | Low | DeepL free tier is generous; cache translations per listing |

## 10. Open items for after kickoff

Not blocking the start; flag when reached:
- Whether to expose the site publicly or keep the URL unlisted.
- Whether to add a "watchlist" feature for specific listings I want extra alerts on.
- Whether to track sold prices for market value analysis (would need to scrape sold-listing data, harder on some sources).

## 11. Out of scope for v1 (explicitly)

- Facebook Marketplace, Craigslist.
- Mobile app or PWA.
- Multi-user accounts.
- Bidding or buying automation.
- Image storage or analysis.
- Notifications outside the daily email.

## 12. Kickoff checklist (before Claude Code starts)

- [ ] GitHub account ready
- [ ] eBay Developer Program account, Client ID and Secret in hand
- [ ] Gmail account with 2FA and an app password generated
- [ ] Personal preferences confirmed: site name, repo name, public or private repo
- [ ] PRD reviewed and signed off
