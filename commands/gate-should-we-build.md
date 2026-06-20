---
description: Evaluate whether a feature idea is worth building before any engineering begins
allowed-tools: Read, Glob, Grep
---

# Should we build this?

Read PRODUCT.md at the project root before doing anything else. You need the full product context — personas, principles, known problems, what we're not building.

The feature idea: $ARGUMENTS

Now evaluate honestly:

1. **Who is this for?** Which persona from PRODUCT.md does this serve? What specific problem of theirs does it solve? If you can't name the persona and the problem in one sentence, that's a red flag.

2. **Priority check.** Look at "current known problems" in PRODUCT.md. How does this feature rank against those? Are we solving a real pain point or adding something nice-to-have while real problems remain unfixed? Be direct — if something on the known problems list matters more, say so.

3. **Scope check.** Does this conflict with anything in "what we're NOT building"? If yes, stop here and explain the conflict.

4. **Simplest version.** Describe the smallest version of this that still solves the core problem. Not a phased rollout — the actual essential kernel. What can we cut and still deliver the value?

5. **Expected outcome.** If we ship this, what specifically changes for the user? Not "better experience" — something concrete like "they can do X in Y seconds instead of Z" or "they no longer have to manually do X."

## Your job

Do not be a yes-man. If this is a bad idea, say so plainly and suggest what we should build instead based on the known problems list. If it's a good idea but scoped too big, say that and describe the smaller version.

End with a clear recommendation: **BUILD**, **BUILD SMALLER** (with the scoped-down version), **DEFER** (with what to prioritize instead), or **DON'T BUILD** (with why).
