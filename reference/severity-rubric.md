# Severity rubric — canonical tiers and the one row `/review` still maps

Canonical three-tier severity ladder for `/review`. It dispatches gauntlet's judges, which
emit these tiers directly (its findings contract, `docs/findings-contract.md` §5), so
`/review` maps one vocabulary only: the `web-design-guidelines` skill's, on its inline
lane-8 path, which returns no findings document. The periodic outcome review
(`agents/review-outcomes.md`) already emits directly in this vocabulary.

## The three tiers

- **Critical** — blocks merge. Fix now.
- **Important** — should fix. Fix this cycle.
- **Track** — not urgent; log it and revisit later.

Never introduce a fourth tier.

## The one label → tier row

| Lane | → Critical (blocks merge) | → Important (should fix) | → Track |
|------|---------------------------|--------------------------|-----------------|
| web-design-guidelines (a11y) | blocking a11y failures (no keyboard access, contrast failures on core flows) | other a11y gaps | polish |

## Objective anchors — what a Critical must cite

A tier is not a self-assessment: a Critical must cite the objective anchor its lane owns — a fact
a reader can check without re-running the reviewer's judgment. For every gauntlet judge the
anchor is named in gauntlet's charter (`charter.md` under its `reference/` directory, "Anchors —
what a critical must cite"), and gauntlet's `scripts/report.py` records an anchorless critical
as `important` at ingest and names the demotion in the compiled report. **A finding labelled
Critical that cites no anchor is recorded Important instead** — the gate door applies this before
the ledger write, and the compiled report names the anchor that was missing. The one anchor
studious states for `/review` itself is the inline lane's:

| Lane | A Critical must cite |
|------|----------------------|
| web-design-guidelines (a11y) | the named guideline that fails (keyboard access, contrast ratio) and the core flow it fails on |

Disposition history is the second filter: a finding already recorded `rejected-as-noise` on this
episode (`studious episode-finding`) is settled, and re-raising it at a higher tier does not
make it a Critical. Re-opening a settled finding needs a new anchor, not a new adjective.
