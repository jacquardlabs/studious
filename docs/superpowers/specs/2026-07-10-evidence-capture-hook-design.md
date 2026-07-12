# Design: Story-scoped evidence-capture hook

**Date:** 2026-07-10
**Status:** Design, pre-implementation
**Story:** evidence-capture-hook (epic: worker-evidence-and-board)
**Source:** [#97](https://github.com/jacquardlabs/studious/issues/97)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** PRODUCT.md's first product principle names the
mechanism this story has to make good on: **"Judgment is the spine; labor is
contracted — gates and reviews decide (should we build it, did we build it right);
building enters through the worker contract and is always gated, never trusted. Studious
never builds in its own lane: gate agents never build, worker agents never gate, and
they never share context."**

"Never trusted" is the part this story closes a real gap in. `reference/worker-contract.md`
already requires a worker to return **"Evidence: Commands actually run with their
captured output... 'Done' without artifacts is not done — an assertion of success with
no output attached is treated as not run."** But today that evidence is the worker's
own transcript, typed by the same party under review — the exact failure mode Winnow's
Roadmap Amendment 006 ("Evidence Bundles / the Exhibit," `docs/amendments/
006-evidence-bundles.md` in the sibling `winnow` repo) documents as non-hypothetical: a
Replit agent fabricated test results and deleted a production database (July 2025); an
open Codex issue records fabricated commit narration with non-existent SHAs. A
dispatched `/work-through` worker's "tests passed" claim is, right now, unfalsifiable by
anything downstream — the acceptance gate has no independent record to check it
against. The job-to-be-done: let a human running `/work-through` unattended, or a gate
reading a worker's return, trust a verification claim because *the harness*, not the
agent, produced the evidence — "capturer ≠ claimant," in the amendment's phrase — without
adding a step either the human or the worker has to remember.

**Scope note on PRODUCT.md's own parked item.** PRODUCT.md's "What we're NOT building"
currently lists: *"A worker-layer skill set (evidence capture and handback first) is
parked and enters through the normal gates on its own evidence, not by default."* This
story is that re-entry. Issue #97 itself says to run `/gate-should-we-build` first and
that the issue "records intent and scope, not gate exemption" — but this story is
running under an approved epic plan, and `reference/epic-plan-contract.md` is explicit
that **"approving the plan is the batched should-we-build for every story in it — no
per-story decide gate runs later."** The epic's premortem
(`docs/studious/premortems/worker-evidence-and-board-epic.md`) is recorded at plan
approval, so that batched decision has already been made for this story. PRODUCT.md
itself will need a proposed edit once this lands, moving this line out of "What we're
NOT building" — flagged here, not applied; that stays with a reviewer under the
propose-don't-apply principle.

## Proposed design

A new **PostToolUse** hook, matched to the `Bash` tool only, ships with the plugin
(`hooks/evidence-capture.sh`, registered in `hooks/hooks.json` alongside the existing
`gate-reminder.sh` PreToolUse entry). While the current git branch is a **story
gate-ledger already knows about** — a work file under `.studious/work/` whose `.branch`
matches the branch the command actually ran on, the same fact `/work-on` and
`/work-through`'s driver already record via `gate-ledger work-set --branch` as an
existing step of arming a feature — and the command just run matches a conservative,
documented allow-list of verification-shaped invocations (test runners, linters, type
checkers, build commands; see below), the hook calls a new `gate-ledger evidence-append`
verb, which appends one record to a new local, gitignored, per-branch store:
`.studious/evidence/<branch-slug>.jsonl`. Nothing else changes: no new command, no new
slash-command step, no prompt or interruption. A branch nobody armed, or a Bash call
that doesn't look like verification, produces no record and no side effect — the hook
is silent by default, the same posture `hooks/gate-reminder.sh` already has for the
`gh pr create` matcher it doesn't fire on.

**Reusing gate-ledger's existing choke points, not inventing a new store shape.** The
epic's own goal statement calls for building this "on gate-ledger's existing write
choke points with no new instrumentation." Concretely: `evidence_dir()` is one more
function in the same family as `ledger_dir()`/`work_dir()`/`epic_dir()`, anchored to
`repo_root()` the same way, so a linked worktree writes to the same shared
`.studious/` the main working tree reads — exactly how gates, work files, and epics
already behave across `/work-through`'s per-story worktrees. `ensure_gitignore()`
already covers `.studious/` broadly, so no gitignore change is needed. The "armed"
check needs no new read verb: `gate-ledger work-list` already emits a `branch` column
per work file, which is the fact the hook needs. The write side is the one genuinely
new surface: `cmd_evidence_append`, following `cmd_record`'s existing shape (arg
parsing, `have jq || have git` degrade-silently guard, `ensure_gitignore`, `mkdir -p`).
Because this is an append-only log rather than a single mutated object,
`cmd_evidence_append` writes with `jq -nc ... >> file` instead of `json_update`'s
read-modify-write-and-rename pattern — a smaller surface for the exact operation it
needs, and avoids read-modify-write contention if two Bash calls in flight ever raced
(not expected within one story's sequential phases, but cheap to get right regardless).

**Record shape — early-footprint only, illustrative here.** The acceptance criteria
scope this story to *"winnow Amendment 006's early-footprint rules only —
capturer-provenance field + in-toto predicate-shaped test-result records — not the
DSSE-signed/driven-flow/screenshot machinery."* Concretely, from the amendment's own
"Early footprint (cheap now, structural later)" section:

1. *"Capturer provenance is recorded on every Evidence object... a claim is only as
   honest as its evidence, and evidence captured by the daemon (capturer ≠ claimant) is
   categorically different from evidence narrated by the agent under review."*
2. *"Evidence serialization aligns to in-toto predicate shapes from day one. Test runs
   map to the existing test-result predicate... Nothing else changes in the PoC — this
   is a serialization decision, not a feature."*

Studious has no persistent daemon process, so `capturer` is populated with a
studious-local value, `"hook"`, for every record this story produces — it is a
constant in v0, but recording it now (rather than only once a second capturer type
exists) is exactly the "cheap now, structural later" point of rule 2, and it is the
field that makes the capturer-≠-claimant property checkable later rather than merely
asserted. For rule 2, this story maps **every** captured command — test, lint,
typecheck, or build — onto in-toto's real, existing `test-result` predicate
(`https://in-toto.io/attestation/test-result/v0.1`; verified against
`in-toto/attestation`'s spec: required fields `result` (`PASSED`/`WARNED`/`FAILED`) and
`configuration`), rather than minting a second "command transcript" predicate — the
amendment reserves that split for Phase 2, which this story does not build. `result` is
derived from the Bash tool's exit status (`0` → `PASSED`, non-zero → `FAILED`;
`WARNED` is unused in v0 — no generic, cross-tool way to detect "passed with warnings"
exists without per-tool output parsing, itself Phase-2-shaped scope). Illustrative
record (the byte-exact shape is pinned at build time in a new reference file, not
here — see below):

```json
{
  "capturedAt": "2026-07-10T21:03:44Z",
  "capturer": "hook",
  "origin": "subagent",
  "agentType": "epic-driver:build-worker",
  "command": "uv run --no-project --with pytest pytest tests/python -v",
  "exitCode": 0,
  "outputDigest": "sha256:9f2c...",
  "predicateType": "https://in-toto.io/attestation/test-result/v0.1",
  "predicate": {
    "result": "PASSED",
    "configuration": [{ "name": "uv run --no-project --with pytest pytest tests/python -v" }]
  }
}
```

`origin` and `agentType` are deliberately **not** nested inside `predicate` — everything
under `predicate`/`predicateType` mirrors winnow's shape; `origin`/`agentType` are
studious's own dispatch-context fields, kept structurally separate so a future diff
against winnow's spec stays about winnow's fields only, not studious's additions.
`origin` is derived from the hook input's `agent_id` field (`agent_id` present →
`"subagent"`, absent → `"interactive"`) — this is the field that answers dogfood item
zero (below). `outputDigest` is a digest, not the raw output — Amendment 006's rule
asks for a digest specifically, and it is the right call independent of the amendment:
raw command output is a plausible place for a secret (a token echoed by a failed auth
check, an API key in a stack trace) to land, and this log is local but long-lived for
the branch's life; a digest lets a later reader confirm two runs produced identical
output without the log itself becoming something that has to be handled as sensitive.

**Dogfood item zero — verified, not assumed.** Issue #97 flags as unverified "whether
PostToolUse hooks capture tool calls inside dispatched worker agents." Checked against
Claude Code's own hooks reference (`code.claude.com/docs/en/hooks`) rather than left as
an assumption: `agent_id` and `agent_type` are documented, populated fields on
`PostToolUse` input **"present only when the hook fires inside a subagent call"** —
i.e., `PostToolUse` hooks do fire for tool calls made inside a Task-dispatched
subagent, and the input payload is exactly how to tell the two cases apart. That
resolves the mechanism-level question this design needs answered to pick an `origin`
field at all. It does not by itself prove studious's specific hook, once written, is
correctly discovering arming and appending correctly from *inside* a dispatched
worker's own process — that is an empirical claim about this story's own code, and
`gates-cite-evidence`'s and this story's own acceptance testing need a real test that
exercises the dispatched-agent path, not a citation to the docs, before either can claim
dual-mode capture works. See Operational readiness.

**Verification-relevant filtering.** The acceptance criteria's own wording is *"a
verification command"* runs, not *"a command"* runs — a deliberate signal, not
accidental phrasing, and worth taking literally: an unfiltered "log every Bash call"
would also record `cd`, `git status`, `ls`, diluting the one property that makes the
log worth a gate's citation (a `FAILED` entry actually means something failed a check,
not that a directory listing exited zero). The hook's allow-list is conservative and
over-inclusive by design — a missed real verification command is a worse failure than
one extra harmless record — covering categories rather than an exhaustive tool list:
test runners (`pytest`, `jest`, `vitest`, `go test`, `cargo test`, `rspec`, `phpunit`,
`npm test`/`npm run test`), lint/static analysis (`eslint`, `ruff`, `flake8`,
`shellcheck`, `markdownlint`/`markdownlint-cli2`), type checkers (`tsc`, `mypy`,
`pyright`), build commands (`npm run build`, `make`, `cargo build`, `go build`), and a
word-boundary catch-all on `test`/`lint`/`typecheck`/`check`/`build` as standalone
tokens so project-specific wrapper scripts are picked up too — CLAUDE.md's own command
suite (`bash tests/test_gate_ledger.sh`, `uv run --no-project python
scripts/check_references.py`) is exactly this shape. Word-boundary matching is what
keeps `git checkout` from false-positiving on `check`. The pattern list is data in the
hook script, not this doc — it is expected to need iteration once this ships against a
real, unrelated project (see Operational readiness and Open questions).

## User journey

This touches PRODUCT.md's critical journey #2, **per-feature gate flow** (`design doc
> /gate-design-review > build with your own workflow > /gate-audit > /gate-acceptance >
merge`), in both its interactive (`/work-on`) and dispatched (`/work-through`) forms —
the "build with your own workflow" step is the one that gains a silent side effect.

Before this story: a worker (human at the keyboard, or a Task-dispatched build-phase
worker under `/work-through`) runs its own verification commands as part of normal
work. Each command's real output scrolls past in that session only. When the worker
returns its summary and "Evidence" section per `reference/worker-contract.md`, that
transcript — pasted or paraphrased by the same agent whose work is under review — is
the only record a downstream gate or a supervising human ever sees.

After this story:

1. A story branch and worktree exist (`/work-on` or `/work-through`'s driver creates
   them); `gate-ledger work-set --branch "<branch>"` records the branch — an existing
   step of both flows, not a new one. The story is now armed.
2. During build, the worker runs its own verification commands exactly as it does
   today — e.g. `uv run --no-project pytest tests/python -v`,
   `npx -y markdownlint-cli2`, `shellcheck bin/gate-ledger` — the same commands
   CLAUDE.md's own "Commands" section names, or the consuming project's equivalent.
3. Each such Bash call completes; Claude Code fires `PostToolUse`;
   `hooks/evidence-capture.sh` runs invisibly — no output the worker or human sees, no
   permission prompt, no delay perceptible to the session. If the branch is armed and
   the command is verification-shaped, one record lands in
   `.studious/evidence/<branch-slug>.jsonl`.
4. The worker's own return still includes its narrated Evidence section, unchanged —
   this story adds a second, independently produced trail; it does not replace the
   worker-contract's existing requirement.
5. A later gate (a separate story, `gates-cite-evidence`, not built here) or a human
   reviewing the branch now has something to check a "tests passed" claim against that
   the worker did not produce and cannot edit.
6. A docs-only story that never runs a verification command leaves the log empty or
   absent — no forced record, no fabricated evidence where none exists.

On a branch nobody armed — a scratch branch, exploratory work outside any gated flow —
nothing changes: no work file, no match, no record, ever.

## Out of scope

- **`handback-skill`'s evidence manifest and context capsule** — a separate, dependent
  story in this epic. This story writes individual records; assembling them into a
  manifest and committing that to the branch is `handback-skill`'s job.
- **`gates-cite-evidence`'s actual gate-side reading and citation logic** — also a
  separate, dependent story. This story does not change what `/gate-audit` or
  `/gate-acceptance` say.
- **Winnow's Phase 2 Exhibit machinery** — DSSE-signed envelopes, sigstore keyless
  signing, driven-flow browser/CLI recordings, before/after screenshot pairs, the
  standalone `exhibit render` path. The acceptance criteria name this exclusion
  directly; Amendment 006 places all of it in "Phase 2 workstream 7," explicitly later
  than the "early footprint" this story implements.
- **Non-`Bash` tool calls.** `Read`, `Write`, `Edit`, `Task`, and MCP tool calls are not
  captured. The worker-contract's own definition of evidence is "commands actually
  run" — file edits aren't a verification claim to check.
- **A gate-ledger read/query verb for the evidence log** (`evidence-get`,
  `evidence-list`). Deferred to whichever of `gates-cite-evidence` or `handback-skill`
  first needs to read the log — either can shape the query to what it actually needs;
  guessing that shape here risks a verb neither downstream story uses as designed. In
  the interim the file is plain, one-object-per-line JSON — directly `jq`/`cat`-able
  for this story's own tests.
- **Retention or pruning policy** beyond extending `gate-ledger gc`'s existing pattern
  (it already removes `.studious/gates/` and `.studious/work/` files whose branch no
  longer exists) to also remove orphaned evidence files — the same rule, the same
  choke point, not a new policy.
- **Cross-project or cross-repo evidence aggregation.** Each project's `.studious/` is
  local to that project, exactly as gates/work/epics are today.
- **A precise, exhaustive classifier for "verification-relevant."** The allow-list
  above is a deliberately approximate v0 heuristic, not a claim of completeness across
  every consuming project's toolchain.

## Alternatives considered

**Rely on the worker's own self-reported Evidence section; build no hook at all.** This
is the status quo `reference/worker-contract.md` already provides, and it is the
simplest possible option — zero new code. Rejected because it is precisely the failure
mode Amendment 006 exists to name: evidence "selected, produced, and narrated by the
party under review" is unfalsifiable by construction, and the real-world fabrication
cases the amendment cites (Replit, Codex) are not evidence that workers lie by default
— they're evidence that a system with no independent check has no way to tell the
difference between an honest worker and a dishonest one. A passive, harness-owned hook
is the one property self-reporting cannot have: capturer ≠ claimant. This is the whole
reason the story exists, not a minor implementation choice.

**Capture from a `Stop`/`SubagentStop` hook instead of per-command `PostToolUse`,
re-deriving individual commands from the session transcript.** Rejected: `Stop` fires
once per turn/session, not once per command, so per-command exit code and output
digest would have to be reconstructed by parsing the transcript file after the fact —
the transcript's format is an internal implementation detail Claude Code does not
document as a stable public contract, unlike the `PostToolUse` hook input schema, which
is. Intercepting the tool call directly, while it is happening, is simpler and rests on
a documented contract instead of a parsing dependency on an undocumented one.

**Capture every Bash call while armed, with no verification-relevant filter.** Simpler
to build (no allow-list to maintain, no false-negative risk from an incomplete
pattern list) and was seriously considered. Rejected primarily because the acceptance
criteria's own wording — "a *verification* command," not "a command" — reads as
deliberate, and secondarily because an unfiltered log dilutes exactly the property a
downstream gate would want to cite: a `FAILED` record should mean a check failed, not
that some unrelated command happened to exit non-zero. Documented here as the fallback
if the allow-list proves impractical to maintain across dogfooded, non-studious
projects (see Open questions).

## Operational readiness

This has a real operational surface, larger than most Studious changes: the hook
registers against every `Bash` call in every session of every project that installs
the plugin, not only sessions actively running a gated story. Its own failure modes
must be inert by design.

- **Migration.** Pure addition. No existing store (`gates/`, `work/`, `epics/`)
  changes shape. `ensure_gitignore()` already covers `.studious/`, so no gitignore
  change is needed for the new `evidence/` subdirectory. Evidence capture only starts
  from whenever a project's plugin update takes effect forward — commands run before
  that are not retroactively captured. That's a real, worth-stating limitation, not a
  bug: there is no data to backfill from.
- **Rollback.** Revert the `hooks/hooks.json` entry and the `gate-ledger` verb. Already
  written `.studious/evidence/*.jsonl` files are inert — nothing else reads them yet in
  this story's scope — so rollback carries no data-loss risk to the other three stores.
- **Rollout.** Ships in the plugin's normal semantic-release cadence; every consuming
  project picks it up automatically on next plugin update via the Jacquard Labs
  marketplace, with no action required — this is precisely what "capture requires no
  new workflow step" means at the distribution level, not just the per-session level.
  Because the blast radius is every Bash call project-wide, the hook must degrade
  silently and fail closed on *doing nothing*, mirroring `hooks/gate-reminder.sh`'s
  existing convention: missing `git`/`jq` → no-op; no armed branch → no-op; any
  internal error → no-op, never a `deny`/`ask` decision, never added latency a user
  would notice, never a network call (the plugin's existing local-only posture).
- **How we'll know it's working or failing.** This is a local CLI plugin with no
  server and no log/metrics backend to check — there is no CloudWatch or Datadog
  equivalent here, and this section shouldn't invent one. The real signals: the
  evidence log itself, directly inspectable (`jq . .studious/evidence/<slug>.jsonl`)
  during and after a real story; a build-phase test suite that exercises **both**
  capture paths concretely — an interactive Bash call and a Bash call made from inside
  an actual Task-dispatched subagent — rather than resting dogfood item zero's answer
  on the docs citation above; and issue #97's own dogfood plan (studyengine #210, then
  #209) as the real-world validation loop, governed by its own stated kill rule:
  *"after 3–4 dogfooded stories, if receipts never changed a gate verdict or a human
  decision, stop."* This story does not need to satisfy that kill rule — it's the
  measure for the epic's thesis, not this story's acceptance — but the design should
  make the kill rule checkable, which passive, low-cost capture does by construction:
  nothing here forces continued investment if the receipts turn out not to matter.

## Open questions

- **Exact `tool_response` field for Bash exit status.** Confirmed via
  `code.claude.com/docs/en/hooks` that `PostToolUse` fires for Bash calls and carries
  `agent_id`/`agent_type` when inside a subagent; not confirmed from that source is the
  precise field name inside `tool_response` carrying the Bash tool's exit status.
  Needs a short build-time spike — log one raw hook invocation and inspect the payload
  — rather than a guess baked into the hook script.
- **Allow-list durability across an unrelated project's toolchain.** The pattern list
  is generic by design, but `studyengine` (the named first dogfood target) may use test
  or check runners this list doesn't cover. Expected to need at least one iteration
  after the first real dogfood run, not a one-shot perfect design — consistent with
  issue #97's own framing of this as a v0 to be tuned, not a finished spec.
  `handback-skill`/`gates-cite-evidence` should keep an eye out for silently-missed
  verification during their own builds, and this list should be revisited if they see
  it.
- **Epic-level (not story-level) verification commands.** `/work-through`'s epic-level
  `/gate-audit`/`/gate-acceptance` dispatches run in the epic integration worktree, on
  the epic branch, not any single story's branch. The epic branch never receives a
  `work-set --branch` entry — only individual story branches do — so the armed check
  correctly treats it as unarmed and the hook no-ops there by construction. Flagged
  here as an intentional consequence of the design, not a gap, since it is easy to
  mistake for one on first read.
- **PRODUCT.md's parked-item line.** Flagged under Problem & persona: this story is the
  re-entry of a PRODUCT.md-parked item. Confirm the follow-up to edit PRODUCT.md's
  "What we're NOT building" section is filed rather than silently forgotten once this
  epic lands — that edit is a proposal for a human to apply, not something any worker
  or gate in this flow writes directly.
