# plan-skill demonstration evidence (2026-07-16)

Committed alongside story `plan-skill`'s build-phase implementation
(`skills/plan/SKILL.md`), to satisfy `docs/design/plan-skill.md`'s
Operational readiness section, "Required demonstrations." Per this repo's
own principle 7 (`.gitignore`'s comment), this folder — like
`docs/design/` — is disposable: it lives on this branch to give
`/gate-audit`/`/gate-acceptance` something real to review, and is expected
to be removed at merge once its substance is folded into the PR's
Done-means evidence table, matching the precedent already set on this
epic (commits `f2aff29`, `2194a68`, `0d76450`, `e6fd44e` on sibling
stories).

Nothing below is simulated or hand-narrated in place of a real command:
every JSON file, every `plan-lint`/`parse_sections.py` output, and every
grep/parse result quoted in the two READMEs is copied verbatim from an
actual invocation, run from this worktree, against the real (uncommitted
at draft time, now committed as evidence) `PLAN.md` this session drafted.

## `ci-wiring-demo/` — demonstrations 1, 2, 3

A real, currently-unblocked small jig feature — wiring `scripts/plan-lint`
and Ruff into CI, named explicitly in `docs/design/plan-lint.md`'s own Out
of scope as "unblocked by this story... but not built by it" — planned by
hand-executing `/plan`'s own Steps 1–4 against a real, newly-written design
doc (`docs/design/plan-lint-ci.md`) and against this repo's real, current
state (its `.github/workflows/`, `CLAUDE.md`, `pyproject.toml`,
`tests/fixtures/plan-lint/*`).

- `PLAN.md` — the real drafted plan. Three calibrated tasks, a `Spine:`
  preamble line (not a heading, per Step 2), risk-free (`LOW`) checkpoint
  blocks, and a real `## Not-here follow-ups` section with three concrete
  (non-placeholder) bullets.
- `plan-lint-output.txt` — `scripts/plan-lint`'s real, unmodified output
  against this file: **0 violations across 3 task(s), exit 0**, on the
  first draft (satisfies Step 5: "a real invocation with a real exit code
  branched on").
- `build-step-1.4-split-check.md` — reproduces `/build`'s own Step 1.4
  splitting rule (a Foreman's judgment call, not a separate script;
  matches the same regex pair `scripts/plan-lint`'s `split_tasks()`
  already encodes for the identical purpose) against this real file: three
  clean task blocks, the trailing `## Not-here follow-ups` section
  correctly excluded from Task 3's — directly answers demonstration 2 and
  epic pre-mortem risk #4.
- `viva-round-trip/` — the real, unmodified `scripts/parse_sections.py`
  (viva 1.18.0, the version actually installed) run against this real
  `PLAN.md`, twice: once with bare auto-detect, once with the explicit
  `--split-on` pattern `/plan`'s own `SKILL.md` mandates. Both produce the
  identical, correct 5-section split (preamble, Task 1, Task 2, Task 3,
  Not-here follow-ups) — no absorption. A third and fourth run reproduce
  the Revision-History collision case against a copy of this same real
  file with a second `##` heading appended: auto-detect alone collapses to
  **2 sections** (every task merged into the preamble!), while the
  explicit `--split-on` pattern stays correct at 5. This directly
  re-confirms, against the real artifact rather than only the pre-existing
  `plan-lint` fixture, both halves of demonstration 3 and closes epic
  pre-mortem risk #5 a second time.

### What this does *not* claim

`docs/design/plan-skill.md`'s own Verdicts table defines `PLAN READY` as
firing only once "every task reaches viva `approved`" — a human decision,
made by a person clicking through viva's browser UI, section by section.
This build-phase session is an unattended agent with no interactive
channel to a live human reviewer (no browser, no `AskUserQuestion`-style
tool available in this dispatch). Submitting an "approved" verdict through
viva's own HTTP API on the human's behalf was considered and rejected —
that would be exactly the self-sign-off `PRODUCT.md`'s "Nothing signs off
on itself" principle exists to forbid, not a legitimate substitute the way
`docs/jig/demonstrations/2026-07-12-build-skill/`'s `claude -p
--agent general-purpose` substitution was for a fresh executor (a
functionally-equivalent isolated process, not a stand-in for a human
*judgment*). So: every **mechanical** gate this plan must clear before a
human ever sees it — `plan-lint`'s real exit code, `/build`'s real
Step 1.4 split, and viva's real section-split mechanism (auto-detect *and*
the Revision-History collision case) — is verified above, for real,
against the real artifact. The one remaining leg, a human actually
clicking through viva's review cards to `approved`, needs a live session
with the project's own user and could not be honestly fabricated here.
This is flagged as the open item for `/gate-acceptance` to weigh, matching
this epic's own established precedent of a "Fix" cycle when a build-phase
demonstration's evidence is incomplete (see `f2aff29`, `2194a68`).

### Fix cycle (retry 1, sha `4ac6183` → this commit)

`/gate-acceptance` returned FIX AND RE-CHECK at sha `4ac6183`, ONE SHOULD
FIX: this leg is exactly what's above — a live viva round-trip approving
each task card was never performed. This fixer session is, itself, another
unattended dispatch with no interactive channel to a live human reviewer —
the identical constraint the original build-phase session already named
above, not a new one this retry introduces. Submitting `approved` through
viva's HTTP API from here would be the same forbidden self-sign-off for the
same reason; doing it anyway to make this section shorter would defeat the
entire point of the demonstration (proving a *human* really can sign off),
not satisfy it. So this retry does not fabricate that leg either. What it
does instead, all within an unattended agent's actual reach:

1. **Re-verified the existing mechanical evidence still holds**, in case
   anything drifted since the original session: `scripts/plan-lint`
   against `ci-wiring-demo/PLAN.md` — still **0 violations across 3
   task(s), exit 0**; `parse_sections.py --split-on` against the same file
   — still **5 sections**, identical split. No regression.
2. **Smoke-tested viva's actual launch path in this exact worktree** —
   `parse_sections.py` then `server.py --mode review --no-browser` against
   a scratch copy of the real `PLAN.md`, confirmed the server opens and
   answers `HTTP 200` on its own `.viva/server.url`, then killed the
   process and deleted `.viva/` **before any `/submit` or `/complete`
   call** — no verdict was ever requested or written, `review-r1.json`
   never came into existence. This only proves the *mechanism* launches
   cleanly here; it is not, and cannot be, a substitute for a human
   clicking through the cards it renders.
3. **Closed the ONE OBSERVATION in the same cycle** (see
   `assumption-falsified-demo/` and `missing-test-runner-demo/` below) —
   optional per the finding, but fully within an agent's own reach since
   neither sub-cause needs viva.

**The blocking leg itself is still open** and still needs exactly what the
original session named: a live session where the project's own developer
runs `/plan` (or the block below) and clicks each task card through to
`approved`. Copy-paste runbook, using the real `ci-wiring-demo/PLAN.md`
already committed here:

```bash
cd <this worktree>
cp docs/jig/demonstrations/2026-07-16-plan-skill/ci-wiring-demo/PLAN.md /tmp/plan-ready-demo.md
VIVA_DIR=$(find ~/.claude/plugins/cache -maxdepth 6 -path "*/viva/*" -name server.py -print0 \
           | xargs -0 ls -t | head -1); VIVA_DIR=${VIVA_DIR%/server.py}
mkdir -p .viva
python3 "$VIVA_DIR/scripts/parse_sections.py" /tmp/plan-ready-demo.md \
  --output .viva/review-input-r1.json --round 1 --doc-file /tmp/plan-ready-demo.md \
  --split-on '(?i)^(Task \d+|Not-here follow-ups|Revision History)' \
&& python3 "$VIVA_DIR/server.py" --mode review \
     --input .viva/review-input-r1.json --output .viva/review-r1.json &
```
Then open the browser tab the server launches, approve all 4 cards (3
tasks + `Not-here follow-ups`), and commit the resulting
`.viva/review-input-r1.json` / `.viva/review-r1.json` pair as this
demonstration's terminal evidence alongside a note that `/plan` reported
`PLAN READY`. Re-run `/gate-acceptance` after.

### Live sign-off (completed — this commit)

The blocking leg above is now closed. The project's own developer ran the
exact runbook above, live, in this worktree, against the real,
already-committed `ci-wiring-demo/PLAN.md` (via a scratch copy, per the
runbook) — round 1 parsed to 5 sections (preamble, Task 1, Task 2, Task 3,
`Not-here follow-ups`) using the mandated `--split-on` pattern, the browser
tab opened, and the developer approved all 5 cards with zero `changes`/
`info` comments. `POST /complete` and `revision_history.py` closed the
session cleanly (server process exited 0).

The terminal evidence pair is committed at
`viva-round-trip/live-signoff-review-input-r1.json` /
`viva-round-trip/live-signoff-review-r1.json` — distinct filenames from the
four mechanical-only `parse_sections.py` invocations above (those never
launched a server or requested a verdict; this one did, and is a real,
human-produced `review-r1.json` with five `"verdict": "approved"` entries).

Per `docs/design/plan-skill.md`'s own Verdicts table, `PLAN READY` fires
when "every task reaches viva `approved`, `scripts/plan-lint` exits 0
against the final file" — both legs are now true for `ci-wiring-demo/
PLAN.md`: `plan-lint-output.txt` above already showed 0 violations, and
this round's `review-r1.json` shows every section approved. `/plan` reports
`PLAN READY` for this plan; `/build` is the named next step per the
Verdicts table.

## `design-gap-demo/` — demonstration 4

`jig` itself has no UI surface (this design doc's own Step 1b finding), so
this demonstration needed a second, disposable target-project fixture per
the design's own Open Questions. `fixture-repo/` is a minimal
Node/Express app fixture with a `CLAUDE.md` naming no scripted-probe tool,
a `package.json` naming neither `playwright` nor an equivalent, no
`playwright.config.*`, and one design doc
(`docs/design/widget-color-picker.md`) whose one load-bearing user-journey
step explicitly requires a live-observed screenshot, not a DOM-attribute
assertion. `README.md` in that folder runs Step 1b's three checkable
signals for real against the fixture (including a real wrinkle: a naive
`grep -i playwright` false-positives on the fixture's own disclaimer
prose, so the actual check has to parse `package.json`'s dependency keys
structurally) and reports the resulting `DESIGN GAP`, naming the specific
gap and the concrete resume action per the Verdicts table's own
requirement.

## `assumption-falsified-demo/` and `missing-test-runner-demo/` — fix cycle, ONE OBSERVATION

Added in the retry-1 fix cycle above to close epic pre-mortem risk #3's
full detection hint: "verify the assumption-falsified and missing-
test-runner causes are demonstrated, not only the probe case demo 4
covers." Both run a real Step 1a/1b check — no viva involved, so both are
fully within an unattended fixer session's own reach.

- `assumption-falsified-demo/` — a fixture design doc claims (falsely, on
  purpose) that `scripts/plan-lint`'s real `split_tasks` function already
  takes a `repo_root: Path` second argument. Step 1a's code-inventory check
  — `grep`, then an `ast` parse of the real function — run for real against
  this actual repo, finds the real signature is `split_tasks(text: str)`,
  one parameter. `DESIGN GAP`, naming the falsified claim, the real
  signature with its `file:line`, and the resume action (revise the doc).
- `missing-test-runner-demo/` — a minimal Python fixture repo
  (`fixture-repo/`) whose `CLAUDE.md` states no baseline/test command
  (structurally — a naive `grep -i test` false-positives on the fixture's
  own disclaimer prose the same way `design-gap-demo/`'s naive
  `grep -i playwright` did, so the real check looks for the `### Quality
  gates` / `**Tests**` shape this repo's own `CLAUDE.md` files actually
  use, not a raw string match) against a design doc proposing one
  `test-backed` checkpoint item. Step 1b's test-runner read, run for real,
  finds nothing stated. `DESIGN GAP`, naming the missing infra and the
  resume action (add a `### Quality gates` section naming the real test
  command).

Together with `design-gap-demo/`'s probe-tooling case, all three named
`DESIGN GAP` sub-causes now have a real, committed, independently-checkable
demonstration — three distinct messages, three distinct resume actions,
none bare.
