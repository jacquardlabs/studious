---
name: review-product-health
description: Periodic product review — evaluate product coherence, scope drift, and roadmap alignment
tools: Read, Glob, Grep, Bash, Write
model: inherit
---

# Product health review

A periodic check on the product itself, not the code. Run this monthly or when you feel the product is drifting.

Read PRODUCT.md first. This review evaluates whether PRODUCT.md is still accurate and whether the product is evolving coherently.

## Detect issue tracker

Before reviewing the feature map, determine whether this project has a live issue tracker:

- **GitHub Issues**: run `gh issue list --limit 1 2>/dev/null` — exit 0 means GitHub Issues is active
- **PRODUCT.md**: check if PRODUCT.md has a `## Feature tracker` section with an explicit tracker link
- **Fallback**: if neither signal is present, assume no tracker

**If a tracker is active:** PRODUCT.md is not the source of truth for individual features — the tracker owns that. Adjust Part 1.3 accordingly (see below).

## Part 1 — Is PRODUCT.md still true?

1. **Persona check.** Read the personas in PRODUCT.md, then scan the recent feature history (git log, recent commits). Are we still building for the stated personas, or have we drifted toward building for ourselves / edge cases / hypothetical users?

2. **Principles check.** Read the product principles. For each one, find one recent feature decision that honored it and one that bent it. Are the principles still the right principles, or has the product evolved past them?

3. **Feature inventory check.**
   - *Tracker active:* The tracker owns individual features — PRODUCT.md should not contain a feature table. If it has a stale Feature map section, flag it as a sync hazard and recommend removing it. Instead, scan the tracker: run `gh issue list --state open 2>/dev/null` and check recent closed issues. Are there shipped features that conflict with PRODUCT.md's principles or "not building" list? Are there open issues requesting things that are explicitly out of scope?
   - *No tracker:* Compare any Feature map in PRODUCT.md against what actually exists in the codebase. Are there shipped features missing from the map? Are there features listed that were removed or never completed?

4. **"Not building" check.** Has anything from the "what we're NOT building" list crept in? Check recent commits and, if a tracker is active, scan open issues for out-of-scope requests that are being entertained.

5. **Known problems freshness.** Are the known problems still the real problems? Have any been fixed but not removed? If a tracker is active, cross-reference with open bug issues — problems tracked there but absent from PRODUCT.md should be evaluated for inclusion.

## Part 2 — Product coherence

1. **Does this feel like one product?** Mentally walk through the product as a new user. Open it cold. Navigate through the core features. Does it feel like a unified product or a collection of features that happen to live together?

2. **Feature interaction.** Do recently added features interact well with existing ones? Or are they isolated silos? Are there natural connections between features that we haven't built yet?

3. **Complexity audit.** For each feature, ask: if we removed this, would users notice? Would they care? Flag any features that add complexity without proportional value.

4. **Onboarding path.** Can a brand new user get to the core value proposition within 60 seconds? Walk through the first-time experience. Flag every point of friction, confusion, or unnecessary decision.

## Part 3 — Update PRODUCT.md

PRODUCT.md owns the strategic layer — personas, principles, product direction, critical journeys, and explicit scope boundaries. It does not track individual features when a tracker is active.

Propose specific updates:

- Personas that need updating (changed needs, new context)
- Principles that need revision or addition
- Items to add or remove from "what we're NOT building"
- Known problems to add, remove, or reprioritize
- **If PRODUCT.md has a stale Feature map and a tracker is active:** propose removing the Feature map section and replacing it with a `## Feature tracker` link

If no tracker is active, also propose:
- Features to add or remove from the feature map

Present the changes as a diff against the current PRODUCT.md. Don't apply them — present them for review.

If previous product reviews exist in `docs/jaqal/product-reviews/`, compare against the most recent one.

Save the report to `docs/jaqal/product-reviews/YYYY-MM-DD-product-review.md`.
