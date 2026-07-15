# Epic-Driven Audit Path — First-Round Changeset Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `workflows/epic-driver.js`'s epic-driven audit path (`/work-through`) the same first-round changeset routing `/gate-audit` already has, so a story's or finale's first audit round doesn't unconditionally dispatch all 9 auditors when some plainly don't apply — while fixing the `carriedForward` landmine that a routed subset would otherwise trigger.

**Architecture:** One new canonical reference file (`reference/audit-routing-signals.md`) holds the IaC and frontend file-pattern lists, read by both `commands/gate-audit.md`'s dispatching agent and a new low-effort mechanical dispatch in `workflows/epic-driver.js`. That dispatch returns `{infraMatch, frontendMatch}`; a new pure function (`resolveAuditRoster`) maps those flags to a `routed`/`routedOut` roster; `routed` replaces the hardcoded `AUDITORS` constant everywhere `dispatched`/`carriedForward` are computed in `auditRound()` and `finaleAuditRound()`. `joinReports` and `auditFanIn` gain a third, distinct "routed out" state alongside the existing "carried forward" and "AGENT DIED" states, visible in the human-facing compiled Summary.

**Tech Stack:** Plain JS (Workflow script, no Node.js module system — `workflows/epic-driver.js` is preprocessed and executed as an async function body, not `require`d), Python/pytest for tests (extracts and runs pure functions in a `node -e` subprocess, and runs the full driver end-to-end with a mocked `agent()`), Markdown for the reference file and `commands/gate-audit.md` prose edit.

Read `docs/superpowers/specs/2026-07-15-audit-first-round-routing-design.md` for the full design rationale before starting — this plan implements it task-by-task but does not repeat its "why."

## Global Constraints

- **Single canonical pattern-list source.** The IaC and frontend file-pattern lists live in exactly one place, `reference/audit-routing-signals.md`. Neither `commands/gate-audit.md` nor `workflows/epic-driver.js` embeds a second copy — both point at the file.
- **Fail open, always.** Any of: a died/unparseable mechanical routing dispatch, a match flag that's missing or not exactly `false`, or a changed file that only ambiguously matches a pattern — all resolve to dispatching the lane (routing it *in*), never routing it out. This mirrors `resolveReauditScope`'s existing fail-closed-to-more-auditing posture and `gate-audit.md`'s own "when ambiguous, run" bias.
- **Operability (auditor 10 / `studious:operability-auditor`) is never routed by this story.** It stays unconditionally in `routed` on every round. Do not add a skip condition for it.
- **`routed` replaces `AUDITORS` everywhere `dispatched`/`carriedForward` are derived**, in both `auditRound()` and `finaleAuditRound()` — this is the landmine fix (design doc "Composition point"). `resolveReauditScope`'s second argument becomes `routed`, not `AUDITORS`.
- **No new persistent/registered auditor identity.** The mechanical routing dispatch is ad hoc-prompted (`schema: REPORT`, `effort: 'low'`), the same shape `ledgerScopeCheckPrompt`/`ledgerAuditPrior` already use — not a 10th entry in `AUDITORS`, not a new `agents/*.md` file.
- **Routed-out visibility is user-facing, not just internal.** `auditFanIn`'s compiled **Summary** — the section a human reads — must carry one plain line per routed-out lane in the form `"<lane>: routed out — not applicable to this changeset (<reason>)"`, with no internal file paths (e.g. `reference/audit-routing-signals.md`) leaking into that reason text.
- **Reuse the existing test harness precedent**, don't invent a new one: `tests/python/test_driver_crash_hardening.py` exports `_extract_function`, `_run_node`, `_run_driver`, `AUDITOR_SHORT_NAMES`, `DRIVER`, `REPO_ROOT`, `MAX_FIX_CYCLES` — import them exactly as `tests/python/test_delta_scoped_reaudit.py` does.
- **Frontend file-pattern list deliberately excludes bare `.js`/`.ts`.** Only framework-specific extensions (`.jsx`, `.tsx`, `.vue`, `.svelte`) and stylesheet/template extensions count as a deterministic frontend signal — a plain `.js`/`.ts` file is not a reliable frontend-only signal (it's also what this very repo's own `workflows/*.js` scripts use) and would make the routing dispatch's pattern match too broad to ever route anything out on a JS-heavy backend repo. `/gate-audit`'s own agent-executed check is unaffected by this — it still exercises full judgment on `.js`/`.ts` content, this list only binds the mechanical, judgment-free JS-side dispatch.
- **CI verification commands (run at the end of Task 4, and after any task that touches these files):**
  - `node --check workflows/epic-driver.js`
  - `npx -y eslint@10.6.0 --report-unused-disable-directives workflows/`
  - `bash tests/test_workflows_lint.sh`
  - `npx -y markdownlint-cli2`
  - `uv run --no-project python scripts/check_references.py`
  - `uv run --no-project --with pytest pytest tests/python -v`

---

### Task 1: Canonical routing-signal reference file + `gate-audit.md` prose edit

**Files:**
- Create: `reference/audit-routing-signals.md`
- Modify: `commands/gate-audit.md` (auditor 9's paragraph, and auditors 6–8's per-changeset bullet)
- Test: `tests/python/test_audit_first_round_routing.py` (new file)

**Interfaces:**
- Produces: `reference/audit-routing-signals.md`, a Markdown file with two named sections ("Infrastructure signal" and "Frontend signal"), each listing patterns as glob-style tokens in backticks. Later tasks (2–4) read this file's *existence and section headers* only conceptually — the actual pattern list is consumed by an LLM agent at runtime (Task 3's mechanical dispatch), not parsed by JS, so no code in later tasks imports structured data from it.

- [ ] **Step 1: Write the reference file**

Create `reference/audit-routing-signals.md`:

```markdown
# Audit routing signals — canonical file-pattern lists

Canonical source for the deterministic (non-content-judged) first-round changeset-routing
rules `commands/gate-audit.md` (auditor 9, and auditors 6–8's per-changeset clause) and
`workflows/epic-driver.js`'s mechanical routing dispatch both apply. Neither restates these
lists inline — both point here, so there is exactly one list to ever drift from. Auditor 10
(operability) is deliberately not covered here: its skip condition is content-judged ("Judge
from the diff's content… not file paths alone" — see `commands/gate-audit.md`), not a
file-pattern rule, and stays unconditionally dispatched on the epic-driven path (see the
design doc for issue #138).

**When ambiguous, apply the pattern anyway — default to running the lane, not skipping it.**
A file that loosely or partially matches a pattern below counts as a match.

## Infrastructure signal (auditor 9 / `infra-auditor`)

A changeset matches this signal if any changed file is:

- IaC: `*.tf`, `*.tfvars`, `*.hcl`, a CloudFormation/SAM template, `cdk.json` or a CDK stack
  source, `Pulumi.yaml`
- Kubernetes manifests or Helm charts
- `Dockerfile*`, `docker-compose*`, `compose.*`
- CI pipeline configs: `.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`
- Deploy configs: `serverless.*`, `Procfile`, `fly.toml`, `render.yaml`, Ansible playbooks

No match on any of these → no infrastructure signal.

## Frontend signal (auditors 6–8 per-changeset clause / `ux-reviewer`, `frontend-reviewer`, Web Interface Guidelines)

A changeset matches this signal if any changed file is:

- Templates: `*.html`, `*.erb`, `*.ejs`, `*.hbs`, `*.pug`
- Components: `*.jsx`, `*.tsx`, `*.vue`, `*.svelte`
- Stylesheets: `*.css`, `*.scss`, `*.sass`, `*.less`

No match on any of these → no frontend signal.

Deliberately excludes bare `.js`/`.ts` files: unlike the framework-specific extensions
above, a plain `.js`/`.ts` file is not a reliable frontend-only signal — it's the same
extension backend services, CLI tools, and this very repository's own `workflows/*.js`
scripts use. `/gate-audit`'s own agent-executed check (auditors 6–8) can still use judgment
beyond this list when it reads a `.js`/`.ts` file's actual content and surrounding context;
`workflows/epic-driver.js`'s mechanical routing dispatch, which has no such judgment,
applies this list literally and therefore does not treat a bare `.js`/`.ts` change as a
frontend signal by itself.

This is the *per-changeset* half of `gate-audit.md`'s auditors 6–8 rule only — the
*project-level* "DESIGN.md has no `## Surfaces` web entry, and the repo confirms it" half is
a separate check `gate-audit.md`'s own prose still owns directly (see
`/extract-design-system` Step 1's canonical web-signal list); it is not part of this file
and not applied by `workflows/epic-driver.js`'s routing dispatch (see the design doc for
issue #138, Out of scope).
```

- [ ] **Step 2: Edit `commands/gate-audit.md`'s auditor 9 paragraph to point at the new file**

Find this exact paragraph (currently one line):

```
Auditor 9 (infrastructure) is changeset-routed: skip it when the changeset touches no infrastructure files — IaC (`*.tf`, `*.tfvars`, `*.hcl`, CloudFormation/SAM templates, `cdk.json` or CDK stack sources, `Pulumi.yaml`), Kubernetes manifests or Helm charts, `Dockerfile*` / `docker-compose*` / `compose.*`, CI pipeline configs (`.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`), or deploy configs (`serverless.*`, `Procfile`, `fly.toml`, `render.yaml`, Ansible playbooks). Note "No infrastructure changes detected — infrastructure audit skipped." When ambiguous, run — default to running, not skipping. This file-signal list lives only here; the agent itself self-skips if dispatched against a changeset with none of these.
```

Replace it with:

```
Auditor 9 (infrastructure) is changeset-routed: skip it when the changeset touches no infrastructure files, per the Infrastructure signal list in `reference/audit-routing-signals.md` — consult it, don't restate it. Note "No infrastructure changes detected — infrastructure audit skipped." When ambiguous, run — default to running, not skipping. The agent itself self-skips if dispatched against a changeset matching none of that list.
```

- [ ] **Step 3: Edit `commands/gate-audit.md`'s auditors 6–8 per-changeset bullet to point at the new file**

Find this exact bullet (part of the "Auditors 6–8 (ux, frontend, accessibility)" list):

```
- **Per-changeset:** the changeset has no frontend changes (no modified template, component, CSS, or JS files). Note "No frontend changes detected — frontend audits skipped."
```

Replace it with:

```
- **Per-changeset:** the changeset has no frontend changes, per the Frontend signal list in `reference/audit-routing-signals.md` — consult it, don't restate it. Note "No frontend changes detected — frontend audits skipped."
```

Leave the **Project-level** bullet immediately above it, and everything else in that section, unchanged.

- [ ] **Step 4: Write the failing test — reference file exists and is pointed at**

Create `tests/python/test_audit_first_round_routing.py`:

```python
"""Regression tests for first-round changeset routing on the epic-driven audit
path (issue #138): `workflows/epic-driver.js`'s `auditRound()`/`finaleAuditRound()`
unconditionally dispatched all 9 auditors on every un-narrowed round, unlike
`commands/gate-audit.md`'s prose-routed standalone gate. This adds a mechanical,
judgment-free `agent()` dispatch (the Workflow script itself has no filesystem/exec
access) that reads one canonical pattern-list file, `reference/audit-routing-signals.md`,
plus a pure `resolveAuditRoster` function that maps its match flags to a
`routed`/`routedOut` roster — replacing `AUDITORS` with `routed` everywhere
`dispatched`/`carriedForward` are computed, which also fixes a landmine: `carriedForward`
computed against the full `AUDITORS` constant would otherwise report a routed-out lane as
a false-clean "carried forward."

Following this repo's established precedent (`test_contract_injection.py`,
`test_delta_scoped_reaudit.py`): pure, explicitly-parameterized functions are extracted
verbatim from `workflows/epic-driver.js` and executed standalone in a plain Node process;
scheduler-level behavior is proven by running the real, unmodified driver source under
`test_driver_crash_hardening.py`'s documented harness shape.
"""

from __future__ import annotations

from pathlib import Path

from test_driver_crash_hardening import (
    AUDITOR_SHORT_NAMES,
    DRIVER,
    MAX_FIX_CYCLES,
    REPO_ROOT,
    _extract_function,
    _run_driver,
    _run_node,
)

GATE_AUDIT_MD = REPO_ROOT / "commands" / "gate-audit.md"
ROUTING_SIGNALS_MD = REPO_ROOT / "reference" / "audit-routing-signals.md"


# ---------- Task 1: canonical reference file ----------


def test_routing_signals_reference_file_exists_with_both_signal_sections() -> None:
    assert ROUTING_SIGNALS_MD.is_file(), "reference/audit-routing-signals.md is missing"
    text = ROUTING_SIGNALS_MD.read_text()
    assert "## Infrastructure signal" in text
    assert "## Frontend signal" in text
    # Spot-check a few tokens moved from gate-audit.md's old inline prose.
    for token in ("*.tf", "Dockerfile*", ".github/workflows"):
        assert token in text, f"expected infra pattern {token!r} in the reference file"
    for token in ("*.jsx", "*.tsx", "*.css"):
        assert token in text, f"expected frontend pattern {token!r} in the reference file"


def test_routing_signals_file_documents_the_bare_js_ts_exclusion() -> None:
    text = ROUTING_SIGNALS_MD.read_text()
    assert "bare `.js`/`.ts`" in text, (
        "the deliberate exclusion of plain .js/.ts from the frontend signal must be "
        "documented, not silently decided"
    )


def test_gate_audit_md_points_at_the_reference_file_instead_of_embedding_lists() -> None:
    text = GATE_AUDIT_MD.read_text()
    assert "reference/audit-routing-signals.md" in text, (
        "commands/gate-audit.md no longer points auditor 9 / 6-8 at the canonical "
        "reference file"
    )
    # The old inline IaC list must be gone from auditor 9's paragraph, not duplicated
    # alongside the new pointer.
    infra_para_start = text.index("Auditor 9 (infrastructure)")
    infra_para_end = text.index("\n\n", infra_para_start)
    infra_para = text[infra_para_start:infra_para_end]
    assert "*.tfvars" not in infra_para, (
        "auditor 9's paragraph still embeds the old inline IaC pattern list — should "
        "point at reference/audit-routing-signals.md instead"
    )
    assert "reference/audit-routing-signals.md" in infra_para


def test_check_references_would_resolve_the_new_pointer() -> None:
    """Mirrors what scripts/check_references.py's REFERENCE_RE already scans for
    (reference/[A-Za-z0-9_./<>-]+\\.md) — confirms the literal path gate-audit.md
    now cites resolves to a real file, without invoking the full CI script here."""
    import re

    ref_re = re.compile(r"reference/[A-Za-z0-9_./<>-]+\.md")
    text = GATE_AUDIT_MD.read_text()
    refs = set(ref_re.findall(text))
    assert "reference/audit-routing-signals.md" in refs
    for ref in refs:
        assert (REPO_ROOT / ref).is_file(), f"{ref} referenced in gate-audit.md but missing"
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v`
Expected: all 4 tests PASS (Steps 1–3 already created the files these tests check — this step is verification, not TDD-red-first, since a docs-only change has nothing to "fail minimally" against; the tests exist to prevent regression from here on).

- [ ] **Step 6: Run markdownlint and check_references**

Run: `npx -y markdownlint-cli2` and `uv run --no-project python scripts/check_references.py`
Expected: both exit 0, no new findings.

- [ ] **Step 7: Commit**

```bash
git add reference/audit-routing-signals.md commands/gate-audit.md tests/python/test_audit_first_round_routing.py
git commit -m "feat(gate-audit): canonical audit-routing-signals reference file (#138)"
```

---

### Task 2: `resolveAuditRoster` pure function

**Files:**
- Modify: `workflows/epic-driver.js` (add function immediately after `resolveReauditScope`, which ends at the line `}` closing its `return { narrowed: true, ... }` block — i.e., directly before the comment block that begins `// Label every auditor lane even when its agent died...` above `joinReports`)
- Test: `tests/python/test_audit_first_round_routing.py` (append)

**Interfaces:**
- Consumes: nothing new — `AUDITORS` (existing constant, an array of 9 `studious:<lane>` strings).
- Produces: `resolveAuditRoster(matchFlags, auditors) → { routed: string[], routedOut: {auditor: string, reason: string}[] }`, called by Task 4's wiring into `auditRound`/`finaleAuditRound`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/python/test_audit_first_round_routing.py`:

```python
import json

AUDITORS_JS = json.dumps([f"studious:{n}" for n in AUDITOR_SHORT_NAMES])


# ---------- Task 2: resolveAuditRoster ----------


def _resolve_roster(match_flags_js: str) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "resolveAuditRoster")
    script = f"""
{fn}
const matchFlags = {match_flags_js}
console.log(JSON.stringify(resolveAuditRoster(matchFlags, {AUDITORS_JS})))
"""
    return _run_node(script)


def test_both_signals_match_routes_all_nine_lanes_in() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: true }')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []


def test_no_infra_match_routes_out_only_infra_auditor() -> None:
    result = _resolve_roster('{ infraMatch: false, frontendMatch: true }')
    assert "studious:infra-auditor" not in result["routed"]
    assert len(result["routed"]) == 8
    assert result["routedOut"] == [
        {"auditor": "studious:infra-auditor", "reason": "no infrastructure changes detected"}
    ]


def test_no_frontend_match_routes_out_ux_and_frontend_reviewer_only() -> None:
    result = _resolve_roster('{ infraMatch: true, frontendMatch: false }')
    assert "studious:ux-reviewer" not in result["routed"]
    assert "studious:frontend-reviewer" not in result["routed"]
    assert len(result["routed"]) == 7
    reasons = {e["auditor"]: e["reason"] for e in result["routedOut"]}
    assert reasons == {
        "studious:ux-reviewer": "no frontend changes detected",
        "studious:frontend-reviewer": "no frontend changes detected",
    }


def test_neither_signal_matches_routes_out_all_three_routable_lanes() -> None:
    result = _resolve_roster('{ infraMatch: false, frontendMatch: false }')
    assert set(result["routed"]) == {
        "studious:security-auditor", "studious:code-auditor", "studious:doc-auditor",
        "studious:architecture-auditor", "studious:test-auditor", "studious:operability-auditor",
    }
    assert len(result["routedOut"]) == 3


def test_operability_is_never_routed_out_regardless_of_flags() -> None:
    for flags in (
        '{ infraMatch: true, frontendMatch: true }',
        '{ infraMatch: false, frontendMatch: false }',
    ):
        result = _resolve_roster(flags)
        assert "studious:operability-auditor" in result["routed"]


def test_null_match_flags_fails_open_to_full_roster() -> None:
    """A died/unparseable mechanical dispatch (matchFlags = null) must route
    everything IN, never guess a partial roster — the same fail-closed-to-more-
    auditing posture resolveReauditScope already uses."""
    result = _resolve_roster('null')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []


def test_malformed_match_flags_missing_keys_fails_open() -> None:
    result = _resolve_roster('{}')
    assert result["routed"] == [f"studious:{n}" for n in AUDITOR_SHORT_NAMES]
    assert result["routedOut"] == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v -k resolve_roster or match`
Expected: FAIL with a Node error — `resolveAuditRoster is not defined` (the function doesn't exist in `workflows/epic-driver.js` yet).

- [ ] **Step 3: Implement `resolveAuditRoster` in `workflows/epic-driver.js`**

In `workflows/epic-driver.js`, immediately after the closing brace of `resolveReauditScope` (the function that ends with `return { narrowed: true, blockingAuditors, priorSha: priorResult.sha, reason: ... } }`) and before the comment block starting `// Label every auditor lane even when its agent died —`, insert:

```js
// First-round changeset routing (#138): decides which of `auditors` this round
// dispatches vs routes out as not applicable to the changeset, from the mechanical
// routing dispatch's {infraMatch, frontendMatch} flags (resolveRoutingMatchFlags,
// added in a later story task) — holds no pattern-matching logic of its own; the
// patterns themselves live in reference/audit-routing-signals.md, read by that
// dispatch, so there is structurally one canonical list, never a second
// hand-maintained copy here. Pure and explicitly parameterized (no closures over
// module state), matching this file's own precedent (resolveReauditScope,
// crashParkArgs, stalledFinaleEntry) for standalone extraction by
// tests/python/test_audit_first_round_routing.py. Fails OPEN (routes a lane IN,
// never out) on missing/malformed flags — the same fail-closed-to-more-auditing
// posture resolveReauditScope already uses, and the same "when ambiguous, run"
// bias commands/gate-audit.md's own routing rules use.
function resolveAuditRoster(matchFlags, auditors) {
  const infraMatch = !matchFlags || matchFlags.infraMatch !== false
  const frontendMatch = !matchFlags || matchFlags.frontendMatch !== false
  const routedOut = []
  const routed = auditors.filter(a => {
    if (a.endsWith(':infra-auditor') && !infraMatch) {
      routedOut.push({ auditor: a, reason: 'no infrastructure changes detected' })
      return false
    }
    if ((a.endsWith(':ux-reviewer') || a.endsWith(':frontend-reviewer')) && !frontendMatch) {
      routedOut.push({ auditor: a, reason: 'no frontend changes detected' })
      return false
    }
    return true
  })
  return { routed, routedOut }
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v`
Expected: all tests PASS, including Task 1's.

- [ ] **Step 5: Run `node --check`**

Run: `node --check workflows/epic-driver.js`
Expected: exits 0, no syntax errors.

- [ ] **Step 6: Commit**

```bash
git add workflows/epic-driver.js tests/python/test_audit_first_round_routing.py
git commit -m "feat(epic-driver): add resolveAuditRoster pure function (#138)"
```

---

### Task 3: Mechanical routing dispatch + `joinReports`/`auditFanIn` routed-out support

**Files:**
- Modify: `workflows/epic-driver.js` (add `routingScopeCheckPrompt` near `ledgerScopeCheckPrompt`; add `resolveRoutingMatchFlags` near `ledgerAuditPrior`; extend `joinReports` and `auditFanIn` signatures)
- Test: `tests/python/test_audit_first_round_routing.py` (append)

**Interfaces:**
- Consumes: `REPORT` schema (existing), `resolveAuditRoster` (Task 2).
- Produces:
  - `routingScopeCheckPrompt(dir, base) → string` (pure prompt builder)
  - `resolveRoutingMatchFlags(dir, base, label, phaseLabel) → Promise<{infraMatch, frontendMatch} | null>` (async, calls `agent()`) — consumed by Task 4's wiring.
  - `joinReports(dispatched, reports, carriedForward, priorSha, fixDeltaDispatched, fixDeltaReport, routedOut)` — extended signature (existing 6 params + new 7th `routedOut`, default-safe when omitted).
  - `auditFanIn(story, reports, base, dir, nextPhase, routed, routedOut)` — extended signature (existing 5 params + new `routed`/`routedOut`).

- [ ] **Step 1: Write the failing tests for `joinReports`'s new `routedOut` param**

Append to `tests/python/test_audit_first_round_routing.py`:

```python
# ---------- Task 3: joinReports routedOut support ----------


def _join_reports_with_routed_out(dispatched, reports, carried, prior_sha,
                                    fix_delta_dispatched, fix_delta_report, routed_out) -> dict:
    source = DRIVER.read_text()
    fn = _extract_function(source, "joinReports")
    script = f"""
{fn}
const result = joinReports(
  {json.dumps(dispatched)},
  {json.dumps(reports)},
  {json.dumps(carried)},
  {json.dumps(prior_sha)},
  {json.dumps(fix_delta_dispatched)},
  {json.dumps(fix_delta_report)},
  {json.dumps(routed_out)}
)
console.log(JSON.stringify(result))
"""
    return _run_node(script)


def test_join_reports_renders_routed_out_lanes_distinctly() -> None:
    result = _join_reports_with_routed_out(
        dispatched=["studious:security-auditor"],
        reports=[{"findings": "clean"}],
        carried=["studious:code-auditor"],
        prior_sha="abc123",
        fix_delta_dispatched=False,
        fix_delta_report=None,
        routed_out=[{"auditor": "studious:infra-auditor", "reason": "no infrastructure changes detected"}],
    )
    assert result["missing"] == []
    assert (
        "--- studious:infra-auditor --- (routed out — not applicable to this changeset: "
        "no infrastructure changes detected; never dispatched, no prior report)" in result["joined"]
    )
    # Never conflated with carried-forward or AGENT DIED.
    assert "studious:infra-auditor --- (carried forward" not in result["joined"]
    assert "studious:infra-auditor --- (AGENT DIED" not in result["joined"]


def test_join_reports_with_no_routed_out_lanes_is_unchanged_shape() -> None:
    """Calling joinReports with routedOut=[] (or omitted) must read exactly as it
    did before this story — no stray 'routed out' text appears."""
    result = _join_reports_with_routed_out(
        dispatched=["studious:security-auditor"],
        reports=[{"findings": "clean"}],
        carried=[],
        prior_sha="",
        fix_delta_dispatched=False,
        fix_delta_report=None,
        routed_out=[],
    )
    assert "routed out" not in result["joined"]


# ---------- Task 3: auditFanIn laneNames sourced from `routed`, not AUDITORS ----------


def test_audit_fan_in_lane_names_come_from_routed_not_full_auditors() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed.map(a => a.split(':')[1])" in fn, (
        "auditFanIn's laneNames must be built from the `routed` parameter, not the "
        "full AUDITORS constant — otherwise a routed-out lane could be named in a "
        "future round's blockingLanes despite never having been dispatched"
    )
    assert "AUDITORS.map(a => a.split(':')[1])" not in fn


def test_audit_fan_in_instructs_a_visible_summary_line_per_routed_out_lane() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed out — not applicable to this changeset" in fn, (
        "auditFanIn must instruct the compiling agent to write a visible Summary "
        "line per routed-out lane, matching /gate-audit's own skip-note convention"
    )


def test_audit_fan_in_distinguishes_routed_out_from_carried_forward_and_died_in_its_prose() -> None:
    source = DRIVER.read_text()
    fn = _extract_function(source, "auditFanIn")
    assert "routed out" in fn and "THIRD" in fn.upper(), (
        "auditFanIn's instructions to the compiling agent must explicitly name "
        "'routed out' as a third, distinct state from carried-forward and AGENT DIED"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v -k "routed_out or lane_names"`
Expected: FAIL — `joinReports` rejects the extra 7th argument silently (JS ignores extra args, so the test instead fails on the missing "routed out" text), and the two `auditFanIn` structural assertions fail because the current source has neither string.

- [ ] **Step 3: Implement the mechanical dispatch prompt builder**

In `workflows/epic-driver.js`, immediately after the closing backtick of `ledgerScopeCheckPrompt` (the function ending `...blockingLanes:<.gates.audit.blockingLanes, verbatim, unreordered, unfiltered>}\`\n}`) and before `function premortemDispatchPrompt(fields) {`, insert:

```js
// First-round changeset routing (#138): a mechanical fact-check, not a judgment
// call — the same shape as ledgerScopeCheckPrompt above. The Workflow script has
// no filesystem/exec access, so this agent() dispatch is the only way to learn
// what changed; it also reads reference/audit-routing-signals.md, the same
// canonical pattern-list file commands/gate-audit.md's own auditor 9 / 6-8 routing
// rules point at, so there is exactly one list to ever drift from.
function routingScopeCheckPrompt(dir, base) {
  return `This is a mechanical fact-check, not a judgment call — apply the listed patterns exactly, never interpret or editorialize. From ${dir}: compute the merge-base with ${base} (git merge-base ${base} HEAD) and run git diff --name-only <that merge-base> HEAD to get the changed-file list. Read reference/audit-routing-signals.md from the plugin root (the Studious plugin root is dirname "$(command -v gate-ledger)")/..) for the canonical IaC/CI/deploy and frontend file-pattern lists. Determine whether any changed file matches the IaC/CI/deploy list (infraMatch) and whether any changed file matches the frontend list (frontendMatch). When a changed file only loosely or ambiguously matches a pattern, resolve that pattern's match to true, never false — the same "when ambiguous, run" bias commands/gate-audit.md's own routing rules use. Return your findings as EXACTLY one line of compact JSON, nothing else: {"infraMatch":<true|false>,"frontendMatch":<true|false>}`
}
```

- [ ] **Step 4: Implement `resolveRoutingMatchFlags`**

In `workflows/epic-driver.js`, immediately after the closing brace of `ledgerAuditPrior` (ends `... return { verdict: GATES.audit.retry, sha: parsed.sha, blockingLanes: parsed.blockingLanes } }`) and before `async function runGate(story, gate, nextPhase) {`, insert:

```js
// First-round changeset routing (#138), resumed/every-round fact resolution: runs
// the mechanical dispatch above and parses its match flags. Recomputed every round
// (not cached across an audit cycle — see the design doc's Alternatives section for
// why staleness risk outweighs one low-effort dispatch). A died or unparseable
// dispatch degrades to null, which resolveAuditRoster already treats as "route
// everything in" — fails open to more auditing, never less, mirroring
// ledgerAuditPrior's own try/catch-to-null convention immediately above.
async function resolveRoutingMatchFlags(dir, base, label, phaseLabel) {
  let r = null
  try {
    r = await agent(routingScopeCheckPrompt(dir, base), { label, phase: phaseLabel, schema: REPORT, effort: 'low' })
  } catch {
    return null
  }
  if (!r || !r.findings) return null
  try { return JSON.parse(r.findings) } catch { return null }
}
```

- [ ] **Step 5: Extend `joinReports` with the `routedOut` parameter**

In `workflows/epic-driver.js`, replace the entire `joinReports` function body:

```js
function joinReports(dispatched, reports, carriedForward, priorSha, fixDeltaDispatched, fixDeltaReport) {
  const missing = []
  const dispatchedBlocks = dispatched.map((a, i) => {
    const r = reports[i]
    if (!r) { missing.push(a); return `--- ${a} --- (AGENT DIED — no report; this lane is UNAUDITED)` }
    return `--- ${a} ---\n${r.findings}`
  })
  const carriedBlocks = carriedForward.map(a =>
    `--- ${a} --- (carried forward: PASS, no Confirmed Critical as of ${priorSha || 'the prior round'} — not re-dispatched this round; not a replay of any Important/Track findings it previously raised)`)
  const fixDeltaBlocks = []
  if (fixDeltaDispatched) {
    if (fixDeltaReport) {
      fixDeltaBlocks.push(`--- fix-delta-cross-lane-pass --- (scoped to the diff since ${priorSha || 'the prior round'}, not the whole changeset)\n${fixDeltaReport.findings}`)
    } else {
      missing.push('fix-delta-cross-lane-pass')
      fixDeltaBlocks.push('--- fix-delta-cross-lane-pass --- (AGENT DIED — no report; this pass is UNAUDITED)')
    }
  }
  const joined = [...dispatchedBlocks, ...carriedBlocks, ...fixDeltaBlocks].join('\n\n')
  return { joined, missing }
}
```

with:

```js
function joinReports(dispatched, reports, carriedForward, priorSha, fixDeltaDispatched, fixDeltaReport, routedOut) {
  const missing = []
  const dispatchedBlocks = dispatched.map((a, i) => {
    const r = reports[i]
    if (!r) { missing.push(a); return `--- ${a} --- (AGENT DIED — no report; this lane is UNAUDITED)` }
    return `--- ${a} ---\n${r.findings}`
  })
  const carriedBlocks = carriedForward.map(a =>
    `--- ${a} --- (carried forward: PASS, no Confirmed Critical as of ${priorSha || 'the prior round'} — not re-dispatched this round; not a replay of any Important/Track findings it previously raised)`)
  // First-round changeset routing (#138): a THIRD lane state, distinct from both
  // carried-forward (ran previously, cleared) and AGENT DIED (dispatched, no
  // report). A routed-out lane was never dispatched because it does not apply to
  // this changeset at all — conflating it with either of the other two would
  // either launder a genuine gap into an unearned PASS, or falsely demand
  // re-auditing of a lane with nothing to audit.
  const routedOutBlocks = (routedOut || []).map(({ auditor, reason }) =>
    `--- ${auditor} --- (routed out — not applicable to this changeset: ${reason}; never dispatched, no prior report)`)
  const fixDeltaBlocks = []
  if (fixDeltaDispatched) {
    if (fixDeltaReport) {
      fixDeltaBlocks.push(`--- fix-delta-cross-lane-pass --- (scoped to the diff since ${priorSha || 'the prior round'}, not the whole changeset)\n${fixDeltaReport.findings}`)
    } else {
      missing.push('fix-delta-cross-lane-pass')
      fixDeltaBlocks.push('--- fix-delta-cross-lane-pass --- (AGENT DIED — no report; this pass is UNAUDITED)')
    }
  }
  const joined = [...dispatchedBlocks, ...carriedBlocks, ...routedOutBlocks, ...fixDeltaBlocks].join('\n\n')
  return { joined, missing }
}
```

- [ ] **Step 6: Extend `auditFanIn` with `routed`/`routedOut` and the routed-out Summary instruction**

In `workflows/epic-driver.js`, replace the entire `auditFanIn` function:

```js
function auditFanIn(story, reports, base, dir, nextPhase) {
  const laneNames = AUDITORS.map(a => a.split(':')[1]).join(', ')
  return `You are compiling Studious's audit gate verdict. Read commands/gate-audit.md from the plugin root (gate-ledger is on PATH; plugin root is dirname of it, up one) and apply ITS compilation rules and severity rubric to the auditor reports below — you judge compilation only, you do not re-audit. A lane marked UNAUDITED (its agent died) means you cannot certify a PASS: the verdict is at best FIX AND RE-AUDIT.\n\nA lane marked "carried forward" (delta-scoped re-audit, #130) is NOT the same as UNAUDITED: it was not re-dispatched this round because the prior round's own compiled verdict already proved it had no Confirmed Critical. Treat its one-line carried-forward status as a clean, confirmed-clean fact for that lane — never as a gap that blocks the verdict, and never invent or replay any Important/Track findings for it beyond that line. A block labeled "fix-delta-cross-lane-pass" is a single, cheap, cross-lane spot-check over the small diff since the prior round, not a tenth specialist auditor — map its findings into the report's severity tiers exactly like any other lane's, tagged by whichever lane's vocabulary they resemble, and put them through the same Critical-challenge step as every other finding.\n\nOut of scope for this verdict: gate-audit.md's own text describes a pre-mortem-verification lane (auditor 11) that fires when a pre-mortem register exists — disregard that lane here, at both story and finale altitude. At story altitude, the epic's cross-story pre-mortem register is verified once, at the epic finale, never per-story. At finale altitude, it is verified by a separate, dedicated premortem-auditor step outside this compilation. The auditor reports below cover only the 9 fixed lanes (security, code, doc, architecture, test, infra, operability, ux, frontend); an absent pre-mortem report is therefore not evidence of an unaudited lane in this context — do not raise it as a finding, and do not let it depress the verdict below what those 9 lanes otherwise support.\n\nChangeset: ${dir}, diff base ${base}.\n\nAuditor reports:\n${reports}\n\nIf, and only if, your verdict is FIX AND RE-AUDIT: also determine blockingLanes — the short name(s) (e.g. "security-auditor", not "studious:security-auditor") of every lane among {${laneNames}} whose report contained a Critical finding that survived your challenge as Confirmed and helped drive this verdict. Omit blockingLanes entirely (do not return an empty array) if your verdict is PASS or NEEDS DISCUSSION, or if ANY lane above is marked AGENT DIED this round — a died lane's true status is unknown, so the next round must default to a full re-audit rather than narrow off an unreliable list.\n\nRecord the verdict from inside ${dir} (substitute <TOKEN> with your verdict; only when you computed blockingLanes above, also append --blocking-lanes "<comma-separated lane names>" to this same command — omit that flag entirely otherwise, per the omission rule above): cd "${dir}" && gate-ledger record --gate audit --verdict "<TOKEN>"${story ? ` && gate-ledger work-log --slug "${workSlug(story)}" --step audit --outcome "<TOKEN>" --phase "${nextPhase}"` : ''}\n\nReturn: verdict (PASS | FIX AND RE-AUDIT | NEEDS DISCUSSION), sha, summary, blockingLanes (only when you computed one, per the rule above — omit the field entirely otherwise).`
}
```

with:

```js
function auditFanIn(story, reports, base, dir, nextPhase, routed, routedOut) {
  const laneNames = routed.map(a => a.split(':')[1]).join(', ')
  const routedOutList = routedOut || []
  const routedOutNote = routedOutList.length
    ? ` This round additionally routed out ${routedOutList.length} lane(s) as not applicable to this changeset — ${routedOutList.map(r => `${r.auditor.split(':')[1]} (${r.reason})`).join(', ')} — never dispatched, present below as a distinct "routed out" block, not evidence of an unaudited gap; do not raise their absence as a finding, and do not let it depress the verdict below what the dispatched/carried-forward lanes actually support.`
    : ''
  const routedOutSummaryInstruction = routedOutList.length
    ? `In your Summary section, include one plain line per routed-out lane in this exact form: "<lane>: routed out — not applicable to this changeset (<reason>)" — e.g. "${routedOutList[0].auditor.split(':')[1]}: routed out — not applicable to this changeset (${routedOutList[0].reason})". This must be visible in the report a human reads, the same way /gate-audit's own skip notes are, not only reflected in your internal reasoning.\n\n`
    : ''
  return `You are compiling Studious's audit gate verdict. Read commands/gate-audit.md from the plugin root (gate-ledger is on PATH; plugin root is dirname of it, up one) and apply ITS compilation rules and severity rubric to the auditor reports below — you judge compilation only, you do not re-audit. A lane marked UNAUDITED (its agent died) means you cannot certify a PASS: the verdict is at best FIX AND RE-AUDIT.\n\nA lane marked "carried forward" (delta-scoped re-audit, #130) is NOT the same as UNAUDITED: it was not re-dispatched this round because the prior round's own compiled verdict already proved it had no Confirmed Critical. Treat its one-line carried-forward status as a clean, confirmed-clean fact for that lane — never as a gap that blocks the verdict, and never invent or replay any Important/Track findings for it beyond that line. A lane marked "routed out" (first-round changeset routing, #138) is a THIRD, distinct state from both: it was never dispatched because it does not apply to this changeset at all — treat it as neutral, neither a gap nor a clean claim, and never conflate it with carried forward or AGENT DIED. A block labeled "fix-delta-cross-lane-pass" is a single, cheap, cross-lane spot-check over the small diff since the prior round, not a tenth specialist auditor — map its findings into the report's severity tiers exactly like any other lane's, tagged by whichever lane's vocabulary they resemble, and put them through the same Critical-challenge step as every other finding.\n\nOut of scope for this verdict: gate-audit.md's own text describes a pre-mortem-verification lane (auditor 11) that fires when a pre-mortem register exists — disregard that lane here, at both story and finale altitude. At story altitude, the epic's cross-story pre-mortem register is verified once, at the epic finale, never per-story. At finale altitude, it is verified by a separate, dedicated premortem-auditor step outside this compilation. The auditor reports below cover this round's routed lane set (${laneNames}); an absent pre-mortem report is therefore not evidence of an unaudited lane in this context — do not raise it as a finding, and do not let it depress the verdict below what those routed lanes otherwise support.${routedOutNote}\n\nChangeset: ${dir}, diff base ${base}.\n\nAuditor reports:\n${reports}\n\n${routedOutSummaryInstruction}If, and only if, your verdict is FIX AND RE-AUDIT: also determine blockingLanes — the short name(s) (e.g. "security-auditor", not "studious:security-auditor") of every lane among {${laneNames}} whose report contained a Critical finding that survived your challenge as Confirmed and helped drive this verdict. Omit blockingLanes entirely (do not return an empty array) if your verdict is PASS or NEEDS DISCUSSION, or if ANY lane above is marked AGENT DIED this round — a died lane's true status is unknown, so the next round must default to a full re-audit rather than narrow off an unreliable list.\n\nRecord the verdict from inside ${dir} (substitute <TOKEN> with your verdict; only when you computed blockingLanes above, also append --blocking-lanes "<comma-separated lane names>" to this same command — omit that flag entirely otherwise, per the omission rule above): cd "${dir}" && gate-ledger record --gate audit --verdict "<TOKEN>"${story ? ` && gate-ledger work-log --slug "${workSlug(story)}" --step audit --outcome "<TOKEN>" --phase "${nextPhase}"` : ''}\n\nReturn: verdict (PASS | FIX AND RE-AUDIT | NEEDS DISCUSSION), sha, summary, blockingLanes (only when you computed one, per the rule above — omit the field entirely otherwise).`
}
```

**Note:** `auditFanIn`'s two existing call sites (in `auditRound` and `finaleAuditRound`) still call it with only 5 arguments at this point in the plan — that's fine, JS leaves the missing `routed`/`routedOut` params `undefined`, and `routed.map(...)` on `undefined` will throw at runtime. This is expected and *will* break those two call sites until Task 4 updates them — Task 3 ends with the call sites still unpatched, so **do not run the end-to-end `_run_driver` tests yet**; only the extraction-based fixture tests (Step 1) and structural assertions exercise `auditFanIn`/`joinReports` directly in this task, never through a live `auditRound()` call.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v`
Expected: all tests PASS (Tasks 1–2's tests still pass; Task 3's new tests now pass since `joinReports`/`auditFanIn` have the new params and prose).

- [ ] **Step 8: Run `node --check`**

Run: `node --check workflows/epic-driver.js`
Expected: exits 0 (syntax is valid even though `auditRound`/`finaleAuditRound` would throw if *invoked* right now — `node --check` only parses, it doesn't run).

- [ ] **Step 9: Commit**

```bash
git add workflows/epic-driver.js tests/python/test_audit_first_round_routing.py
git commit -m "feat(epic-driver): mechanical routing dispatch + routed-out lane rendering (#138)"
```

---

### Task 4: Wire into `auditRound`/`finaleAuditRound` + end-to-end regression suite

**Files:**
- Modify: `workflows/epic-driver.js` (`auditRound()` and `finaleAuditRound()` bodies)
- Test: `tests/python/test_audit_first_round_routing.py` (append)

**Interfaces:**
- Consumes: `resolveRoutingMatchFlags`, `resolveAuditRoster` (Tasks 2–3), extended `joinReports`/`auditFanIn` (Task 3).
- Produces: fully working feature — this is the task where `auditRound`/`finaleAuditRound` actually call the new machinery instead of the hardcoded `AUDITORS` constant.

- [ ] **Step 1: Wire `auditRound()`**

In `workflows/epic-driver.js`, in `async function auditRound(story, note, nextPhase, priorResult) {`, replace:

```js
  const scope = resolveReauditScope(priorResult, AUDITORS, GATES.audit.retry)
  const dispatched = scope.narrowed ? scope.blockingAuditors : AUDITORS
  const reports = await parallel(dispatched.map(a => () =>
    agent(auditDispatchPrompt({ ctxBlock: ctx(story), note, slug, storyWorktreePath: storyWorktree(story), contract: CONTRACT }),
      { agentType: a, label: `audit:${a.split(':')[1]}:${story}`, phase: `story:${story}`, schema: REPORT })))
  const fixDeltaReport = scope.narrowed
    ? await agent(fixDeltaDispatchPrompt({ ctxBlock: ctx(story), note, storyWorktreePath: storyWorktree(story), priorSha: scope.priorSha, contract: CONTRACT }),
        { label: `audit:fix-delta:${story}`, phase: `story:${story}`, schema: REPORT })
    : null
  const carriedForward = scope.narrowed ? AUDITORS.filter(a => !dispatched.includes(a)) : []
  const { joined, missing } = joinReports(dispatched, reports, carriedForward, scope.priorSha, scope.narrowed, fixDeltaReport)
  let result = await agent(auditFanIn(story, joined, `epic/${slug}`, storyWorktree(story), nextPhase),
    { label: `audit:compile:${story}`, phase: `story:${story}`, schema: GATE_RESULT, model: 'opus' })
```

with:

```js
  const matchFlags = await resolveRoutingMatchFlags(storyWorktree(story), `epic/${slug}`, `audit:routing-scope:${story}`, `story:${story}`)
  const { routed, routedOut } = resolveAuditRoster(matchFlags, AUDITORS)
  const scope = resolveReauditScope(priorResult, routed, GATES.audit.retry)
  const dispatched = scope.narrowed ? scope.blockingAuditors : routed
  const reports = await parallel(dispatched.map(a => () =>
    agent(auditDispatchPrompt({ ctxBlock: ctx(story), note, slug, storyWorktreePath: storyWorktree(story), contract: CONTRACT }),
      { agentType: a, label: `audit:${a.split(':')[1]}:${story}`, phase: `story:${story}`, schema: REPORT })))
  const fixDeltaReport = scope.narrowed
    ? await agent(fixDeltaDispatchPrompt({ ctxBlock: ctx(story), note, storyWorktreePath: storyWorktree(story), priorSha: scope.priorSha, contract: CONTRACT }),
        { label: `audit:fix-delta:${story}`, phase: `story:${story}`, schema: REPORT })
    : null
  const carriedForward = scope.narrowed ? routed.filter(a => !dispatched.includes(a)) : []
  const { joined, missing } = joinReports(dispatched, reports, carriedForward, scope.priorSha, scope.narrowed, fixDeltaReport, routedOut)
  let result = await agent(auditFanIn(story, joined, `epic/${slug}`, storyWorktree(story), nextPhase, routed, routedOut),
    { label: `audit:compile:${story}`, phase: `story:${story}`, schema: GATE_RESULT, model: 'opus' })
```

Leave the rest of `auditRound` (the `missing.length` belt-and-braces block and `return result`) unchanged.

- [ ] **Step 2: Wire `finaleAuditRound()`**

In `workflows/epic-driver.js`, in `async function finaleAuditRound(note, priorResult) {`, replace:

```js
  const scope = resolveReauditScope(priorResult, AUDITORS, GATES.audit.retry)
  const dispatched = scope.narrowed ? scope.blockingAuditors : AUDITORS
  const reports = await parallel(dispatched.map(a => () =>
    agent(finaleAuditDispatchPrompt({ note, repoRoot, epicWorktreePath: epicWorktree, slug, defaultBranch: input.defaultBranch, epicGoal: epic.goal, contract: CONTRACT }),
      { agentType: a, label: `finale:${a.split(':')[1]}`, phase: 'Finale', schema: REPORT })))
  const fixDeltaReport = scope.narrowed
    ? await agent(finaleFixDeltaDispatchPrompt({ note, repoRoot, epicWorktreePath: epicWorktree, slug, defaultBranch: input.defaultBranch, priorSha: scope.priorSha, contract: CONTRACT }),
        { label: 'finale:fix-delta', phase: 'Finale', schema: REPORT })
    : null
  const carriedForward = scope.narrowed ? AUDITORS.filter(a => !dispatched.includes(a)) : []
  const { joined, missing } = joinReports(dispatched, reports, carriedForward, scope.priorSha, scope.narrowed, fixDeltaReport)
  let result = await agent(auditFanIn(null, joined, input.defaultBranch, epicWorktree, ''),
    { label: 'finale:audit-compile', phase: 'Finale', schema: GATE_RESULT, model: 'opus' })
```

with:

```js
  const matchFlags = await resolveRoutingMatchFlags(epicWorktree, input.defaultBranch, 'finale:routing-scope', 'Finale')
  const { routed, routedOut } = resolveAuditRoster(matchFlags, AUDITORS)
  const scope = resolveReauditScope(priorResult, routed, GATES.audit.retry)
  const dispatched = scope.narrowed ? scope.blockingAuditors : routed
  const reports = await parallel(dispatched.map(a => () =>
    agent(finaleAuditDispatchPrompt({ note, repoRoot, epicWorktreePath: epicWorktree, slug, defaultBranch: input.defaultBranch, epicGoal: epic.goal, contract: CONTRACT }),
      { agentType: a, label: `finale:${a.split(':')[1]}`, phase: 'Finale', schema: REPORT })))
  const fixDeltaReport = scope.narrowed
    ? await agent(finaleFixDeltaDispatchPrompt({ note, repoRoot, epicWorktreePath: epicWorktree, slug, defaultBranch: input.defaultBranch, priorSha: scope.priorSha, contract: CONTRACT }),
        { label: 'finale:fix-delta', phase: 'Finale', schema: REPORT })
    : null
  const carriedForward = scope.narrowed ? routed.filter(a => !dispatched.includes(a)) : []
  const { joined, missing } = joinReports(dispatched, reports, carriedForward, scope.priorSha, scope.narrowed, fixDeltaReport, routedOut)
  let result = await agent(auditFanIn(null, joined, input.defaultBranch, epicWorktree, '', routed, routedOut),
    { label: 'finale:audit-compile', phase: 'Finale', schema: GATE_RESULT, model: 'opus' })
```

Leave the rest of `finaleAuditRound` unchanged.

- [ ] **Step 3: Write the failing end-to-end tests**

Append to `tests/python/test_audit_first_round_routing.py`:

```python
# ---------- Task 4: end-to-end, real driver under the documented harness shape ----------


def _nine_lane_pass_rules(story: str) -> list[dict]:
    return [
        {"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}}
        for name in AUDITOR_SHORT_NAMES
    ]


_FINALE_CLEAN_RULES = [
    {"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in AUDITOR_SHORT_NAMES
] + [
    {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
    {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
    {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
]


def test_full_surface_match_dispatches_all_nine_lanes_unchanged() -> None:
    """Both signals matching (a changeset touching infra AND frontend files)
    must dispatch every one of the 9 lanes — identical to pre-#138 behavior,
    just with one extra cheap routing-scope dispatch first."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": True, "frontendMatch": True})}},
        *_nine_lane_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count(f"audit:routing-scope:{story}") == 1
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:{story}") == 1
    assert out["result"]["landed"] == 1


def test_backend_only_changeset_routes_out_infra_and_frontend_lanes() -> None:
    """The acceptance-critical case: no infra, no frontend signal → only the
    6 always-applicable lanes dispatch, not all 9."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    routed_out_names = ["infra-auditor", "ux-reviewer", "frontend-reviewer"]
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for name in always_run:
        assert labels.count(f"audit:{name}:{story}") == 1
    for name in routed_out_names:
        assert f"audit:{name}:{story}" not in labels, f"{name} was dispatched despite being routed out"
    assert out["result"]["landed"] == 1


def test_routed_out_lanes_appear_in_the_compile_prompt_with_plain_reasons() -> None:
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    assert len(compile_prompts) == 1
    prompt = compile_prompts[0]
    assert "studious:infra-auditor --- (routed out — not applicable to this changeset: no infrastructure changes detected" in prompt
    assert "studious:ux-reviewer --- (routed out" in prompt
    assert "studious:frontend-reviewer --- (routed out" in prompt
    # No internal reference-file path leaks into the routed-out reason text.
    assert "audit-routing-signals.md" not in prompt.split("routed out")[1][:200]
    # The Summary instruction is present so the human-facing report gets the line too.
    assert "routed out — not applicable to this changeset (<reason>)" in prompt


def test_dead_routing_dispatch_fails_open_to_the_full_nine_lane_roster() -> None:
    """Acceptance-critical failure mode: if the mechanical routing dispatch
    dies, every one of the 9 lanes must still dispatch — never a partial,
    guessed roster."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "throw": "gate-ledger not found"},
        *_nine_lane_pass_rules(story),
        {"match": rf"^audit:compile:{story}$", "result": {"verdict": "PASS", "sha": "s1", "summary": "clean"}},
        {"match": rf"^merge:{story}$", "result": {"merged": True, "sha": "s2", "notes": "clean"}},
        *_FINALE_CLEAN_RULES,
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"a died routing dispatch crashed the story instead of failing open: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    for name in AUDITOR_SHORT_NAMES:
        assert labels.count(f"audit:{name}:{story}") == 1, (
            f"{name} was not dispatched after the routing check died — must fail "
            "open to the full roster, never a guessed partial one"
        )
    assert out["result"]["landed"] == 1


def test_retry_narrowing_operates_within_the_routed_roster_never_a_routed_out_lane() -> None:
    """A routed-out lane must never be re-dispatched on a narrowed retry, and
    must never be listed as carried-forward — it stays routed-out across the
    whole audit cycle."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"

    labels = [c["label"] for c in out["calls"]]
    total_rounds = 1 + MAX_FIX_CYCLES
    assert labels.count(f"audit:security-auditor:{story}") == total_rounds
    non_blocking_always_run = [n for n in always_run if n != "security-auditor"]
    for name in non_blocking_always_run:
        assert labels.count(f"audit:{name}:{story}") == 1, (
            f"{name} was re-dispatched on a narrowed retry — should have been carried forward"
        )
    for name in ("infra-auditor", "ux-reviewer", "frontend-reviewer"):
        assert f"audit:{name}:{story}" not in labels, f"{name} was dispatched despite being routed out for the whole cycle"

    compile_prompts = [c["prompt"] for c in out["calls"] if c["label"] == f"audit:compile:{story}"]
    for retry_prompt in compile_prompts[1:]:
        # Routed-out lanes stay "routed out" across every round, never flip to
        # "carried forward" once a retry cycle begins.
        assert "studious:infra-auditor --- (routed out" in retry_prompt
        assert "studious:infra-auditor --- (carried forward" not in retry_prompt
        for name in non_blocking_always_run:
            assert f"studious:{name} --- (carried forward: PASS" in retry_prompt


def test_routing_scope_recomputes_each_round_not_cached_across_the_retry_loop() -> None:
    """Operational readiness commitment: the mechanical routing dispatch is
    recomputed every round, not cached across the audit cycle, so a fix commit
    that changes the file surface mid-cycle is picked up by the very next
    round rather than staying stale. `_run_driver`'s label-matched mock can't
    vary its response by call order, so the observable proof is: the
    routing-scope dispatch is invoked once PER ROUND, not once total — a
    cached list would only ever call it once regardless of how many fix
    cycles run."""
    story = "a"
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {story: {"title": "A", "criteria": "c", "gates": ["audit"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    blocking_result = {
        "verdict": "FIX AND RE-AUDIT", "sha": "s1", "summary": "security found a critical",
        "blockingLanes": ["security-auditor"],
    }
    rules = [
        {"match": rf"^audit:routing-scope:{story}$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False})}},
        *[{"match": rf"^audit:{name}:{story}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": rf"^audit:compile:{story}$", "result": blocking_result},
        {"match": rf"^audit:fix-delta:{story}$", "result": {"findings": "fix-delta clean"}},
        {"match": rf"^fix:audit:{story}$", "result": {"status": "done", "sha": "f1", "summary": "attempted", "evidence": "ran tests"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    total_rounds = 1 + MAX_FIX_CYCLES
    assert labels.count(f"audit:routing-scope:{story}") == total_rounds, (
        "the routing-scope dispatch must run once per round, proving it isn't "
        "cached across the retry loop — a cached list would call it only once"
    )


def test_finale_routing_mirrors_the_story_level_mechanism() -> None:
    epic = {
        "slug": "epx", "title": "T", "goal": "g", "concurrency": 1,
        "stories": {"a": {"title": "A", "criteria": "c", "gates": ["acceptance"]}},
    }
    always_run = ["security-auditor", "code-auditor", "doc-auditor", "architecture-auditor", "test-auditor", "operability-auditor"]
    rules = [
        {"match": r"^acceptance:a$", "result": {"verdict": "SHIP", "sha": "a0", "summary": "ok"}},
        {"match": r"^merge:a$", "result": {"merged": True, "sha": "a1", "notes": "clean"}},
        {"match": r"^finale:routing-scope$", "result": {"findings": json.dumps({"infraMatch": False, "frontendMatch": False})}},
        *[{"match": rf"^finale:{name}$", "result": {"findings": "clean"}} for name in always_run],
        {"match": r"^finale:audit-compile$", "result": {"verdict": "PASS", "sha": "f1", "summary": "clean"}},
        {"match": r"^finale:acceptance$", "result": {"verdict": "SHIP", "sha": "f2", "summary": "ship it"}},
        {"match": r"^finale:ready$", "result": {"verdict": "READY", "sha": "f3", "summary": "marked ready"}},
    ]
    out = _run_driver(epic, rules)
    assert out["ok"], f"driver crashed: {out.get('error')}"
    labels = [c["label"] for c in out["calls"]]
    assert labels.count("finale:routing-scope") == 1
    for name in always_run:
        assert labels.count(f"finale:{name}") == 1
    for name in ("infra-auditor", "ux-reviewer", "frontend-reviewer"):
        assert f"finale:{name}" not in labels
    assert out["result"]["finale"]["ready"] is True
```

- [ ] **Step 4: Run the tests to verify they fail (before Steps 1–2's wiring)**

If following strict TDD order, run this step *before* Steps 1–2's edits: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v -k "full_surface_match or backend_only or dead_routing or retry_narrowing or finale_routing or routed_out_lanes_appear"`
Expected: FAIL — every test rejects with `UNMOCKED agent label: audit:routing-scope:a` (or `finale:routing-scope`), since `auditRound`/`finaleAuditRound` don't dispatch that label yet.

(If Steps 1–2 were already applied per the plan's numbering above, apply them now, then run this step to confirm PASS instead — either order is fine as long as you observe the red state once.)

- [ ] **Step 5: Run the full new test file to verify everything passes**

Run: `uv run --no-project --with pytest pytest tests/python/test_audit_first_round_routing.py -v`
Expected: all tests PASS.

- [ ] **Step 6: Run the full existing suite to confirm no regression**

Run each of:
```bash
node --check workflows/epic-driver.js
npx -y eslint@10.6.0 --report-unused-disable-directives workflows/
bash tests/test_workflows_lint.sh
npx -y markdownlint-cli2
uv run --no-project python scripts/check_references.py
uv run --no-project --with pytest pytest tests/python -v
```
Expected: every command exits 0. The full `pytest tests/python -v` run must show `test_delta_scoped_reaudit.py`'s existing tests still passing unchanged (they call `joinReports` with 6 positional args, which remains valid now that `routedOut` is an optional 7th parameter) and `test_driver_crash_hardening.py`'s tests still passing (they don't reference `auditFanIn`/`joinReports` at all).

- [ ] **Step 7: Commit**

```bash
git add workflows/epic-driver.js tests/python/test_audit_first_round_routing.py
git commit -m "feat(epic-driver): wire first-round changeset routing into auditRound/finaleAuditRound (#138)"
```

---

## Self-Review Notes (for whoever executes this plan)

- **Spec coverage:** Task 1 covers the design's "One canonical source" section; Task 2 covers "One new pure function: resolveAuditRoster"; Task 3 covers "One new mechanical dispatch" + the `joinReports`/`auditFanIn` halves of "Composition point" and "Three lane states, not two"; Task 4 covers "Where this plugs in", the design's Operational readiness "failure mode" (fail-open) and "recomputed every round, not cached" commitment (`test_routing_scope_recomputes_each_round_not_cached_across_the_retry_loop`), and the pre-mortem register's items 1–6 (item 7, dispatch-volume-at-scale on a real multi-story epic, is a production observation, not something a fixture test can prove — note it in the eventual PR description as an open follow-up, not a gap in this plan).
- **Frontend pattern list precision:** the design doc says "template/component/CSS/JS file" generically; this plan makes the concrete, disclosed choice to exclude bare `.js`/`.ts` from the mechanical routing signal (Global Constraints, and documented inline in `reference/audit-routing-signals.md` itself) because a plain `.js`/`.ts` file is not a reliable *frontend-only* signal and would make the routing dispatch's match too broad on JS-heavy backend repos (including this one). This is a genuine implementation-level precision decision the three design-review passes didn't reach — flag it to the task reviewer explicitly rather than treating it as settled.
- **`auditFanIn`'s call-site break window:** Task 3 intentionally leaves `auditFanIn`'s two call sites un-updated (they still pass only 5 args) until Task 4 — this is a deliberate, disclosed intermediate state (see the note at the end of Task 3, Step 6), not an oversight. Do not run end-to-end `_run_driver` tests between Task 3 and Task 4.
