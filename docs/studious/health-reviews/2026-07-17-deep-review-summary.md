# Deep review — master summary — 2026-07-17

Full sweep, first cycle for this project. All six periodic reviews plus the
codebase-health-lane idiom audit ran against `main`
(`/Users/bryan/Projects/jig`, worktree `deep-review`). Every metric below is
baseline — no prior reports existed in any `docs/studious/*-reviews/`
directory before this run.

| Review | Report |
|---|---|
| Codebase health | `docs/studious/health-reviews/2026-07-17-health-review.md` |
| Code idioms (codebase-health lane) | `docs/studious/health-reviews/2026-07-17-code-idioms.md` |
| Interface health | `docs/studious/interface-reviews/2026-07-17-interface-review.md` |
| Architecture | `docs/studious/architecture-reviews/2026-07-17-architecture-review.md` |
| Product health | `docs/studious/product-reviews/2026-07-17-product-review.md` |
| Security health | `docs/studious/security-reviews/2026-07-17-security-review.md` |
| README drift | `docs/studious/readme-reviews/2026-07-17-readme-review.md` |

**Idiom feedback recurrence check:** insufficient review history (need 2+
prior cycles) — skipped. This is cycle 1.

## Overall read

jig is small, young, and unusually disciplined for its size — clean
architecture, a comprehensive test suite, no secrets exposure, a coherent
product story. The one theme that recurs across nearly every review, from
different angles, is that **the mechanisms designed to keep this discipline
from decaying are not actually enforced anywhere**: no CI runs the tests or
linter that would catch drift, and the two concrete drift instances found
this cycle (both in the shared vocabulary the whole system leans on) are
exactly the kind of thing those un-run tests exist to catch.

## Cross-review findings (systemic, elevated priority)

1. **CI enforcement gap — the load-bearing finding of this cycle.**
   Codebase health rates it **Critical**; architecture rates the same fact
   **Important**. Independently reached from two different angles (test/dep
   health vs. structural evolution-readiness): `.github/workflows/release.yml`
   is the only workflow in the repo and it only runs `semantic-release` — no
   job runs `unittest discover` or `ruff check`, and `main` has no branch
   protection. Architecture's framing sharpens why this matters more than an
   ordinary CI gap: the project's own ratified principle is "nothing signs
   off on itself; scripts re-verify everything," and CI is the one place that
   principle has no re-verification step of its own.

2. **The CI gap is why live vocabulary drift went undetected.** Architecture
   flags that the codebase's "cross-surface pinning tests" — the tests that
   exist specifically to catch prose/code/doc disagreement — never run in
   CI. Interface health then independently found two live instances of
   exactly that disagreement: `task-execution-discipline/SKILL.md:88` lists
   `FIX` as a task-status token against `build/SKILL.md` and DESIGN.md's own
   vocabulary table, and `plan/SKILL.md:21-24` still describes `/design`'s
   output using section names DESIGN.md itself says were superseded. These
   read as one causal chain, not three unrelated findings: the safety net
   exists in the test suite, isn't hooked to CI, and drift walked through the
   gap.

3. **"Fragile vocabulary derivation" is a named, three-way-confirmed debt
   class.** PRODUCT.md's own known-problems section already names "fragile
   vocabulary derivation" as tracked debt. Architecture explains the
   structural mechanism (Track 3 & 4: each rule is encoded up to 3x — SKILL.md
   prose, script code, and a test reference implementation — and DESIGN.md/
   SKILL.md prose is itself a parsed, code-coupled runtime input). Interface
   health then supplies the concrete instances (finding 1 above). Three
   reviews converging on the same debt class from product framing, structural
   cause, and live symptom is a stronger signal than any one finding alone.

4. **Issue #36 — tracker says open, code says fixed.** Codebase health
   caught this directly (`pyproject.toml`'s `select` → `extend-select` fix is
   already in commit `fc547f1`, but the GitHub issue and PRODUCT.md's
   known-problems list both still describe it as open). Architecture's own
   residual line independently flagged the identical fact as an
   out-of-scope note for the next product review. Cheapest fix in this
   entire report: close the issue.

5. **README version staleness, caught twice.** README review rates this
   **Critical** (v1.5.0 referenced twice; actual current release is v1.6.0).
   Product health independently caught the same fact (T2), routing it back
   to the README review rather than duplicating the fix. Both reviews agree
   on cause: PR #85 bumped the README to v1.5.0, then v1.6.0 shipped
   automatically via `semantic-release` with no README follow-up — the same
   category of "nothing re-verifies the docs after an automated step" gap as
   finding 1, one layer up the stack.

6. **`skills/build/SKILL.md` is the file to watch.** Codebase health and
   interface health both flag it, independently, as the largest and
   most-churned skill file (600 lines, 8 touches in 90 days) — not a problem
   yet, but the one place responsibility sprawl would show up first.

## Prioritized action plan

### Critical (this week)

1. **Add a required CI job running tests and lint.** (codebase health,
   architecture) `uv run --no-project python3 -m unittest discover -s tests -v`
   plus `ruff check .`, triggered on `pull_request`, required before merge.
   Enable branch protection on `main` requiring it. This is prerequisite to
   trusting every other finding's mitigation in this report — do it first.
2. **Fix README version staleness** (readme, product T2): update both
   v1.5.0 references (lines 20, 129) to v1.6.0, including the release-tag
   links. Diff is already drafted in the README review report.

### Important (this month)

**CI / supply chain**
- Pin `python-semantic-release`'s install in `.github/workflows/release.yml:27`
  to an exact version + hash — it runs inside the `contents:write` job
  holding `RELEASE_TOKEN`, a PAT with cross-repo dispatch reach. (security)
- While that CI job is being touched anyway (Critical #1 above), fold this
  pin in at the same time rather than as a second PR.

**Vocabulary / prose drift**
- Fix `skills/task-execution-discipline/SKILL.md:88` — drop `FIX` from the
  task-status enum; it should read `PASS`/`REPLAN`/`ESCALATE`, matching
  `build/SKILL.md` and DESIGN.md. This is the shared text every fresh
  `/build` executor reads before writing a status — maximally reachable.
  (interface)
- Update `plan/SKILL.md:21-24`'s stale design-doc section-name example (or
  drop it — `/plan` doesn't functionally depend on the wrong names).
  (interface)
- Sharpen PRODUCT.md's "no named agent personas" principle to name the
  distinction `/build` already draws (functional, ephemeral session roles
  vs. resident BMAD-style personas) — diff drafted below. (product)

**Tracker / doc hygiene**
- Close issue #36 (already fixed in code) and refresh PRODUCT.md's
  known-problems list. (codebase health, architecture)
- `docs/design/*.md` accumulation is worse than when issue #71 was filed (4
  → 7 tracked files despite a `.gitignore` rule that should catch them).
  Prioritize #71's mechanical-safeguard ask before the next milestone adds
  more. (codebase health)

**Test coverage**
- Add a focused `test_gitutil.py` — `_gitutil.py` is imported by 6 of 7 CLI
  scripts and has no direct unit test of its own. (codebase health)
- Unify or fixture-bound the two divergent task-heading parsers
  (`scripts/_planparse.py:31` vs `tests/_load_bearing.py:24`) — a real plan
  with a non-numeric label or missing em-dash would silently partition
  differently, and today's cross-surface "agreement" test can't catch it.
  (architecture)

### Track (next review cycle)

- PRODUCT.md's unresolved `<!-- FILL IN -->` placeholder on the
  Product-principles selection (codebase health) — resolve at next
  `/deep-review product`.
- Four test files creeping toward the 500-line god-file bar
  (`test_verify.py` 966, `test_design_lint.py` 740, `test_build_skill.py`
  696, `test_plan_lint.py` 636) — watch growth rate, no action yet.
  (codebase health)
- `skills/build/SKILL.md` size/churn (codebase health, interface) — watch
  for a 7th responsibility; split into a companion reference file if it
  crosses ~750 lines.
- Document the triple-encoding tradeoff and context-docs-as-code-coupled-
  runtime-inputs pattern in CLAUDE.md (architecture Track 3 & 4) — diff
  drafted below.
- Document the risk-tag vs. severity-tier vocabulary divergence in CLAUDE.md
  — DESIGN.md already names this as needed; still missing. (interface)
- Document the exit-code / `error:`-prefix CLI convention in DESIGN.md's
  Formatting section — real and consistent across all 8 scripts, just
  unwritten. (interface)
- SHA-pin `actions/checkout@v4` and `actions/setup-python@v5` in
  `release.yml` instead of mutable major-version tags. (security)
- `shell=True` on project-/plan-supplied commands — evaluated, documented,
  accepted trust boundary (issue #48); no action, logged so the record
  shows it was assessed. (security)
- Model-routing/telemetry issue cluster (#22, #33, #40–#43) has zero
  visibility from PRODUCT.md — consider a "Directions under evaluation"
  pointer once #43's audit lands. (product T1)
- `task-execution-discipline` (6th skill dir) is unmentioned in PRODUCT.md's
  "five skills" framing — confirm the omission is intentional. (product T3)
- Watch issue #83 (parallel executors) against the "sequential for-loop is
  the default" invariant as it advances. (product T4)
- Idiom audit's four Low-severity polish items (`scripts/design-lint` over
  the 500-line bar; `verify.run_items`'s 5 positional params; bare `dict`
  returns in `verify`/`evidence-freshness`; the repeated `sys.path.insert`
  boilerplate, which is working as intended) — no urgency, revisit if any
  grows.

## Context doc updates (proposed — not applied)

### PRODUCT.md (from product health review)

```diff
@@ ## Product principles @@
 - **Anti-cleverness tripwire** — sequential for-loop is the default; no
-  named agent personas, no sprint ceremony, no resident coordinating roles.
+  named agent personas, no sprint ceremony, no resident coordinating roles.
+  (Functional, ephemeral session roles — the Foreman/Executor/Inspector a
+  single `/build` loop dispatches one at a time — are not "personas": they
+  are not resident, not anthropomorphized, and hold no state across tasks.
+  The prohibition targets BMAD-style named resident agents, not role labels
+  on a for-loop's stages.)
```

Optional, left out of the diff (tracker already owns this state and
PRODUCT.md deliberately avoids duplicating it): a one-line "Directions under
evaluation" note pointing at the model-routing/telemetry issue cluster
(#22, #33, #40–#43).

### DESIGN.md (from interface health review)

- Add the exit-code and `error:`-prefix convention as an explicit line under
  Formatting (or a new "Plugin CLI conventions" subsection) — real and
  consistent across all 8 scripts today, just not written down.
- No change needed for the `/plan` stale-section-names finding — DESIGN.md's
  own text is already correct; the drift is one-directional (code lagging
  doc), fixed on the `plan/SKILL.md` side instead.

### CLAUDE.md (from architecture review, plus one interface-review Track item)

- Record the triple-encoding pattern (SKILL.md prose + script code + test
  reference impl, up to 3x per rule) as a named, accepted tradeoff — currently
  discoverable only by reading `tests/_*.py` docstrings. Note it compounds
  with the CI gap: the pinning tests that justify the tradeoff don't run in
  CI yet.
- Note that DESIGN.md's Vocabulary table and `SKILL.md` prose are parsed as
  structured data by the test suite (`tests/_vocabulary.py`,
  `tests/_task_split_boundary.py`) — a table-cell rename is a code change,
  not just a doc edit.
- Add the one-paragraph disambiguation DESIGN.md's own risk list already
  calls for: jig's risk tags (`LOW`/`REPLAN-RISK`/`ESCALATE-RISK`) are a
  deliberately different vocabulary from studious's report tiers
  (Critical/Important/Track), not meant to align.

### README.md (from README drift review)

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

## Metrics dashboard

| Metric | Value | Trend vs last review | Source |
|--------|-------|---------------------|--------|
| Test coverage | not verified — no coverage tool available, read-only posture forbids running the suite | baseline | codebase health |
| TODO/FIXME count | 0 real (1 `FILL IN` placeholder in PRODUCT.md; 1 fixture-literal false-positive in idiom audit) | baseline | codebase health |
| Outdated deps | N/A — stdlib-only, no third-party dependency manifest | baseline | codebase health |
| Known vulnerabilities | N/A — no scanner available; no third-party deps to scan | baseline | codebase health |
| Largest file (lines) | `tests/test_verify.py` — 966 (largest non-test source: `scripts/design-lint` — 561) | baseline | codebase health |
| Coupling / circular-dependency count | 0 | baseline | codebase health |
| Dead-code symbol count | 0 (confirmed after ruling out grep-alias false positives) | baseline | codebase health |
| Endpoint-convention-violation count | N/A — no API/endpoints | baseline | codebase health |
| Security: Critical/High findings | 0 | baseline | security health |
| Exposed secrets (git history) | 0 | baseline | security health |
| Security-config violations | 1 (unpinned install in privileged release workflow) | baseline | security health |
| Surfaces reviewed | 1 (plugin) | baseline | interface health |
| Cross-surface inconsistencies | 2 (both Important) | baseline | interface health |
| Design system deviations | 0 | baseline | interface health |
| Web: component count / largest CSS file | N/A — no web surface | baseline | interface health |
| Web: accessibility issues (by severity) | N/A — no web surface | baseline | interface health |

## Residual

First-ever cycle: every trend is baseline by definition, and the idiom
recurrence check correctly found insufficient history (0 prior
`code-idioms.md` reports) rather than manufacturing a pattern. All seven
agents ran read-only — no build, test, install, or dependency resolution was
executed at any point in this sweep. `docs/studious/reviews/metrics.jsonl`
did not exist before this run; it and its parent directory were created by
this summary step and now hold this cycle's one baseline line.
