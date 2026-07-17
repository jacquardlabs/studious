# Dependency auditor — supply-chain review of the diff at gate time

**Date:** 2026-07-17
**Status:** Design, pre-implementation
**Source:** [#64](https://github.com/jacquardlabs/studious/issues/64), story `dep-auditor` of epic
`expand-gate-coverage` — first story in the epic DAG; `prompt-auditor` (#93) depends on this one
landing so the two lanes never edit the same fan-out regions concurrently (epic pre-mortem, item 1).
Scope addition recorded on the issue (2026-07-11 fleet gap analysis): license compliance is one
dimension of this lane, not a separate agent.

## Problem & persona

PRODUCT.md's primary persona: **"A developer (solo or small team) building features with Claude
Code who wants product judgment and quality gates woven into the build, without heavy process."**

A CVE, an abandoned package, or a license-incompatible dependency entering via a PR's new
dependency is caught today only by the periodic `review-codebase-health` dependency lane — weeks
after merge at worst, and only when the persona remembers to run `/deep-review`. At gate time,
coverage is one dimension deep: `security-auditor`'s §8 runs read-only scanners and names known
CVEs, but it is one of eight dimensions in an always-on lane whose core job is injection, auth,
and secrets — supply-chain review gets whatever attention is left over, and license compatibility,
maintenance signal (archived repos, typosquat-adjacent names), and lockfile↔manifest drift have no
owner at any gate.

The gap is structural, the same shape #114 closed for operability: the concern exists at the
periodic altitude (`review-codebase-health`) but has no diff-scoped specialist at the gate
altitude, which is exactly where a bad dependency is cheapest to reject — before merge, while the
diff that introduced it is the whole review surface.

## Proposed design

One new changeset-routed lane in the `/gate-audit` fan-out, wired identically to the
infrastructure lane (auditor 9): routed by a deterministic file-pattern list in
`reference/audit-routing-signals.md`, self-skipping when dispatched against a non-matching diff,
registered in `reference/severity-rubric.md`, and mirrored on the epic-driven path in
`workflows/epic-driver.js` so `/work-through` epics get the same coverage as supervised runs.

### 1. `agents/dependency-auditor.md` (new) — the gate lane

Frontmatter: `name: dependency-auditor`; description "Dependency auditor. Reviews a changeset's
dependency manifest and lockfile diffs for new/updated dependencies, known vulnerabilities,
license compatibility, maintenance signal, and lockfile-manifest drift. Diff-scoped and
gate-invoked (/gate-audit); skipped when the changeset touches no dependency manifest or lockfile
— not the periodic whole-repo dependency review, which review-codebase-health owns.";
`tools: Read, Grep, Glob, Bash`; `model: opus`; `effort: medium`.

- **`model: opus`** — supply-chain review is security-family judgment (is this package
  trustworthy, does this advisory reach this usage, does this license fit this project's
  regime); CONTRIBUTING.md's stakes rule pins security judgment to `opus`, matching
  `security-auditor` and `infra-auditor`.
- **`effort: medium`** — rubric-driven verification, not open-ended free-hunting: the work
  enumerates per changed dependency (look up advisories, check the license, check the
  maintenance signal, diff lockfile against manifest) rather than sweeping an open surface.
  Same argument that places merge-blocking `premortem-auditor` at `medium`. Alternatives
  considered below records the case for `high`.

Carries the shared prompt contract (epic pre-mortem, item 3): injected posture block from the
orchestrator, fallback read from `${CLAUDE_PLUGIN_ROOT}/reference/prompt-contract.md` — the
injection-defense preamble matters more here than in most lanes, since manifests and lockfiles
are exactly where an attacker-controlled package name or install-script URL masquerades as data.

**This agent's addendum** (the same slot security-auditor and infra-auditor use): never install
or resolve dependencies — postinstall and build scripts run attacker-controlled code. Advisory
data comes from read-only lookups only: `gh api` against the GitHub Advisory Database, an
osv.dev `POST /v1/query` per changed package@version, or a read-only scanner (`osv-scanner
--lockfile`) if one is present. If the network or every lookup path is unavailable, report
"could not verify — advisory data unreachable" and mark affected findings `Potential` — never
imply clean.

**Lane boundaries (criterion 4), stated in both directions:**

- `security-auditor` keeps injection, auth, and secrets in code — everything about what the
  project's own code does. This lane owns the supply chain of the diff: what the changeset's
  manifest and lockfile changes pull in. security-auditor's §8 (Dependencies) narrows to an
  escalation pointer at build time (see wiring below) so two lanes never hunt the same CVEs.
- `infra-auditor` keeps container hygiene: Dockerfile base images, `ADD` from URLs, unpinned
  system packages. This lane owns application package manifests and lockfiles only.
- `review-codebase-health` keeps the periodic whole-repo dependency posture (accumulated
  staleness in unchanged deps). This lane is diff-scoped: only what the changeset adds,
  updates, or removes — including the transitive changes visible in the lockfile diff.
- Other auditors escalate a dependency smell they stumble on; treat escalations as leads, not
  coverage.

**Five dimensions (criterion 3)** — output-row `dimension` enum: `new-deps` /
`known-vulns` / `license` / `maintenance` / `lockfile-drift`:

1. **New and updated dependencies** — inventory the diff's manifest changes: direct adds,
   version bumps (patch vs. major), range loosening (pin → `^`/`*`), registry or source changes
   (registry → git URL/tarball), and new install-script surface. Scale attention to the change:
   a patch bump of an existing dep warrants a fraction of what a brand-new direct dependency gets.
2. **Known vulnerabilities** — per changed package@version, query GitHub advisory data or
   osv.dev (read-only, per the addendum). Severity starts from the advisory and is gated by
   reachability: an advisory on an API the codebase demonstrably never calls drops a tier and is
   marked `Potential`; a lookup that could not run is "could not verify," never clean.
3. **License compatibility** — per the scope comment on #64: licenses incompatible with the
   project's regime (copyleft entering a permissive or proprietary codebase, license-missing
   packages), detected from the project's LICENSE file and package metadata. CLAUDE.md's
   documented licensing posture, when it predates the changeset, overrides the default read.
4. **Maintenance signal** — archived or deprecation-marked repos, typosquat-adjacent names
   (small edit distance to a popular package the project doesn't otherwise use), packages
   published days ago with install scripts, single-release packages taking a load-bearing role.
5. **Lockfile–manifest drift** — manifest changed without the lockfile regenerated (or the
   reverse), lockfile entries outside the manifest's declared range, integrity hashes removed or
   weakened, resolved URLs pointing off-registry.

**Skip rule** (infra-auditor pattern — a skipped lane is a valid outcome): if the changeset
touches no dependency manifest or lockfile (per the Dependency signal list in
`reference/audit-routing-signals.md`), report that and stop. Second layer, content-level: a
matching file touched only outside its dependency surface — `pyproject.toml` edited only in
`[tool.*]` tables, `package.json` edited only in `scripts` — self-skips with a note after
reading the diff hunks, the same way infra-auditor self-skips a dispatched-but-non-matching diff.

**Severity** — security-family ladder, advisory-anchored and reachability-gated:

- **Critical** — a malicious or typosquat package entering the tree; a known-exploited or
  critical-severity advisory on a dependency the changeset adds or updates, on a plausibly
  reachable path.
- **High** — a high-severity advisory; a license violation in code the project distributes; an
  off-registry resolution or integrity-hash removal in the lockfile.
- **Medium** — an abandoned/archived dependency taking a load-bearing role; drift that makes
  builds unreproducible; an advisory reachable only under unusual preconditions.
- **Low** — hygiene: loose ranges, stale-but-safe versions, pre-1.0 churn risk.

The orchestrator maps Critical+High→Critical, Medium→Important, Low→Track — the same row shape
as security/infra/operability.

### 2. `reference/dependency-checklist.md` (new) — lookup data

Same contract as `reference/infra-checklist.md` and `reference/operability-checklist.md`:
lookup data the model won't recall verbatim, not a detection crutch. Contents: the per-ecosystem
manifest↔lockfile pair table (which file pairs with which, what "regenerated" looks like);
advisory lookup command shapes (`gh api` advisory queries, the osv.dev `POST /v1/query` body,
`osv-scanner --lockfile` invocation) with their read-only caveats; a license-family
compatibility table (permissive / weak-copyleft / strong-copyleft against project regimes);
typosquat heuristics; and per-ecosystem drift signatures. CLAUDE.md's documented posture
overrides anything here.

### 3. `reference/audit-routing-signals.md` — the Dependency signal

New section, `## Dependency signal (auditor 11 / dependency-auditor)`, following the existing
two exactly (canonical list, "no match → no signal" closer, the file-wide "when ambiguous, apply
the pattern anyway" bias). The list, by ecosystem:

- JS/TS: `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`,
  `npm-shrinkwrap.json`
- Python: `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`, `Pipfile`,
  `Pipfile.lock`, `setup.py`, `setup.cfg`
- Go: `go.mod`, `go.sum` · Rust: `Cargo.toml`, `Cargo.lock` · Ruby: `Gemfile`,
  `Gemfile.lock`, `*.gemspec` · PHP: `composer.json`, `composer.lock`
- JVM: `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradle.lockfile`, `libs.versions.toml`
- .NET: `*.csproj`, `packages.config`, `packages.lock.json`, `Directory.Packages.props`
- Elixir: `mix.exs`, `mix.lock` · vendored trees: `vendor/`, `third_party/`

The header prose ("auditor 9, and auditors 6–8's per-changeset clause") gains the dependency
clause so the file's own inventory of consumers stays true. A file-level match deliberately
over-fires (a `[tool.ruff]`-only `pyproject.toml` edit still routes the lane in); the agent's
content-level self-skip is the second layer, identical to how a CI-config-comment edit still
dispatches infra-auditor. Routing stays deterministic so the mechanical dispatch can apply it.

### 4. `commands/gate-audit.md` — lane wiring

Follows the operability story's wiring exactly. Dependency becomes **auditor 11** (the
changeset-routed lanes cluster at 9–11); pre-mortem verification renumbers 11 → 12.

- Frontmatter `description` (also the skill trigger text — no `skills/` file exists for this
  command, so no `writing-skills` invocation is needed) gains "a dependency check joins in when
  the changeset touches dependency manifests or lockfiles".
- New routing paragraph under "Launch all auditors in parallel": changeset-routed, "per the
  Dependency signal list in `reference/audit-routing-signals.md` — consult it, don't restate
  it", skip note "No dependency manifest or lockfile changes detected — dependency audit
  skipped.", when ambiguous run.
- New numbered dispatch entry: "### Dependency auditor (runs when the changeset touches
  dependency manifests or lockfiles)" with the lane brief and the boundary sentence (secrets
  and in-code vulnerabilities stay with @agent-security-auditor; container base images stay
  with @agent-infra-auditor).
- Every roster enumeration updates: "Spawn auditors 1–7, 9, and 10" → "1–7, 9–11"; re-audit
  scope condition 3's "nine auditors" list becomes ten and gains `dependency-auditor`; the
  fix-delta pass's "(1–7, 9, 10)" → "(1–7, 9–11)"; carry-forward's "the nine" → "the ten";
  the record section's "(1–7, 9, 10 — never 8 or 11)" → "(1–7, 9–11 — never 8 or 12)".
- The Important-findings grouping list gains "dependencies".
- No evidence-log block for this lane — it asserts no execution-pass claim the log's
  test-result shape could back, same as the other non-test lanes.

### 5. `agents/security-auditor.md` — §8 narrows to the boundary

§8 (Dependencies) currently owns read-only scanners, known CVEs, dependency confusion, and
lockfile integrity — a direct overlap with the new lane. It narrows to the escalation shape
the fleet already uses between security and infra: dependency-auditor owns the supply chain of
the diff (advisories, licenses, maintenance, drift in manifest/lockfile changes);
security-auditor keeps secrets everywhere and everything the project's own code does, and
escalates a supply-chain smell rather than hunting it. Without this edit, two always-adjacent
lanes duplicate CVE lookups on every dependency-touching diff — the "stay in lane" invariant
and the audit's cost budget both lose.

### 6. `workflows/epic-driver.js` — parity on the automated path

Without this, the lane exists on the supervised path only and `/work-through` epics silently
lack it (the operability story's exact rationale; the epic plan contains no separate
driver-wiring story). Post-#141 the driver routes mechanically, so parity is three small edits:

- `AUDITORS` gains `studious:dependency-auditor` (the roster test in
  `tests/python/test_audit_premortem_scope.py` explicitly allows growth).
- `routingScopeCheckPrompt` reports a third flag — `{"infraMatch":…,"frontendMatch":…,
  "depMatch":…}` — matched against the same canonical file's new Dependency signal list, same
  "when ambiguous, resolve to true" bias.
- `resolveAuditRoster` routes `dependency-auditor` out when `depMatch` is exactly `false`,
  reason "no dependency manifest or lockfile changes detected" (plain text, matching the
  gate's own skip-note wording, no internal file path). The existing fail-open shape is
  preserved: a missing or unparseable flag routes the lane IN.

### 7. Roster-count touch list (epic pre-mortem, item 2)

- `CLAUDE.md` — "The 17 review/audit agents share a standardized prompt contract" → 18.
- `README.md` — the `/gate-audit` bullet gains the dependency clause; "Up to 11 auditors" → 12;
  the CI-mode section's "up to 10" parenthetical is re-derived and corrected in the same pass.
- `PRODUCT.md` — the journey-2 auto-skip sentence gains the dependency lane.
- `CONTRIBUTING.md` — `dependency-auditor` joins the `opus` model list and the `medium` effort
  list, with a one-line rationale beside the premortem-auditor note it argues from.
- `reference/severity-rubric.md` — new row: dependency-auditor | Critical, High | Medium | Low,
  per that file's own closing rule.
- `tests/python/test_agent_descriptions.py` — `CHANGESET_AGENTS` gains `dependency-auditor`;
  `tests/python/test_audit_first_round_routing.py` fixtures extend to the third flag and the
  grown roster.

## User journey

Extends PRODUCT.md's critical user journey #2 (per-feature gate flow) at the audit step.

1. The persona's branch adds `left-pad-utils@2.1.0` to `package.json` and regenerates
   `package-lock.json`, alongside application code. They run `/gate-audit`.
2. The changeset matches the Dependency signal (two manifest/lockfile files); auditor 11
   dispatches in the same parallel wave as the other routed lanes.
3. The lane inventories the diff: one new direct dependency, four transitive additions in the
   lockfile. An osv.dev query returns a high-severity advisory on one transitive addition; the
   package name sits one edit from a popular package the project doesn't use; the license is
   MIT — compatible. It reports one High (advisory, reachable), one High (typosquat-adjacent
   name, `Potential`), residual line naming what came back clean and that lookups ran online.
4. The orchestrator maps High → Critical, the challenge step confirms the citation against the
   lockfile diff, verdict **FIX AND RE-AUDIT** with `blockingLanes: ["dependency-auditor"]` —
   the persona learns before merge, not weeks later from a periodic review.
5. The same persona's next branch touches only `agents/*.md` prose: the changeset matches no
   Dependency signal pattern; the summary reads "No dependency manifest or lockfile changes
   detected — dependency audit skipped." — no dispatch cost, same shape as the web lanes.
6. On a `/work-through` epic, the mechanical routing dispatch reports `depMatch:false` for a
   docs-only story and the compiled summary lists the lane as routed out with that same plain
   reason — parity between the supervised and automated paths.

## Out of scope

- **The prompt-auditor lane (#93)** — the next story in this epic's DAG; its design phase reads
  this story's landed diff (epic pre-mortem, item 1), not the pre-epic snapshot.
- **A periodic dependency-health `/deep-review` area** — `review-codebase-health` keeps its
  dependency lane unchanged; the #118 pattern (defer a periodic lane while another altitude
  covers the concern) applies in reverse here.
- **Full-tree scanning of unchanged dependencies** — the lane is diff-scoped by contract;
  accumulated staleness in untouched deps stays with the periodic review.
- **SBOM generation, Dependabot/Renovate config authoring, or auto-fixing** — recommend-only is
  a repo invariant; the lane reports, never edits manifests.
- **Container base images and CI-action pinning** — infra-auditor's lane, unchanged.
- **`/gate-acceptance`, `.github/workflows/gate-audit-pr.yml` behavior** — the CI-mode audit
  invokes `/gate-audit` as-is and inherits the lane with no workflow edit.
- **Retry caps, ledger schema, severity ladder** — dispatch-width and lane-count change only;
  no bookkeeping or calibration machinery moves.

## Alternatives considered

- **Deepen security-auditor §8 instead of a new lane (status quo, hardened).** Rejected:
  supply-chain review skips cleanly on most diffs while security runs always-on — bundled, the
  cost is paid on every diff or the attention is never really paid. A separate routed lane
  matches "stay in lane," gives the concern a rubric and a skip rule, and is the issue's own
  framing. The §8 overlap is resolved by narrowing, not duplicating (design §5).
- **Leave coverage to the periodic review only.** Rejected: weeks-late detection is the
  problem statement, not a mitigation.
- **A top-level `/gate-deps` command.** Rejected by the repo invariant: one fan-out command,
  many subagents — never a command per check.
- **Content-judged skip rule (like operability) instead of a file-pattern list.** Rejected:
  manifests and lockfiles are a closed, deterministic file surface — exactly what
  `reference/audit-routing-signals.md` exists for, and what lets the epic driver's mechanical
  dispatch route the lane without judgment. Operability's content-judged rule exists because
  runtime surface has no reliable path signature; dependency surface does.
- **`effort: high`, matching infra-auditor.** Considered — supply-chain misses are
  merge-blocking. Chosen `medium` because the work is enumerable per changed dependency
  (rubric-driven, the premortem-auditor argument) and the epic's own pre-mortem (item 4) warns
  against over-provisioned new lanes; bump to `high` later if gate outcomes show shallow misses,
  which is a one-line frontmatter change.
- **Skip epic-driver parity this story.** Rejected: the epic plan has no separate wiring story,
  and the operability precedent names the failure plainly — the lane would land on the
  supervised path only while epics silently lack it.

## Operational readiness

- **Migration.** Additive: two new files, edits to two prompt files, one JS roster/routing
  extension, count updates. No ledger schema change — `blockingLanes` already carries arbitrary
  lane names, and `resolveReauditScope` validates against whatever roster it is passed.
- **Failure modes.** Routing dispatch dies or omits `depMatch` → fail-open, lane routes IN
  (existing #141 convention, no new idiom). Advisory lookup blocked (offline/sandboxed gate
  run) → findings degrade to `Potential` with "could not verify — advisory data unreachable" in
  the residual line, never a clean claim. Lane dispatched against a non-matching diff → agent
  self-skip, a valid reported outcome.
- **Rollback.** Revert the branch: remove the two new files, restore gate-audit.md's 11-lane
  numbering, security-auditor §8, the driver's 9-lane roster and two-flag prompt, and the
  counts. Nothing persisted needs migration.
- **Rollout.** Ships via semantic-release on merge to `main`; the next `/gate-audit` or
  `/work-through` run after upgrade picks the lane up with nothing to configure.
- **How we'll know it's working or failing.** (1) Criterion 5's checks green:
  `scripts/check_references.py`, `scripts/validate_plugin.py`, markdownlint. (2) Fixture tests:
  `test_audit_first_round_routing.py` covering `depMatch` true/false/absent (absent → routed
  in), `test_agent_descriptions.py` covering the new agent's description shape,
  `test_audit_premortem_scope.py`'s roster growth. (3) Live: a diff adding a dependency routes
  the lane in and the report carries advisory-backed rows; a prose-only diff shows the skip
  note. (4) Failing signal: the lane firing on diffs with no dependency surface (routing list
  too loose) or gate latency regressing on manifest-touching diffs (rubric too broad — the epic
  pre-mortem's item-4 class).

## Open questions

- **Advisory lookup in sandboxed environments** — some gate runs will have no network. The
  degrade path is specified (`Potential` + "could not verify"), but whether `gh api` or osv.dev
  is the more reliably reachable primary settles at implementation, in the checklist's command
  table, not in the agent prompt.
- **Vendored-tree patterns (`vendor/`, `third_party/`)** — included in the signal list for
  fail-closed coverage, but a giant vendored diff may deserve a scoping note in the agent
  (review the vendoring event, not every vendored file). Settle at implementation.
- **README's CI-mode "up to 10" count** — pre-existing drift suspected (it predates the
  operability lane's renumbering); the build phase re-derives it rather than blindly
  incrementing.
