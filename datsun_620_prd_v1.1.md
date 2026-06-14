# PRD: Datsun 620 Reference and King Cab Listings Tracker

**Version:** 1.1
**Owner:** Matt
**Status:** Draft for Claude Code kickoff

## 0. Changelog (1.0 to 1.1)

Updated after kickoff Q&A and a fitness-for-purpose review against the stated goal (comparative specs site plus a wide-net, low-volume King Cab listings tracker with notify-on-appearance).

- **Hosting:** public repo with an unlisted Pages URL. Confirms zero cost; accepts that repo, data, and site are technically public but obscure.
- **Listings filter:** reoptimised from precision-first ("strict, zero false positives") to **recall-first** (wide net on any Datsun 620, then score and rank likelihood of being a King Cab, multilingual). Rationale: for a rare car the costly mistake is missing a real one, not seeing a wrong one.
- **Notification:** changed from a fixed daily digest to **notify-on-change only**. Checks run frequently; email is sent only when there is something new or changed. Silent runs send nothing.
- **Specs:** automated collection with a **conflict-reconciliation** step. Agreeing sources auto-accept; disagreements or weak sources go to a conflicts queue for a human decision, and decisions are remembered.
- **Specs presentation:** comparison-first (side by side across years and markets), not isolated per-variant sheets.
- **Storage:** JSON / NDJSON instead of a committed SQLite binary. Simpler, diffable, right-sized for the volume.
- **FX:** switched from exchangerate.host (now requires a key) to a keyless source (Frankfurter, ECB-backed).
- **eBay:** use the current **Browse API** (the Finding API was decommissioned Feb 2025).
- **Source scope:** reliable core first (eBay + Goo-net) proven end to end, then the harder auction/proxy sources as best-effort with explicit "source skipped" flagging.
- **Relisted detection:** simple fuzzy matching, not VIN/photo matching.

## 1. Purpose

A single web app with two views:

1. **Specs**: a comparative reference of every Datsun 620 pickup variant across major markets (1972 to 1979), with dimensions and specifications, collected automatically from public sources with a human-in-the-loop where sources conflict. Presented comparison-first so variants can be read side by side.
2. **Listings**: a frequently-refreshed feed of Datsun 620 King Cab listings worldwide, cast as a wide net (any 620, then scored for King Cab likelihood across languages), with price (original currency and GBP), location, LHD/RHD, and history (price changes, time on market, relisted detection). An email notification is sent only when a new or changed listing appears.

The build runs autonomously via GitHub Actions on a free tier, with no paid infrastructure.

## 2. Goals and non-goals

### Goals
- Comprehensive, accurate, comparative spec sheet for every 620 market variant, with a citation per fact.
- Wide-net King Cab listing sweep across the highest signal-to-noise global sources, optimised for recall so genuine cars are not missed.
- Multilingual King Cab detection and scoring (handles "King Cab", "Kingcab", "extended cab", キングキャブ, and listings that only show the body style in photos).
- Full price and listing history per vehicle, so trends and relisted cars are visible.
- Notification only when something changes. No empty or routine emails.
- Zero recurring cost.

### Non-goals
- Real-time alerts.
- Routine or scheduled emails when nothing has changed.
- Buying or bidding on my behalf.
- Coverage of every possible listing source on day one (Facebook Marketplace, Craigslist, niche regional sites deferred).
- A mobile app.

## 3. Users

One user: me. The site is public but unlisted (unguessable URL is sufficient; no auth needed for v1). Nothing in the data is sensitive.

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

**Collection and reconciliation.** Data is collected automatically from multiple public sources, then reconciled:
1. The same field is gathered from more than one source where possible.
2. If sources agree, the value is auto-accepted with its citations.
3. If sources disagree, or only a weak source exists, the field goes to a **conflicts queue** (`data/specs-conflicts.json`) listing each candidate value and its source.
4. I review the queue and pick; my decision is recorded (`data/specs-decisions.json`) so the same conflict is not re-raised on the next refresh.

Specs collection runs on manual trigger, not a schedule. Output is committed as structured JSON.

**Presentation.** Comparison-first: the primary view lets variants be compared side by side across years and markets (comparison table plus selector/filter), with per-variant detail behind it. Citations visible per fact.

### 4.2 Listings view

Refreshed on a frequent schedule. v1 source plan, core first:

| Tier | Source | Method | Coverage |
|---|---|---|---|
| Core | eBay (US, UK, DE, AU) | Official Browse API | Multi-country |
| Core | Goo-net Exchange | HTML scrape, auto-translated | Japan |
| Best-effort | Bring a Trailer | HTML scrape | US auctions |
| Best-effort | Cars & Bids | HTML scrape | US auctions |
| Best-effort | Hemmings | HTML scrape | US classifieds |
| Best-effort | Yahoo Auctions Japan (via Buyee or ZenMarket) | HTML scrape of proxy | Japan |

The core sources are proven end to end first. Best-effort sources are added once the core works; they may be blocked by datacenter-IP filtering or bot protection, in which case the run continues and the skipped source is flagged.

**Filtering: recall-first, not strict.** The goal is to not miss genuine cars, accepting that I will eyeball edge cases.
- Cast a wide net: pull anything matching **Datsun 620** from each source.
- Score each listing for King Cab likelihood using multilingual signals: "King Cab", "Kingcab", "King-Cab", "extended cab", キングキャブ, and other market terms, plus body-style fields and structural hints where present.
- Present everything, ranked: likely King Cabs surfaced first, a "possible / unconfirmed" bucket below. I can confirm or dismiss; the wrong ones are cheap to discard.

Per-listing data captured:
- Title, source, source URL
- Asking or current bid price (original currency)
- Price converted to GBP using the day's fixed rate
- Currency code
- Country and region (where available)
- LHD or RHD (inferred from country and listing details; flagged as inferred where not explicit; manual override allowed)
- Year, model trim
- Mileage
- Condition notes (extracted text)
- King Cab likelihood score and the signals behind it
- Photos (URL only, not stored)
- First seen date, last seen date
- Price history (timestamped)
- Status: active, sold, withdrawn, relisted
- Relisted-from reference (if matched to a prior listing by fuzzy match on title, price, location, and key details)

**FX**: a daily fixed rate fetched once per run from a keyless source (Frankfurter, ECB-backed). Stored alongside each listing snapshot so historical GBP values remain consistent.

**Storage**: JSON / NDJSON committed to the repo (`data/listings.json` plus per-run snapshots). Human-readable, diffable, right-sized for the expected volume (tens of listings, not thousands).

### 4.3 Email notification

Sent via Gmail SMTP from a Google account using an app password, stored as a GitHub Actions secret. **Sent only when there is something to report.** A run with no new or changed listings sends nothing.

Notification contents (only the non-empty sections appear):
- New listings since last run (with thumbnail, price in original + GBP, country, LHD/RHD, King Cab likelihood, link)
- Price changes (old to new, percentage delta)
- Relisted detections (with link to prior listing in history)
- Status changes (sold, withdrawn)
- Any sources skipped this run (blocked or errored)

Plain HTML email, no tracking pixels.

## 5. Architecture

### 5.1 Stack

| Layer | Choice | Why |
|---|---|---|
| Site framework | Astro (static site generator) | Fast static output, easy to host on GitHub Pages, good for content-heavy and comparison-table sites |
| Site hosting | GitHub Pages (public repo, unlisted URL) | Free, in the same repo as scrapers |
| Scrape runner | GitHub Actions, scheduled (cron) | Free for public repos |
| Storage | JSON / NDJSON committed to repo | Simple, version-controlled, diffable, right-sized for this volume |
| Language | Python 3.12 for scrapers, TypeScript for site | Python has the best scraping ecosystem; Astro uses TS |
| Scraping libraries | httpx, BeautifulSoup, Playwright only for JS-heavy sites | Playwright only where necessary, since it is slower and more bot-detectable |
| eBay | Browse API (OAuth) | Finding API decommissioned Feb 2025; Browse is the current path |
| Translation | DeepL free tier or Google Translate via deep-translator | Japanese listings and multilingual King Cab detection |
| Email | Gmail SMTP via Python smtplib | Free, no third-party service |
| FX | Frankfurter (ECB-backed) | Free, no key |

### 5.2 Repo layout (proposed)

```
datsun-620/
├── .github/
│   └── workflows/
│       ├── scrape.yml             # cron: frequent listings check, notify on change
│       └── specs-refresh.yml      # manual trigger
├── scrapers/
│   ├── specs/                     # one collector per spec source + reconciler
│   ├── listings/                  # one scraper per listing source
│   ├── common/                    # FX, dedup, translation, King Cab scoring, schema
│   └── tests/
├── data/
│   ├── specs.json                 # reconciled spec database
│   ├── specs-conflicts.json       # fields needing a human decision
│   ├── specs-decisions.json       # my recorded decisions, replayed on refresh
│   ├── listings.json              # current listings + history
│   ├── snapshots/                 # per-run listing snapshots
│   └── fx-rates.json              # daily FX log
├── site/                          # Astro app
│   ├── src/
│   │   ├── pages/
│   │   │   ├── index.astro        # landing
│   │   │   ├── specs/             # comparison-first specs view
│   │   │   └── listings/          # ranked listings view
│   │   └── components/
│   └── astro.config.mjs
├── emailer/
│   └── send_notification.py
├── prd.md
└── README.md
```

### 5.3 Listings flow (scheduled)

1. GitHub Actions cron triggers the listings check.
2. FX rate fetched once; written to `fx-rates.json`.
3. Core scrapers run (eBay, Goo-net); best-effort scrapers run if reachable, otherwise skipped and flagged.
4. Results normalised to common schema, scored for King Cab likelihood (multilingual), deduped against `listings.json`.
5. Changes computed: new, price changed, status changed, relisted matches.
6. Data updated; site rebuilt; deployed to GitHub Pages.
7. **If and only if there are changes**, email notification generated and sent via Gmail SMTP.
8. Run summary committed back to repo for audit trail.

### 5.4 Specs refresh flow (manual)

Manually triggered via GitHub Actions UI button. Runs all spec collectors, reconciles against `specs-decisions.json`, writes `specs.json` and any new entries to `specs-conflicts.json`, rebuilds site. No email. I review the conflicts queue and record decisions, which are applied on the next refresh.

## 6. Multi-agent build plan for Claude Code

| Agent | Responsibility |
|---|---|
| **Architect** | Repo scaffolding, GitHub Actions workflows, shared schema definitions, FX module, SMTP module |
| **Specs collector** | Per-market collectors, normalisation to common spec schema, source citation tracking, the reconciler and conflicts queue |
| **Listings scraper** | Per-source listing scrapers (core first), common normalisation, multilingual King Cab scoring, LHD/RHD inference, fuzzy relisted detection |
| **Frontend** | Astro site, comparison-first specs view, ranked listings view with filters, vehicle history pages |
| **Notifier** | Notification template, change detection, send-only-on-change logic, Gmail SMTP send |
| **QA** | Schema validation, end-to-end tests against fixtures, FX sanity checks, regression tests for King Cab scoring (recall on golden listings) |
| **Product (me, in plain language)** | Review output at each milestone, steer scope, decide spec conflicts; Claude Code flags tradeoffs rather than guessing |

Architect goes first; the shared schema is the contract. Other agents run concurrently once the schema is frozen.

## 7. Milestones

| # | Milestone | Definition of done |
|---|---|---|
| M1 | Scaffolding | Repo created, workflows defined (not yet running real scrapers), schema files in place, deploy pipeline confirmed with a placeholder site |
| M2 | Specs v1 | At least three of six markets collected, reconciler and conflicts queue working, comparison view renders, citations visible |
| M3 | Specs complete | All six markets, manual refresh works, conflicts queue and recorded decisions working end to end |
| M4 | Listings core | eBay + Goo-net scraping, recall-first scoring, ranked listings view renders, FX working, scheduled run end to end, notify-on-change working |
| M5 | Listings complete | Best-effort sources added (with skip flagging), full history, fuzzy relisted detection |
| M6 | Polish | Filters on listings view (country, LHD/RHD, year, price range, King Cab likelihood), per-vehicle history pages, README and ops notes |

## 8. Verification approach

Before any scraper or collector is "done":
- Unit tests against saved HTML / API fixtures, so they can be re-run when sites change.
- Golden listings per source, including at least one that does not use the words "King Cab" but is one, to test recall.
- King Cab scoring checked for recall on the golden set (genuine cars must not be dropped) and reasonableness on near-misses.
- FX conversion verified against the Frankfurter response.
- Translation and multilingual detection spot-checked on three Japanese listings.
- Specs reconciler checked: agreeing sources auto-accept, disagreeing sources land in the conflicts queue, recorded decisions are replayed.

Before notifications go live:
- Dry-run mode that writes the notification to a file in the repo for me to review.
- Once I sign off, switch to live send.

## 9. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Source sites change HTML and break scrapers | High over time | Fixtures + clear error logs; each scraper isolated so one failure does not kill the run |
| Best-effort sources block GitHub Actions datacenter IPs / bot protection | High on those sources | Core sources do not depend on them; run continues and flags the skip; revisit paid proxy only if coverage there becomes important (would break zero cost) |
| King Cab cars missed (false negatives) | Moderate | Recall-first wide net + scoring + golden recall tests; I review the "possible" bucket |
| LHD/RHD inference wrong | Low to moderate | Default by country, flag as inferred, allow manual override per listing |
| GitHub Actions free usage exceeded | Low | Public repo; runs are short and low-volume |
| Gmail SMTP flagged as spam | Low | Send to myself only; whitelist sender |
| Translation API rate limits | Low | Free tiers are generous; cache translations per listing |
| Spec sources contradict each other | Moderate | Reconciler routes conflicts to me; decisions recorded and replayed |

## 10. Open items for after kickoff

Not blocking the start; flag when reached:
- Whether to add a "watchlist" for specific listings I want extra attention on.
- Whether to track sold prices for market value analysis (harder on some sources).
- Whether to invest in getting the best-effort sources reliable (likely needs a paid proxy).

## 11. Out of scope for v1 (explicitly)

- Facebook Marketplace, Craigslist.
- Mobile app or PWA.
- Multi-user accounts.
- Bidding or buying automation.
- Image storage or analysis.
- Notifications outside email-on-change.

## 12. Kickoff checklist (before Claude Code starts)

- [ ] GitHub account ready
- [ ] eBay Developer Program account, credentials for the **Browse API** (OAuth) in hand
- [ ] Gmail account with 2FA and an app password generated
- [ ] Personal preferences confirmed: site name, repo name (repo will be **public**)
- [ ] PRD reviewed and signed off
