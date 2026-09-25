# Tracker

Everything left on the Datsun 620 and Hilux tracker. The live, tickable copy is the tracker page (https://claude.ai/artifact/UekmKQa9pGXToDPV92vpcL); this file is its repo copy, seeded 2026-09-25 and updated when asked.

## 1. Waiting on you

- [ ] **1.1** Create a dedicated alerts-only Gmail account : You
  Hemmings, Cars & Bids, CLASSIC.COM, Car & Classic, AutoTrader UK, Gumtree AU, carsales and Cars.com all block GitHub's servers, so they can't be scraped. Every one of them offers saved-search emails instead. A Gmail account used only for those alerts lets the daily run read them and add the listings to the tracker. This is the single biggest coverage gain left: Car & Classic is where your reference RN30 was listed, and one CLASSIC.COM alert covers Cars & Bids, Hemmings and the big US auction houses at once.
- [ ] **1.2** Set up saved searches on the blocked sites, sent to the new account : You _(status: Open, after 1.1)_
  After 1.1. On each site, save a search for the Datsun 620 (and Datsun pickup 1972-79) and for the Hilux 1978-83, with email alerts on. Suggested list: CLASSIC.COM (620 model alert), Hemmings, Cars & Bids, Car & Classic, AutoTrader UK, Gumtree AU, carsales, Cars.com, Kleinanzeigen (Suchauftrag). Claude builds the reader only against real emails, so a week of received alerts is what unblocks 2.2.
- [ ] **1.3** Decide what to do with Kaidee (Thailand) : Both _(status: Decide)_
  Kaidee rebuilt its site as an app that loads everything in the browser. Every page, including its robots.txt, now returns the same empty shell, so there is no way to confirm scraping is allowed. It fails every day. Thailand is still covered by Truck2Hand, which carries four live 620s.
- [ ] **1.4** Decide whether Cars & Bids and Hemmings keep running every day : Both _(status: Decide)_
  Both have been blocked for 75 days in a row. The block is an IP ban on GitHub's servers, not a rule change, so it will not lift. They run muted every day, cost a few seconds each, and add nothing.
- [ ] **1.5** Confirm the morning email is arriving : You
  The digest is only emailed when the repo variable DIGEST_LIVE is 1. Claude cannot see repo variables from here, so this is unverified. Check that an email with both trucks arrives on 26 Sep. If it doesn't, set DIGEST_LIVE to 1 under Settings, Secrets and variables, Actions, Variables. The run on 25 Sep started at 04:58 UTC, about 06:00 in Jersey, so the cron fix is holding.
- [ ] **1.6** Tell Claude your buying criteria for each truck : You _(status: Decide)_
  The features in section 4 (instant alerts, fair-price check, landed cost) need to know what a truck you'd act on looks like. One line per truck is enough: budget ceiling in GBP, King Cab only or any cab, drive side, condition you'd accept (project, running, restored), and countries you'd import from.
- [ ] **1.7** Set up the dead-man's switch (optional) : You
  GitHub emails you when a run fails, but not when runs stop happening at all. A free healthchecks.io check (period 1 day, grace 6 hours) emails you if the daily run goes quiet. Add its ping URL as the secret HEALTHCHECK_PING_URL. Ten minutes, from a phone.
- [ ] **1.8** Check the first Hilux results on 26 Sep : Both
  The Hilux work merged after the 25 Sep run, so the first real Hilux run on main is the morning of 26 Sep. Look at /hilux/ and the Hilux section of the digest. Anything that looks wrong (a diesel, a Surf, a wrong year) is an identity rule to fix in one place, and a quick thread can do it.

## 2. Claude's queue

- [ ] **2.1** Fix the six 620 collector bugs found during the Hilux build : Claude
  Found while building the Hilux side and left for a follow-up: Yahoo Auctions category search, Bring a Trailer live auction cards, Kijiji's listing format, FLEX price parsing, and everycar's sold state. Each is small. Together they mean some 620 listings are being missed or mislabelled today.
- [ ] **2.2** Build the email-alert reader : Claude _(status: Open, waiting on 1.1 and 1.2)_
  Reads the alerts inbox from 1.1 during the daily run and turns each alert into a listing, with one parser per site built from real received emails. Brings in Hemmings, Cars & Bids, CLASSIC.COM, Car & Classic and the other blocked sites for both trucks.
- [ ] **2.3** Gumtree UK sees only the newest ~26 Hilux ads each day : Claude _(status: Open, after 2.2)_
  Gumtree's search filters sit under a path its robots.txt disallows, so the collector reads only the newest page. A slow day is fine; a busy week can push a Hilux past it. Fix: move Gumtree UK to the saved-search email route once 2.2 exists, or confirm daily coverage is enough.
- [ ] **2.4** Confirm eBay's UK and Germany car categories : Claude
  The eBay fix used category ids that are proven for the US and Australia. The UK and Germany ones are the right nodes but held no Datsun on the day, so they are unproven. A check once a Datsun is listed in either would confirm them.
- [ ] **2.5** Re-probe Chobrod (Thailand) : Claude
  Chobrod has a dedicated 620 page with live stock but timed out from GitHub's servers in September. Worth one more try; if it still times out, park it for the email route.

## 3. Tech debt

- [ ] **3.1** Run the tests on every pull request : Claude
  Tests only run inside the daily job. Nothing checks a pull request before merge, so broken code can merge and first fail at 00:17 the next morning. A small workflow that runs the tests and builds the site on each pull request closes that gap. Highest-value item in this section.
- [ ] **3.2** A failing test should not cost a day of data : Claude _(status: Open, after 3.1)_
  Today a single failing test stops the whole daily run, so no listings are saved that day. Once 3.1 catches problems before merge, the daily job can keep scraping and flag the failure instead.
- [ ] **3.3** Retry once on a network timeout : Claude
  No collector retries. One slow response marks a source failed for the day and feeds the failure counters. A single retry with a short wait removes most false alarms.
- [ ] **3.4** Make the shared scraper helpers official : Claude
  16 of the 24 Hilux collectors borrow private pieces from the Datsun collectors, and the same browser header is copied 24 times. Renaming something on the Datsun side could quietly break the Hilux. Moving these into the shared module removes that trap.
- [ ] **3.5** One config file per truck for thresholds and known blocks : Claude
  The quiet-source thresholds, the 7-day escalation and the known-blocked list are hard-coded in several files and shared by both trucks. One small config per truck makes them easy to find and tune.
- [ ] **3.6** Only commit Hilux data from a finished Hilux run : Claude
  If the Hilux step crashes halfway, the files it already wrote still get committed. Writing to a temporary place and moving the files only on success keeps half-finished data out of the repo.
- [ ] **3.7** Lock dependency versions : Claude
  Python packages are pinned loosely and Node has no pinned version, so a new release upstream can change behaviour overnight. A lock file and a pinned Node version make runs repeatable.
- [ ] **3.8** Bring the README, ops notes and PRD up to date : Claude
  Several docs describe the old setup: the 04:17 cron (now 00:17), six collectors (now 20 for the 620 and 24 for the Hilux), SQLite and exchangerate.host (now JSON files and Frankfurter), Kaidee as normally green, no Hilux data files in the table, and a link to a probe script that no longer exists.
- [ ] **3.9** Remove dead pieces : Claude
  The old Buyee probe script, the eBay check workflow that only fires on a stale branch, and the one-off legacy import script. None run; they mislead whoever reads the repo next.
- [ ] **3.10** Test the page-fetching logic, not just the parsers : Claude
  Tests check that each collector reads a saved page correctly, but nothing tests the paging and page limits around it. A few tests with fake responses would cover that, and switching to pytest means a new test can't be forgotten.
- [ ] **3.11** Check the 30-minute run limit still fits : Claude
  One job now scrapes 44 sources for two trucks inside a 30-minute limit. Measure the first week of Hilux runs and raise the limit, or split the trucks into two jobs, before a slow day tips it over.
- [ ] **3.12** Stop the deploy step publishing a branch by accident : Claude
  If the daily job is ever run by hand on a branch, the deploy step publishes that branch to the live site. Locking deploys to main prevents it.

## 4. New features worth doing

- [ ] **4.1** Instant alert when a strong match appears : Both _(status: Decide)_
  Today a great truck waits in the morning digest with everything else. This sends a separate short email the moment the daily run finds a strong match (a 620 King Cab, or an RN30-like Hilux) inside your criteria from 1.6, with price, landed cost and link. The best trucks go fast; this is the biggest buying win.
- [ ] **4.2** Landed cost to Jersey on every listing : Both _(status: Decide)_
  A US or Japanese truck's price is not what you'd pay. This adds an estimate on each listing and in the digest: shipping by region, import duty and GST for Jersey, and a note on drive side. Figures would be clearly labelled as estimates with their sources.
- [ ] **4.3** Fair-price check from sold prices : Both _(status: Decide)_
  Bring a Trailer results and Yahoo closed auctions give real sold prices. This shows, on each listing, how its asking price compares with recent sales of the same truck in similar condition. Useful for negotiating. Honest limit: sold data for these trucks is thin, so it would show ranges and sample sizes, not a single number.
- [ ] **4.4** Keep a copy of each listing's photos and text : Both _(status: Decide)_
  Adverts vanish when a truck sells or is withdrawn, along with the photos you might want to compare against later. This saves the description and a few photos when a listing is first seen, for the listings you'd care about. Trade-off: repo size grows; limited to strong matches it stays small.
- [ ] **4.5** Market trends page : Both _(status: Decide)_
  How many trucks are for sale, where, and at what median price, week by week, for each truck. Needs a small daily snapshot saved going forward (today only the latest run is kept), so the chart fills in over time.
- [ ] **4.6** Buyer's inspection checklist per truck : Both _(status: Decide)_
  A page per truck drawn from the specs research: where they rust, how to confirm the chassis code and engine are original, which parts are hard to find, and questions to ask a seller. Open it on your phone at a viewing.
- [ ] **4.7** Spot the same truck listed on two sites : Both _(status: Decide)_
  Relist detection only works within one site today. Matching across sites (same photos, price and location) would stop one truck showing up as two and reveal dealers reposting private sales at a markup. Harder to get right; was a non-goal for v1.
