---
name: evaluate-feature-idea
description: Use when the user is explicitly deciding whether to build a specific feature — asking "should we build X", "is this worth building", "is this a good idea", or weighing a feature idea against what else matters. This routes the decision to Studious's should-we-build gate. Do NOT use for general feature brainstorming, for shaping a design once the decision to build is already made, or for prioritizing existing issues (that's /bet).
---

# Should we build this?

This is the natural-language entry to Studious's first quality gate. The user is questioning whether a feature is worth building — route that to the gate instead of answering from the hip.

Invoke the `/bet` command, passing the feature idea the user described as its argument. Do not reimplement the gate's logic here — the command owns it. It scores the idea against PRODUCT.md (persona fit, priority vs. known problems, scope conflicts, the simplest viable version) and returns **BUILD / BUILD SMALLER / DEFER / DON'T BUILD**.

Only the user decides. Surface the gate's recommendation and its reasoning; do not start building.
