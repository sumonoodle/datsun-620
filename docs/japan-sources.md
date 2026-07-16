# Japan sources: experiment outcomes (M5, PRD 4.4)

Date of record: 2026-07-16. All evidence from live runs on GitHub-hosted
runners (the machines the daily pipeline uses), Actions run 29512474301 and
predecessors.

## What was tried

| Attempt | Result |
|---|---|
| Goo-net Exchange (English export site), plain HTTP with browser headers | HTTP 404 wall on the Datsun index. Same behaviour the v1.0 build logged daily for six weeks. |
| Buyee search (Japanese query), plain HTTP with browser headers | HTTP 403. |
| Buyee search via Playwright (real Chromium, JS executed, English locale) | HTTP 403, page title "403 Forbidden", zero item links. |

## Conclusion

The Playwright result is the decisive one: a full browser gets the same 403,
so Buyee blocks by IP reputation (GitHub's datacenter ranges), not by
detecting non-browser traffic. Goo-net behaves the same way with a 404 mask.
No scraping technique running from GitHub Actions will get through; the block
is on where the request comes from, not what it looks like.

## Current state (by design, PRD 4.4)

- Both collectors are built, tested against fixtures, and run daily.
- Each blocked day is logged and shown in the digest's source health section
  with a running streak count.
- At 7 consecutive blocked days the digest escalates: "decision needed".
- The daily run always succeeds regardless; v1 does not depend on Japan.
- The King Cab filter already handles Japanese listings (katakana term,
  Japanese parts exclusion) and titles get translated automatically, so if
  either source ever unblocks, listings flow with no code changes.

## Options if Japan coverage becomes a priority

1. **Residential/rotating proxy** for the two Japan collectors only.
   Breaks the zero-cost constraint (usable proxies are paid) and adds a
   credential to manage. Feasible, works with the existing code (httpx
   supports proxies), roughly $5-15/month for the volume needed.
2. **A different Japan-facing source** that tolerates datacenter IPs
   (e.g. ZenMarket search, or car-export aggregators like BE FORWARD /
   tradecarview). Each needs the same experiment run before trusting it.
3. **Self-hosted runner** (a Raspberry Pi or home machine registered to the
   repo) whose residential IP would not be blocked. Zero recurring cost but
   adds an always-on device to maintain, and repo-runner security needs care
   on a public repo (runners should only run workflow code you wrote).
4. **Drop Japan sources for v1** and revisit if a King Cab actually needs
   finding from Japan. The 620 King Cab market is mostly US anyway.

Recommendation: option 4 now (accept documented block), revisit with option 2
if the digest's 7-day escalation keeps firing and Japan coverage feels
genuinely missed. Options 1 and 3 stay on the shelf unless the owner wants
them.
