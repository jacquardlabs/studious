# Audit Coverage Seams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the six audit-coverage seams from `docs/superpowers/specs/2026-07-09-audit-coverage-seams-design.md` — new infra-auditor, test-auditor, and review-security-health agents plus operational-readiness contract threading and performance-seam assignment.

**Architecture:** Studious is a Claude Code plugin whose "source" is markdown prompt files. Three new agents join the existing roster (two gate-time changeset auditors wired into `/gate-audit` and `workflows/epic-driver.js`, one periodic reviewer wired into `/deep-review`); the remaining seams are edits to existing prompts and contracts. Correctness = lint passes, references resolve, and the Python routing tests pass.

**Tech Stack:** Markdown prompt files; `uv` + pytest for the Python tests; `npx markdownlint-cli2` for lint; one JS edit (`workflows/epic-driver.js`).

## Global Constraints

- Branch: `feat/audit-coverage-seams` (already created off origin/main; spec committed as 426552b). Never commit to main.
- Every agent cites the prompt contract ONLY as `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` — `tests/python/test_contract_injection.py::test_no_agent_carries_a_bare_relative_contract_citation` fails on a bare `reference/prompt-contract.md`. Citing OTHER reference files bare (e.g. `reference/infra-checklist.md`) is correct and expected.
- New gate auditors' frontmatter `description` must contain "changeset" or "diff-scoped" AND the literal "/gate-audit" (`tests/python/test_agent_descriptions.py`).
- Model pins: `opus` for infra-auditor and review-security-health, `inherit` for test-auditor. Never a bare tier.
- Severity: three canonical tiers only (`reference/severity-rubric.md`); each new gate auditor registers its own mapping row there.
- Recommend-only: all three agents audit and report; none writes to the repo except review-security-health's single report file in the consuming project's `docs/studious/`.
- Never edit `.claude-plugin/plugin.json` (version is CI-managed).
- Verification commands (run after every task; all must be clean):
  - `npx -y markdownlint-cli2` → `Summary: 0 error(s)`
  - `uv run --no-project python scripts/check_references.py` → `Reference check passed`
  - `uv run --no-project --with pytest pytest tests/python -q` → all pass
- Commit after every task with the message given in the task.

---

### Task 1: `reference/infra-checklist.md` — lookup data for the infrastructure lane

**Files:**

- Create: `reference/infra-checklist.md`

**Interfaces:**

- Consumes: nothing (first task).
- Produces: the file path `reference/infra-checklist.md`, cited by Task 2's agent. Its section names ("Per-tool misconfiguration signatures", "Workflow-injection sinks", "Per-tool defaults") are referenced from the agent prose but nothing parses them mechanically.

- [ ] **Step 1: Create the file**

Write `reference/infra-checklist.md` with exactly this content (shape and voice mirror `reference/security-checklist.md` — lookup data, not a detection crutch):

````markdown
# Infrastructure checklist — lookup data

Not a detection crutch — a capable model already knows these misconfiguration classes.
This file is the **lookup data** it won't recall verbatim: exact signatures, the
workflow-injection sink list, and per-tool defaults. The five dimensions live inline in
`agents/infra-auditor.md`; consult this for the specifics. CLAUDE.md's documented
infrastructure posture overrides anything here. Severity stays exposure-gated: no path
from an attacker or an outage to the resource → `Potential`, drop a tier.

## Per-tool misconfiguration signatures (one line each)

- **IAM wildcards** — `Action: "*"`, `Principal: "*"` / `AWS: "*"`, `Resource: "*"` on
  write-capable actions, unscoped `iam:PassRole`, `sts:AssumeRole` trust to any account.
- **Public exposure** — security group / firewall ingress from `0.0.0.0/0` or `::/0` on
  non-public ports, `publicly_accessible = true`, bucket ACL `public-read`/policy with
  `Principal: "*"`, K8s `Service type: LoadBalancer` or `Ingress` without auth in front.
- **Missing encryption** — no `encrypted`/`storage_encrypted`/`kms_key_id` on volumes,
  DBs, queues, topics; TLS disabled or `enforce_ssl = false`; unencrypted state backend.
- **Stateful-resource safety** — no `deletion_protection`, no backup/versioning/PITR on
  databases and buckets, `force_destroy = true`, `skip_final_snapshot = true`.
- **Blast radius** — a rename or immutable-field change that forces destroy/replace
  (Terraform plan would show `-/+`; `moved` blocks / CDK logical-ID retention absent);
  state migrations without a documented path.

## Workflow-injection sinks (GitHub Actions and kin)

- Untrusted event fields interpolated into `run:` or `script:` — `${{ github.event.issue.title }}`,
  `${{ github.event.pull_request.title }}`, `${{ github.event.comment.body }}`,
  `${{ github.head_ref }}` — attacker-controlled text becomes shell. Fix: pass via `env:`.
- `pull_request_target` (or `workflow_run`) combined with a checkout of the PR head
  (`ref: ${{ github.event.pull_request.head.sha }}`) — secrets + attacker code.
- Third-party actions pinned to a tag or branch (`uses: some/action@v3`) instead of a
  commit SHA — the tag can move under you.
- `permissions:` absent (legacy default is write-all) or broader than the job needs;
  `GITHUB_TOKEN` with `write` handed to steps that only read.
- Secrets reachable from fork-triggered runs; `secrets: inherit` passed to a reusable
  workflow that doesn't need them.
- Self-hosted runners on public-PR workflows.

## Container signatures

- No `USER` directive (runs as root); `:latest` or unpinned base image; secrets via
  `ARG`/`ENV`/`COPY .env`; `ADD` from a URL; `curl | sh` installs; package installs
  without version pins where the ecosystem supports them (`apt-get install -y pkg`
  vs `pkg=1.2.*`).

## Per-tool defaults

The tool sets what "missing" means — detect it from the changed files before rating a
finding.

| Tool | Encryption | Public access | Deletion safety |
|---|---|---|---|
| Terraform (raw) | Off unless set — absence is the finding | Provider default (usually private); explicit `0.0.0.0/0` is the finding | Off unless set |
| CDK (L2+) | Many constructs encrypt by default — verify the construct level before flagging | `blockPublicAccess` on by default for S3 | `RemovalPolicy` defaults to DESTROY on some constructs — verify stateful ones |
| CloudFormation | Off unless set | Off unless set | `DeletionPolicy` absent = delete |
| Kubernetes | N/A (cluster concern) | `Service`/`Ingress` exposure is explicit — judge the auth in front | PDB/replicas absent = single-replica |
| Docker/Compose | N/A | `ports:` binds 0.0.0.0 unless an address is given | N/A |
| GitHub Actions | N/A | fork/PR trigger surface | `permissions:` absent = legacy write-all |

If the tool can't be determined, say so in the residual line and rate defaults-dependent
findings `Potential`.
````

- [ ] **Step 2: Verify lint**

Run: `npx -y markdownlint-cli2`
Expected: `Summary: 0 error(s)`

- [ ] **Step 3: Commit**

```bash
git add reference/infra-checklist.md
git commit -m "feat: add infra-checklist reference — lookup data for the infrastructure audit lane"
```

---

### Task 2: `agents/infra-auditor.md` — the infrastructure gate auditor (TDD)

**Files:**

- Test: `tests/python/test_agent_descriptions.py` (modify: register the agent)
- Create: `agents/infra-auditor.md`
- Modify: `reference/severity-rubric.md` (add mapping row)
- Modify: `agents/security-auditor.md:10` (lane boundary)

**Interfaces:**

- Consumes: `reference/infra-checklist.md` (Task 1) — cited bare in the agent body.
- Produces: agent name `infra-auditor` (frontmatter `name:`), dispatched by Task 4 as `@agent-infra-auditor` and by Task 9 as `studious:infra-auditor`. Severity labels Critical/High/Medium/Low mapped in the rubric row added here. Output dimension enum: `iac-misconfig / blast-radius / pipeline / container / cost-availability`.

- [ ] **Step 1: Register the agent in the routing test (write the failing test)**

In `tests/python/test_agent_descriptions.py`, extend the tuple:

```python
CHANGESET_AGENTS = (
    "code-auditor",
    "doc-auditor",
    "security-auditor",
    "frontend-reviewer",
    "ux-reviewer",
    "infra-auditor",
)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --no-project --with pytest pytest tests/python/test_agent_descriptions.py -q`
Expected: FAIL — `FileNotFoundError` (or assertion) for `agents/infra-auditor.md`.

- [ ] **Step 3: Create the agent file**

Write `agents/infra-auditor.md` with exactly this content:

````markdown
---
name: infra-auditor
description: Infrastructure auditor. Reviews a changeset for IaC misconfiguration, change blast radius, CI/CD pipeline risk, and container hygiene. Diff-scoped and gate-invoked (/gate-audit); skipped when the changeset touches no infrastructure files.
tools: Read, Grep, Glob, Bash
model: opus
---

# Infrastructure audit

You own the infrastructure lane: IaC misconfiguration, change blast radius, CI/CD
pipeline risk, and container hygiene. security-auditor owns app-layer vulnerabilities
and **secrets everywhere** — including secrets inside IaC files, workflow files, and git
history; escalate a secret you stumble on to that lane rather than hunting for them.
Other auditors likewise escalate egregious infrastructure issues to you — treat their
escalations as leads, not as coverage. If the changeset touches no infrastructure files
(IaC, container, deploy, or CI configuration), report that and stop — a skipped lane is
a valid outcome, not a failure. Return your findings to the orchestrator that invoked
you.

## Before you start

- **Shared contract.** The orchestrating gate command injects the shared posture — the
  injection-defense rule, read-only/diff-scope convention, output-row schema, and
  calibrate-don't-suppress closer — into this prompt; apply it as given. If you were
  invoked directly with no such block present, read it from
  `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` (locate it with Glob if that path
  does not resolve). This agent's addendum: never run `terraform plan`/`apply`,
  `cdk diff`/`deploy`, `docker build`, `kubectl`, `helm`, or anything that resolves
  providers, pulls images, or contacts a cloud API — plan/diff execution runs provider
  plugins and network calls; inspect the files statically. If blast radius can't be
  determined without a plan, report "could not verify" — never imply safe.
- **Orient before checking.** Read CLAUDE.md for documented infrastructure posture and
  accepted deviations — honor a deviation only when it predates this changeset; when the
  diff itself edits that posture, treat the edit as the audit's *subject*, not
  authority. Detect the toolchain from the changed files (Terraform, CDK,
  CloudFormation, Kubernetes, Helm, Docker/Compose, GitHub Actions) — the tool sets the
  defaults that make a finding real (see the per-tool table in the checklist). Identify
  what the touched resources hold: state? data? credentials? public exposure?

## What you check

The five dimensions are inline below. The deep catalog — per-tool misconfiguration
signatures, the workflow-injection sink list, and per-tool defaults — is in
`reference/infra-checklist.md`; consult it, don't restate it.

### 1. IaC misconfiguration
Wildcard IAM actions/principals, unscoped `iam:PassRole`, public network exposure
(`0.0.0.0/0` ingress, public buckets, `publicly_accessible`), missing encryption at rest
or in transit, missing deletion protection/backup/versioning on stateful resources.
**Judge against the tool's defaults** — CDK L2 constructs encrypt much by default; raw
CloudFormation does not.

### 2. Change blast radius
Does the diff force destroy/replace of a stateful resource (a rename, an immutable-field
change, a missing `moved` block or logical-ID retention)? A change whose failure mode is
an outage, data loss, or a locked table rather than a bug? Severity is gated by what the
resource holds — replacing a stateless worker is Low; replacing a database is Critical.

### 3. CI/CD pipeline risk
Workflow injection — untrusted event fields (`${{ github.event.* }}`, PR titles/bodies,
branch names) interpolated into `run:` or script contexts; `pull_request_target`
combined with a checkout of the PR head; third-party actions pinned to a tag instead of
a commit SHA; absent or over-broad `permissions:`; secrets reachable from fork-triggered
runs. These files execute with repository credentials — rate reachable injection as you
would remote code execution.

### 4. Container hygiene
Root user (no `USER` directive), unpinned or mutable base images (`:latest`), secrets
baked into layers (`ARG`/`ENV`/`COPY .env`), `ADD` from a URL, unpinned package
installs where the ecosystem supports pinning.

### 5. Cost and availability signals
Single-AZ/single-replica stateful services, unbounded log retention, oversized instance
defaults. Mostly Track-tier — flag only what the diff introduces or worsens; calibrate,
don't pad.

## Severity

Define every finding against this rubric. The orchestrator maps Critical+High→Critical,
Medium→Important, Low→Track (see `reference/severity-rubric.md`) — a standalone run
relies on these definitions. Severity is **gated by exposure**: a misconfiguration on a
resource nothing external can reach drops a tier and is marked `Potential`.

- **Critical** — reachable exposure or destruction: public access to data, credential
  exfiltration via pipeline injection, forced replacement of a stateful resource.
- **High** — privilege escalation or exposure one misstep away: wildcard IAM on a
  reachable role, an unpinned action with secrets access.
- **Medium** — exploitable only under unusual preconditions, or a real availability
  risk.
- **Low** — hardening and cost hygiene.

## Output

Emit findings per the injected output-row schema: **dimension** is one of iac-misconfig
/ blast-radius / pipeline / container / cost-availability.

Close with: a checklist of must-fix items (Critical/High); a summary table of findings
by dimension and severity; and a **residual line** — what you verified clean, the
toolchain detected, assumptions made, and limitations (no plan executed, tool
undetermined).

Apply the injected calibrate-don't-suppress / clean-result-is-valid closer. This agent's
addendum: a *missing control on an exposed or stateful surface* — no encryption on data
at rest, no pinning on an action with secrets access, no deletion protection on a
production database — is a finding in its own right; never demote it to a context note.
Minimize only cost/availability hygiene when nothing stateful or public depends on it.

## What you do NOT do

- Secrets and app-layer vulnerabilities — security-auditor's lane; escalate, don't hunt.
- Code quality (code-auditor), docs (doc-auditor), structural fit (architecture-auditor)
  — stay out of their lanes; mention only if severe.
- Fix files, run IaC tools, plan deployments, or orchestrate other agents. You audit and
  report your findings to the orchestrator that invoked you.
````

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project --with pytest pytest tests/python/test_agent_descriptions.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Register the severity-rubric row**

In `reference/severity-rubric.md`, in the per-auditor mapping table, add this row directly after the `security-auditor` row:

```markdown
| infra-auditor | Critical, High | Medium | Low |
```

- [ ] **Step 6: State the lane boundary in security-auditor**

In `agents/security-auditor.md`, replace the sentence in the opening paragraph:

Old:

```markdown
You own the deep, authoritative security pass and the canonical severity rubric. Other auditors do not hunt for security issues, but may escalate an egregious one they stumble on — treat their escalations as leads, not as coverage. Return your findings to the orchestrator that invoked you.
```

New:

```markdown
You own the deep, authoritative security pass and the canonical severity rubric. You keep **secrets everywhere** — application code, IaC files, workflow files, git history; infra-auditor owns infrastructure misconfiguration and CI/CD pipeline risk — escalate those to it rather than hunting them. Other auditors do not hunt for security issues, but may escalate an egregious one they stumble on — treat their escalations as leads, not as coverage. Return your findings to the orchestrator that invoked you.
```

- [ ] **Step 7: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add tests/python/test_agent_descriptions.py agents/infra-auditor.md reference/severity-rubric.md agents/security-auditor.md
git commit -m "feat: add infra-auditor — IaC, blast-radius, pipeline, and container lane"
```

---

### Task 3: `agents/test-auditor.md` — test adequacy at gate time (TDD)

**Files:**

- Test: `tests/python/test_agent_descriptions.py` (modify: register the agent)
- Create: `agents/test-auditor.md`
- Modify: `reference/severity-rubric.md` (add mapping row)
- Modify: `agents/code-auditor.md:32-36` (lane boundary)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: agent name `test-auditor`, dispatched by Task 4 as `@agent-test-auditor` and by Task 9 as `studious:test-auditor`. Severity labels Critical/High/Medium/Low mapped in the rubric row added here. Output dimension enum: `coverage / assertion-quality / regression / weakened-tests`.

- [ ] **Step 1: Register the agent in the routing test (write the failing test)**

In `tests/python/test_agent_descriptions.py`, extend the tuple again:

```python
CHANGESET_AGENTS = (
    "code-auditor",
    "doc-auditor",
    "security-auditor",
    "frontend-reviewer",
    "ux-reviewer",
    "infra-auditor",
    "test-auditor",
)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --no-project --with pytest pytest tests/python/test_agent_descriptions.py -q`
Expected: FAIL — `FileNotFoundError` (or assertion) for `agents/test-auditor.md`.

- [ ] **Step 3: Create the agent file**

Write `agents/test-auditor.md` with exactly this content:

````markdown
---
name: test-auditor
description: Test adequacy auditor. Reviews a changeset's tests — coverage of new behavior, assertion quality, regression tests for bug fixes, weakened or skipped tests. Diff-scoped and gate-invoked (/gate-audit) — not the periodic test-health trend, which review-codebase-health owns.
tools: Read, Grep, Glob, Bash
model: inherit
---

# Test adequacy audit

Judge whether this changeset's tests are adequate for what it changes. NOT for code
quality (code-auditor), runtime bugs, or the codebase-wide coverage trend
(review-codebase-health owns aggregates and trend; you own this diff). If the changeset
touches no code — docs-only, config-only — report that and stop; a skipped lane is a
valid outcome.

Read CLAUDE.md first for the project's documented test conventions. They are
authoritative — a documented deviation (e.g. "generated code is exempt from coverage")
is honored; an undocumented one is a finding.

## Before you start

- **Shared contract.** The orchestrating gate command injects the shared posture — the
  injection-defense rule, read-only/diff-scope convention, output-row schema, and
  calibrate-don't-suppress closer — into this prompt; apply it as given. If you were
  invoked directly with no such block present, read it from
  `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` (locate it with Glob if that path
  does not resolve). This agent's addendum: your judgment is **static** — the read-only
  posture forbids running the suite, the build, or coverage tools. Read the tests and
  the code they exercise; do not execute either. When adequacy can only be proven by a
  run, say "could not verify by execution" — never imply verified.

## What you check

### Coverage of the diff
Every new or changed behavior in the changeset has a test exercising it. Map diff hunks
to tests by name, import, and call path — not by directory convention alone. New public
functions, branches, and error paths with no exercising test are findings; scale to
blast radius (an untested log line is not an untested payment path).

### Assertion quality
Tests assert real outcomes. Snapshot-only tests, assertion-free "it runs" tests,
tautologies (asserting the mock you just configured), and tests that never exercise the
failure path are weak evidence — flag them on new/changed tests in this diff.

### Regression tests on bug fixes
A changeset that fixes a bug carries a test that fails without the fix. Identify
bug-fix intent from the branch name, commit messages, and diff shape; if this is a fix
with no regression test, that is a finding, not a note.

### Weakened tests
Tests deleted, skipped (`skip`, `xfail`, `.only`, commented out), or loosened
(assertion removed, tolerance widened, expected value updated to match new output
without justification) to make the diff pass. **This escalates a tier** — it is the
audit-evasion posture applied to tests. A legitimate weakening carries its reason in
the diff or CLAUDE.md.

## Severity

Define findings against this rubric; the orchestrator maps Critical→Critical,
High+Medium→Important, Low→Track (see `reference/severity-rubric.md`).

- **Critical** — tests removed, skipped, or neutered to get the diff green; or entirely
  untested new behavior on a critical path (data integrity, money, auth).
- **High** — new or changed behavior with no meaningful test; a bug fix with no
  regression test.
- **Medium** — weak assertions on new tests (snapshot-only, missing failure paths).
- **Low** — coverage polish on low-blast-radius code.

## Output

Emit findings per the injected output-row schema: **dimension** is one of coverage /
assertion-quality / regression / weakened-tests. For a coverage finding, name BOTH the
untested code location and where its test should live.

Close with a **residual line** — what you verified adequately tested, how you mapped
diff to tests, and limitations (suite not executed, coverage data not read).

Apply the injected calibrate-don't-suppress / clean-result-is-valid closer. This agent's
addendum: don't demand tests the project's conventions don't — CLAUDE.md's documented
test policy calibrates every finding; a changeset meeting it cleanly is a clean result.

## What you do NOT do

- Code quality, style, complexity — code-auditor's lane.
- Security (security-auditor), docs (doc-auditor), structure (architecture-auditor) —
  escalate an egregious cross-lane issue; don't hunt.
- Run the suite, fix tests, write tests, or orchestrate agents. You audit and report.
````

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run --no-project --with pytest pytest tests/python/test_agent_descriptions.py -q`
Expected: PASS (all tests).

- [ ] **Step 5: Register the severity-rubric row**

In `reference/severity-rubric.md`, add this row directly after the `code-auditor` row:

```markdown
| test-auditor | Critical | High, Medium | Low |
```

- [ ] **Step 6: State the lane boundary in code-auditor**

In `agents/code-auditor.md`, in the `**Does NOT check:**` list, replace:

Old:

```markdown
**Does NOT check:**
- Security vulnerabilities — security-auditor handles this
- Visual design — ux-reviewer handles this
- Product fit — product-reviewer handles this
```

New:

```markdown
**Does NOT check:**
- Security vulnerabilities — security-auditor handles this
- Test adequacy — test-auditor handles this
- Visual design — ux-reviewer handles this
- Product fit — product-reviewer handles this
```

- [ ] **Step 7: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add tests/python/test_agent_descriptions.py agents/test-auditor.md reference/severity-rubric.md agents/code-auditor.md
git commit -m "feat: add test-auditor — changeset test-adequacy lane"
```

---

### Task 4: Wire both auditors into `/gate-audit` (single renumbering pass)

**Files:**

- Modify: `commands/gate-audit.md` (frontmatter description, launch/skip rules, auditor sections, category list)

**Interfaces:**

- Consumes: `@agent-infra-auditor` (Task 2), `@agent-test-auditor` (Task 3) — `scripts/check_references.py` verifies both resolve.
- Produces: the final auditor numbering (1–5 backend, 6–8 web, 9 infrastructure, 10 pre-mortem) that README copy (Task 9) describes; the infra file-signal list (lives ONLY here, per the spec's open question).

- [ ] **Step 1: Update the frontmatter description**

Old:

```markdown
description: Run the audit suite — security, code quality, docs, and architecture always run; UX, frontend, and an accessibility pass join in on projects with a web surface; pre-mortem verification joins in when a register exists for this branch
```

New:

```markdown
description: Run the audit suite — security, code quality, docs, architecture, and tests always run; UX, frontend, and an accessibility pass join in on projects with a web surface; infrastructure joins in when the changeset touches infra files; pre-mortem verification joins in when a register exists for this branch
```

- [ ] **Step 2: Update the launch rules and web-specific skip block**

Old:

```markdown
Spawn auditors 1–6 — plus auditor 8 when a pre-mortem register exists — as subagents simultaneously; do not run them sequentially. Auditor 7 is an inline external check, described below.

Auditors 5–7 (ux, frontend, accessibility) are web-specific. Skip them when either condition holds:
```

New:

```markdown
Spawn auditors 1–7 and 9 — plus auditor 10 when a pre-mortem register exists — as subagents simultaneously; do not run them sequentially. Auditor 8 is an inline external check, described below.

Auditor 9 (infrastructure) is changeset-routed: skip it when the changeset touches no infrastructure files — IaC (`*.tf`, `*.tfvars`, `*.hcl`, CloudFormation/SAM templates, `cdk.json` or CDK stack sources, `Pulumi.yaml`), Kubernetes manifests or Helm charts, `Dockerfile*` / `docker-compose*` / `compose.*`, CI pipeline configs (`.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`), or deploy configs (`serverless.*`, `Procfile`, `fly.toml`, `render.yaml`, Ansible playbooks). Note "No infrastructure changes detected — infrastructure audit skipped." When ambiguous, run — default to running, not skipping. This file-signal list lives only here; the agent itself self-skips if dispatched against a changeset with none of these.

Auditors 6–8 (ux, frontend, accessibility) are web-specific. Skip them when either condition holds:
```

- [ ] **Step 3: Add test-auditor as backend auditor 5**

After the architecture-auditor entry (currently item 4), add:

```markdown
5. **@agent-test-auditor** — Review the changeset's test adequacy: does new or changed behavior carry tests, do the tests assert real outcomes, does a bug fix carry a regression test, and were any tests deleted, skipped, or weakened to make the diff pass? Skip with a note if the changeset touches no code.
```

- [ ] **Step 4: Renumber the frontend auditors and pre-mortem section**

- `5. **@agent-ux-reviewer**` → `6. **@agent-ux-reviewer**`
- `6. **@agent-frontend-reviewer**` → `7. **@agent-frontend-reviewer**`
- `7. **Web Interface Guidelines (external, optional, with vendored fallback)**` → `8. **Web Interface Guidelines (external, optional, with vendored fallback)**`; inside that item, `Unlike auditors 1–6, this runs inline` → `Unlike auditors 1–7 and 9, this runs inline`
- `8. **@agent-premortem-auditor**` → `10. **@agent-premortem-auditor**`

- [ ] **Step 5: Add the infrastructure auditor section**

Between the `### Frontend auditors` block (after item 8) and the `### Pre-mortem verification` section, add:

```markdown
### Infrastructure auditor (runs when the changeset touches infra files)

9. **@agent-infra-auditor** — Review the changeset's infrastructure changes: IaC misconfiguration, change blast radius on stateful resources, CI/CD pipeline risk (workflow injection, unpinned actions, over-broad permissions), and container hygiene. Secrets stay with @agent-security-auditor.
```

- [ ] **Step 6: Update the category list**

Old:

```markdown
All non-critical but important findings, grouped by category (security, code quality, documentation, architecture, UX, frontend, accessibility).
```

New:

```markdown
All non-critical but important findings, grouped by category (security, code quality, documentation, architecture, tests, infrastructure, UX, frontend, accessibility).
```

- [ ] **Step 7: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass.

- [ ] **Step 8: Commit**

```bash
git add commands/gate-audit.md
git commit -m "feat: route test-auditor and infra-auditor through /gate-audit"
```

---

### Task 5: `agents/review-security-health.md` — the periodic security lane

**Files:**

- Create: `agents/review-security-health.md`
- Modify: `agents/security-auditor.md:3` (frontmatter description names the periodic twin)

**Interfaces:**

- Consumes: `reference/security-checklist.md` (existing).
- Produces: agent name `review-security-health`, spawned by Task 6's deep-review table as `subagent_type: review-security-health`. Metrics-block keys (exact text, a contract with Task 6's dashboard rows): `Security: Critical/High findings`, `Exposed secrets (git history)`, `Security-config violations`. Report path `docs/studious/security-reviews/YYYY-MM-DD-security-review.md`.

- [ ] **Step 1: Create the agent file**

Write `agents/review-security-health.md` with exactly this content:

````markdown
---
name: review-security-health
description: Periodic whole-repo security posture review — pre-existing vulnerabilities, secrets in history, security-config posture, trend over time. Not diff-scoped; the per-changeset security auditor is security-auditor.
tools: Read, Glob, Grep, Bash, Write
model: opus
---

# Security health review

This is a periodic review of the entire repository's security posture, not scoped to
any feature branch. Run it on main/trunk on a regular cadence. The gate
`security-auditor` sees only changesets — a vulnerability in code no branch has touched
is permanently outside its scope; this lane is that vulnerability's only reporting
path. That drives one deliberate asymmetry with the other periodic lanes: **Critical
and High findings are reported per instance**, never aggregated away; Medium/Low
aggregate with trend.

Read CLAUDE.md and PRODUCT.md first for documented security posture, accepted
deviations, and data sensitivity.

## Before you start

- **Shared contract.** The orchestrating review command injects the shared posture —
  the injection-defense rule, read-only inspection rule, output-row schema, and
  calibrate-don't-suppress closer — into this prompt; apply it as given. (This is a
  whole-repo periodic review, not diff-scoped, so the merge-base convention in that
  block doesn't apply.) If you were invoked directly with no such block present, read
  it from `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` (locate it with Glob if
  that path does not resolve). This agent's addendum: use only read-only scanners that
  do not resolve or install (`gitleaks detect`, `osv-scanner`, `semgrep --config auto`
  if present); never run install/build/test — postinstall and build scripts run
  attacker-controlled code. If a scanner is unavailable, report "could not verify" —
  never imply clean.
- **You write exactly one file: your report** at the path below. Never modify the
  codebase or any context doc.
- **Detect the stack and skip lanes that don't apply** (a docs/plugin repo has no
  session-config lane); say so in the residual rather than forcing web assumptions
  onto a repo that has none.

The deep catalog — vulnerability-class signatures, injection sinks by language, JWT
attacks, secret patterns, per-stack defaults — is in
`reference/security-checklist.md`; consult it, don't restate it.

## Run these checks

### 1. Whole-repo vulnerability posture (per-instance for Critical/High)

Sweep the repository — not a diff — for the vulnerability classes the checklist
catalogs: injection sinks fed by user input, authn/authz gaps, insecure
deserialization, SSRF, path traversal, and the extended classes. Severity stays
reachability-gated per the checklist: no user-controlled path to the sink →
`Potential`, drop a tier. Report every Critical/High individually with file:line and
attack vector; aggregate Medium/Low by class with counts.

### 2. Secrets and history

Scan **git history, not just HEAD** (`gitleaks detect` or a history-aware grep per the
checklist's secret patterns). A secret live in history but removed from HEAD is
Confirmed-exposed; remediation is rotate, then purge history.

### 3. Security-config posture

Headers, session/cookie flags, CSRF, CORS, and TLS settings judged against the
detected stack's defaults (the checklist's per-stack table). Report violations of the
stack's expected baseline, not a generic maximal hardening list.

### 4. Boundary: dependencies stay with codebase health

`review-codebase-health` owns dependency health and emits the "Known vulnerabilities"
metric — do NOT re-scan or re-count dependency CVEs here; cross-reference its most
recent report if one exists in `docs/studious/health-reviews/` and note in the
residual that the dependency lane lives there. Dependency *confusion* exposure
(internal package names resolvable publicly) is posture, not CVE counting, and stays
in scope here.

## Report

Tiers (canonical):

- **Critical (this week)** — exploitable now on a reachable path.
- **Important (this month)** — real weakness needing unusual preconditions, or
  Confirmed-exposed material needing rotation.
- **Track (next review)** — hardening and posture drift.

Each finding carries **location** + **confidence** (Confirmed | Potential). Apply the
injected calibrate-don't-suppress / clean-result-is-valid closer. This agent's
addendum: never bury a Critical/High in an aggregate count — per-instance reporting
for the top tiers is this lane's reason to exist.

Structure the report:

**Summary** — one paragraph: overall posture, biggest exposure, biggest strength.
**Critical**, **Important**, **Track** — findings grouped by tier.
**Metrics snapshot** — these key names are a **contract with `/deep-review`'s
dashboard** (`commands/deep-review.md`) — do not rename them:

- Security: Critical/High findings
- Exposed secrets (git history)
- Security-config violations

Mark any metric N/A (with the reason) when its lane was skipped.

**Trend vs last cycle** — if prior reports exist in
`docs/studious/security-reviews/`, compare against the most recent and note each
metric and finding as up/down/flat/new/resolved; else "baseline".
**Residual line** — what you verified clean, scanners used or unavailable, lanes
skipped and why, assumptions, limitations.

Save the report to `docs/studious/security-reviews/YYYY-MM-DD-security-review.md`
(create the directory if needed).
````

- [ ] **Step 2: Name the periodic twin in security-auditor's description**

In `agents/security-auditor.md` frontmatter:

Old:

```markdown
description: Comprehensive security analysis — OWASP Top 10, injection, auth, secrets, headers. Reviews a changeset; diff-scoped and gate-invoked (/gate-audit).
```

New:

```markdown
description: Comprehensive security analysis — OWASP Top 10, injection, auth, secrets, headers. Reviews a changeset; diff-scoped and gate-invoked (/gate-audit) — not the periodic whole-repo posture review, which review-security-health owns.
```

- [ ] **Step 3: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass (the description edit keeps "changeset" and "/gate-audit", so `test_agent_descriptions.py` stays green).

- [ ] **Step 4: Commit**

```bash
git add agents/review-security-health.md agents/security-auditor.md
git commit -m "feat: add review-security-health — periodic whole-repo security posture lane"
```

---

### Task 6: `/deep-review` sixth lane + `studious-init` scaffold

**Files:**

- Modify: `commands/deep-review.md` (description, intro, contract-assembly note, area table, phase headers, dashboard, comment)
- Modify: `commands/studious-init.md:61-65` (scaffold directory list)

**Interfaces:**

- Consumes: `review-security-health` (Task 5) and its three metric keys verbatim.
- Produces: area keyword `security`; dashboard row text = metric keys (the metrics-history file keys by row text, so new rows read "new" on first run — no migration needed, resolving the spec's second open question).

- [ ] **Step 1: Update every five→six site in `commands/deep-review.md`**

Six exact replacements:

1. Frontmatter description, old:

   ```markdown
   description: Run the periodic review suite — all five reviews with a compiled master summary, or a single area. Codebase health, interface health, architecture, product health, README drift.
   ```

   New:

   ```markdown
   description: Run the periodic review suite — all six reviews with a compiled master summary, or a single area. Codebase health, interface health, architecture, product health, security posture, README drift.
   ```

2. Intro, old: `With no argument, runs all five and compiles a master summary` → new: `With no argument, runs all six and compiles a master summary`
3. Contract assembly, old: `the five periodic reviewers, and ` + backtick `code-auditor` → new: `the six periodic reviewers, and ` + backtick `code-auditor` (edit only the word `five`).
4. Phase 1 header, old: `### Phase 1 — Run all five reviews in parallel` → new: `### Phase 1 — Run all six reviews in parallel`
5. Phase 1 body, old: `Spawn all five subagents simultaneously` → new: `Spawn all six subagents simultaneously`; and old: `Run all five with` → new: `Run all six with`
6. Phase 2, old: `After all five reviews complete, read all five reports` → new: `After all six reviews complete, read all six reports`; and old: `Compile a single prioritized list across all five reviews:` → new: `Compile a single prioritized list across all six reviews:`

- [ ] **Step 2: Add the area-table row**

In the area-argument table, after the `product` row and before the `readme` row, add:

```markdown
| `security` | `review-security-health` | Whole-repo vulnerability posture (per-instance Critical/High), secrets in history, security-config posture, trend | `docs/studious/security-reviews/YYYY-MM-DD-security-review.md` |
```

- [ ] **Step 3: Add the dashboard rows**

In the Phase 2 metrics-dashboard table, after the `Endpoint-convention-violation count` row, add:

```markdown
| Security: Critical/High findings | — | — | security health |
| Exposed secrets (git history) | — | — | security health |
| Security-config violations | — | — | security health |
```

And update the sentence below the table, old:

```markdown
Every row maps to a metric one of the two health reports actually emits — don't add rows no agent produces.
```

New:

```markdown
Every row maps to a metric one of the three health reports actually emits — don't add rows no agent produces.
```

- [ ] **Step 4: Scaffold the report directory in `commands/studious-init.md`**

In the directory list at lines 61–65, after `- docs/studious/product-reviews/` (backticked in the file), add the line:

```markdown
- `docs/studious/security-reviews/`
```

- [ ] **Step 5: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass (`test_contract_injection.py::test_each_fanout_command_reads_the_anchored_contract` still finds the anchored path in deep-review.md — untouched).

- [ ] **Step 6: Commit**

```bash
git add commands/deep-review.md commands/studious-init.md
git commit -m "feat: add security posture as /deep-review's sixth periodic lane"
```

---

### Task 7: Operational readiness — contract row, template, pre-mortem seeding, acceptance question

**Files:**

- Modify: `reference/design-doc-contract.md` (required-sections table)
- Modify: `templates/design-doc.md` (scaffold section)
- Modify: `commands/gate-design-review.md` (Part 3 seeding)
- Modify: `commands/gate-acceptance.md` (Part 3 second question)

**Interfaces:**

- Consumes: nothing from earlier tasks (independent seam).
- Produces: the section name "Operational readiness" referenced by all four files; Task 8's architecture-auditor dimension verifies its migration commitments at gate time.

- [ ] **Step 1: Add the contract row**

In `reference/design-doc-contract.md`'s required-sections table, after the `Alternatives considered` row and before the `Open questions` row, add:

```markdown
| Operational readiness | (seeds the technical pre-mortem lane and gate-time verification, not a numbered product question) | Names the migration plan and its rollback, the rollout strategy, and how the team will know the feature is working or failing in production (logs, metrics, alarms). "N/A — no operational surface" with a one-line reason satisfies it — a local tool shouldn't fabricate an ops plan, but the section must say so explicitly rather than be omitted. |
```

- [ ] **Step 2: Add the template section**

In `templates/design-doc.md`, between the `## Alternatives considered` block and the `## Open questions` heading, add:

```markdown
## Operational readiness

<!-- Migration plan and its rollback, rollout strategy, and how you'll know the feature
     is working or failing in production (logs, metrics, alarms). Write
     "N/A — no operational surface" with a one-line reason if that's the truth. -->
```

- [ ] **Step 3: Seed the pre-mortem from the section**

In `commands/gate-design-review.md` Part 3, replace:

Old:

```markdown
Seed the product lane from the product-reviewer findings and persona walkthrough; seed the technical lane from the design's architecture and data flow.
```

New:

```markdown
Seed the product lane from the product-reviewer findings and persona walkthrough; seed the technical lane from the design's architecture and data flow, and from its Operational readiness section — an ops commitment that could silently not ship (a migration without its rollback, a feature with no failure signal) is a technical-lane item.
```

- [ ] **Step 4: Add the acceptance question**

In `commands/gate-acceptance.md` Part 3, replace:

Old:

```markdown
Close with one gate-specific question the checklist doesn't ask: **One complaint** — what's the single thing a real user would complain about if we shipped this as-is? Be specific. There's always something.
```

New:

```markdown
Close with two gate-specific questions the checklist doesn't ask:

- **One complaint** — what's the single thing a real user would complain about if we shipped this as-is? Be specific. There's always something.
- **Operability** — does the branch deliver what the design doc's Operational readiness section committed to (the migration and its rollback, the rollout strategy, the working/failing signals)? If the section said "N/A — no operational surface", confirm that still holds for what was actually built.
```

- [ ] **Step 5: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add reference/design-doc-contract.md templates/design-doc.md commands/gate-design-review.md commands/gate-acceptance.md
git commit -m "feat: thread operational readiness through design contract, pre-mortem, and acceptance"
```

---

### Task 8: architecture-auditor — data & migrations dimension + performance-seam assignment

**Files:**

- Modify: `agents/architecture-auditor.md` (new dimension, expanded bottleneck bullet, dimension enum)
- Modify: `agents/code-auditor.md` (runtime-performance exclusion line)

**Interfaces:**

- Consumes: the Operational readiness section name (Task 7) — the migrations dimension verifies its commitments.
- Produces: dimension enum value `data-migrations` in architecture-auditor's output rows.

- [ ] **Step 1: Expand the bottleneck bullet (performance-seam ownership)**

In `agents/architecture-auditor.md`, under `### Complexity distribution`, replace:

Old:

```markdown
- Are there concrete bottlenecks introduced — N+1 queries, unbounded loops, synchronous work that should be deferred?
```

New:

```markdown
- Are there concrete runtime bottlenecks introduced — N+1 queries, hot-path algorithmic complexity, chatty sequential I/O, a missing index on a newly queried column, unbounded loops, synchronous work that should be deferred? This lane owns backend runtime performance; frontend-reviewer owns render and bundle.
```

- [ ] **Step 2: Add the data & migrations dimension**

After the `### Complexity distribution` block and before `## Output`, add:

```markdown
### Data & migrations

- Is every schema migration in the changeset reversible — a real down-path, not a comment?
- Is it compatible with the previous deploy's still-running code (a column dropped or renamed while old code reads it, an enum value removed while old code writes it)?
- Are backfills safe at production scale — batched, resumable, no long-held locks on hot tables?
- If the design doc's Operational readiness section commits to a migration/rollback plan, does the changeset deliver it? (`review-architecture` watches migration posture periodically after merge; you are the gate-time check.)
```

- [ ] **Step 3: Update the dimension enum**

In `agents/architecture-auditor.md` Output section, replace:

Old:

```markdown
Emit findings per the injected output-row schema: **severity** is the mapped tier above; **location** is file:line (for a coupling finding, name BOTH modules — two locations, not one); **dimension** is one of pattern-fit / coupling / complexity; **finding** notes drift as documented vs actual.
```

New:

```markdown
Emit findings per the injected output-row schema: **severity** is the mapped tier above; **location** is file:line (for a coupling finding, name BOTH modules — two locations, not one); **dimension** is one of pattern-fit / coupling / complexity / data-migrations; **finding** notes drift as documented vs actual.
```

- [ ] **Step 4: Name the perf owner in code-auditor's exclusions**

In `agents/code-auditor.md`, in the `**Does NOT check:**` list (as it stands after Task 3), replace:

Old:

```markdown
- Test adequacy — test-auditor handles this
```

New:

```markdown
- Test adequacy — test-auditor handles this
- Runtime performance — architecture-auditor owns concrete bottlenecks; the idiom linters' PERF-class findings still count as idiomatic style
```

- [ ] **Step 5: Verify lint, references, and the full test suite**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q`
Expected: `0 error(s)`, `Reference check passed`, all tests pass.

- [ ] **Step 6: Commit**

```bash
git add agents/architecture-auditor.md agents/code-auditor.md
git commit -m "feat: gate-time data-migrations dimension; assign backend perf to architecture-auditor"
```

---

### Task 9: Epic driver fan-out + repo-wide count updates

**Files:**

- Modify: `workflows/epic-driver.js:47-50` (AUDITORS array), `:342` (comment)
- Modify: `tests/python/test_contract_injection.py:148` (docstring count)
- Modify: `README.md:69`, `README.md:98`
- Modify: `.github/workflows/gate-audit-pr.yml:85`
- Modify: `CLAUDE.md:56`
- Modify: `CONTRIBUTING.md` (model-assignment lists)

**Interfaces:**

- Consumes: agent names `studious:test-auditor`, `studious:infra-auditor` (Tasks 2–3); the numbering "up to 10" produced by Task 4 (8 subagents + inline a11y + premortem = 10 lanes; 9 max subagents).
- Produces: nothing downstream — this is the closing sweep.

- [ ] **Step 1: Append both auditors to the driver's fan-out**

In `workflows/epic-driver.js`, replace:

Old:

```javascript
const AUDITORS = [
  'studious:security-auditor', 'studious:code-auditor', 'studious:doc-auditor',
  'studious:architecture-auditor', 'studious:ux-reviewer', 'studious:frontend-reviewer',
]
```

New:

```javascript
const AUDITORS = [
  'studious:security-auditor', 'studious:code-auditor', 'studious:doc-auditor',
  'studious:architecture-auditor', 'studious:test-auditor', 'studious:infra-auditor',
  'studious:ux-reviewer', 'studious:frontend-reviewer',
]
```

(Both agents self-skip when their lane doesn't apply — the dispatch prompts already say "If your lane does not apply, say so", and the agents' own prompts instruct the skip — so the driver needs no routing logic; `joinReports` keeps labeling lanes by index.)

- [ ] **Step 2: Update the driver's lane-count comment**

Old:

```javascript
  // One story-slot fans out to 6 auditors + a compiler; the harness queues
```

New:

```javascript
  // One story-slot fans out to 8 auditors + a compiler; the harness queues
```

- [ ] **Step 3: Update the contract-test docstring**

In `tests/python/test_contract_injection.py`, replace:

Old:

```python
    The driver dispatches the six auditors directly (per-story and epic-finale) and
```

New:

```python
    The driver dispatches the eight auditors directly (per-story and epic-finale) and
```

- [ ] **Step 4: Update README line 69**

Old:

```markdown
- Audit before merge with `/gate-audit`. Security, code quality, docs, and architecture always run; UX, frontend, and an accessibility pass (via the `web-design-guidelines` skill, or a vendored fallback when it isn't installed) join in on projects with a web surface; and if the design-review gate recorded a pre-mortem register for this branch, a dedicated auditor checks each predicted failure mode — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 8 auditors, each staying in its lane.
```

New:

```markdown
- Audit before merge with `/gate-audit`. Security, code quality, docs, architecture, and test adequacy always run; UX, frontend, and an accessibility pass (via the `web-design-guidelines` skill, or a vendored fallback when it isn't installed) join in on projects with a web surface; infrastructure joins in when the changeset touches IaC, container, or CI-pipeline files; and if the design-review gate recorded a pre-mortem register for this branch, a dedicated auditor checks each predicted failure mode — REALIZED / NOT REALIZED / CAN'T VERIFY, evidence attached. Up to 10 auditors, each staying in its lane.
```

- [ ] **Step 5: Update README line 98**

Old:

```markdown
`.github/workflows/gate-audit-pr.yml` runs `/gate-audit` non-interactively against a PR and posts the report as a PR comment — the same auditor fan-out you'd get locally (up to 8, depending on the project's web surface and whether a pre-mortem register exists), without anyone having to remember to run it.
```

New (edit only the parenthetical; keep the rest of the line):

```markdown
`.github/workflows/gate-audit-pr.yml` runs `/gate-audit` non-interactively against a PR and posts the report as a PR comment — the same auditor fan-out you'd get locally (up to 10, depending on the project's web surface, whether the changeset touches infrastructure files, and whether a pre-mortem register exists), without anyone having to remember to run it.
```

- [ ] **Step 6: Update the CI workflow's skip-comment count**

In `.github/workflows/gate-audit-pr.yml:85`, replace `the 6-7-agent audit fan-out` with `the up-to-9-agent audit fan-out` (9 = the maximum subagent count; the accessibility pass is inline).

- [ ] **Step 7: Update CLAUDE.md's contract count from evidence**

First verify the post-change carrier count:

Run: `grep -l "Shared contract" agents/*.md | wc -l`
Expected: `16` (13 existing carriers + 3 new agents).

Then in `CLAUDE.md:56`, replace `The 14 review/audit agents share a standardized prompt contract` with `The 16 review/audit agents share a standardized prompt contract`. (The old "14" was already drifted — the pre-change carrier count is 13; fix to the verified number, don't add 3 to 14.)

- [ ] **Step 8: Update CONTRIBUTING's model-assignment lists**

Old:

```markdown
- **`opus`** — security, architecture, and product/UX judgment: `security-auditor`, `architecture-auditor`, `product-reviewer`, `ux-reviewer`, `review-architecture`, `review-product-health`.
- **`inherit`** — code hygiene, docs, frontend code, inventory sweeps, and triage: `code-auditor`, `doc-auditor`, `frontend-reviewer`, `review-codebase-health`, `review-interface-health`, `review-readme`, `backlog-priorities`, `backlog-hygiene`.
```

New:

```markdown
- **`opus`** — security, architecture, and product/UX judgment: `security-auditor`, `infra-auditor`, `architecture-auditor`, `product-reviewer`, `ux-reviewer`, `review-architecture`, `review-product-health`, `review-security-health`.
- **`inherit`** — code hygiene, docs, tests, frontend code, inventory sweeps, and triage: `code-auditor`, `doc-auditor`, `test-auditor`, `frontend-reviewer`, `review-codebase-health`, `review-interface-health`, `review-readme`, `backlog-priorities`, `backlog-hygiene`.
```

- [ ] **Step 9: Verify everything**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py && uv run --no-project --with pytest pytest tests/python -q && uv run --no-project python scripts/validate_plugin.py`
Expected: all clean.

- [ ] **Step 10: Commit**

```bash
git add workflows/epic-driver.js tests/python/test_contract_injection.py README.md .github/workflows/gate-audit-pr.yml CLAUDE.md CONTRIBUTING.md
git commit -m "feat: fan out new auditors in epic driver; sync roster counts repo-wide"
```

---

### Task 10: Full verification and stale-count sweep

**Files:** none created or modified (verification only; fix anything found, amend into the offending task's area with a targeted commit).

- [ ] **Step 1: Run the full CI-equivalent suite**

```bash
npx -y markdownlint-cli2
uv run --no-project python scripts/check_references.py
uv run --no-project python scripts/validate_plugin.py
uv run --no-project --with pytest pytest tests/python -v
bash tests/test_gate_ledger.sh
shellcheck bin/gate-ledger hooks/gate-reminder.sh tests/test_gate_ledger.sh
```

Expected: every command exits 0 (gate-ledger and shellcheck are untouched by this change — they confirm no accidental damage).

- [ ] **Step 2: Grep for stale counts — expect ZERO hits from every command**

```bash
grep -rn "up to 8\|Up to 8" README.md commands agents
grep -rn "all five" commands/deep-review.md
grep -rn "The 14" CLAUDE.md
grep -rn "six auditors\|6 auditors" workflows tests
grep -rn "6-7-agent" .github/workflows
```

Expected: no output from any command. Also confirm the intentional non-edit: `grep -n "all five" reference/epic-plan-contract.md` still matches — that "five" counts gate-profile stages, not reviews, and must NOT change.

- [ ] **Step 3: Review the complete diff against the spec**

Run: `git diff origin/main...HEAD --stat`
Expected: 4 new files (`reference/infra-checklist.md`, `agents/infra-auditor.md`, `agents/test-auditor.md`, `agents/review-security-health.md`; plus the spec and this plan), and modifications to: `tests/python/test_agent_descriptions.py`, `tests/python/test_contract_injection.py`, `reference/severity-rubric.md`, `agents/security-auditor.md`, `agents/code-auditor.md`, `agents/architecture-auditor.md`, `commands/gate-audit.md`, `commands/deep-review.md`, `commands/studious-init.md`, `reference/design-doc-contract.md`, `templates/design-doc.md`, `commands/gate-design-review.md`, `commands/gate-acceptance.md`, `workflows/epic-driver.js`, `README.md`, `.github/workflows/gate-audit-pr.yml`, `CLAUDE.md`, `CONTRIBUTING.md`. Anything outside this list is scope creep — investigate before proceeding.
