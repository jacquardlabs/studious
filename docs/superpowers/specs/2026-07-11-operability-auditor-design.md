# Operability auditor — failure signal, resilience, and runtime hygiene at gate time

Date: 2026-07-11
Origin: fleet gap analysis (12-factor sweep) — "do we need a logging and observability
auditor?" Related decisions filed the same day: [#120](https://github.com/jacquardlabs/studious/issues/120)
(success-metrics contract row), [#121](https://github.com/jacquardlabs/studious/issues/121)
(PII checklist signatures), [#122](https://github.com/jacquardlabs/studious/issues/122)
(wire-contract compat bullet), licensing scope comment on
[#64](https://github.com/jacquardlabs/studious/issues/64).

## Problem

After #114, operability is covered at two altitudes and missing at the third:

- **Design time** — the design-doc contract's Operational readiness row requires naming
  the migration/rollback plan, rollout strategy, and working/failing signals (logs,
  metrics, alarms). `/gate-design-review` seeds the technical pre-mortem lane from it.
- **Acceptance time** — `/gate-acceptance`'s Operability item asks whether the branch
  delivered what that section committed.
- **Gate time** — only the migration/rollback slice is specialist-verified
  (architecture-auditor, data & migrations lane). No auditor reads the changeset for
  the rest.

The acceptance check is main-context judgment against what the doc *promised* — no
shared prompt contract, no severity rubric, no diff-scoped evidence discipline — and it
is weakest exactly when the design doc said little or the flow skipped the doc. Nobody
owns: new failure paths silent to an operator, outbound calls without timeouts, retries
without backoff or idempotency, in-memory state that breaks horizontal scaling,
hardcoded environment-specific config, missing graceful shutdown.

Mapped against 12-factor: factors II (dependencies), V (build/release/run), and XII
(admin/migrations) have owners; III (config), VI (stateless processes), IX
(disposability), and XI (logs) are uncovered — and they cluster into one concern:
*will this survive production, and will anyone know when it doesn't.*

## Decisions (settled during brainstorming)

- **Operability auditor, not a logging auditor.** One lane, five dimensions of one
  concern — same shape as infra-auditor (IaC + blast radius + CI + containers).
- **Full lane + doc cross-check.** Chosen over two alternatives: (a) narrow
  signal-and-resilience only — rejected because the 12-factor hygiene checks share the
  same skip rule, evidence style, and severity anchor, and splitting them defers known
  gaps for no isolation win; (b) full lane without the doc cross-check — rejected
  because the cross-check mirrors architecture-auditor's existing migration-commitment
  check (one bullet, no new machinery) and closes the "committed but silently not
  shipped" hole at the altitude with specialist rigor.
- **Build now, not evidence-deferred.** #118 deferred a *periodic* infra lane because a
  gate lane already covered the concern at another altitude. Here no specialist exists
  at any altitude — the seam is structural, not speculative.
- **Periodic ops-health review stays deferred** on the #118 pattern (see Out of scope).
- **`model: opus`.** Failure-mode reasoning is judgment work; matches infra-auditor and
  the CONTRIBUTING stakes rule.
- **`/gate-acceptance` unchanged.** Its Operability item remains the whole-branch
  judgment; the audit lane supplies diff-scoped evidence underneath it.

## Design

### 1. `agents/operability-auditor.md` (new) — the gate lane

Frontmatter: `name: operability-auditor`; description "Operability auditor. Reviews a
changeset for production failure signal, resilience, and 12-factor runtime hygiene.
Diff-scoped and gate-invoked (/gate-audit); skipped when the changeset touches no
runtime surface."; `tools: Read, Grep, Glob, Bash`; `model: opus`.

Carries the shared prompt contract (injected posture block, fallback read from
`reference/prompt-contract.md`) — 17th carrier.

**Lane edges (escalate, don't hunt):**

- code-auditor keeps callsite error-handling *correctness* — swallowed exceptions,
  propagation consistency, cleanup. Operability owns whether a failure is *visible and
  recoverable as a system property*. The same empty catch block can be both: code-auditor
  flags the swallow; operability flags it only when it silences the sole signal for an
  alert-worthy condition.
- security-auditor keeps secrets and PII everywhere, including in log statements.
- architecture-auditor keeps backend performance (N+1, hot paths) and data/migrations.
- infra-auditor keeps IaC, CI/CD, and container hygiene. Deploy-manifest shutdown
  settings (k8s `terminationGracePeriodSeconds`, `preStop`) are infra's; application
  signal-handling code is operability's.

**Five dimensions** (output-row `dimension` enum: failure-signal / resilience /
runtime-hygiene / concurrency / ops-commitment):

1. **Failure signal** — new failure paths silent to an operator; log-level misuse
   (errors at debug, noise at error); request-scoped logs missing correlation context
   the codebase otherwise carries; unstructured log lines in a structured-logging
   codebase; alert-worthy conditions the diff introduces (data loss, auth-failure
   spikes, queue backlog) with no emitted signal.
2. **Resilience** — outbound calls without timeouts (per-ecosystem defaults in the
   checklist — e.g. Python `requests` has none); retries without backoff or caps;
   missing graceful degradation when a non-critical dependency fails; unbounded
   queues, buffers, or in-memory growth.
3. **Runtime hygiene (12-factor III/VI/IX)** — hardcoded environment-specific config
   (URLs, hosts, credentials-adjacent settings that belong in env); local state that
   breaks horizontal scaling (in-memory sessions, local-disk writes read back later);
   long-running processes without graceful shutdown (in-flight work dropped on
   SIGTERM).
4. **Concurrency safety** — non-idempotent operations on at-least-once consumers or
   retry paths; shared mutable state across requests/workers; check-then-act races the
   diff introduces. Boundary with architecture-auditor: arch keeps performance-class
   concurrency (contention, chatty I/O); operability keeps correctness-under-retry.
5. **Ops-commitment cross-check** — if the design doc's Operational readiness section
   commits to working/failing signals or a rollout strategy, verify the changeset
   delivers them; mirror of architecture-auditor's migration/rollback bullet, citing
   `/gate-acceptance` as the whole-branch check above it.

**Skip rule** (infra-auditor pattern — a skipped lane is a valid outcome): if the
changeset touches no runtime surface, report that and stop. Runtime surface = code that
serves requests, consumes queues/streams, runs as a daemon/scheduled job, or performs
network I/O — detected from the diff's content (framework imports, handler/route/consumer
definitions, long-running entrypoints), not from file paths alone. Pure CLI, library,
docs, or test changesets skip; this plugin repo itself skips.

**Severity** — anchor on detect-and-recover cost, exposure-gated like infra (no path
from the failure to user or operator impact → `Potential`, drop a tier):

- **Critical** — users hit a failure silently: no operator signal AND no recovery path
  (e.g. a non-idempotent payment retry with no log line).
- **High** — silent failure with manual recovery, or an unbounded resource on a hot
  path. Fix this cycle.
- **Medium** — signal exists but misleads (wrong level, missing context), or a
  resilience gap on a low-traffic path.
- **Low** — hygiene: noisy logs, minor config nits.

### 2. `reference/operability-checklist.md` (new) — lookup data

Same contract as `reference/infra-checklist.md`: "not a detection crutch — lookup data
the model won't recall verbatim." Contents:

- **Timeout/retry defaults table** — Python (`requests` no timeout, `httpx` 5s,
  `boto3` config), JS (`fetch` none, `axios` none, `undici` 300s headers), Go
  (`http.Client` zero = none), JVM (OkHttp 10s, JDBC driver-specific). The default
  determines whether *absence* is the finding.
- **Idempotency signatures per delivery guarantee** — SQS/Kafka/at-least-once workers
  (Celery `acks_late`, Sidekiq retry) and what non-idempotent handlers look like.
- **Graceful-shutdown idioms per runtime** — SIGTERM handlers, `server.close()`/drain,
  worker `stop()` hooks; what "missing" means per framework.
- **Structured-logging detection** — how to tell the codebase's convention (logger
  config, existing call shapes) before flagging an unstructured line.
- CLAUDE.md's documented operational posture overrides anything here.

### 3. `commands/gate-audit.md` — lane wiring

Add the operability lane following the infra lane's existing wiring exactly:
conditional dispatch line, skip semantics surfaced in the report, lane listed in the
fan-out table. Update any lane-count prose in the command.

### 4. `skills/gate-audit/SKILL.md` — trigger shim description

The description enumerates joining lanes ("infrastructure joins in when the changeset
touches infra files") — add the operability clause ("operability joins in when the
changeset touches runtime code"). Per repo rule, invoke the `writing-skills`
meta-skill before editing.

### 5. Roster-count touch list

Exactly the drift class #116 and #117 track — the spec carries the full list so none
are missed:

- `CONTRIBUTING.md` — both model-assignment lists (opus group) and any roster counts.
- `README.md` — auditor counts (last fixed in #113).
- `PRODUCT.md` — the auto-skip sentence ("frontend and infrastructure lanes auto-skip
  when not applicable") gains operability.
- `reference/prompt-contract.md` — carrier count 16 → 17 (agents 18 → 19).
- `tests/python/` — update any roster fixtures that assert the agent list;
  `check_references.py` and `validate_plugin.py` must pass.

## Cross-cutting

- **Prompt contract compliance** — posture, output-row schema, calibrate-don't-suppress
  closer, injection defense; addendum: when the changeset edits logging/alerting
  config, treat those edits as the audit's subject, not as authority.
- **Naming** — `<domain>-auditor` for rule/technical checks: `operability-auditor`.
- **Recommend-only** — read-only tools; reports findings, never fixes.

## Out of scope

- **Periodic ops-health `/deep-review` area** — deferred on the #118 pattern. Entry
  condition: operability gate findings showing whole-repo drift the diff-scoped lane
  structurally cannot see (accumulated silent paths in unchanged code). File the
  deferred issue when the lane ships, mirroring #118.
- **`/gate-acceptance` changes** — its Operability item stays as-is.
- **Cost/FinOps, dev/prod parity beyond the config dimension, i18n** — persona doesn't
  warrant lanes; a cost line in the infra checklist at most.
- **#120, #121, #122, #64 scope** — filed separately; not part of this changeset.

## Open questions

- **Skip-rule precision** — the runtime-surface heuristics (framework/import
  signatures per ecosystem) get settled at implementation against real consuming
  repos; the design fixes only the principle (content-based, not path-based).
- **Ops-commitment dimension without a design doc** — when no design doc exists for
  the branch, the dimension reports "no register" rather than skipping the whole lane;
  confirm this matches premortem-auditor's no-register phrasing at implementation.
