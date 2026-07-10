# Audit coverage seams — infra, pipeline, ops readiness, tests, periodic security, perf

**Date:** 2026-07-09
**Status:** Approved design, pre-implementation

## Problem

The audit/review roster covers application code deeply and its operational shell not at
all. A coverage sweep of the 15-agent roster (2026-07-09) mapped every gate-time and
periodic lane against what a changeset can contain and found six seams:

1. **IaC misconfiguration — no owner.** Nothing reviews Terraform, CDK, CloudFormation,
   K8s manifests, Helm, or Dockerfiles. security-auditor's eight dimensions are
   app-shaped (OWASP, routes, sessions); of infra it genuinely owns only secrets and
   PII-in-logs. A wildcard IAM policy, a 0.0.0.0/0 security group, or a root-user
   Dockerfile passes `/gate-audit` unexamined.
2. **CI/CD workflow changes — no owner.** A `.github/workflows/*.yml` diff runs with
   repo secrets and write tokens; nobody checks for workflow injection
   (`${{ github.event.* }}` in `run:`), `pull_request_target` footguns, unpinned
   third-party actions, or over-broad `permissions:`. Bites every repo, including this
   one.
3. **Operational readiness — no gate asks "can we operate it".** The design-doc
   contract has no rollout/rollback/migration/observability section; the one migration
   question that exists (`agents/review-architecture.md`) runs periodically on main —
   after merge. A feature can pass all four gates with a table-locking migration, no
   log line on its failure path, and no rollback story.
4. **Test adequacy — no gate-time owner.** `review-codebase-health` tracks coverage
   trend periodically, but no gate auditor checks whether *this changeset's* tests are
   adequate; code-auditor's scope list omits tests entirely.
5. **Periodic security — gate-only coverage.** `/deep-review`'s five lanes contain no
   security pass, and the gate auditor only ever sees changesets, so a pre-existing
   vulnerability in unchanged code is permanently out of every auditor's scope.
6. **Backend performance — split thin.** architecture-auditor has one bottleneck
   bullet, frontend-reviewer covers render/bundle, code-auditor runs linter PERF
   selects; a missing index or hot-path O(n²) on a non-structural backend change falls
   between lanes.

## Decisions (settled during brainstorming)

| Question | Decision |
|----------|----------|
| Packaging | One spec, one PR, branch `feat/audit-coverage-seams` |
| IaC + pipeline ownership | One combined **infra-auditor** (`opus`) — not two agents, not folded into security-auditor |
| Test adequacy ownership | New **test-auditor** (`inherit`) — not a code-auditor scope extension |
| Periodic security shape | New **review-security-health** (`opus`) — not a whole-repo scope override of security-auditor |
| Ops readiness shape | Threaded through existing seams (contract row + architecture-auditor dimension + acceptance question); no new gate, no new pre-mortem lane |
| Backend perf | Ownership documented in existing agents; no perf-auditor |

## Design

### 1. `agents/infra-auditor.md` (new) — IaC and pipeline risk at gate time

`model: opus` (blast-radius judgment is security-adjacent); tools Read, Grep, Glob,
Bash; full prompt-contract compliance (injected blocks + addendum). Five dimensions:

- **IaC misconfiguration** — wildcard IAM actions/principals, public network exposure,
  missing encryption at rest/in transit, missing deletion protection/backup on stateful
  resources.
- **Change blast radius** — a diff that forces destroy/replace of a stateful resource,
  state-migration hazards, changes whose failure mode is an outage rather than a bug.
- **CI/CD pipeline risk** — workflow injection sinks, `pull_request_target` +
  PR-head checkout, unpinned third-party actions (tag instead of SHA), over-broad
  `permissions:`/token scope, secrets exposed to fork-triggered runs.
- **Container hygiene** — root user, unpinned/mutable base images, secrets baked into
  layers, ADD-from-URL.
- **Cost and availability signals** — single-AZ/single-replica stateful services,
  unbounded log retention, oversized defaults. Mostly Track-tier; calibrate, don't pad.

Lane boundary, stated in both prompts: security-auditor keeps **secrets everywhere**
(including IaC files and git history) and app-layer OWASP; infra-auditor owns
**misconfiguration and pipeline risk**; each escalates cross-lane finds, neither hunts
the other's lane.

Routing in `/gate-audit`: per-changeset skip, same shape as the frontend trio — skip
(with an explicit note) when the changeset touches no IaC, container, deploy, or
workflow files. Presence in the diff is decisive, so no project-level condition is
needed. When ambiguous, run — default to running, not skipping.

### 2. `reference/infra-checklist.md` (new) — lookup data

Mirrors `reference/security-checklist.md`'s shape and contract: not a detection crutch,
but the lookup data a capable model won't recall verbatim — per-tool misconfiguration
signatures (Terraform, CDK, CloudFormation, K8s, Docker/Compose, Helm, GitHub Actions),
the workflow-injection sink list, and a per-tool defaults table (what "missing" means
per tool, the way the security checklist's per-stack table sets CSRF/header
expectations). Severity stays reachability/exposure-gated. Depth lives here; the agent
points at it.

### 3. Operational readiness — contract row, not a new gate

Three small edits thread the question through existing seams:

- **`reference/design-doc-contract.md`** gains a required **Operational readiness**
  row: migration plan with rollback, rollout strategy, and how you'll know the feature
  is working/failing in production. "N/A — no operational surface" with a one-line
  reason satisfies it (a local CLI tool shouldn't fabricate an ops plan). Like the
  Open-questions row, it maps to no numbered product question — it seeds the technical
  pre-mortem lane and gate-time verification. `templates/design-doc.md` gains the
  matching scaffold section.
- **`agents/architecture-auditor.md`** gains a **data & migrations** dimension:
  migrations reversible, compatible with the previous deploy's still-running version,
  backfill-safe. This promotes to gate time the question `review-architecture`
  currently asks only after merge (both keep it; the periodic pass watches drift).
- **`commands/gate-acceptance.md`** Part 3 gains one gate-specific question alongside
  "One complaint": **Operability** — does the branch deliver what the design doc's
  Operational readiness section committed to? `commands/gate-design-review.md` Part 3
  seeds the technical pre-mortem lane from the section's content.

### 4. `agents/test-auditor.md` (new) — test adequacy at gate time

`model: inherit` (rule-based); tools Read, Grep, Glob, Bash; joins `/gate-audit`'s
backend group; skipped (with a note) for changesets touching no code — docs-only,
config-only. Checks are **static** — the read-only posture forbids running the suite:

- New or changed behavior in the diff carries tests exercising it.
- Assertions check real outcomes — not snapshot-only, not smoke-only, not
  assertion-free "it runs" tests.
- Bug-fix changesets carry a regression test reproducing the bug.
- No tests deleted, skipped, `.only`'d, or weakened to make the diff pass — this one
  escalates a tier; it is the audit-evasion posture applied to tests.
- CLAUDE.md's documented test conventions are authoritative; a documented deviation is
  honored, an undocumented one is a finding.

code-auditor's "Does NOT check" list gains test adequacy → test-auditor.

### 5. `agents/review-security-health.md` (new) — periodic security lane

`model: opus`; tools Read, Glob, Grep, Bash, Write; periodic-family shape (writes
exactly one file: its report). Owns the whole-repo posture pass the gate can never see.
Split with gate-time security-auditor mirrors the codebase-health ↔ code-auditor split,
stated in both prompts — with one deliberate asymmetry: Critical/High findings are
reported **per instance**, not aggregated, because unchanged-code vulnerabilities have
no other reporting path. Medium/Low aggregate with trend. Also: secrets-in-history
sweep, security-config posture (headers, session, CORS against the detected stack).
Consults `reference/security-checklist.md` — zero rubric duplication.

**Dependency-CVE counting stays with `review-codebase-health`** — its "Known
vulnerabilities" metric key is a dashboard contract; this lane defers to it explicitly
rather than double-reporting.

Report: `docs/studious/security-reviews/YYYY-MM-DD-security-review.md` (create the
directory if needed). Emits canonical three-tier severity directly — no
severity-rubric row, matching the periodic family.

`/deep-review` goes five lanes → six: `security` area keyword and table row, "all
five" → "all six" throughout, dashboard rows for the metrics this agent's report
emits (Critical/High finding count, exposed-secrets count, security-config-violation
count), and metrics-history keys to match. `/studious-init` scaffolds
`docs/studious/security-reviews/`.

### 6. Backend performance — close the seam by assignment

No new agent. architecture-auditor's bottleneck bullet expands to explicitly own
concrete runtime bottlenecks in the changeset — N+1 queries, hot-path algorithmic
complexity, chatty sequential I/O, missing index on a newly queried column.
code-auditor's "Does NOT check" list names runtime performance → architecture-auditor.
frontend-reviewer keeps render/bundle. Three sentences total.

## Cross-cutting

- **Prompt contract**: all three new agents carry the shared-contract block reference
  and their own addenda, same as the existing set; the contract-sharing count in
  project CLAUDE.md ("The 14 review/audit agents") becomes 16 — the verified carrier
  count (13 current `Shared contract` carriers + 3 new; the documented 14 had already
  drifted).
- **`reference/severity-rubric.md`**: rows for infra-auditor (Critical, High →
  Critical; Medium → Important; Low → Track) and test-auditor (Critical → Critical;
  High, Medium → Important; Low → Track).
- **`commands/gate-audit.md`**: test-auditor joins the backend group, infra-auditor
  gets a conditionally-routed section; auditor numbering and the summary's category
  list gain tests + infrastructure.
- **Counts and rosters**: README's two "up to 8" auditor counts become "up to 10" and
  its always-run enumeration gains tests; the periodic-review count 5 → 6;
  CONTRIBUTING's model-assignment lists add infra-auditor + review-security-health
  under `opus`, test-auditor under `inherit`; `commands/deep-review.md` description
  updates.
- **CI**: `.github/workflows/gate-audit-pr.yml` needs no behavioral change — routing
  degrades the same way locally and in CI; only its skip-comment's stale "6-7-agent"
  count becomes "up-to-9-agent". New/edited markdown must pass `markdownlint-cli2` and
  `scripts/check_references.py`.

## Out of scope

- A periodic infra-health lane — revisit if infra-auditor findings show whole-repo
  drift the diff-scoped gate can't see.
- A perf-auditor, and any runtime profiling — the read-only posture holds.
- An `operational` pre-mortem lane — operational failure modes stay in the `technical`
  lane, verified by `/gate-audit`.
- Any auto-fix or state-modifying behavior — recommend-only holds for all three new
  agents.
- Backfilling existing installs' report directories — review-security-health creates
  its directory on first write, same as the pre-mortem register.

## Open questions

- The exact file-signal list for infra routing (extensions, paths, filenames) —
  finalize at implementation; keep the list in `commands/gate-audit.md` only, so it
  can't drift across files.
- Whether the deep-review dashboard's new security rows need a metrics-history
  migration note — resolve against `docs/studious/reviews/metrics.jsonl`'s "new key →
  'new'" behavior at implementation (expected: no migration needed).
