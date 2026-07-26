# README drift report: jig

## Summary

README is **significantly out of date**. 1 finding: stale version claim (× 2 instances) that actively misleads users about the current release. The version discrepancy occurred when v1.6.0 shipped post-PR #85, which had updated the README to v1.5.0; the README was never bumped after the automatic release.

---

## Stale claims

- **Critical** · line 20 + line 129 · version tracking · README states "current release is [v1.5.0](https://github.com/jacquardlabs/jig/releases/tag/v1.5.0)" but plugin.json and CHANGELOG confirm v1.6.0 is current (commit fdf63f5, released 2026-07-18). Evidence: `.claude-plugin/plugin.json` version field = "1.6.0"; CHANGELOG.md top entry = "v1.6.0 (2026-07-18)"; git log shows v1.6.0 released after PR #85 updated README to v1.5.0. · **Confirmed** · Update both v1.5.0 references to v1.6.0, including the GitHub release tag links.

---

## Missing

None detected.

---

## Broken

None detected.

---

## Voice drift

None detected.

---

## Structure gaps

None detected.

---

## Proposed diff

```diff
 > [!NOTE]
 > **Shipped.** All five skills (`/design`, `/plan`, `/build`, `/finish`,
 > `/coach`) are implemented and registered in the jacquardlabs marketplace.
 > Milestones M0–M6 are complete; current release is
-> [v1.5.0](https://github.com/jacquardlabs/jig/releases/tag/v1.5.0). See the
+> [v1.6.0](https://github.com/jacquardlabs/jig/releases/tag/v1.6.0). See the

 M0–M6 are complete. M0 (pre-work gate) ran a paper dogfood of `/design` and
 `/plan` against a real dependency ([viva](https://github.com/jacquardlabs/viva)
 issue #109) before any plugin code was written, surfacing blocking gaps —
 full detail in `docs/jig/dogfood/FRICTION-REPORT.md` on branch
 [`docs/m0-paper-dogfood`](https://github.com/jacquardlabs/jig/tree/docs/m0-paper-dogfood).
 M1 shipped the plugin scaffold; M2–M6 shipped `/design`, `/plan`, `/build`,
-`/finish`, and `/coach` in turn. Current release is
-[v1.5.0](https://github.com/jacquardlabs/jig/releases/tag/v1.5.0) — see the
+`/finish`, and `/coach` in turn. Current release is
+[v1.6.0](https://github.com/jacquardlabs/jig/releases/tag/v1.6.0) — see the
```

---

## Residual

Verified: all five user-invoked skills (design, plan, build, finish, coach) ship with real SKILL.md; m1–m6 milestones all complete; 8 deterministic scripts (`design-lint`, `plan-lint`, `verify`, `status-flip`, `evidence-capture`, `evidence-freshness`, `build-report`, `worktree-setup`) ship in scripts/; LICENSE, CHANGELOG.md, PRODUCT.md, DESIGN.md, CLAUDE.md all exist at stated paths; portfolio-relationship table (studious/viva/cctx links) unchanged; install instructions remain current; usage pipeline unchanged; design principles (11 items, §2) unchanged; all cross-references (README → CHANGELOG, DESIGN.md, PRODUCT.md, GitHub issues) resolve. Compared against: baseline (no prior readme-reviews exist); most recent commits show PR #85 bumped version to v1.5.0, then v1.6.0 released automatically without README follow-up (commit fdf63f5 / chore(release): v1.6.0 [skip ci]).
