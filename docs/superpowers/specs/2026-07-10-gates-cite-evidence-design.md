# Design: Gates cite the branch's evidence log

**Date:** 2026-07-10
**Status:** Design, pre-implementation
**Story:** gates-cite-evidence (epic: worker-evidence-and-board)
**Source:** [#97](https://github.com/jacquardlabs/studious/issues/97)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The principle this story closes the loop on is
PRODUCT.md's first: **"Judgment is the spine; labor is contracted — gates and reviews
decide (should we build it, did we build it right); building enters through the worker
contract and is always gated, never trusted."** `reference/worker-contract.md` already
requires a worker to hand back **"Evidence: Commands actually run with their captured
output... 'Done' without artifacts is not done."** — but until this story, that
requirement is enforced by nothing: a gate reads the worker's own narration and has no
independent record to check it against, even on a branch where one now exists.

The sibling story `evidence-capture-hook` (landed, `ca0eac0`) closed the *capture* half:
a passive hook now appends one record per verification command to
`.studious/evidence/<branch-slug>.jsonl` while a story is armed. But per its own `bin/
gate-ledger` header comment, capture shipped with **"no read verb yet."** Nothing reads
the log. A `/gate-audit` or `/gate-acceptance` run today produces the exact same report
whether the branch has a rich evidence trail or none at all — the log's existence has
zero observable effect. That is precisely the gap issue #97 names as the reason this
piece must exist at all: **"Without this consumer, the kill rule below is unfalsifiable"**
— the epic's own kill rule (*"after 3–4 dogfooded stories, if receipts never changed a
gate verdict or a human decision, stop"*) cannot even be evaluated if no gate ever looks
at a receipt. This story is that first look: it makes a captured record change what a
report says, in the two places a gate today explicitly admits it cannot confirm
something without executing it.

Issue #97 itself frames the target behavior directly: **`/gate-acceptance` and
`/gate-audit` "reference the branch's evidence log when present ('verified per evidence
log' vs 'attested — no evidence log found')."** This story's own acceptance criteria
sharpens that into three testable conditions, read as one continuous rule about the
*same* claim rather than three unrelated ones: cite a specific entry when a log exists
and covers the claim being made; say the claim is **attested** when a log exists for the
branch but doesn't cover this particular claim (self-reported, not independently
confirmed — a real, meaningful signal precisely because the evidence system is active
for this branch and this claim still wasn't captured); and leave the report **completely
unchanged** — no new wording anywhere — for a branch with no evidence log at all. That
third clause matters as a design constraint, not just a nice-to-have: it is what keeps
"attested" a meaningful, occasional flag rather than universal noise stamped onto every
report from every project that hasn't adopted the evidence hook yet (which, for a while,
is most of them).

**Scope note.** This story runs under the epic's already-approved plan;
`reference/epic-plan-contract.md` is explicit that **"approving the plan is the batched
should-we-build for every story in it — no per-story decide gate runs later."** The
epic's own pre-mortem (`docs/studious/premortems/worker-evidence-and-board-epic.md`,
item 4, "Shared gate-ledger choke point") flags the real risk this design has to answer:
that this story and the `evidence-capture-hook` story both touch `bin/gate-ledger`'s
write/read surface, and sequencing alone doesn't guarantee this story's design actually
accounts for what `evidence-capture-hook` landed rather than what its design doc merely
proposed. This doc is grounded in the **landed** diff (`ca0eac0`) and the **landed**
`reference/evidence-format.md`, not the earlier design-time sketch — the two differ (the
`PostToolUse`/`PostToolUseFailure` split was discovered mid-build), and only the landed
shape is safe to build against.

## Proposed design

**Where a gate report actually asserts "I can't confirm this without running it."**
Two, and only two, places in the current prompt corpus make that admission explicitly,
and both are read-only by contract (`reference/prompt-contract.md`: *"Inspect read-only;
never execute the target... Do NOT run the project's build, test, install"*), so both are
structurally unable to close the gap themselves:

1. **`@agent-test-auditor`** (`/gate-audit` only): *"your judgment is static — the
   read-only posture forbids running the suite... When adequacy can only be proven by a
   run, say 'could not verify by execution' — never imply verified."*
2. **`@agent-premortem-auditor`** (`/gate-audit`'s technical lane **and**
   `/gate-acceptance`'s product lane): *"CAN'T VERIFY — the evidence is not observable
   statically (needs a live run, an external service, or a manual test). Say exactly
   what manual check would settle it."*

These are the two loci this story teaches to consult the evidence log before settling
for a disclaimer. Nothing else in either gate's dispatch roster (security-, code-,
architecture-, doc-, infra-, ux-, frontend-auditor; product-reviewer) makes an
execution-pass/fail claim the log's content — test-result predicates only — could ever
back; widening further would be handing unused data to auditors with no reason to want
it (see Alternatives).

Because `@agent-premortem-auditor` runs in *both* gates' dispatch rosters, one shared
edit to `agents/premortem-auditor.md` covers `/gate-acceptance`'s half of this story's
acceptance criteria entirely — `/gate-acceptance` never dispatches test-auditor, and no
other moment in its report (product review, implementation walkthrough, verdict) makes
a claim the evidence log's shape could back. `/gate-audit` additionally needs the
test-auditor edit.

**The read side — one new, minimal gate-ledger verb.** `evidence-capture-hook`'s own
design doc named the gap and deliberately deferred it: *"A gate-ledger read/query verb
for the evidence log (`evidence-get`, `evidence-list`)... Deferred to whichever of
`gates-cite-evidence` or `handback-skill` first needs to read the log."* This story is
that first need. `gate-ledger` gains `evidence-list [--branch B]`, following
`cmd_gate_get`'s exact existing shape (the closest precedent — a single-branch,
optional-`--branch`, cat-if-present-else-silent read): resolve the branch slug via the
same `branch_slug()` every other store already uses, `cat` `.studious/evidence/
<slug>.jsonl` if it exists, produce no output and exit 0 if it doesn't (no file, or `jq`/
`git` unavailable). Named `-list` rather than `-get` because the file is fundamentally a
list of records — one JSON object per line — not a single object, unlike every existing
`-get` verb's target file. No filtering flags: the log is the scope of one branch's
build-phase runs, small by construction, and deciding *which* entry backs *which* claim
is exactly the judgment call the two consulting agents are already positioned to make
with full context — a verb that pre-filters would be substituting code's judgment for
the prompt's, backwards from "code owns bookkeeping; prompts own judgment." Read-only:
this story writes nothing to `bin/gate-ledger`'s existing stores and changes no store's
shape.

**Wiring — one evidence-log resolution per orchestrating command, stamped into exactly
the dispatches that need it.** Both `commands/gate-audit.md` and
`commands/gate-acceptance.md` already establish changeset scope once, up front, and are
already each **"the single context-assembly point"** for the shared four-block prompt
contract (`reference/prompt-contract.md`) they stamp into every dispatch. This story adds
one more resolution alongside that existing step, but the block it produces is *not*
added to the universal four — it is stamped only into test-auditor's dispatch (gate-audit)
and premortem-auditor's dispatch (both gates, when a register exists so premortem-auditor
runs at all):

1. Run `gate-ledger evidence-list` once, before dispatching.
2. Empty output → do nothing further. No block is added to any dispatch prompt. Both
   agents' prompts are byte-identical to what they'd be without this story, which is what
   makes the "no evidence log, no behavior change" guarantee structural rather than a
   convention someone has to remember — there is no code path left that could add
   wording when there is nothing to add it from.
3. Non-empty output → stamp it, verbatim, under an `Evidence log for this branch`
   heading, into test-auditor's and premortem-auditor's dispatch prompts, with one
   instruction shared by both: *"Before writing a disclaimer that something can't be
   confirmed without executing it, check the entries above for a command matching what
   you'd otherwise flag. A matching entry — cite it exactly (the command, `predicate.
   result`, `capturedAt`) in place of the disclaimer. No matching entry — keep the
   disclaimer, but say the claim is attested (self-reported, not independently
   confirmed by this branch's evidence log) rather than leaving it unqualified."*

**Concretely, per agent:**

- `agents/test-auditor.md`'s existing addendum (*"your judgment is static... When
  adequacy can only be proven by a run, say 'could not verify by execution'"*) gains the
  three-way rule above as a direct extension of that sentence, not a rewrite of the
  agent's scope or severity model.
- `agents/premortem-auditor.md`'s **CAN'T VERIFY** bullet gains the same rule: when the
  "manual check that would settle it" the item names matches a captured command, the
  verdict resolves — `predicate.result: "PASSED"` with no contradicting diff evidence →
  **NOT REALIZED**, cited to the log entry; `predicate.result: "FAILED"` or the diff
  otherwise showing the failure mode → **REALIZED**, cited to both the log entry and the
  diff. No match → **CAN'T VERIFY** stands, now explicitly labeled attested-not-settled
  per the rule above instead of a bare "here's the manual check."

Neither edit touches severity mapping, the verdict ladder, or `reference/
severity-rubric.md` — a citation changes *how confidently* a claim is stated, never
*what tier* a finding lands in on its own. A CAN'T VERIFY item that resolves to REALIZED
via the log becomes a real finding through the *existing* REALIZED path (BLOCKER/SHOULD
FIX per the current rule), not a new severity this story invents.

## User journey

This touches PRODUCT.md's critical journey #2, **per-feature gate flow** (`design doc >
/gate-design-review > build with your own workflow > /gate-audit > /gate-acceptance >
merge`), specifically the two gate steps — the "build with your own workflow" step is
unchanged; this story only changes what the two gates *say* about what happened there.

**Concrete, already-real example.** The `evidence-capture-hook` story's own pre-mortem
register (`docs/studious/premortems/2026-07-10-evidence-capture-hook-design.md`) has a
technical-lane item #2: *"Dispatched-worker capture never fires from inside a Task
subagent... Detection hint: A build-phase test that dispatches a real Task subagent
running a verification command and asserts a record with `origin: "subagent"` lands in
the shared `.studious/evidence/<slug>.jsonl`."* Before this story: `@agent-premortem-
auditor` is read-only, cannot dispatch a subagent or run that test itself, and reports
CAN'T VERIFY with the manual check named — permanently, on every future audit of that
branch, regardless of whether the test was in fact run and passed during build. After
this story: if that story's own build phase ran `bash tests/test_evidence_capture.sh`
while armed (a verification-shaped command, matched by the hook's own allow-list), a
record exists in that branch's evidence log. `/gate-audit`'s premortem-auditor dispatch
now carries that log; item #2 resolves to REALIZED or NOT REALIZED, cited to the
specific entry, instead of sitting at CAN'T VERIFY forever. This is not a hypothetical
walked through in the abstract — it is the exact shape of item this story exists to
close, on a register that already exists in this repo today.

**Ordinary path, step by step:**

1. A story branch is armed (`/work-on` or `/work-through`); the worker runs its normal
   verification commands during build; `evidence-capture-hook`'s hook — unchanged by
   this story — silently appends matching records to the branch's log. No new step here;
   this story doesn't touch capture.
2. `/gate-audit` runs. Before dispatching, it resolves the branch's evidence log
   (new). Auditors 1–4, 6–9 dispatch exactly as before — no evidence-log content reaches
   them. Test-auditor (5) and premortem-auditor (10, when a register exists) receive the
   log, when one exists, alongside their existing dispatch content.
3. Test-auditor's report: coverage/adequacy findings unchanged in kind; its residual
   line, where it would have said "could not verify by execution," now either cites a
   specific PASSED/FAILED entry or explicitly says the claim is attested.
4. Premortem-auditor's report: CAN'T VERIFY items whose detection hint matches a
   captured command resolve to REALIZED/NOT REALIZED with a log citation; unmatched ones
   stay CAN'T VERIFY, now labeled attested rather than left bare.
5. `/gate-acceptance` runs later (same branch, further along); its Part 2 dispatches
   premortem-auditor again, product lane — same resolution, same behavior, independent
   of what `/gate-audit` did earlier (each command resolves the log itself; no state is
   shared between gate runs beyond what's already on disk).
6. A branch that never ran a matching verification command, or was never armed at all,
   produces empty output from `gate-ledger evidence-list` in both gates. Every dispatch
   prompt is unchanged from today. Every report reads exactly as it did before this
   story shipped.

## Out of scope

- **`handback-skill`'s evidence manifest and context capsule** — a separate, dependent
  sibling story. This story's `evidence-list` verb is designed to serve it too (plain
  passthrough, no gate-specific shaping), but wiring `handback-skill` to call it is that
  story's own build.
- **Citing the evidence log from any auditor besides test-auditor and premortem-
  auditor.** Security-, code-, architecture-, doc-, infra-, ux-, frontend-auditor and
  product-reviewer never assert an execution-pass/fail claim the log's test-result-only
  shape could back; handing them log content they have no use for is out-of-lane noise,
  not a citation opportunity. If real dogfood use surfaces a genuine claim elsewhere,
  that is a follow-up, evidence-driven change — not something to guess into this story.
- **`/gate-design-review` and `/gate-should-we-build`.** Neither runs after code exists
  to verify; there is no execution claim in either report to ground.
- **Changing `evidence-capture-hook`'s capture behavior, allow-list, or record shape.**
  This story is read-only against everything that story landed — `bin/gate-ledger`'s
  write side, `hooks/evidence-capture.sh`, and `reference/evidence-format.md`'s pinned
  shape are all unchanged inputs here, not surfaces this story edits.
- **A precise, general algorithm for matching "which log entry backs which claim."**
  Left to the consulting agent's own judgment at run time, informed by the rule this
  design states — not pinned to a matching heuristic here, per this contract's own
  non-requirement against baking implementation detail into a design doc.
- **Any new severity tier or change to `reference/severity-rubric.md`.** A citation
  changes confidence in wording; it never changes which tier a finding lands in on its
  own — that stays owned by the existing REALIZED/NOT REALIZED and severity rules.
- **`board-events-log` / `board-server` / `board-ui`.** Separate epic stories, downstream
  of this one in the DAG; this story neither depends on nor blocks their design.
- **Retroactive citation for commits predating this story or `evidence-capture-hook`.**
  There is no log to cite before either shipped — same "nothing to backfill" limitation
  the sibling story already named for capture.

## Alternatives considered

**Read the raw `.jsonl` file inline in the two command prompts (`cat`/`jq` directly),
adding no new `gate-ledger` verb.** Simpler on paper — zero new shell function. Rejected:
resolving the file's path correctly means reproducing `repo_root()`'s git-common-dir
worktree-anchoring logic and `branch_slug()`'s slugging rule inline, in Markdown, a
second time. That is exactly the kind of duplicated bookkeeping PRODUCT.md's own
principle warns against ("code owns bookkeeping; prompts own judgment") and CLAUDE.md
calls a defect pattern when scheduling/ledger logic leaks into a prompt. A path-resolution
bug fixed in `bin/gate-ledger` tomorrow would silently not apply to the copy living in
two Markdown files.

**Stamp the evidence-log block into all four shared-contract-receiving dispatches (or
even all ten auditors), rather than only test-auditor and premortem-auditor.** Keeps the
wiring uniform with the existing four-block pattern — one shared block, everyone gets
it. Rejected: every other auditor's whole reason for existing is a *static*,
diff-content judgment (security posture, code quality, architecture fit, doc drift,
infra risk, UX, frontend structure, product fit) that an execution-pass/fail log entry
does nothing to strengthen or weaken. Handing it to them anyway risks an auditor
inventing a citation opportunity that isn't real for its domain (a lint PASSED entry
does not back a security claim), and dilutes what "cites the evidence log" means for a
reader — it should mean "this is a claim the log could settle," not "this text happened
to be nearby."

**A filtering/summarizing `evidence-list` (`--result FAILED`, `--command-contains
pytest`, or similar).** Would let a consuming agent ask a narrower question instead of
scanning the whole log. Rejected for v0: the log is scoped to one branch's build-phase
runs and is small by construction (`evidence-capture-hook`'s own hook is
"conservative and over-inclusive," not exhaustive), so there is little a filter saves;
worse, picking a filter shape now means guessing which axis (result? command substring?
time window?) either consumer actually needs before either has been built against the
real verb — exactly the premature-shape risk `evidence-capture-hook`'s own design
doc named as its reason to defer this verb at all. A plain passthrough, mirroring
`cmd_gate_get`'s existing precedent, is the smallest verb that unblocks both known
consumers; either can ask for a filter later once it knows what shape it actually needs.

## Operational readiness

- **Migration.** Pure addition. `evidence-list` is a new read-only verb; no existing
  `gate-ledger` verb or store (`gates/`, `work/`, `epics/`, `evidence/`) changes shape.
  `commands/gate-audit.md`, `commands/gate-acceptance.md`, `agents/test-auditor.md`, and
  `agents/premortem-auditor.md` each gain a small, additive block — no existing section
  is restructured. No gitignore change (nothing new is written). Citation only starts
  from whichever plugin version a project is on going forward; gate reports run before
  that are not retroactively annotated — there is nothing to backfill, same as
  `evidence-capture-hook`'s own stated limitation.
- **Rollback.** Revert the one new `gate-ledger` verb and the four Markdown edits. This
  story writes nothing to disk at any point — no data-loss or corruption risk on
  rollback, unlike a change to a write path.
- **Rollout.** Ships via the plugin's normal semantic-release cadence; a consuming
  project's very next `/gate-audit` or `/gate-acceptance` run after updating picks this
  up automatically, no action required. If `gate-ledger` is missing or `evidence-list`
  errors for any reason, the correct behavior is silent degrade to the empty-output path
  (treated identically to "no evidence log") — **not** the surfaced-to-the-user
  treatment `gate-ledger record` gets elsewhere in these same commands (*"tell the user
  the verdict could not be recorded to the gate ledger — do not skip silently"*). That
  distinction is deliberate: a failed `record` call silently
  loses a verdict that otherwise has no other record anywhere, which is worth surfacing;
  a failed `evidence-list` call only means the report reads exactly as it always has,
  which is already this story's explicitly correct behavior for the "no log" case, not a
  failure mode to alarm the user over.
- **How we'll know it's working or failing.** No server, no logs/metrics backend to
  check — same as `evidence-capture-hook`. The real signals: run `/gate-audit` against
  the `evidence-capture-hook` story's own already-landed branch (a real evidence log
  should exist there if its build ran matching commands while armed) and confirm
  test-auditor's and premortem-auditor's reports cite specific entries rather than bare
  disclaimers, using the concrete pre-mortem item #2 walked through above as the
  acceptance case; run the same gates against a branch with no evidence log and confirm
  the report is unchanged from pre-story output. Beyond this story's own acceptance,
  it is the first place issue #97's epic-level kill rule (*"after 3–4 dogfooded stories,
  if receipts never changed a gate verdict or a human decision, stop"*) becomes
  checkable at all — this story doesn't have to satisfy that rule itself, but every gate
  run after it lands is a real data point toward it.

## Open questions

- **Whether citation should extend past test-auditor and premortem-auditor.** Deliberately
  not guessed here (see Out of scope) — real dogfood runs (issue #97's studyengine #210,
  then #209) are the intended signal for whether another auditor's claims would actually
  benefit, not a speculative expansion baked into this design.
- **The allow-list-miss edge case.** If a verification command genuinely ran during build
  but `evidence-capture-hook`'s allow-list didn't match it, no record exists, the log for
  that branch is indistinguishable from "no verification ran at all," and this story's
  "no log → no behavior change" rule means the report gives no signal that anything was
  missed — it silently falls back to today's unqualified wording rather than an
  "attested" flag. This is an inherited limitation of the sibling story's v0 allow-list
  scope, not a new gap this story introduces or should widen the allow-list to fix.
- **Whether `evidence-list`'s plain-passthrough shape holds up once `handback-skill`
  builds against it.** This design assumes both downstream consumers want the same raw
  shape; confirm once `handback-skill` is actually built rather than assuming its manifest
  step needs nothing more from the verb.
- **Whether a citation ever visibly changes a gate's verdict**, as opposed to only its
  wording, in real use — the concrete test of whether this story (and by extension the
  epic's thesis) earns its keep, per the kill rule above.
