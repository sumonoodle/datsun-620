# Claude Code kickoff prompt: Datsun 620 project

You are kicking off a new project. The full PRD is in `datsun_620_prd_v1.1.md` at the repo root (or paste it in if not yet committed). Read it end to end before doing anything else.

## How I work

- I am not a developer. Use plain language for technical decisions.
- Plan before building. Explain what you're building and why before writing code. Present technology choices with pros, cons, and a recommendation when there's a real tradeoff.
- Lead with your recommendation, then reasoning, then alternatives.
- Mark confidence as high, moderate, low, or unknown when it matters. Say "I don't know" rather than guessing.
- If you hit a blocker or an approach isn't working, say so immediately. Do not silently work around it.
- Verify facts that can be verified. For library versions, API changes, current best practice, search rather than rely on training.
- Direct, dry, economical tone. No em dashes. No emojis. No performative hedging.

## How to run this build

Use a multi-agent approach. The PRD section 6 defines the agent split: Architect, Specs collector, Listings scraper, Frontend, Notifier, QA, and me as Product.

Run them in parallel where the work allows. Architect always goes first because everything else depends on the shared schema and repo scaffolding.

## What I want from you, in order

### Step 1: Read and react

Read the PRD. Tell me:
- Anything that's ambiguous or contradictory.
- Anything you'd recommend changing before we start, with reasoning.
- Any technology choices in the PRD you'd push back on, with alternatives.

Do not write any code yet.

### Step 2: Detailed plan for M1 (Scaffolding)

Once I've responded to Step 1, propose a detailed plan for Milestone 1 only. The plan should include:
- The exact repo structure you'll create.
- The shared schema for both specs and listings (the contract every other agent will code against).
- The GitHub Actions workflow files you'll write, with cron schedule and trigger logic.
- A placeholder Astro site that deploys to GitHub Pages successfully, proving the pipeline works end to end.
- How you'll verify M1 is done before moving on.
- What you need from me to start (secrets, account access, decisions still open).

Wait for my sign-off before executing.

### Step 3: Execute M1

Once I sign off, build M1. When done:
- Summarise what you built.
- Show me the deploy URL.
- Tell me what's next and what decisions or inputs you need.

### Step 4: Plan and execute M2 through M6

For each subsequent milestone, repeat the same pattern: plan, sign-off, execute, summarise. Run agents in parallel within a milestone where the dependencies allow.

## Working rules during the build

- When you have a routine decision to make (variable naming, file organisation, internal library choice), make it and note it in the summary. Don't ask.
- When there's a meaningful tradeoff (user-facing behaviour, architecture, cost, scope creep), flag it and let me choose.
- When you change something at my request, just change it. Don't re-explain the context unless the change introduces a tradeoff I should know about.
- If I share a view or estimate, treat it as input. Form your own from the evidence, then compare. Say where you agree, where you diverge, and why.
- Commit often with clear messages. I want to be able to see what each agent did.

## What success looks like for v1

- Site live on GitHub Pages with Specs and Listings views.
- Daily GitHub Actions cron running, scraping all six listing sources, updating the SQLite history, rebuilding the site, sending the email digest.
- Specs refresh runs on manual trigger across all six markets.
- Strict King Cab filtering with zero obvious false positives in a sample of 20 listings.
- Email digest arrives in my inbox each morning before I start work in Jersey.
- Total cost: zero.

## First action

Begin with Step 1. Read the PRD, then respond with your reactions and any clarifying questions. Do not start coding.
