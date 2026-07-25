# jig issue transfer map — 2026-07-25

jig moved into this repo as a second plugin (#150). Its 38 open issues came with it:
36 transferred, 2 closed as done by the merge itself.

**GitHub renumbers on transfer, and it does not rewrite `#N` references inside issue
bodies.** So a bare `#29` in a transferred issue means *jig's* #29, not this repo's —
and this repo has its own #29, which is something else entirely. Use this table before
following any bare reference in an issue that came from jig.

A jig number absent from this table was never transferred; it still resolves as
`jacquardlabs/jig#N`, since that repo is kept as the read-only history reference.

| was | now | title |
|-----|-----|-------|
| `jacquardlabs/jig#10` | #191 | Open question: mockup step in /design for UI-heavy features |
| `jacquardlabs/jig#13` | #192 | Open question: UI probe mechanization — scripted playwright vs self-attestation |
| `jacquardlabs/jig#16` | #193 | Fan-out opt-in mode: N competing implementations + comparative judge |
| `jacquardlabs/jig#17` | #194 | Open question: commit granularity — per-green-cap vs per-task |
| `jacquardlabs/jig#18` | #195 | Deferred task type: migrations and dependency bumps |
| `jacquardlabs/jig#19` | #196 | Open question: /simplify invocation semantics for the refactor leg |
| `jacquardlabs/jig#22` | #185 | Open question: per-stage model routing |
| `jacquardlabs/jig#29` | #175 | M1 audit Track-tier findings (bundled, revisit next cycle) |
| `jacquardlabs/jig#33` | #186 | Emit a dispatch telemetry event per build task / executor |
| `jacquardlabs/jig#37` | #176 | Vocabulary derivation from DESIGN.md is fragile (soft-fail parser, weak guard) and invisible from the doc side |
| `jacquardlabs/jig#38` | #177 | m1-followup audit Track-tier findings (bundled, revisit next cycle) |
| `jacquardlabs/jig#40` | #187 | Shared routing-table contract (schema + routing_reason vocabulary, read by jig and studious) |
| `jacquardlabs/jig#41` | #188 | Replay harness: re-run recorded build tasks on a model set, compare via the oracle hierarchy |
| `jacquardlabs/jig#42` | #189 | Dynamic model classifier (later, evidence-gated on #40/#41) |
| `jacquardlabs/jig#43` | #190 | Run the speed/price-per-task audit on jig's dispatch surfaces — before /build, the inspector, and fan-out land |
| `jacquardlabs/jig#46` | #173 | Design doc doesn't document the evidence-dir-commit step before status-flip |
| `jacquardlabs/jig#52` | #178 | m4-build-core audit Track-tier findings (bundled, revisit next cycle) |
| `jacquardlabs/jig#59` | #179 | evidence-capture's docs/jig/evidence/<date>-<task>/ path can collide across independent branches |
| `jacquardlabs/jig#63` | #180 | m4-closeout audit Track-tier findings (bundled, revisit next cycle) |
| `jacquardlabs/jig#67` | #182 | Add a release-blocking status-check requirement on main's branch ruleset |
| `jacquardlabs/jig#68` | #183 | Lint a /plan-authored PLAN.md itself in CI, once a story routinely commits one as demonstration evidence |
| `jacquardlabs/jig#69` | #184 | Add a type-checking job to CI |
| `jacquardlabs/jig#71` | #181 | docs/design/*.md files are force-added and never stripped before merge, despite the "die at merge" .gitignore rule |
| `jacquardlabs/jig#75` | #174 | Disambiguate the PASS token before /finish and studious gates share a PR body |
| `jacquardlabs/jig#79` | #197 | Collapse the six derive_*_vocabulary clones into one _derive_vocabulary helper |
| `jacquardlabs/jig#80` | #198 | Coach reads '## Revision History' presence as signed-off — REVISED docs false-positive |
| `jacquardlabs/jig#83` | #199 | Parallel executors for independent /build tasks (deferred behind #43, #74) |
| `jacquardlabs/jig#88` | #200 | README version reference goes stale after automatic semantic-release |
| `jacquardlabs/jig#89` | #201 | Unpinned python-semantic-release install in privileged release.yml job |
| `jacquardlabs/jig#90` | #202 | task-execution-discipline/SKILL.md lists FIX as a task-status token, contradicting build/SKILL.md and DESIGN.md |
| `jacquardlabs/jig#91` | #203 | plan/SKILL.md describes /design's output using superseded design-doc section names |
| `jacquardlabs/jig#92` | #204 | PRODUCT.md's 'no named agent personas' principle reads as contradicting /build's Foreman/Executor/Inspector language |
| `jacquardlabs/jig#93` | #205 | _gitutil.py has no direct unit test despite being imported by 6 of 7 CLI scripts |
| `jacquardlabs/jig#94` | #206 | Divergent task-heading parsers: scripts/_planparse.py vs tests/_load_bearing.py |
| `jacquardlabs/jig#95` | #207 | deep-review-2026-07-17 Track-tier findings (bundled, revisit next cycle) |
| `jacquardlabs/jig#99` | #208 | scripts/verify's mechanized test-backed/script tier derivation runs a bare method path as a shell command — fails on every non-executable file (#84 regression) |

## Closed rather than transferred

| jig issue | why |
|-----------|-----|
| `jacquardlabs/jig#55` | Wire `ruff check .` into a CI job — done by the merge; CI's `jig lint + tests` job runs it pinned at 0.16.0. |
| `jacquardlabs/jig#87` | Wire the unittest suite into a CI job — done by the merge; the same job runs all 420 tests. |

## Known stale references

Two kinds of bare `#N` survive in transferred bodies and in `plugins/jig/`'s own prose,
and neither was rewritten — mechanical rewriting would have changed meaning:

- **Ranges** like `#87–#94` span issues that transferred and issues that did not.
- **Genuine studious references.** `#190`'s "Studious's measured data (#130)" already
  meant this repo's #130; rewriting it as a jig reference would have inverted it.

Cleaning up the remaining references inside `plugins/jig/`'s prompt files is tracked
separately — it is prose churn, deliberately kept out of the migration diff.
