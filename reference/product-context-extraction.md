---
description: Extract product context from the existing codebase and populate PRODUCT.md
allowed-tools: Read, Glob, Grep, Bash, Task, Write, WebFetch
---

# Extract product context from codebase

Analyze the existing codebase to discover what this product actually is, who it serves, and how it works — based on evidence in the code, not assumptions. Do not invent or idealize — document what IS.

Read PRODUCT.md first. If it already has content, you're updating it. If it's the blank template, you're populating it from scratch.

## Step 1 — Read existing documentation

Before touching the code, check for context that already exists:
- README.md, README, or any root-level docs
- CONTRIBUTING.md
- Any docs/ directory content
- package.json description, keywords, and homepage fields
- Any marketing copy, landing page text, or about page content in the codebase
- App store descriptions (if mobile)
- Meta tags, og:description, page titles in the HTML

Extract a first-draft understanding of what this product claims to be.

## Step 2 — Detect issue tracker

Before mapping features, check whether this project has a live issue tracker:

- Run `gh issue list --limit 1 2>/dev/null` — exit 0 means GitHub Issues is active
- Check for a GitHub remote: `git remote get-url origin 2>/dev/null | grep github.com`

**If a tracker is active:** skip Step 3 (feature surface mapping). In Step 9, write a `## Feature tracker` section with a link to the tracker (`gh repo view --json url --jq .url 2>/dev/null`) instead of a Feature map table. The tracker is the source of truth for individual features.

**If no tracker:** continue with the full feature map in Step 3.

## Step 3 — Map the feature surface (skip if tracker active)

Discover what users can actually do by examining:

**Routes and navigation:**
- Scan all route definitions (React Router, Next.js pages/app directory, Express routes, Django/Flask routes, API routes, etc.)
- Identify which routes are public vs authenticated
- Identify which routes are user-facing vs admin/internal
- Map the navigation structure (sidebar items, nav links, menu entries)

**User-facing features:**
- For each major route or page, summarize what the user can do there
- Check for feature flags or gated features (partially shipped or A/B tested)
- Check for disabled or hidden features (commented out routes, feature flag configs)
- Note any onboarding flows, wizards, or setup screens

**API surface (if applicable):**
- Scan API route handlers — what resources can be created, read, updated, deleted?
- Check for any public API documentation (Swagger/OpenAPI specs, API docs routes)
- Identify webhook handlers (indicates integrations)

Write the feature map as: feature name > what users can do > current state (shipped/beta/hidden/broken).

## Step 4 — Identify the users

Look for evidence of who uses this product:

**Authentication and roles:**
- What auth method is used? (email/password, OAuth, SSO, magic link, none)
- Are there user roles or permission levels? What are they?
- Is there an admin panel separate from the user experience?
- Is there multi-tenancy (organizations, teams, workspaces)?

**User-facing language:**
- Scan UI copy, labels, button text, onboarding text, error messages, email templates
- What terminology does the product use? (customers, patients, members, users, teams?)
- What domain language appears? (orders, appointments, lessons, recipes, projects?)
- This reveals the target audience more reliably than any README

**Data models:**
- What is the central entity? (the thing most other tables/collections reference)
- What does a user profile contain? (fields reveal assumptions about the user)
- Check seed data or fixtures — sample data often models the intended user

Draft the persona based on what the code reveals, not what you think it should be.

## Step 5 — Discover the business model

Look for revenue and pricing signals:

- Stripe, Paddle, LemonSqueezy, or other payment integrations
- Pricing page content, plan definitions, subscription tiers
- Feature gating by plan level (free vs paid checks in the code)
- Trial logic, usage limits, or quota enforcement
- Any billing-related database models (subscriptions, invoices, plans)
- Affiliate or referral code logic
- Ad placement or sponsorship slots

If none found, note "No monetization logic found in codebase."

## Step 6 — Trace the critical user journeys

Identify the 2-3 most important flows by looking at:

**First-time experience:**
- What happens when a new user first arrives? (landing page > signup > onboarding > ?)
- What's the first thing they can do that delivers value?
- How many steps from "I just signed up" to "I got value"?

**Core loop:**
- What's the action users repeat most? (creating, searching, consuming, tracking?)
- Trace the full flow: trigger > action > result > next step
- Check analytics events if present — event names reveal what the team considers important

**Return triggers:**
- Are there notifications, emails, or reminders that bring users back?
- Is there any scheduled/recurring content (daily digest, weekly report)?
- Check cron jobs, scheduled tasks, or notification templates

Document each journey as: trigger > steps > outcome.

## Step 7 — Find what's NOT being built

Look for explicit boundaries:

- Check for rejected feature requests in GitHub issues (if accessible)
- Look for TODO comments that say "out of scope" or "not planned"
- Check for integrations that were started but abandoned
- Look for commented-out features or deprecated routes
- Check .env.example for services that are configured but unused

Also infer boundaries from what's absent:
- No social features in a productivity tool = likely intentional
- No mobile-specific code in a web app = web-only scope
- No i18n/l10n = single-language target
- No multi-tenancy = individual users only

Note these as "Likely out of scope (inferred)" vs "Explicitly out of scope (documented)."

## Step 8 — Identify known problems

Scan for evidence of things that are broken or painful:

- TODO, FIXME, HACK, WORKAROUND, XXX comments — group by area
- GitHub issues labeled as bugs (if accessible)
- Error tracking configuration (Sentry, LogRocket, etc.) — what errors are being monitored?
- Retry logic or defensive code that suggests known failure points
- Commented-out features or workarounds that suggest regressions
- Test files with skipped or pending tests (often mark known failures)

Prioritize by likely user impact, not code severity.

## Step 9 — Write PRODUCT.md

Populate each section with what you found. For each section:

1. **Lead with evidence** — "Based on the route structure and UI copy, this product is..." not "This product is..."
2. **Flag uncertainty** — if you're inferring rather than reading explicit documentation, say so
3. **Include the gaps** — if a section has no evidence (e.g., no business model found), say that explicitly rather than skipping it
4. **Quote the code** — when user-facing copy reveals the product's voice or audience, include the actual text as evidence

Sections that require human judgment (product principles, anti-patterns for what not to build) should be left with a prompt:

```
<!-- FILL IN: Based on the product as it exists, what principles
     seem to be driving decisions? What would you add? -->
```

End with a confidence summary:
- **High confidence**: sections populated from explicit documentation or clear code patterns
- **Medium confidence**: sections inferred from code structure and naming
- **Low confidence / needs your input**: sections that require product intent only the developer knows
