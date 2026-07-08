# Self-Verification Harness + Gate Ledger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CI self-verification to the Studious repo (#24) and a local per-branch gate ledger that makes the PR-time hook reminder specific (#27).

**Architecture:** Two independent tracks. Track A adds `.github/workflows/ci.yml` running three deterministic file checks (markdownlint, plugin-manifest validation, `@agent-*`/skill link-check) on `pull_request` (plus manual `workflow_dispatch`). Track B ships a single `bin/gate-ledger` executable that gate commands call (bare command via the plugin's `bin/` PATH) to write a gitignored `.studious/gates/<branch>.json` record, which the rewritten `gate-reminder.sh` hook reads (via `${CLAUDE_PLUGIN_ROOT}`) to produce a specific — but still always-`ask` — PR reminder.

**Tech Stack:** GitHub Actions, Python 3 (stdlib only, run via `uv`), pytest, `markdownlint-cli2` (npx), Bash, `jq`.

## Global Constraints

- Python scripts use the **standard library only** — no third-party imports in `scripts/*.py`.
- Python tooling runs via **uv** (`uv run --no-project …`), per project convention.
- The gate ledger is **local and gitignored** — it must never enter a consuming project's tracked tree. Path: `.studious/gates/<branch-slug>.json`; `branch-slug` = branch name with `/` → `-`.
- The hook **always returns `permissionDecision: "ask"`** — never `allow`/`deny`. The ledger changes only the reason text.
- Recorded verdicts are the gate's exact **token**: audit ∈ {`PASS`, `FIX AND RE-AUDIT`, `NEEDS DISCUSSION`}; acceptance ∈ {`SHIP`, `FIX AND RE-CHECK`, `HOLD`}. "Passing" = audit `PASS`, acceptance `SHIP`.
- `bin/gate-ledger` must degrade gracefully when `jq` is absent (skip writes / emit no reason) so the hook falls back to today's generic message.
- Commit messages use **Conventional Commits** (`feat:`, `test:`, `chore:`, `docs:`) — `python-semantic-release` derives versions from them.
- Work on branch `feat/self-verification-and-gate-ledger` off `main`. `release.yml` is not modified.

---

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `scripts/check_references.py` | create | Resolve every `@agent-*` and `the \`<name>\` skill` reference in `commands/` + `agents/` to a real file; exit 1 with a precise message on any dangling ref |
| `scripts/validate_plugin.py` | create | Validate `.claude-plugin/plugin.json` required fields, types, semver, name pattern |
| `.markdownlint-cli2.jsonc` | create | markdownlint config (ratchet at current state) |
| `bin/gate-ledger` | create | `record` + `status` subcommands; gitignore self-heal; jq-graceful |
| `tests/python/conftest.py` | create | Put `scripts/` on `sys.path` for tests |
| `tests/python/test_check_references.py` | create | Unit tests for the link-checker |
| `tests/python/test_validate_plugin.py` | create | Unit tests for the manifest validator |
| `tests/test_gate_ledger.sh` | create | Bash integration tests for `bin/gate-ledger` |
| `.github/workflows/ci.yml` | create | Run all checks + tests on `pull_request` + `workflow_dispatch` |
| `commands/gate-audit.md` | modify | Append "Record to ledger" step |
| `commands/gate-acceptance.md` | modify | Append "Record to ledger" step |
| `hooks/gate-reminder.sh` | modify | Read ledger via `gate-ledger status`; specific reason; still `ask` |

Track A = scripts + config + tests + ci.yml. Track B = `bin/gate-ledger` + ledger tests + 2 command edits + hook rewrite. Tracks are independent; within Track A, `ci.yml` (A4) comes last; within Track B, `bin/gate-ledger` (B1) comes first.

---

## Track A — Self-verification harness (#24)

### Task A1: Reference link-checker

**Files:**
- Create: `scripts/check_references.py`
- Create: `tests/python/conftest.py`
- Test: `tests/python/test_check_references.py`

**Interfaces:**
- Produces: `find_broken(root: pathlib.Path) -> list[str]` — returns a list of human-readable error strings (empty when all refs resolve). `main() -> int` returns process exit code.

- [ ] **Step 1: Write the conftest so tests can import from `scripts/`**

Create `tests/python/conftest.py`:

```python
import sys
from pathlib import Path

# Make scripts/ importable as top-level modules in tests.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
```

- [ ] **Step 2: Write the failing tests**

Create `tests/python/test_check_references.py`:

```python
from pathlib import Path

from check_references import find_broken


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_resolves_clean(tmp_path: Path) -> None:
    _write(tmp_path / "agents" / "security-auditor.md", "x")
    _write(tmp_path / "commands" / "gate.md", "Use @agent-security-auditor here")
    assert find_broken(tmp_path) == []


def test_flags_dangling_agent(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "Use @agent-ghost here")
    errors = find_broken(tmp_path)
    assert len(errors) == 1
    assert "agents/ghost.md missing" in errors[0]


def test_allows_external_skill(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "invoke the `web-design-guidelines` skill")
    assert find_broken(tmp_path) == []


def test_flags_missing_internal_skill(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "invoke the `ghost-skill` skill")
    errors = find_broken(tmp_path)
    assert any("skills/ghost-skill/ missing" in e for e in errors)


def test_passes_when_internal_skill_exists(tmp_path: Path) -> None:
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)
    _write(tmp_path / "commands" / "gate.md", "invoke the `real-skill` skill")
    assert find_broken(tmp_path) == []
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest pytest tests/python/test_check_references.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'check_references'`.

- [ ] **Step 4: Write the implementation**

Create `scripts/check_references.py`:

```python
#!/usr/bin/env python3
"""Verify every @agent-* and internal-skill reference in commands/ and agents/ resolves.

Run from CI to catch broken cross-references (e.g. an agent rename that orphans a
command's @agent-* reference). Standard library only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("commands", "agents")
AGENT_RE = re.compile(r"@agent-([a-z0-9-]+)")
# "the `<name>` skill" is the codebase's phrasing for a skill reference.
SKILL_RE = re.compile(r"the `([a-z0-9-]+)` skill")
# Skills referenced by name but legitimately shipped elsewhere, not in this repo.
EXTERNAL_SKILLS = {"web-design-guidelines"}


def find_broken(root: Path) -> list[str]:
    errors: list[str] = []
    for sub in SCAN_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            rel = md.relative_to(root)
            for name in sorted(set(AGENT_RE.findall(text))):
                if not (root / "agents" / f"{name}.md").is_file():
                    errors.append(
                        f"@agent-{name} referenced in {rel} but agents/{name}.md missing"
                    )
            for name in sorted(set(SKILL_RE.findall(text))):
                if name in EXTERNAL_SKILLS:
                    continue
                if not (root / "skills" / name).is_dir():
                    errors.append(
                        f"skill `{name}` referenced in {rel} but skills/{name}/ missing"
                    )
    return errors


def main() -> int:
    errors = find_broken(REPO)
    if errors:
        print("Reference check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Reference check passed: all @agent-* and skill references resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest pytest tests/python/test_check_references.py -v`
Expected: PASS (5 passed).

- [ ] **Step 6: Run the checker against the real repo**

Run: `uv run --no-project python scripts/check_references.py`
Expected: `Reference check passed: all @agent-* and skill references resolve.` (exit 0). If it fails, a real dangling reference exists — fix the referencing command/agent file, not the checker.

- [ ] **Step 7: Commit**

```bash
git add scripts/check_references.py tests/python/conftest.py tests/python/test_check_references.py
git commit -m "feat: add @agent-/skill reference link-checker"
```

---

### Task A2: Plugin manifest validator

**Files:**
- Create: `scripts/validate_plugin.py`
- Test: `tests/python/test_validate_plugin.py`

**Interfaces:**
- Produces: `validate(data: dict) -> list[str]` — error strings (empty when valid). `main() -> int` reads `.claude-plugin/plugin.json` and returns exit code.

- [ ] **Step 1: Write the failing tests**

Create `tests/python/test_validate_plugin.py`:

```python
from validate_plugin import validate

GOOD = {
    "name": "studious",
    "description": "d",
    "version": "2.0.0",
    "author": {"name": "Jacquard Labs"},
    "repository": "https://github.com/jacquardlabs/studious",
    "license": "MIT",
    "keywords": ["review"],
}


def test_good_manifest_passes() -> None:
    assert validate(GOOD) == []


def test_missing_required_field() -> None:
    data = dict(GOOD)
    del data["license"]
    assert any("license" in e for e in validate(data))


def test_bad_semver() -> None:
    data = dict(GOOD)
    data["version"] = "2.0"
    assert any("semver" in e for e in validate(data))


def test_bad_name_pattern() -> None:
    data = dict(GOOD)
    data["name"] = "Studious_X"
    assert any("name" in e for e in validate(data))


def test_author_without_name() -> None:
    data = dict(GOOD)
    data["author"] = {}
    assert any("author.name" in e for e in validate(data))


def test_keywords_must_be_list() -> None:
    data = dict(GOOD)
    data["keywords"] = "review"
    assert any("keywords" in e for e in validate(data))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run --no-project --with pytest pytest tests/python/test_validate_plugin.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'validate_plugin'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/validate_plugin.py`:

```python
#!/usr/bin/env python3
"""Validate .claude-plugin/plugin.json against Studious's required manifest shape.

Standard library only. Cross-check against the official Claude Code plugin manifest
schema if one is published; until then this local check stands.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / ".claude-plugin" / "plugin.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
NAME = re.compile(r"^[a-z0-9-]+$")
REQUIRED = ("name", "description", "version", "author", "repository", "license", "keywords")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED:
        if key not in data:
            errors.append(f"missing required field: {key}")

    name = data.get("name")
    if "name" in data and not isinstance(name, str):
        errors.append("name must be a string")
    elif isinstance(name, str) and not NAME.match(name):
        errors.append(f"name '{name}' must match ^[a-z0-9-]+$")

    version = data.get("version")
    if "version" in data and not isinstance(version, str):
        errors.append("version must be a string")
    elif isinstance(version, str) and not SEMVER.match(version):
        errors.append(f"version '{version}' is not semver (X.Y.Z)")

    author = data.get("author")
    if isinstance(author, dict):
        if "name" not in author:
            errors.append("author.name is required")
    elif "author" in data:
        errors.append("author must be an object with a name")

    if "keywords" in data and not isinstance(data.get("keywords"), list):
        errors.append("keywords must be an array")

    return errors


def main() -> int:
    try:
        data = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plugin.json could not be read/parsed: {exc}")
        return 1
    errors = validate(data)
    if errors:
        print("Plugin manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Plugin manifest valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run --no-project --with pytest pytest tests/python/test_validate_plugin.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Run the validator against the real manifest**

Run: `uv run --no-project python scripts/validate_plugin.py`
Expected: `Plugin manifest valid.` (exit 0).

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_plugin.py tests/python/test_validate_plugin.py
git commit -m "feat: add plugin manifest validator"
```

---

### Task A3: markdownlint config (ratchet at current state)

**Files:**
- Create: `.markdownlint-cli2.jsonc`

**Interfaces:** none (consumed by `markdownlint-cli2` and `ci.yml`).

- [ ] **Step 1: Write the config**

Create `.markdownlint-cli2.jsonc`:

```jsonc
{
  // Studious markdown lint. Prose-heavy prompt files, so several stylistic rules are
  // disabled. The link-check (scripts/check_references.py) and plugin-schema jobs carry
  // the real protection; this job ratchets the markdown at its current state and blocks
  // new violations of every still-enabled rule.
  "config": {
    "default": true,
    // Prose rules — intentionally off for command/agent/skill content:
    "MD013": false, // line length
    "MD033": false, // inline HTML (system-reminder tags, etc.)
    "MD041": false, // first line must be a heading (frontmatter precedes it)
    // Current violators — tighten incrementally via a follow-up `--fix` pass:
    "MD022": false, // blanks around headings
    "MD032": false, // blanks around lists
    "MD060": false, // table formatting
    "MD040": false, // fenced code language
    "MD026": false, // trailing punctuation in heading
    "MD029": false  // ordered list prefix
  },
  "globs": ["commands/**/*.md", "agents/**/*.md", "skills/**/*.md", "*.md"],
  "ignores": ["node_modules", "CHANGELOG.md", "docs/**"]
}
```

- [ ] **Step 2: Run markdownlint to verify a clean pass**

Run: `npx -y markdownlint-cli2`
Expected: exit 0, `Summary: 0 error(s)`. If a still-enabled rule fires on existing files, either fix the genuine issue or add the rule to the disabled list with a one-line reason — do not broaden globs.

- [ ] **Step 3: Commit**

```bash
git add .markdownlint-cli2.jsonc
git commit -m "chore: add markdownlint config ratcheting current state"
```

---

### Task A4: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `scripts/check_references.py`, `scripts/validate_plugin.py`, `tests/python/`, `.markdownlint-cli2.jsonc` (A1–A3), and `tests/test_gate_ledger.sh` (B1).

> Depends on A1–A3 and B1 (the `ledger` job runs B1's test script). Sequence A4 after B1, or create A4 with only the `markdown` + `python-checks` jobs and add the `ledger` job in B1's commit.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  workflow_dispatch:

jobs:
  markdown:
    name: markdownlint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - run: npx -y markdownlint-cli2

  python-checks:
    name: link-check + schema + unit tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - name: Link-check references
        run: uv run --no-project python scripts/check_references.py
      - name: Validate plugin manifest
        run: uv run --no-project python scripts/validate_plugin.py
      - name: Unit tests
        run: uv run --no-project --with pytest pytest tests/python -v

  ledger:
    name: gate-ledger tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Gate-ledger integration tests
        run: bash tests/test_gate_ledger.sh
```

- [ ] **Step 2: Verify the referenced commands run locally (proxy for the workflow)**

Run each job's command locally and confirm exit 0:

```bash
npx -y markdownlint-cli2
uv run --no-project python scripts/check_references.py
uv run --no-project python scripts/validate_plugin.py
uv run --no-project --with pytest pytest tests/python -v
bash tests/test_gate_ledger.sh
```

Expected: all exit 0. (The workflow itself is exercised when the PR opens.)

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "feat: add CI self-verification workflow"
```

---

## Track B — Gate ledger (#27)

### Task B0: Verify `bin/` PATH resolution (load-bearing prerequisite)

**Why first:** B2 calls `gate-ledger` as a **bare command**, relying on the plugin's `bin/`
being on the Bash tool's PATH at runtime. This is doc-derived, not yet observed. Its
failure mode is **silent**: if the bare command doesn't resolve, records never write, the
hook falls back to the generic message, and the entire test suite still passes green while
#27 does nothing. Confirm the assumption empirically before trusting B1–B3.

**Files:** none (verification only).

- [ ] **Step 1: Create the executable stub and install the plugin locally**

```bash
mkdir -p bin
printf '#!/usr/bin/env bash\necho "gate-ledger reachable: $*"\n' > bin/gate-ledger
chmod +x bin/gate-ledger
```

Ensure the plugin is installed/enabled in a real Claude Code session (e.g. via
`scripts/install-dev.sh` or `/plugin install`).

- [ ] **Step 2: Observe whether the bare command resolves in a Bash tool call**

In an active Claude Code session with the plugin enabled, run from the Bash tool:

```bash
command -v gate-ledger && gate-ledger status
```

Expected (assumption holds): `command -v` prints a path under the plugin's `bin/` and the
stub echoes. Record the result.

- [ ] **Step 3: Branch on the outcome**

- **If it resolves:** proceed with B1–B3 exactly as written (bare `gate-ledger` in B2).
- **If it does NOT resolve:** the bare-command path is unavailable to slash commands. Keep
  `bin/gate-ledger` for the hook (which uses `${CLAUDE_PLUGIN_ROOT}` and is unaffected),
  but change **B2** to embed the record logic **inline** in the command markdown instead
  of calling an external command — a self-contained `jq` snippet writing
  `.studious/gates/<branch>.json` with the same shape and `.gitignore` self-heal as
  `cmd_record`. Do not rely on a path the runtime doesn't provide.

- [ ] **Step 4: Remove the stub** (B1 writes the real implementation)

```bash
rm bin/gate-ledger
```

---

### Task B1: `bin/gate-ledger` executable

**Files:**
- Create: `bin/gate-ledger`
- Test: `tests/test_gate_ledger.sh`

**Interfaces:**
- Produces (CLI contract relied on by B2 + B3):
  - `gate-ledger record --gate <audit|acceptance> --verdict "<TOKEN>"` — upserts the record, ensures `.studious/` is gitignored, exits 0 (also exits 0 silently if `jq`/`git` unavailable).
  - `gate-ledger status` — prints a single reason line to stdout for the hook, or **nothing** when there is no usable ledger (so the hook uses its default). Always exits 0.

- [ ] **Step 1: Write the failing test script**

Create `tests/test_gate_ledger.sh`:

```bash
#!/usr/bin/env bash
# Integration tests for bin/gate-ledger. Requires git + jq.
set -uo pipefail

LEDGER="$(cd "$(dirname "$0")/.." && pwd)/bin/gate-ledger"
fails=0

check() { # description, expected, actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1"; echo "       expected: $2"; echo "       actual:   $3"; fails=$((fails + 1))
  fi
}
contains() { # description, needle, haystack
  case "$3" in
    *"$2"*) echo "ok   - $1" ;;
    *) echo "FAIL - $1"; echo "       expected substring: $2"; echo "       in: $3"; fails=$((fails + 1)) ;;
  esac
}

sandbox() { # create a throwaway git repo, echo its path
  local d; d=$(mktemp -d)
  git -C "$d" init -q
  git -C "$d" config user.email t@t.t
  git -C "$d" config user.name t
  git -C "$d" commit -q --allow-empty -m init
  git -C "$d" checkout -q -b feat/foo
  printf '%s' "$d"
}

# --- record writes the expected shape ---
d=$(sandbox)
( cd "$d" && "$LEDGER" record --gate audit --verdict PASS )
f="$d/.studious/gates/feat-foo.json"
check "record creates branch-slug ledger file" "yes" "$([ -f "$f" ] && echo yes || echo no)"
check "record stores verdict token" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "record stores branch name" "feat/foo" "$(jq -r '.branch' "$f")"
check "record stores HEAD sha" "$(git -C "$d" rev-parse --short HEAD)" "$(jq -r '.gates.audit.sha' "$f")"

# --- record self-heals .gitignore ---
contains "record adds .studious/ to .gitignore" ".studious/" "$(cat "$d/.gitignore")"
check "ledger is gitignored (not in status)" "" "$(cd "$d" && git status --porcelain .studious 2>/dev/null)"

# --- second record upserts (latest wins, second gate added) ---
( cd "$d" && "$LEDGER" record --gate acceptance --verdict SHIP )
check "upsert keeps audit" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "upsert adds acceptance" "SHIP" "$(jq -r '.gates.acceptance.verdict' "$f")"

# --- status: both passing at HEAD ---
out=$(cd "$d" && "$LEDGER" status)
contains "status reports clean pass" "proceed" "$out"

# --- status: missing gate ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" record --gate audit --verdict PASS )
out=$(cd "$d2" && "$LEDGER" status)
contains "status names the missing gate" "acceptance never ran" "$out"

# --- status: non-passing verdict ---
d3=$(sandbox)
( cd "$d3" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
( cd "$d3" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$d3" && "$LEDGER" status)
contains "status surfaces non-passing audit" "FIX AND RE-AUDIT" "$out"

# --- status: stale sha ---
d4=$(sandbox)
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$d4" && git commit -q --allow-empty -m more )
out=$(cd "$d4" && "$LEDGER" status)
contains "status flags stale gate" "re-run" "$out"

# --- status: no ledger -> empty (hook uses default) ---
d5=$(sandbox)
out=$(cd "$d5" && "$LEDGER" status)
check "status empty when no ledger" "" "$out"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
```

- [ ] **Step 2: Run the test script to verify it fails**

Run: `bash tests/test_gate_ledger.sh`
Expected: FAIL — `bin/gate-ledger` does not exist yet (file-not-found / many FAILs).

- [ ] **Step 3: Write the implementation**

Create `bin/gate-ledger`:

```bash
#!/usr/bin/env bash
# gate-ledger — read/write Studious's per-branch gate ledger.
#
# Local, gitignored state at .studious/gates/<branch-slug>.json in the consuming
# project. Written by /gate-audit and /gate-acceptance (via `record`); read by the
# PR-time hook (via `status`). Degrades silently when git or jq is unavailable.
set -uo pipefail

LEDGER_DIR=".studious/gates"

branch_name() { git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD; }
branch_slug() { local b; b=$(branch_name); printf '%s' "${b//\//-}"; }
head_sha()    { git rev-parse --short HEAD 2>/dev/null || echo ""; }
now_iso()     { date -u +%Y-%m-%dT%H:%M:%SZ; }

have() { command -v "$1" >/dev/null 2>&1; }

ensure_gitignore() {
  # Self-heal: keep .studious/ out of the user's git status, even for projects
  # initialized before the ledger existed.
  local root gi
  root=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  gi="$root/.gitignore"
  if [ ! -f "$gi" ] || ! grep -qxF '.studious/' "$gi" 2>/dev/null; then
    printf '\n# Studious local gate ledger (do not commit)\n.studious/\n' >> "$gi"
  fi
}

cmd_record() {
  local gate="" verdict=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --gate)    gate="$2"; shift 2 ;;
      --verdict) verdict="$2"; shift 2 ;;
      *) echo "gate-ledger: unknown arg '$1'" >&2; return 2 ;;
    esac
  done
  [ -n "$gate" ] && [ -n "$verdict" ] || { echo "gate-ledger: --gate and --verdict required" >&2; return 2; }
  have jq && have git || { echo "gate-ledger: jq/git unavailable; skipping ledger write" >&2; return 0; }

  ensure_gitignore
  mkdir -p "$LEDGER_DIR"
  local file; file="$LEDGER_DIR/$(branch_slug).json"
  [ -f "$file" ] || printf '{"branch":"","gates":{}}' > "$file"

  local tmp; tmp=$(mktemp)
  jq --arg b "$(branch_name)" --arg g "$gate" --arg v "$verdict" \
     --arg s "$(head_sha)" --arg t "$(now_iso)" \
     '.branch = $b | .gates[$g] = {verdict: $v, sha: $s, ranAt: $t}' \
     "$file" > "$tmp" && mv "$tmp" "$file"
}

cmd_status() {
  have jq && have git || return 0
  local file; file="$LEDGER_DIR/$(branch_slug).json"
  [ -f "$file" ] || return 0

  local head a_v a_s c_v c_s
  head=$(head_sha)
  a_v=$(jq -r '.gates.audit.verdict // empty' "$file")
  a_s=$(jq -r '.gates.audit.sha // empty' "$file")
  c_v=$(jq -r '.gates.acceptance.verdict // empty' "$file")
  c_s=$(jq -r '.gates.acceptance.sha // empty' "$file")

  local msgs=()
  [ -z "$a_v" ] && msgs+=("audit never ran on this branch")
  [ -z "$c_v" ] && msgs+=("acceptance never ran on this branch")
  [ -n "$a_v" ] && [ "$a_s" != "$head" ] && msgs+=("audit ran at $a_s but HEAD is $head — re-run before merging")
  [ -n "$c_v" ] && [ "$c_s" != "$head" ] && msgs+=("acceptance ran at $c_s but HEAD is $head — re-run before merging")
  [ -n "$a_v" ] && [ "$a_s" = "$head" ] && [ "$a_v" != "PASS" ] && msgs+=("audit returned $a_v")
  [ -n "$c_v" ] && [ "$c_s" = "$head" ] && [ "$c_v" != "SHIP" ] && msgs+=("acceptance returned $c_v")

  if [ "${#msgs[@]}" -eq 0 ]; then
    printf 'audit (PASS) and acceptance (SHIP) ran on this branch at HEAD — proceed.'
  else
    local joined; joined=$(printf '%s; ' "${msgs[@]}"); joined=${joined%; }
    printf 'Studious gate check — %s. Proceed anyway?' "$joined"
  fi
}

case "${1:-}" in
  record) shift; cmd_record "$@" ;;
  status) shift; cmd_status "$@" ;;
  *) echo "usage: gate-ledger {record --gate G --verdict V | status}" >&2; exit 2 ;;
esac
```

- [ ] **Step 4: Make it executable**

Run: `chmod +x bin/gate-ledger`

- [ ] **Step 5: Run the test script to verify it passes**

Run: `bash tests/test_gate_ledger.sh`
Expected: PASS — `all gate-ledger tests passed` (exit 0).

- [ ] **Step 6: Add the `ledger` job to CI (if A4 already landed without it)**

If `.github/workflows/ci.yml` does not yet contain the `ledger` job from Task A4, add it now (see A4 Step 1).

- [ ] **Step 7: Commit**

```bash
git add bin/gate-ledger tests/test_gate_ledger.sh
git commit -m "feat: add gate-ledger record/status helper"
```

---

### Task B2: Wire `record` into the gate commands

**Files:**
- Modify: `commands/gate-audit.md` (append after the `### Verdict` section, end of file)
- Modify: `commands/gate-acceptance.md` (append after the `## Part 3 — Verdict` section, end of file)

**Interfaces:**
- Consumes: `gate-ledger record --gate … --verdict …` (B1), invoked as a bare command via the plugin's `bin/` PATH.

> **Gated on B0.** Use the bare-command form below only if B0 Step 2 confirmed `gate-ledger` resolves on PATH. If it did not, embed the equivalent inline `jq` record snippet (B0 Step 3) in each command instead.

- [ ] **Step 1: Append the record step to `commands/gate-audit.md`**

Add at the end of the file (after the `NEEDS DISCUSSION` bullet):

```markdown

## Record the verdict

After stating the verdict, record it to the local gate ledger so the PR-time reminder
can be specific. Run (substituting the verdict token you just assigned — `PASS`,
`FIX AND RE-AUDIT`, or `NEEDS DISCUSSION`):

```bash
gate-ledger record --gate audit --verdict "PASS"
```

The ledger is local and gitignored — it never enters the repo. If the `gate-ledger`
command is unavailable, skip this step.
```

- [ ] **Step 2: Append the record step to `commands/gate-acceptance.md`**

Add at the end of the file (after the "FIX AND RE-CHECK items…" line):

```markdown

## Record the verdict

After stating the verdict, record it to the local gate ledger so the PR-time reminder
can be specific. Run (substituting the verdict token you just assigned — `SHIP`,
`FIX AND RE-CHECK`, or `HOLD`):

```bash
gate-ledger record --gate acceptance --verdict "SHIP"
```

The ledger is local and gitignored — it never enters the repo. If the `gate-ledger`
command is unavailable, skip this step.
```

- [ ] **Step 3: Verify the link-check and markdownlint still pass**

Run:
```bash
uv run --no-project python scripts/check_references.py
npx -y markdownlint-cli2
```
Expected: both exit 0. (No new `@agent-*`/skill refs were added; nested code fences are within the disabled-rule set.)

- [ ] **Step 4: Commit**

```bash
git add commands/gate-audit.md commands/gate-acceptance.md
git commit -m "feat: record audit/acceptance verdicts to the gate ledger"
```

---

### Task B3: Rewrite the PR-time hook to read the ledger

**Files:**
- Modify: `hooks/gate-reminder.sh` (full rewrite of the body)

**Interfaces:**
- Consumes: `${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger status` (B1). `CLAUDE_PLUGIN_ROOT` is exported into hook processes (confirmed via Claude Code plugin docs).

- [ ] **Step 1: Write the failing test (hook reason wiring)**

Append to `tests/test_gate_ledger.sh`, before the final summary block:

```bash
# --- hook surfaces the ledger reason and always asks ---
HOOK="$(cd "$(dirname "$0")/.." && pwd)/hooks/gate-reminder.sh"
d6=$(sandbox)
( cd "$d6" && "$LEDGER" record --gate audit --verdict PASS )
hook_out=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh pr create"}}')
contains "hook decision is ask" '"permissionDecision": "ask"' "$hook_out"
contains "hook reason names missing acceptance" "acceptance never ran" "$hook_out"

# --- hook stays silent for non-PR commands ---
hook_noop=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)" \
  bash "$HOOK" <<<'{"tool_input":{"command":"ls -la"}}')
check "hook ignores non-PR commands" "" "$hook_noop"
```

- [ ] **Step 2: Run the test to verify the new cases fail**

Run: `bash tests/test_gate_ledger.sh`
Expected: FAIL on "hook reason names missing acceptance" — the current hook emits a generic message, not the ledger reason.

- [ ] **Step 3: Rewrite `hooks/gate-reminder.sh`**

Replace the file contents with:

```bash
#!/usr/bin/env bash
# Studious gate reminder — a PreToolUse hook that fires before `gh pr create`.
#
# Non-blocking by design: it always returns an "ask" decision so a human confirms
# before the PR opens. When a gate ledger exists for the current branch
# (.studious/gates/<branch>.json, written by /gate-audit and /gate-acceptance) it
# makes the reason SPECIFIC — naming a missing, stale, or non-passing gate — instead
# of asking blindly. With no ledger (or no jq) it falls back to the generic prompt.

input=$(cat)

printf '%s' "$input" | grep -q 'gh pr create' || exit 0

default_reason="Studious: opening a PR. Did /gate-audit and /gate-acceptance run on this branch? Proceed if the gates passed or don't apply to this change."

reason=""
ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ]; then
  reason=$("$ledger" status 2>/dev/null) || reason=""
fi
[ -n "$reason" ] || reason="$default_reason"

if command -v jq >/dev/null 2>&1; then
  jq -n --arg r "$reason" '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "ask",
      permissionDecisionReason: $r
    }
  }'
else
  # jq-less fallback: reason is controlled text; emit static generic prompt.
  cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Studious: opening a PR. Did /gate-audit and /gate-acceptance run on this branch? Proceed if the gates passed or don't apply to this change."
  }
}
JSON
fi

exit 0
```

- [ ] **Step 4: Run the full ledger test script to verify all pass**

Run: `bash tests/test_gate_ledger.sh`
Expected: PASS — `all gate-ledger tests passed` (exit 0).

- [ ] **Step 5: Verify markdownlint + reference checks still pass**

Run:
```bash
uv run --no-project python scripts/check_references.py
npx -y markdownlint-cli2
```
Expected: both exit 0.

- [ ] **Step 6: Commit**

```bash
git add hooks/gate-reminder.sh tests/test_gate_ledger.sh
git commit -m "feat: make PR gate reminder specific via the gate ledger"
```

---

## Final integration

- [ ] **Run the entire local suite** (mirrors CI):

```bash
npx -y markdownlint-cli2
uv run --no-project python scripts/check_references.py
uv run --no-project python scripts/validate_plugin.py
uv run --no-project --with pytest pytest tests/python -v
bash tests/test_gate_ledger.sh
```
Expected: all exit 0.

- [ ] **Open the PR** targeting `main`, body closing both issues:

```bash
git push -u origin feat/self-verification-and-gate-ledger
gh pr create --title "feat: self-verification harness + gate ledger" \
  --body "Closes #24. Closes #27."
```

The opened PR triggers `ci.yml` — it lints and link-checks this very changeset (dogfooding). The gate-reminder hook will fire on the `gh pr create` above; answer per the ledger reason.

---

## Self-Review

**Spec coverage:**
- #24 link-check → A1 ✓ · plugin schema → A2 ✓ · markdownlint → A3 ✓ · CI workflow on `pull_request` + `workflow_dispatch` → A4 ✓ · golden fixtures explicitly out of scope ✓
- #27 local gitignored ledger → B1 (path, slug, self-heal) ✓ · 2-gate write scope → B2 ✓ · always-`ask` specific-reason hook → B3 ✓ · verdict tokens (`PASS`/`SHIP`) → B1 status + B2 record ✓ · jq graceful degradation → B1/B3 ✓
- Open plumbing question → resolved (bin/ PATH for commands, `CLAUDE_PLUGIN_ROOT` for hook) ✓

**Placeholder scan:** No TBD/TODO; every code step shows full file content; every run step states expected output.

**Type/contract consistency:** CLI contract `gate-ledger record --gate <g> --verdict <v>` / `gate-ledger status` is identical across B1 (impl + tests), B2 (callers), and B3 (hook). Python `find_broken(root)` and `validate(data)` signatures match between impl and tests. Ledger JSON shape (`.branch`, `.gates.<g>.{verdict,sha,ranAt}`) is identical in B1 impl, B1 tests, and B3 status reads. Verdict tokens (`PASS`, `SHIP`, `FIX AND RE-AUDIT`) consistent across record callers, status logic, and tests.
