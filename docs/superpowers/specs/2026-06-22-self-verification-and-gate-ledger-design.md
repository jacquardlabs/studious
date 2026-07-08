# Design — Self-verification harness (#24) + Gate ledger (#27)

Date: 2026-06-22
Issues: #24 (A1, BUILD, Horizon 1), #27 (M1, BUILD, Horizon 2)
Status: revised after `/gate-design-review` (REVISE → addressed), pre-implementation

> Developer-local spec — not committed to git per global conventions (specs/plans stay local).

## Context

Studious is a markdown-prompt plugin: commands, agents, skills, and one PR-time hook.
Two gaps motivate this work:

- **#24** — The one quality tool in the room has no quality gate on itself. CI is only
  `release.yml` (semantic-release on push to main). No lint, no schema check, no
  link-check. Gate-contract regressions are caught by hand (v1.5 was a manual behavioral
  audit). The v2.0.0 Jaqal→Studious rename rewrote nearly every file — broken
  `@agent-*`/skill cross-references are the live risk. A dangling `@agent-*` ref doesn't
  just fail a maintainer test; it silently drops an auditor for the **end user** who runs
  the command.
- **#27** — Every gate is stateless and the PR hook (`gate-reminder.sh`) asks blindly on
  every `gh pr create`. It can't tell the user *which* gate is missing. The user-serving
  fix is a per-branch ledger the hook reads to make its reminder **specific**.

The two pair: #24 is CI on *this repo*; #27 is plugin behavior that runs in *consuming
projects*. Sequenced together per both issues' verdicts.

## Decisions (locked with user, post-design-review)

| Decision | Choice |
|----------|--------|
| #24 v1 scope | 3 deterministic checks now (link-check, plugin schema, markdownlint); golden fixtures phased to a follow-up |
| #24 tooling | Python (link-check + schema) + npm markdownlint-cli2 |
| #27 ledger storage | **Local / gitignored** at `.studious/gates/<branch-slug>.json`; never enters the consuming project's tracked tree |
| #27 write scope | **2 gates** — `audit` + `acceptance` (exactly what the hook reads) |
| Hook behavior | **Always `ask`** (non-blocking, independent checkpoint preserved); the ledger only makes the *reason text* specific. No auto-allow. |
| markdownlint strictness | Disable MD013/MD033/MD041 (prose-noise); keep structural rules; tighten later |

### Revision history (design-review reversals)

The `/gate-design-review` gate (product-reviewer + persona walkthrough) raised two
BLOCKERs against the first draft. Both reversed an earlier user decision; both accepted:

1. **Committed ledger → local/gitignored.** Committing wrote Studious bookkeeping into
   the *consuming project's* repo (PR diffs, accumulating on `main`) — a violation of the
   "lightweight, that's the whole system" thesis. The committed/durable record is X1's
   job, out of scope here.
2. **Silent auto-allow → always ask.** Auto-allow let the gate command (an LLM) write its
   own verdict and the hook silently skip the prompt on that self-report — removing the
   independent human checkpoint the hook was explicitly designed to be, and giving the
   user no signal. It also rarely fired (after a gate runs you commit fixes, so
   `SHA ≠ HEAD` by PR time). Dropped entirely; the ledger drives specific *reason text*
   instead.
3. Write scope trimmed 4 → 2 gates (`should-we-build`/`design-review` writes had no v1
   reader; they were X1 groundwork).

---

## Feature 1 — Self-verification harness (#24)

### New CI workflow

`.github/workflows/ci.yml`, triggered on `pull_request` and `workflow_dispatch` (a `push` trigger was deliberately omitted — with both, CI double-fires on every PR-branch push; `pull_request` already covers the dogfooding run).
`release.yml` is untouched (still owns main). Three independent jobs — all deterministic
file checks, no LLM, no subagents.

### Job 1 — markdownlint (Node)

- `markdownlint-cli2` with `.markdownlint-cli2.jsonc` at repo root.
- Disable prose-noise rules: `MD013` (line length), `MD033` (inline HTML),
  `MD041` (first-line heading). Keep structural rules (link syntax, list/heading
  consistency).
- Globs: `commands/`, `agents/`, `skills/`, root `*.md`.

### Job 2 — plugin schema validation (Python)

- `scripts/validate_plugin.py` validates `.claude-plugin/plugin.json` against a local
  JSON Schema:
  - required: `name`, `description`, `version`, `author.name`, `repository`, `license`, `keywords`
  - `name` matches `^[a-z0-9-]+$`
  - `version` is semver
  - types enforced
- Implementation note: cross-check against the official Claude Code plugin manifest
  schema if one is published; otherwise this local schema stands.

### Job 3 — link-check (Python) — highest value

- `scripts/check_references.py` parses every markdown file under `commands/` and `agents/`:
  - `@agent-<name>` → assert `agents/<name>.md` exists
  - internal skill invocation → assert `skills/<name>/` exists
  - `EXTERNAL_SKILLS` allowlist (currently `web-design-guidelines`) — permitted to be absent
- Non-zero exit with a precise message:
  `@agent-foo referenced in commands/bar.md but agents/foo.md missing`.
- This is the job that catches the v2.0.0 rename class of bug — and it protects the **end
  user**, not just the maintainer: an orphaned `@agent-*` ref silently drops an auditor
  from the user's `/gate-audit` run.

### Scoped out of v1 (honest gaps)

- Plain-name agent refs in the deep-review table (e.g. `review-codebase-health` without
  the `@agent-` prefix) — hard to detect without false positives.
- Golden-fixture verdict-structure tests — phased to a follow-up; they require running
  the actual gates (subagents/LLM), which is expensive and nondeterministic in CI and
  needs recorded/mocked runs.

---

## Feature 2 — Gate ledger (#27)

### Ledger file

- Path: `.studious/gates/<branch-slug>.json` — **gitignored, never committed**.
- `branch-slug` = branch name with `/` replaced by `-`.
- The recorder ensures `.studious/` is in the consuming project's `.gitignore` on first
  write (self-healing for projects already past `/studious-init`), so the ledger never
  appears in the user's `git status` or PR diffs.
- Shape — latest record per gate wins; `verdict` stores the gate's actual **token**:

```json
{
  "branch": "feat/foo",
  "gates": {
    "audit":      { "verdict": "PASS", "sha": "abc1234", "ranAt": "2026-06-22T18:30:00Z" },
    "acceptance": { "verdict": "SHIP", "sha": "abc1234", "ranAt": "2026-06-22T18:45:00Z" }
  }
}
```

### Write-side

Two gate commands gain a final "Record to ledger" step that upserts
`{verdict, sha, ranAt}` under the gate's key for the current branch:

- `gate-audit` → key `audit`, verdict token ∈ {`PASS`, `FIX AND RE-AUDIT`, `NEEDS DISCUSSION`}
- `gate-acceptance` → key `acceptance`, verdict token ∈ {`SHIP`, `FIX AND RE-CHECK`, `HOLD`}

`sha` = `git rev-parse --short HEAD`; `ranAt` = ISO-8601 UTC. The recorded `verdict` is
the exact token the gate emits — not descriptive prose — so the hook matches reliably.

### Read-side — `gate-reminder.sh`

Stays **non-blocking — always `ask`**. The ledger only changes the *reason text*:

| Ledger state (current branch) | Reason text |
|-------------------------------|-------------|
| audit=`PASS` AND acceptance=`SHIP`, both SHA==HEAD | "audit (PASS) and acceptance (SHIP) ran on this branch — proceed." |
| a relevant gate missing | "acceptance never ran on this branch — proceed anyway?" |
| gate present but SHA≠HEAD | "audit ran 3 commits ago — re-run before merging?" |
| gate present, non-passing token | "audit returned FIX AND RE-AUDIT — proceed anyway?" |
| no ledger / `jq` unavailable | today's unconditional message (graceful degradation) |

Every path returns `ask` — the independent human confirmation the hook was designed to be
is preserved. "Passing" = audit `PASS`, acceptance `SHIP`; any other token is treated as
not-passing.

---

## Ledger read/write plumbing (resolved)

Single source of truth is `bin/gate-ledger` with `record` and `status` subcommands.
Per Claude Code plugin docs (confirmed via claude-code-guide): `CLAUDE_PLUGIN_ROOT` is
**not** exported to Bash-tool calls during slash-command execution, but files in a
plugin's **`bin/`** are automatically on the Bash tool's PATH as bare commands.

- **Read-side (hook):** calls `${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger status` —
  `CLAUDE_PLUGIN_ROOT` is exported into hook processes (already used by `hooks.json`).
- **Write-side (2 gate commands):** call bare `gate-ledger record …` via the `bin/` PATH.

This PATH claim is doc-derived, so the plan's first Track-B step (B0) observes it
empirically before trusting it; the documented fallback if it fails is an inline `jq`
record snippet embedded in each command (no path dependency).

`jq` is the JSON parser for both sides, with graceful fallback (hook → unconditional
`ask`; recorder → best-effort) when absent.

---

## Components & boundaries

| Unit | Purpose | Depends on |
|------|---------|------------|
| `.github/workflows/ci.yml` | Orchestrate CI jobs on PR | the 3 scripts + markdownlint-cli2 + ledger tests |
| `scripts/validate_plugin.py` | Validate plugin.json structure | stdlib only (local checks) |
| `scripts/check_references.py` | Resolve `@agent-*`/skill refs to files | repo file tree, `EXTERNAL_SKILLS` allowlist |
| `.markdownlint-cli2.jsonc` | markdownlint rule config | — |
| `bin/gate-ledger` | Read/write the ledger (`record`/`status`); ensure `.gitignore` entry | `git`, `jq` |
| `gate-audit.md`, `gate-acceptance.md` | Append a "record to ledger" step | bare `gate-ledger` (or inline snippet) |
| `hooks/gate-reminder.sh` | Specific-reason PR reminder (always `ask`) | `gate-ledger status`, ledger file |

## Testing

- **#24 scripts:** unit-test `check_references.py` and `validate_plugin.py` against
  fixtures (a known-good tree, a dangling `@agent-x`, a missing required plugin field).
  These are the regression tests for the harness itself.
- **#27 ledger:** test `gate-ledger record` upsert (new gate, overwrite same gate, and
  `.gitignore` self-heal) and `status` reason-text matrix (both-passing / missing / stale
  / non-passing / fallback). Every case must return `ask`.
- Run the CI workflow on the implementation branch's own PR — it should lint and
  link-check this very changeset.

## Out of scope

- Auto-allow / any non-`ask` hook decision (reversed at design review).
- Committed or durable "verdict of record" (PR comments, issue trackers, committed
  ledger) — that is X1's job; #27 stays "no spec-graph machinery."
- `should-we-build` / `design-review` ledger writes — added when X1 needs a reader.
- Golden-fixture verdict tests (#24 follow-up).
- Ledger pruning/garbage collection (now moot — gitignored, dies with the working copy).
