# Interface health review — 2026-07-17

First-ever run of this review track for jig. No prior report exists in
`docs/studious/interface-reviews/` (only `.gitkeep`) and no legacy
`docs/studious/frontend-reviews/` directory exists either — every metric
below is baseline.

## Summary

jig's only user-facing surface is the plugin surface (six skills + eight
deterministic scripts) — DESIGN.md correctly declares no web/CLI/TUI/API/
report surface, and that declaration matches the code. Reviewed: the
plugin surface's six `SKILL.md` files and eight `scripts/` CLIs. Overall
health is good — verdict vocabulary is consistent, script CLI conventions
(argparse flags, exit codes, `error:` stderr format) are uniform across
all eight scripts, and four of six skills match DESIGN.md's Vocabulary
table exactly. The biggest experience risk is a real vocabulary drift in
`task-execution-discipline/SKILL.md` (the shared discipline text every
fresh `/build` executor reads) that contradicts both `build/SKILL.md` and
DESIGN.md on whether `FIX` is a task-status token. The biggest debt item
is `plan/SKILL.md` still describing `/design`'s output using a design-doc
section-name set DESIGN.md itself says was superseded.

## Critical

None found.

## Important

- **tier** Important · **location** `skills/task-execution-discipline/SKILL.md:88` (plugin/prompt-tooling) · **dimension** cross-surface vocabulary (command↔shim drift) · **finding** states task status moves `todo` → `in-progress` → `PASS`/`FIX`/`REPLAN`/`ESCALATE`, but `skills/build/SKILL.md:50` ("`FIX` is never a status suffix") and DESIGN.md's Vocabulary table (`/build` task status = `todo`→`in-progress`→`PASS`/`REPLAN`/`ESCALATE`; `FIX` is listed as a separate, transient failure-routine action, never a status suffix) both say the opposite · **confidence** Confirmed · **recommendation** Fix line 88 to read `PASS`/`REPLAN`/`ESCALATE` (drop `FIX` from the status-flip enum); this is the shared text every fresh `/build` executor reads before writing any status, so the contradiction is maximally reachable.

- **tier** Important · **location** `skills/plan/SKILL.md:21-24` (plugin/prompt-tooling) · **dimension** cross-surface vocabulary / documented-vs-actual drift · **finding** describes a future `/design`-produced doc's sections as `Intent / Experience / Contracts / Approach / Assumptions / Not doing / Risks`, but DESIGN.md's Formatting section explicitly states this wording was superseded and every shipped, gate-reviewed design doc — including `/design`'s own Step 4 (`skills/design/SKILL.md:129-140`) — uses the seven names `Problem & persona / Proposed design / User journey / Out of scope / Alternatives considered / Operational readiness / Open questions` instead · **confidence** Confirmed · **recommendation** Update `/plan`'s Input step to name the current seven sections (or simply drop the stale example, since `/plan` already reads "by content, not a fixed heading grammar" and doesn't functionally depend on the wrong names) — low functional risk today, but a maintainer reading `/plan` as reference will get the wrong section list.

## Track

- **tier** Track · **location** `CLAUDE.md` (repo-wide) · **dimension** cross-surface vocabulary documentation · **finding** DESIGN.md's own risk list (#3) flags the risk-tag (`LOW`/`REPLAN-RISK`/`ESCALATE-RISK`) vs. severity-tier (Critical/Important/Track) vocabulary divergence as "worth a note in CLAUDE.md once both appear side by side" — no such note exists yet in CLAUDE.md · **confidence** Confirmed · **recommendation** add the one-paragraph disambiguation note to CLAUDE.md next time a PR body or joint changelog surfaces both vocabularies together; not urgent while they stay in separate tables.

- **tier** Track · **location** `skills/build/SKILL.md` (plugin/prompt-tooling) · **dimension** surface-module sprawl · **finding** at 600 lines, `build/SKILL.md` is by far the largest of the six skill files (next largest: `plan/SKILL.md` at 327); it already carries setup, dispatch loop, inspector step, failure routine, and risk-cadence logic in one file · **confidence** Confirmed · **recommendation** no functional problem today, but if a future milestone adds another `/build` sub-concern, consider splitting into a companion reference file (the pattern `task-execution-discipline/SKILL.md` already establishes for shared discipline text) rather than growing this file further.

- **tier** Track · **location** `scripts/*` (plugin CLI surface) · **dimension** formatting convention / DESIGN.md completeness · **finding** all eight scripts share an undocumented-but-consistent convention (exit 0 = clean, 1 = check failure, 2 = usage error; `error: <msg>` to stderr) that DESIGN.md's Formatting section doesn't capture as an explicit cross-script convention · **confidence** Confirmed (pattern verified across all 8 scripts) · **recommendation** codify this in DESIGN.md's Formatting section so a future script is written against a stated convention rather than an implicit one; genuine nice-to-have, not a defect — every script already follows it.

## Metrics snapshot

- Surfaces reviewed: 1 (plugin) — web/CLI-standalone/TUI/API/report lanes skipped per DESIGN.md's single-surface declaration, confirmed accurate against the code.
- Skill files reviewed: 6 (`design`, `plan`, `build`, `finish`, `coach`, `task-execution-discipline`); total 1,790 lines.
- Scripts reviewed: 8 CLIs + 2 shared modules (`_gitutil.py`, `_planparse.py`); total 2,554 lines.
- Cross-surface (cross-file) vocabulary inconsistencies found: 2 (both Important, above).
- Design-system deviations found: 0 (script CLI conventions and verdict vocabulary otherwise uniform).
- DESIGN.md-documented open risks independently re-confirmed still open: PASS-token collision (issue #75, open), risk-tag/severity-tier divergence (no CLAUDE.md note yet).

## DESIGN.md updates (proposed)

- Add the exit-code and `error:`-prefix convention (see Track finding above) as an explicit line under Formatting or a new "Plugin CLI conventions" subsection — currently a real, consistent pattern that exists only in code, not in the doc.
- Once `plan/SKILL.md`'s stale section-name example is fixed, no DESIGN.md change is needed there — DESIGN.md's own text is already correct; the drift is one-directional (code lagging doc).

## Trend vs last cycle

Baseline — first run of this review track.

## Residual line

Verified clean: all four verdict-bearing skills (`design`, `plan`, `build`, `finish`) match DESIGN.md's Vocabulary table exactly by direct grep against each `SKILL.md`; `coach`'s no-verdict-of-its-own claim and Pocock-rule dispatch scope hold up against its full text; all 8 scripts share one argparse/exit-code/error-message convention; date-format convention (`YYYY-MM-DD`) is consistent between jig's own report paths and studious's review-file convention, confirmed by `build-report`'s own docstring cross-reference. Assumptions: no web/CLI-standalone/TUI/API/report surface exists to review (confirmed against DESIGN.md's Surfaces table and the actual `.claude-plugin/`/`skills/`/`scripts/` tree) — the pixel-blindness caveat in the standard closer template does not apply here since there is no rendered pixel surface in this product at all, not merely one this review couldn't observe. Limitation: did not exhaustively line-read all 8 scripts' internals (sampled entry points, argument parsers, and exit paths only, per the audit's "sample main commands" instruction), so a deeper per-script logic bug is out of this review's scope (belongs to `code-auditor`/`/gate-audit`).
