# Design: Unify contract-block injection to one verbatim resolver; harden the runtime fixture

**Date:** 2026-07-09
**Status:** Design, pre-implementation
**Epic:** gate-ledger-robustness — "Retire the debt the M1 finale audit and the
2026-07-07 cross-project prompt audit surfaced"
**Story:** contract-injection-unify
**Source:** [#110](https://github.com/jacquardlabs/studious/issues/110),
[#111](https://github.com/jacquardlabs/studious/issues/111)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team)
building features with Claude Code who wants product judgment and quality gates
woven into the build, without heavy process."** PRODUCT.md's second critical user
journey is that developer running `/gate-audit` on a feature branch and getting six
parallel auditors' judgment, security included. `/work-through` (epic driver) runs
that same journey unattended, at epic scope, for every story in an approved plan —
PRODUCT.md's "one repo, entrypoints per scope" principle names it as the same
discipline "entered" at a higher altitude, not a different product.

The 2026-07-07 contract-injection story (`docs/superpowers/specs/2026-07-07-contract-injection-design.md`,
issue #88) made the four fan-out gate commands (`gate-audit.md`, `deep-review.md`,
`gate-design-review.md`, `gate-acceptance.md`) the single assembly point for the
shared posture contract in `reference/prompt-contract.md`: each reads the file once
via `${CLAUDE_PLUGIN_ROOT}` and stamps its four blocks — injection-defense,
read-only/diff-scope, output-row schema, calibrate-don't-suppress closer — verbatim
into every dispatched agent's prompt. That story's own finale audit (PR #108) caught
what it missed: `workflows/epic-driver.js`, which fans the same six auditors and the
premortem-auditor out itself on the fully-automatic `/work-through` path (subagents
cannot spawn subagents, so the driver bypasses `gate-audit.md` to keep its parallel
lanes and died-lane detection), never adopted the inversion. Its `CONTRACT` const
still injects a **pointer** — "read `reference/prompt-contract.md` from the plugin
root" — not the blocks themselves.

That leaves one file with three resolution mechanisms, as #110 names them: (a) the
four commands, verbatim push via `${CLAUDE_PLUGIN_ROOT}`; (b) the 13 agents' own
anchored Glob fallback for standalone invocation; (c) the driver's runtime pointer.
The security consequence is concrete: **on the fully-automatic epic path, a
driver-dispatched auditor — security included — receives no inline injection-defense
posture.** It must resolve a file at runtime and may proceed without it if that
resolution fails or is skipped under load. The command path #88 hardened is strictly
stronger than the path most epics actually run under, which inverts the point of
hardening it. #111 names the adjacent gap: the only test locking any of this
(`tests/python/test_contract_injection.py`) asserts the driver's source *text* cites
the contract correctly — it never executes the driver's prompt assembly, so a
regression that drops the actual block at dispatch time (as opposed to the citation)
would pass the suite clean.

## Proposed design

**Collapse the driver's resolution into the same push mechanism the commands already
use, instead of a second, weaker one.** `commands/work-through.md` becomes the
assembly point for the automated path exactly as the four gate commands are for the
supervised one: before invoking the Workflow tool, it reads
`${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` once (same anchored resolution,
same Glob fallback if it doesn't substitute) and hands the four blocks, verbatim, to
`epic-driver.js` as part of `args` — alongside `epic`, `phases`, `repoRoot`,
`defaultBranch`, which the command already assembles this way today.

Inside the script, the `CONTRACT` const stops being a hardcoded sentence that tells an
agent where to go looking, and becomes the text `work-through.md` just handed it. The
three dispatch sites that already interpolate `${CONTRACT}` — `auditRound`'s
per-auditor prompt, `finaleAuditRound`'s per-auditor prompt, and the finale premortem
dispatch — are unchanged at the call site; what flows through `${CONTRACT}` changes
from a pointer to the actual blocks. No runtime-pointer resolution remains anywhere on
the automated path: the last hop from "where is the contract" to "here is the
contract" happens once, at the orchestrating LLM layer, before any Task dispatch for
that invocation exists.

**Fail closed on a missing contract.** If `input.contract` arrives empty or missing —
a stale invocation, a dropped field in a future edit to `work-through.md`, any break
in the handoff — the driver must refuse to dispatch an unguarded auditor rather than
silently reverting to the old pointer behavior or, worse, an empty string spliced into
the prompt. This is the behavior the hardened fixture below exists to prove, and it is
what makes "no runtime-pointer resolution remains" a property the driver enforces
rather than one that merely happens to hold today.

**Three mechanisms collapse to two, and the remaining split is deliberate.** After
this change, mechanisms (a) and (c) are the same mechanism wearing two skins: an
orchestrating LLM — a gate command's prose, or `work-through.md` immediately before
it calls the Workflow tool — reads `reference/prompt-contract.md` once and stamps its
four blocks verbatim into every Task prompt it is responsible for, whether it builds
that prompt directly or hands the text to code (`epic-driver.js`) that builds the
prompt on its behalf. That is one resolution mechanism at the orchestration layer,
regardless of whether the dispatching layer underneath it is prose or a script.

Mechanism (b) — each of the 13 agents' own `${CLAUDE_PLUGIN_ROOT}` Glob fallback —
stays, and stays deliberately. It is not a competing way to resolve the *same* call
site; it is a narrower backstop for the case where an agent is invoked with **no**
orchestrator upstream at all (an ad hoc direct invocation the fan-out commands and the
driver don't cover). Removing it would make a future direct-invocation path fail
open — an unguarded auditor with no posture and no self-heal — instead of fail safe.
Keeping it costs nothing on the paths this story hardens (the fallback only fires when
its "if you were invoked directly with no such block present" precondition holds,
which after this change is never true on the command or driver paths) and keeps a
mis-invoked agent from running with zero defense. This satisfies the acceptance
criterion by explicit justification rather than by forcing a single mechanism onto a
case it was never meant to cover.

**Harden the runtime fixture (#111).** `test_contract_injection.py` today only proves
that the driver's source text cites the contract with the right anchoring
(`test_driver_defines_a_plugin_root_contract_injection`,
`test_driver_audit_and_premortem_dispatches_inject_the_contract`) — string assertions
against the file, never an execution. Both tests currently encode the *old* claim
("the driver has no hands to read a file... it cannot stamp the blocks in verbatim")
that this story overturns; they are replaced, not merely edited, by a fixture that
actually **runs** the driver's prompt-assembly logic for the three fan-out dispatch
sites with a real `reference/prompt-contract.md` payload and asserts the resulting
dispatch prompt contains the actual block text end-to-end — not a citation of where
to find it. The same fixture asserts the counter-case: given a dropped/empty contract
payload, the assembly either raises before any dispatch prompt is built, or the
prompt demonstrably lacks the block — proving the fixture would have caught the
regression #110 found, not merely documenting that the regression once existed. It
requires no live model: unlike the golden-fixture harness
(`scripts/run_gate_audit_fixtures.py`) that exercises a full `/gate-audit` run headless
via `claude -p`, this fixture exercises only the driver's own prompt-construction, a
property that holds independent of any agent's actual response.

## User journey

This touches PRODUCT.md's critical journey #2 (**per-feature gate flow**) at the audit
step, run at epic scope instead of story scope. Before this change, on the
`/work-through` path:

1. The user approves an epic plan; `/work-through` drives it unattended.
2. For each story reaching its audit gate, `epic-driver.js` fans six auditors and,
   at the finale, a seventh (premortem-auditor) out directly.
3. Each dispatch prompt carries a sentence telling the auditor to go read
   `reference/prompt-contract.md` from the plugin root at runtime.
4. Whether that resolution actually happens, and happens before the auditor starts
   judging, is not verified anywhere the user or CI can see — it rests on the
   dispatched agent's own diligence, unlike the identical audit run through
   `/gate-audit` directly, where the four blocks already sit inline in the prompt.

After:

1. The user approves an epic plan; `/work-through` drives it unattended, unchanged
   from the user's vantage point.
2. Before calling the Workflow tool, `work-through.md` reads
   `reference/prompt-contract.md` once and hands its four blocks to the script as
   data.
3. `epic-driver.js` stamps those same four blocks into every auditor and
   premortem-auditor dispatch it builds — per-story and at the finale — exactly as
   `/gate-audit` stamps them into its own dispatches.
4. A security-relevant finding surfaced by a driver-dispatched auditor now rests on
   the same inline posture a supervised `/gate-audit` run gives that auditor, closing
   the asymmetry #110 named. No step the user takes changes; the difference is a
   failure mode they could not previously see, removed.

## Out of scope

- **The four blocks' content or wording.** This story moves how they reach the
  driver's dispatches, never what they say. Rewording the shared posture is a
  separate change under a separate gate.
- **The 13 agents' own Glob-fallback line.** Kept as-is and unedited — see "Proposed
  design" for why it remains a deliberate, narrower backstop rather than a resolution
  mechanism this story folds in.
- **`reference/security-checklist.md`, `severity-rubric.md`, `idioms/<lang>.md`.**
  Large, on-demand rubrics owned by a single agent each, not the shared four-line
  posture stamped across all thirteen — the prior contract-injection design already
  recorded these as a separate concern, and nothing here revisits that call.
- **`scripts/run_gate_audit_fixtures.py` and its live-model golden fixtures.**
  Untouched. The new executed fixture this story adds is a separate, model-free check
  of the driver's own prompt-assembly, not a rewrite of the `/gate-audit` behavioral
  harness.
- **Any change to the driver's scheduling, retry-cap, merge, or verdict logic**
  (`runGate`, `auditFanIn`, park/merge semantics) beyond what carries the contract
  text. This story touches contract resolution only.
- **The fallback (prompt-orchestrated, no-Workflow-tool) driver's scheduling
  semantics.** It already dispatches through the real gate commands, which self-inject
  under #88; this story does not change that path's scheduling, only confirms (an
  open question below) whether it needs an explicit contract-read step of its own.
- Per PRODUCT.md's "What we're NOT building," this remains recommend-only:
  the driver still only judges and reports; nothing here grants it authority to fix.

## Alternatives considered

**Give the script its own file read.** Resolve the plugin root and read
`reference/prompt-contract.md` directly inside `epic-driver.js` at execution time,
the way a Node CLI script normally would. Rejected: the script's own existing comment
states plainly it "has no hands to read a file," and nothing in this repo — no
`fs`/`require` call anywhere in `workflows/`, no documented Workflow-tool capability —
shows the script can perform filesystem I/O; the one thing consistently true today is
that the invoking command assembles `args` and hands them over as data. Routing the
contract text through `args`, the same channel `epic`/`phases`/`repoRoot` already use,
needs no new, unverified capability.

**Strengthen the agents' own Glob fallback and let the driver lean on it instead of
injecting anything itself.** Rejected: this is the asymmetry #110 flagged, just moved
one layer down — every driver-dispatched auditor would pay a filesystem search per
dispatch, and there would still be no proof, anywhere testable, that the posture
reached the prompt before the auditor started judging. The fallback is deliberately a
last resort for an agent an orchestrator failed to reach, not a substitute for
orchestrator-side injection.

**Duplicate the four blocks as a second hardcoded literal inside `epic-driver.js`.**
Rejected: two copies of the same four blocks drift — precisely the failure
`reference/prompt-contract.md` exists to prevent, and precisely the alternative the
prior contract-injection design already rejected for the agent files. A driver-local
copy would be a third place the blocks live, not a second; every future wording change
to the contract would need to remember this file too.

## Open questions

- **How the hardened fixture executes the driver's prompt-assembly.** The Workflow
  tool's module-loading and sandboxing semantics (which globals it injects, whether
  the script runs as an ES module, a wrapped function body, or something else) are not
  documented anywhere in this repo, and the tool's own schema is not available to
  introspect from this worktree. Two build-time paths: (a) confirm the harness's
  execution model first and write the fixture directly against `epic-driver.js`; or
  (b) refactor the three dispatch-prompt-building call sites into small,
  explicitly-parameterized pure functions that any plain Node process can execute
  regardless of how the real harness loads the file, and fixture those. (b) is the
  safer default — it doesn't depend on undocumented harness internals — but the choice
  belongs to the build phase, not this doc.
- **The exact shape of `args.contract`.** A single concatenated string of the four
  blocks, or an object keyed by block name. Cosmetic; match whatever convention
  `input.epic`/`input.phases` already sets during build.
- **Whether the fallback driver needs its own explicit contract-read line.** It
  already dispatches via the real gate commands (which self-inject per #88), so no
  change looks necessary — worth a one-line confirmation in `commands/work-through.md`
  during build rather than an assumption here.
