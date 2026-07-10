# Prompt-contract dedup — remove command/agent output-contract duplication and stale meta-doc references

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Source:** [#92](https://github.com/jacquardlabs/studious/issues/92), story `prompt-contract-dedup` of epic `gate-ledger-robustness` (M2)

## Problem & persona

PRODUCT.md names two personas this story serves in different proportions.

The **primary persona** — "a developer (solo or small team) building features with
Claude Code who wants product judgment and quality gates woven into the build, without
heavy process" — hits the user-visible half of this problem directly. Issue #92, point
1: `commands/backlog-priorities.md:33-37` promises the deep-dive output is "Recommended
(top pick) / Also strong candidates / Honorable mentions"; the agent it spawns,
`agents/backlog-priorities.md:43-55`, actually emits a numbered rank list with
fit/effort/impact/confidence fields. Same invocation, two contradictory formats — the
command's promise is simply wrong about what the persona will see. `backlog-hygiene`
has the same shape of drift: the command's `## Output` (`commands/backlog-hygiene.md:31`)
lists "Possible duplicates" where the agent emits `## Merge duplicates`
(`agents/backlog-hygiene.md:40`), and the command's list omits the agent's `## Could not
verify` section entirely — so a user reading only the command's description doesn't
know that section exists, or that a hygiene run can leave issues unverifiable.

The **secondary persona** — "the maintainer dogfooding Studious on Studious" — owns the
rest: points 2-4 are maintainer-facing hygiene with no per-invocation user impact, but
direct violations of this repo's own stated invariants. Point 2: roughly 13 agents that
cite `reference/prompt-contract.md` do so *twice* — once correctly in "Before you start"
("apply it as given"), and again as a restated closer at the end of `## Output`
("Apply the injected calibrate-don't-suppress / clean-result-is-valid closer.") — which
is, in the contract file's own words, "exactly the drift-by-copy the contract exists to
prevent" (`reference/prompt-contract.md:1-13`). `code-auditor.md` compounds this locally:
its `## Scope` section (lines 20-30) restates the section headings its own `## What to
check` (lines 41-87) already spells out in full. Point 3: `commands/deep-review.md`
quotes `CLAUDE.md: "Commands report; they never modify external state"` as though that
line exists in the *consuming* project's CLAUDE.md — but `/deep-review` reads the
consuming project's three context docs (line 10), and that exact sentence is this
plugin repo's own CLAUDE.md (`CLAUDE.md:54`), not something any consuming project would
have. `CLAUDE.md:56` claims "the 14 review/audit agents share a standardized prompt
contract" when the count is 13 (verified by grep below). `README.md:48` says "6 auditors
in parallel (security, code quality, docs, architecture, UX, frontend)" and never
mentions the conditional 8th, `@agent-premortem-auditor`, that `commands/gate-audit.md`
dispatches "only when a register exists" (lines 25-26, 40-44). Point 4:
`commands/gate-audit.md` and `commands/work-on.md` both list `Write` in `allowed-tools`
but neither file's body ever names a file it writes — all their state changes go
through `gate-ledger` (a Bash-invoked binary) or through the gates they invoke, which
themselves declare their own `Write` where they actually use it
(`commands/gate-design-review.md` writes the pre-mortem register;
`commands/deep-review.md` writes the metrics history and summary report). An
over-permissioned command is a standing claim the audit/hygiene tooling itself would
flag in any other file — "for a suite whose brand is 'audits and reports, never
modifies,' the allowed-tools should prove it."

Grounding invariant this whole story serves: CLAUDE.md's own architecture section — "
`reference/` — curated rubrics agents read at audit time... Agents consult these instead
of restating them inline — keep depth in `reference/`, keep agents pointing at it" — and
the CLAUDE.md skills convention: a shim's "body delegates to the matching command and
must not duplicate its logic." Commands delegating to the agents they spawn, and agents
citing `prompt-contract.md` exactly once, are the same rule applied one layer down.

### Evidence (grepped against this worktree, current state)

```
$ grep -c "prompt-contract" agents/{product-reviewer,review-interface-health,premortem-auditor,architecture-auditor,security-auditor,review-codebase-health,review-readme,review-architecture,code-auditor,ux-reviewer,doc-auditor,review-product-health,frontend-reviewer}.md
# every file: 1 — the path string is cited once; the CONTENT of the closer is
# restated a second time without re-citing the path (see per-file line numbers below)
```

Per-agent second-citation location (the redundant closer restatement) and whether it
carries an addendum worth preserving:

| Agent | "Before you start" (kept, unchanged) | Redundant closer line | Addendum text after it? |
|---|---|---|---|
| product-reviewer.md | :14 | :60 | Yes — no-Bash residual scope note |
| review-interface-health.md | :16 | :71 | Yes — cross-surface inconsistency calibration |
| premortem-auditor.md | :16 | :46 | Yes — out-of-lane/staleness residual note |
| architecture-auditor.md | :16 | :47 | No — bare restatement, nothing follows |
| security-auditor.md | :14 | :63 | Yes — missing-control calibration |
| review-codebase-health.md | :16 | :75 | Yes — accumulating-problem calibration |
| review-readme.md | :14 | :63 | Yes — documented-command-doesn't-resolve note |
| review-architecture.md | :16 | :73 | Yes — load-bearing-path calibration |
| code-auditor.md | :16 | :101 | No — bare restatement, nothing follows |
| ux-reviewer.md | :14 | :73 | Yes — static-review-only limitation |
| doc-auditor.md | :14 | :57 | No — bare restatement, nothing follows |
| review-product-health.md | :16 | :63 | Yes — core-persona-drift calibration |
| frontend-reviewer.md | :16 | :74 | Yes — no-build-run limitation |

```
$ grep -n "The 14 review/audit agents" CLAUDE.md
56:- **Every agent/command reads PRODUCT.md, DESIGN.md, or CLAUDE.md**... The 14
   review/audit agents share a standardized prompt contract...

$ grep -rl "prompt-contract" agents/ | wc -l
13   # actual count
```

```
$ sed -n '48p' README.md
- Audit before merge with `/gate-audit`: 6 auditors in parallel (security, code
  quality, docs, architecture, UX, frontend)... [no mention of the conditional 8th]

$ sed -n '105p' README.md
`.github/workflows/gate-audit-pr.yml` runs `/gate-audit`... the same 6-7 auditor
fan-out you'd get locally... [same omission, softer count]
```

```
$ sed -n '116p' commands/deep-review.md
Propose-only, per this repo's recommend-only posture (CLAUDE.md: "Commands report;
they never modify external state")... [that sentence is CLAUDE.md:54 of THIS repo,
not the consuming project's CLAUDE.md that /deep-review actually reads]
```

```
$ grep -n "allowed-tools" commands/gate-audit.md commands/work-on.md
commands/gate-audit.md:3:allowed-tools: Read, Glob, Grep, Bash, Task, Write
commands/work-on.md:4:allowed-tools: Read, Glob, Grep, Bash, Task, Write

$ grep -in "write" commands/gate-audit.md commands/work-on.md
# (no hits outside the frontmatter line itself — neither body ever writes a file)

$ grep -n "allowed-tools" commands/gate-should-we-build.md commands/gate-acceptance.md \
    commands/gate-design-review.md commands/deep-review.md
commands/gate-should-we-build.md:3:allowed-tools: Read, Glob, Grep, Bash        # no Write, no file written — consistent
commands/gate-acceptance.md:3:allowed-tools: Read, Glob, Grep, Bash, Task       # no Write, no file written — consistent
commands/gate-design-review.md:3:...Task, Write   # writes docs/studious/premortems/<slug>.md — justified
commands/deep-review.md:3:...Task, Write, Edit     # writes metrics.jsonl + summary report — justified
```

## Proposed design

Four independent fixes, one per issue point, each a subtraction or a one-line
correction — no new files, no new mechanism.

### 1. Backlog command/agent delegation (`commands/backlog-priorities.md`, `commands/backlog-hygiene.md`)

Apply the same split the skill shims already model
(`skills/continue-feature-work/SKILL.md`: "Do not reimplement its logic here — the
command owns position tracking and the step order"). A command keeps:

- Its own frontmatter contract (`description`, `argument-hint`, `allowed-tools`).
- The tracker-agnostic disclaimer and "read PRODUCT.md/CLAUDE.md first" line.
- **Argument/mode semantics that are the command's own surface, not the agent's
  workflow** — `backlog-priorities` still states, in its own words, that empty
  `$ARGUMENTS` means overview mode and a named intent means deep-dive (this is what a
  user types, not how the agent formats a rank); `backlog-hygiene` has no argument to
  describe.
- One line delegating output shape and evidence rules to the agent by reference,
  instead of restating them: e.g. "Output format and evidence rules are the agent's —
  see `agents/backlog-priorities.md`'s `## Output` section, including its per-mode
  format and its closing 'What I couldn't assess' line" (and, for hygiene, explicitly
  naming the `## Could not verify` section so its existence is documented at the
  command level too, per the acceptance criterion).
- The recommend-only boundary line at the very end (`"This command is recommend-only.
  It never starts work, creates branches, or modifies issues."` /
  `"...never closes, comments on, or modifies any issues."`). This is kept, not
  deleted, even though the agent's own "What this agent does NOT do" section says the
  same thing in agent-voice — it is the command's own user-facing promise about what
  invoking `/backlog-priorities` or `/backlog-hygiene` can and cannot do, the same role
  README.md's top-level framing plays, not a restatement of the agent's internal
  workflow or output shape. Removing it would leave the command file silent on its own
  blast radius, which is a different kind of information than "how the agent formats
  its report."

Delete: the numbered `## Run the analysis` workflow steps that duplicate the agent's
own `## Workflow` steps (`backlog-priorities` steps 1-2, 4 already fully own the mode
resolution the command's step 3 restates; `backlog-hygiene` steps 1-4 duplicate the
agent's steps 1-5 near-verbatim), and the entire restated `## Output` bullet/fence
block in both commands.

This resolves the actual drift (command promises one shape, agent emits another) by
removing the second, stale copy rather than trying to keep two copies in sync — the
same fix direction CLAUDE.md prescribes for `reference/` duplication.

### 2. One prompt-contract citation per agent (13 files)

Rule, applied uniformly: **the citation lives only in "Before you start"** ("apply it
as given" already commits the agent to following the injected closer without
restating it). At the `## Output` end of each file:

- **Where the closer restatement is bare** (architecture-auditor.md, code-auditor.md,
  doc-auditor.md) — delete the line outright. Nothing of substance is lost; "apply it
  as given" already covers it.
- **Where an agent-specific addendum follows the restatement** (the other 10 agents)
  — delete only the leading restatement clause ("Apply the injected
  calibrate-don't-suppress / clean-result-is-valid closer.") and keep the addendum
  sentence in place, in the same `## Output` location, standing on its own (e.g.
  architecture-auditor's neighbor pattern already shows the shape: `## Output` ends
  with agent-specific severity/schema guidance and no separate closer citation at all —
  match that). The addendum is real, agent-specific calibration content (a residual-line
  scope note, a specific "never demote X to a residual note" instance) that is not what
  the double-citation issue is about; only the redundant re-citation of the shared
  contract is deleted.

Also, `code-auditor.md`: delete the `## Scope` section's `**code-auditor checks:**` /
`**Does NOT check:**` bullet summary (lines 20-30) since `## What to check` (lines
41-87) already gives the full, authoritative version of the "checks" half; keep
`**Does NOT check:**` and the cross-lane escalation sentence, since neither is
restated anywhere else in the file.

### 3. Stale meta-doc references

- `CLAUDE.md:56` — "14 review/audit agents" → "13 review/audit agents" (matches the
  grep above; re-verify count at implementation time in case a sibling M2 story adds
  or removes an agent first — see Open questions).
- `README.md:48` — append the conditional 8th to the auditor list, e.g. "...UX,
  frontend), plus the pre-mortem auditor when a pre-mortem register exists on the
  branch" (name it distinctly from the already-present accessibility-pass clause that
  follows in the same sentence).
- `README.md:105` — same underlying fact (auditor count omits the conditional 8th) in
  the same file; fix consistently in the same pass rather than leaving one occurrence
  corrected and the other stale (a `doc-auditor` run would flag the resulting
  inconsistency). Adjust "the same 6-7 auditor fan-out" to acknowledge the conditional
  8th the same way line 48 now does, keeping the phrasing CI-appropriate (this line
  describes the PR-comment path, not the interactive one).
- `commands/deep-review.md:116` — stop attributing the quoted sentence to a CLAUDE.md
  the reader (running in the consuming project) does not have. Replace the
  parenthetical with a Studious-native attribution that doesn't imply the consuming
  project's CLAUDE.md carries this sentence — e.g. "per Studious's own recommend-only
  posture (this plugin never writes `reference/idioms/<lang>.md` for you)" — dropping
  the false "CLAUDE.md:" quote-attribution while keeping the actual constraint
  (propose-only, this step never writes the idiom file) intact.

### 4. Drop over-permissioned `Write` (`commands/gate-audit.md`, `commands/work-on.md`)

Remove `Write` from both `allowed-tools` frontmatter lines. Confirmed by grep above:
neither file's body names a file it writes; all persistence goes through
`gate-ledger` (Bash) or through the gate commands they invoke (which carry their own,
justified `Write`/`Edit` where a concrete write exists — `gate-design-review.md`,
`deep-review.md`). No behavior changes; this only narrows a standing grant that was
never exercised, matching `gate-should-we-build.md`'s and `gate-acceptance.md`'s
existing (correct) `allowed-tools`.

## User journey

Two journeys, matching the two persona halves in Problem & persona:

1. **Primary persona, PRODUCT.md journey #3 (per-project health loop) and the
   backlog-specific slice of it.** The persona runs `/backlog-priorities` with no
   argument. Before this fix: the command's own description promises
   "Recommended / Also strong candidates / Honorable mentions," but the actual output
   (produced by the agent) is a numbered rank list with fit/effort/impact/confidence —
   a persona who read the command file first (or who has Studious explain itself) gets
   a wrong expectation. After this fix: the command states only that it delegates
   output shape to the agent, so there is exactly one place (the agent file) that can
   ever be wrong about what a run produces — the persona's expectation, wherever they
   read it, always matches. Same for `/backlog-hygiene`: the persona now sees the
   `## Could not verify` section exists (documented at the command level, not just
   buried in the agent) before ever running it, and doesn't mistake "Possible
   duplicates" for the actual `## Merge duplicates` heading they'll see in output.
2. **Secondary persona, dogfooding maintenance.** The maintainer edits an audit/review
   agent's prompt (adding a new dimension, tightening a calibration note) sometime
   after this fix ships. Because each agent now cites `prompt-contract.md` exactly
   once, there is no second, silently-stale copy of the closer for the maintainer to
   forget to update in lockstep — the exact failure mode `reference/prompt-contract.md`
   itself names as what it exists to prevent. When the maintainer next reads
   `CLAUDE.md`, `README.md`, or `deep-review.md`'s idiom-feedback step, the agent count
   and auditor count they see match `grep -rl prompt-contract agents/ | wc -l` and
   `commands/gate-audit.md`'s actual dispatch list, and the CLAUDE.md quote in
   `deep-review.md` no longer claims something about a document the reader (running in
   the consuming project) doesn't have open. When the maintainer next reviews
   `allowed-tools` on any command (their own habit, or a `doc-auditor`/`code-auditor`
   pass), `gate-audit.md` and `work-on.md` no longer carry a permission their bodies
   never use.

## Out of scope

- **`commands/gate-acceptance.md` and `commands/gate-design-review.md`'s
  `allowed-tools`** — both were checked (Problem & persona evidence above) and are
  already correct: `gate-acceptance.md` has no `Write`; `gate-design-review.md`'s
  `Write` is justified by the pre-mortem register it writes at
  `docs/studious/premortems/<slug>.md`. Neither is touched.
- **`commands/deep-review.md`'s `Write`/`Edit`** — justified by the metrics-history
  append and the master-summary write it performs; not an over-permission finding, and
  this story only touches its stale CLAUDE.md quote (point 3), not its tool grants.
- **Any change to what the agents actually check, score, or output** — this story is a
  pure duplication/staleness cleanup; the four fixes above never change a rubric, a
  severity mapping, a scoring formula, or which gate/review an agent belongs to.
  `reference/prompt-contract.md` itself is untouched — the fix is agents citing it
  correctly, not the contract's content.
- **`agents/backlog-priorities.md` and `agents/backlog-hygiene.md`'s own content** —
  these already own the full, correct workflow and output contract; this story deletes
  the *commands'* stale second copies, not the agents' originals.
- **The other 15 non-contract-citing agent/command files** (e.g. `bin/gate-ledger`,
  `workflows/epic-driver.js`, skill shims) — untouched; this story's scope is the
  backlog pair, the 13 contract-citing agents, the three named meta-docs, and the two
  named over-permissioned commands, per the acceptance criteria.
- **Renumbering or renaming any auditor** (e.g. giving the conditional pre-mortem
  auditor a fixed slot number instead of "8, when a register exists") — out of scope;
  this story only makes README.md's prose match `gate-audit.md`'s existing dispatch
  list, not change the dispatch list itself.

## Alternatives considered

- **Fold each preserved addendum into the existing "Before you start" bullet instead
  of leaving it in place at `## Output`.** Rejected: ten of the thirteen "Before you
  start" bullets already carry their own, different addendum sentence (e.g.
  architecture-auditor's "when the changeset itself edits CLAUDE.md conventions...").
  Merging a second, unrelated addendum into that same sentence produces one long,
  two-topic bullet that is harder to read than leaving the (still agent-specific, still
  non-duplicative) addendum where the reader already expects agent-specific output
  guidance — at the end of `## Output`. The only thing being deleted is the
  contract-restatement clause, not the location of the surviving content, which keeps
  the diff smallest and the two addenda topically separated.
- **Leave the backlog commands' `## Output` sections in place but rewrite them to
  match the agents exactly**, instead of deleting them and delegating by reference.
  Rejected: this is the status quo's own failure mode — two copies that must be kept
  in lockstep will drift again the next time either file changes (exactly how this
  bug arose per the 2026-06-27 backlog-priorities-overview design doc, which touched
  the agent's output format without a corresponding command update). Deleting the
  copy and pointing at the single source removes the possibility of the two ever
  disagreeing again.
- **Leave `README.md:105`'s "6-7 auditor fan-out" phrasing untouched** on the theory
  that only line 48 was explicitly named in the issue. Rejected: both lines assert the
  same undercount for the same reason (the conditional 8th), in the same file; fixing
  one and leaving the other creates a fresh, easily-caught inconsistency in the same
  document a `doc-auditor` pass would flag on its next run. Fixing both, consistently,
  in the same commit is cheaper than parking a known-stale line for a future story.
- **Have `gate-audit.md`/`work-on.md` keep `Write` "for future flexibility."** Rejected
  outright — this is precisely the over-permission issue #92 flags, and CLAUDE.md's
  own recommend-only invariant plus the sibling gates' already-correct
  `allowed-tools` (`gate-should-we-build.md`, `gate-acceptance.md`) set the standard:
  grant a tool only when a concrete write exists in the file. Either command can add
  `Write` back the moment a real write is designed, with its own justification line
  the way `gate-design-review.md` and `deep-review.md` already have.

## Open questions

- **Agent count re-verification at build time.** This story's own build phase must
  re-run `grep -rl "prompt-contract" agents/ | wc -l` immediately before editing
  `CLAUDE.md:56`, in case a sibling M2 story in this epic (`contract-injection-unify`,
  `gate-doc-commit-ordering`, `scheduler-fixes`, `workflows-js-lint`,
  `premortem-hook-awareness`) lands first and changes the agent roster. The count is
  13 as of this design (verified above); trust the re-grep over this document if they
  disagree.
- **Exact replacement wording for `deep-review.md:116`'s attribution.** The design
  above fixes the substance (don't claim the consuming project's CLAUDE.md carries a
  sentence unique to this plugin's own CLAUDE.md) but leaves the precise phrasing to
  the build phase — any wording that (a) doesn't cite "CLAUDE.md" as if the reader's
  project has this exact sentence, and (b) keeps the actual constraint (this step
  never writes `reference/idioms/<lang>.md`) intact, satisfies the acceptance
  criterion.
