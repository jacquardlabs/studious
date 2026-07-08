# Design: Invert contract layering — commands inject contract blocks into dispatches

**Date:** 2026-07-07
**Status:** Design, pre-implementation
**Story:** contract-injection (epic: gate-runtime-correctness)
**Source:** [#88](https://github.com/jacquardlabs/studious/issues/88)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team)
building features with Claude Code who wants product judgment and quality gates woven
into the build, without heavy process."** Their job-to-be-done is running a Studious
gate — `/gate-audit`, `/deep-review`, `/gate-design-review`, `/gate-acceptance` — in
their own repository and getting the audit the product promises. The secondary persona,
**"the maintainer dogfooding Studious on Studious,"** owns the CI harness that is
supposed to prove the gates work.

Today that promise silently breaks in a real consuming project. PRODUCT.md's principle
**"Grounded in shared context — every gate and review reads from the same three context
docs, so judgments are consistent rather than per-prompt improvisation"** extends, in
the implementation, to a shared *posture* contract: the injection-defense rule, the
read-only/diff-scope convention, the output-row schema, and the calibration closer live
once in `reference/prompt-contract.md`, and all 13 audit/review agents cite that file
by bare relative path with "consult it, don't restate it." But a dispatched agent
executes with its working directory set to the consuming project, and
`reference/prompt-contract.md` lives in the plugin install directory, not the user's
repo. Nothing in the agent prompt tells it where the plugin is. So the agent either
burns turns hunting the file via Glob or — worse — proceeds without the shared posture
and schema at all.

The failure is invisible because the one place the file *does* resolve is CI:
`scripts/run_gate_audit_fixtures.py` symlinks `reference/` into every fixture repo
before invoking the gate. Green fixtures therefore validate a world users never see. A
gate that drops its injection-defense preamble in a real repo will still pass its
golden fixtures. This is precisely the silent-degradation class `/studious-doctor`
exists to catch, reaching the gates themselves.

## Proposed design

Invert the layering: move contract assembly from the agent (pull) to the orchestrating
command (push).

Today the agent is responsible for fetching the shared contract at audit time. Under
the new design, the **fan-out gate command is the single context-assembly point.**
Before it dispatches its agents, the command reads `reference/prompt-contract.md` once
from the plugin install — the same `${CLAUDE_PLUGIN_ROOT}` resolution that
`/studious-init` and `/studious-doctor` already rely on, with the same Glob fallback
when it doesn't substitute — and stamps the four contract blocks verbatim into every
Task dispatch prompt, right alongside the explicit changeset scope the command already
hands each agent. The agent receives the full shared posture inline and never touches
the plugin's filesystem to get it.

The agent files, in turn, shrink. Each drops its bare-relative citations of
`reference/prompt-contract.md` and keeps only what carries real domain information: its
own dimension enum, its severity mapping, and the short agent-specific addendum that
today follows each citation (a missing tool, a domain caveat, "no dev server"). Because
an agent may still be invoked directly rather than through a command, each keeps a
single defensive fallback line naming where the posture would otherwise come from — so a
standalone run degrades to a known path rather than to nothing.

What the user experiences does not change in the happy path they can see — the report
looks the same. What changes is that it now *arrives the same way in their repo as it
does in CI*: the gate carries its own posture, so the judgment is consistent rather
than dependent on a filesystem coincidence. The design leans on three PRODUCT.md
principles: **"Grounded in shared context"** (the shared posture now actually reaches
every agent), **"Code owns bookkeeping; prompts own judgment"** (context assembly is
orchestration, so it belongs to the command, not smeared across 13 agent prompts), and
**"Stay in your lane"** (agents shrink to their single domain concern; the shared
scaffolding moves to the one orchestrator that owns fan-out).

The acceptance test inverts with the layering. `run_gate_audit_fixtures.py` drops its
`reference/` symlink, and the harness asserts that a dispatched agent still receives the
injection-defense rule, diff-scope convention, output-row schema, and closer in its
prompt — proving the contract resolves without the symlink, in the world the user
actually runs in.

## User journey

This touches PRODUCT.md's critical journey #2 (**per-feature gate flow**) and #3
(**per-project health loop**), at the dispatch step inside each.

Before, in a real consuming project:

1. The developer runs `/gate-audit` on their feature branch.
2. The command fans out six auditors, each pointed at `reference/prompt-contract.md`.
3. Each auditor, running with cwd = the developer's repo, cannot resolve that path.
4. The auditor hunts (wasted turns) or proceeds without the shared posture — no
   injection-defense preamble, no output-row schema. The report may still look
   plausible, so the degradation goes unnoticed.

After:

1. The developer runs `/gate-audit` on their feature branch.
2. The command resolves the plugin root, reads the contract once, and injects the four
   blocks — plus the changeset scope it already passes — into each auditor's dispatch.
3. Each auditor receives the full shared posture inline and audits with it, with no
   filesystem dependency on the plugin's `reference/`.
4. The report reflects the shared contract deterministically, identically to CI.

No step the user takes changes. The one visible difference is the absence of a failure
mode they could not previously see. The same inversion applies wherever a command fans
out contract agents — `/deep-review`'s five reviewers, `/gate-design-review` and
`/gate-acceptance`'s product-reviewer.

## Out of scope

- **The other bare-relative reference citations.** `reference/security-checklist.md`,
  `reference/severity-rubric.md`, and `reference/idioms/<lang>.md` are large rubrics
  read on demand by a single owning agent, not shared four-line posture stamped across
  all 13. Injecting them wholesale into every dispatch would bloat every prompt for no
  gain. Issue #88 lists them under the *minimal* fix (anchor on `${CLAUDE_PLUGIN_ROOT}`);
  they are a separate concern from this story's contract inversion and stay as they are
  here.
- **Changing the content of the contract.** The four blocks move; their wording is not
  this story's subject. Rewording the posture is a different change under a different
  gate.
- **The false-positive verification step.** Issue #88 notes the single assembly point
  would later be a natural home for a false-positive verification pass. That is a
  benefit this design *enables*, not a deliverable it *includes*.
- **Broader CI-fixture rework.** Only the `reference/` symlink is removed, and only to
  prove the injection resolves without it. The rest of the fixture harness is untouched.
- Per PRODUCT.md's "What we're NOT building," this remains recommend-only and
  auto-applies nothing — the gate still only reports, and no agent gains authority to
  fix.

## Alternatives considered

**Minimal fix — anchor every citation on `${CLAUDE_PLUGIN_ROOT}`.** Leave the pull model
and rewrite each agent's `reference/prompt-contract.md` to
`${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md`. Rejected: it depends on
`${CLAUDE_PLUGIN_ROOT}` substituting inside *subagent* context, which #88 only confirms
for commands and hooks, not agent files — so it may re-create the same silent gap it
means to close. It also keeps 13 fragile citations and a filesystem read per agent per
dispatch, and it leaves no single point where the shared posture is assembled. It is
strictly less than the inversion for the same edit surface.

**Inline the contract into every agent.** Copy the four blocks verbatim into each of the
13 agent files, deleting the shared file. Rejected: 13 copies drift, which is exactly
the failure `reference/prompt-contract.md` was created to prevent — a single-source-of-
truth defeated by duplication. It also bloats every agent with scaffolding that is not
its domain.

**Ship the symlink into consuming projects.** Have `/studious-init` create the same
`reference/` symlink the CI harness does. Rejected: it writes plugin-internal
structure into the user's repository, cannot be kept current as the plugin updates, and
pollutes a tree Studious's principles say it must not modify.

The inversion is chosen because it makes the runtime path match the CI path, removes the
dependency on unverified subagent substitution, keeps the single source of truth, and
concentrates fan-out scaffolding in the one orchestrator that owns it.

## Open questions

- Do `/gate-design-review` and `/gate-acceptance` — which dispatch product-reviewer —
  resolve `${CLAUDE_PLUGIN_ROOT}` as reliably as `/gate-audit` and `/deep-review`? #88
  confirms substitution for the latter two; the former two must be checked during build,
  with the same Glob fallback wired if not.
- What is the minimal shape of the standalone-invocation fallback line an agent keeps —
  enough that a directly-invoked agent still reaches the posture, without re-introducing
  the bare-relative dependency this story removes?
- Should the injected block be the full verbatim contract text or a compacted form? The
  acceptance criterion is that the four named elements are present in the prompt; the
  build should confirm verbatim injection is not prohibitively large before compacting.
