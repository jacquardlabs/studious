# Pre-mortem — epic `m10-flow-coherence`

Epic: M10 — Post-merge flow coherence (5 open issues, 3 stories; #247 and #253 deferred)
Branch: `epic/m10-flow-coherence`
Recorded: 2026-07-29, at plan approval, before any story dispatched.

Assume the epic shipped and something went wrong. Each mode below names what
would have failed, how it would show up, and what the story that owns it must do
to keep it from happening. `@agent-premortem-auditor` verifies each against the
finished changeset at the finale and returns REALIZED / NOT REALIZED / CAN'T VERIFY.

This epic is unusual in one respect worth stating at the top: **all three stories are
prose on a densely test-pinned surface**, the class of work that historically costs
`/work-through` the most (M11's two prompt-prose stories consumed six of seven
invocations while its five code stories landed in one). The epic runs serially, cap 1,
canary first, deliberately. Modes 1 and 3 exist because of that.

---

## 1 · A fix cycle satisfies one pinned phrase by contradicting another

**Owner:** all three stories · **Verifier:** the finale audit fan-out

Every story here edits prose that a test asserts on literally. `tests/jig/test_coach_skill.py`
pins two evidence paths and a collision-naming assertion; `tests/jig/test_build_skill.py`
and `tests/jig/test_finish_skill.py` pin phrases in the files `pass-token` rewrites;
`reference/evidence-format.md` carries its own "Consumers that must stay in sync" list.
A fix-and-retry round that satisfies the finding it was given by rewording a phrase
another test pins produces a second failure, and the next round reverses the first fix.
That is not a hypothetical: it is the mechanism behind M11's two prose stories, where
every finding across four rounds landed in the untraceable remainder of the diff.

**Realized if:** any story's fix-cycle rounds grow rather than shrink in scope — round
N's findings touching more files or more distinct claims than round N-1's — or the
landed diff contains a phrase that contradicts a still-passing assertion elsewhere in
the same test tree.

## 2 · The rename surface leaks in despite the fork being settled against it

**Owner:** `pass-token` (#174) · **Verifier:** the finale audit fan-out

The interview settled `pass-token` on scope-to-tables and explicitly rejected renaming
the `/build` task status to `VERIFIED`. The rejected option is the tempting one mid-build:
a worker fixing an audit finding about ambiguity will reach for the rename, because a
rename genuinely removes the ambiguity that a convention only documents. The cost the
human weighed is invisible from inside a single fix round — the rename crosses
`tests/jig/test_vocabulary_derivation.py`, which derives the vocabulary by regex over
the very prose being renamed. That is the #176/#115/#116 failure class, and M9 exists
because it already reached production behaviour twice (#211, #213).

**Realized if:** `scripts/status-flip`'s `SUFFIX_RE` changed, or
`tests/jig/test_vocabulary_derivation.py` was modified, or the token `VERIFIED` appears
as a task status anywhere in the landed diff.

## 3 · Two stories collide on `skills/coach/SKILL.md`

**Owner:** `pass-token` (#174) · **Verifier:** `coach-evidence-path` (#260)

`coach-evidence-path` edits that file's orientation-table evidence row (line 59 at plan
time). `pass-token` must keep its own rule consistent with the same file's "Vocabulary
discipline" block (lines 77–81) and its task-status row (line 57). Two stories editing
one file is exactly what the driver's single merge-fix attempt is worst at: it aborts
and parks, and a parked story on a three-story chain blocks everything behind it. The
serial cap and the `coach-evidence-path → receipt-grammar → pass-token` chain exist for
this, so the mode is only reachable if the ordering is subverted.

**Realized if:** the epic branch carries a merge-fix or conflict-resolution commit
touching `skills/coach/SKILL.md`, or `pass-token`'s diff reverts, re-breaks, or
re-litigates the path grammar `coach-evidence-path` landed.

## 4 · `receipt-grammar` re-implements work that closed months ago

**Owner:** `receipt-grammar` (#148) · **Verifier:** the finale audit fan-out

Issue #148 was filed when jig was a separate repo, and two of its four scope bullets
have since been satisfied by closed issues: branch identity in the evidence path
(#179/#258) and gates citing the shared format (#97, via
`gate-ledger evidence-list --dedupe`). A worker that treats the bullet list as a work
list re-opens both. The criteria say *document* for exactly these two, and the
distinction is load-bearing — re-implementing #97 would mean a second evidence reader,
which is the duplication `reference/evidence-format.md` already warns against under
"Reading the log."

**Realized if:** the diff adds a second evidence reader alongside `evidence-list`,
changes `scripts/evidence-capture`'s `target_dir` construction, or modifies
`hooks/evidence-capture.sh`'s record shape rather than describing it.

## 5 · PRODUCT.md's rewritten known-problem overstates what shipped

**Owner:** `receipt-grammar` (#148) · **Verifier:** the finale `/gate-acceptance`

`receipt-grammar` rewrites PRODUCT.md's known-problem #4, which currently asserts the
two-store split is "written down nowhere as a decision." Every gate and review reads
PRODUCT.md as ground truth — the file says so itself at line 215, and names the exact
failure: "a stale entry here is not a documentation nit, it is the discipline running
on bad fuel." A rewrite claiming the problem is fully resolved when only the *decision*
was recorded (the two stores still exist, by design) makes every later gate reason from
a false premise. The same risk applies to claiming resolution of the durable-report
home if that decision ends up scoped out instead of settled.

**Realized if:** PRODUCT.md's new text asserts anything the landed diff does not
support — a unified store, a retired store, or a settled report home that no file
actually states.

## 6 · Two context docs describe the evidence stores differently

**Owner:** `receipt-grammar` (#148) and `pass-token` (#174) · **Verifier:** the finale audit fan-out

The stories write different files: `receipt-grammar` owns `reference/evidence-format.md`
and PRODUCT.md; `pass-token` owns DESIGN.md and two `SKILL.md` files. Both describe the
same seam — the committed per-task store feeds `/finish`'s PR evidence table, which is
also where the `PASS` collision bites. If `pass-token`'s DESIGN.md edit describes that
table's relationship to the evidence stores differently from how `receipt-grammar`'s
decision record does, the epic ships two grammars again at a new altitude, having spent
itself closing the first pair. The per-story audits cannot catch this: the two
descriptions live in different stories' diffs.

**Realized if:** `reference/evidence-format.md`, PRODUCT.md, and DESIGN.md disagree
after the finale about which store is committed, which is gate-readable, or which feeds
the PR evidence table.

## 7 · A dispatched design doc re-decides a fork the human already settled

**Owner:** `receipt-grammar` (#148) and `pass-token` (#174) · **Verifier:** `/gate-design-review`, both stories

No human approves a design doc on this path. Both remaining stories are decisions about
durable, cross-surface rules, and both had their central fork settled at the interview —
two stores not one, `reference/evidence-format.md` not a `docs/` root record, the
report home in scope, scope-to-tables not a rename. Those answers reach every dispatch
through the driver's shared context block marked settled. A design doc that re-opens
one, or quietly designs against the rejected option, has no human between it and the
build, and `/gate-design-review` is an agent reviewing rather than a human approving.

**Realized if:** either design doc argues for, or designs against, an option the
interview rejected, or presents a settled fork as still open.
