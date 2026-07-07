# Install-statusline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/install-statusline`, an optional per-project installer that wires a terse gate-status segment (`audit✓ acceptance—`) into the user's Claude Code statusline without touching global config or clobbering an existing statusline command.

**Architecture:** Three new pieces layered on the existing `bin/gate-ledger` state store: (1) a `gate-ledger statusline` subcommand that renders the terse segment, (2) `bin/studious-statusline`, a render wrapper invoked on every statusline tick that replays a saved previous command and appends the segment, (3) `bin/studious-statusline-install`, a one-shot tool that detects/saves the previous command and wires (or unwires) `.claude/settings.local.json`. `commands/install-statusline.md` is a thin prompt that just invokes tool (3).

**Tech Stack:** Bash, `jq`, `git` — same stack as the existing `bin/gate-ledger`. No new languages or dependencies.

## Global Constraints

- Never hand-edit `.claude-plugin/plugin.json`'s version — semantic-release owns it.
- Match `bin/gate-ledger`'s existing bash style: `set -uo pipefail`, a `have()` helper for tool-presence checks, `local var; var=$(...)` (never `local var=$(...)` — masks the command's exit code), atomic writes via `mktemp` + `mv`.
- Symbols: `✓` (U+2713) pass-at-HEAD, `⚠` (U+26A0) stale-or-non-passing, `—` (U+2014 em dash) never-ran. These are literal UTF-8 characters in the source, not escape sequences — the repo already carries UTF-8 (em dashes appear throughout `bin/gate-ledger`'s comments).
- New command frontmatter uses only `description` (+ `argument-hint` when the command takes an argument) and `allowed-tools` — no `name` or `model` field, matching every existing file in `commands/`.
- `shellcheck 0.11.0` and `markdownlint-cli2 0.23.0` (the pinned CI versions) must pass on every touched file.
- Commands invoke plugin-shipped executables by bare name (e.g. `studious-statusline-install`), never via `${CLAUDE_PLUGIN_ROOT}/bin/...` — that variable does not expand in command markdown bodies (see `commands/work-on.md` and the `#85` fix already in this repo).

---

### Task 1: `gate-ledger statusline` subcommand

**Files:**
- Modify: `bin/gate-ledger` (add `cmd_statusline`, add dispatch case, update usage string)
- Modify: `tests/test_gate_ledger.sh` (add statusline test section)

**Interfaces:**
- Produces: `gate-ledger statusline` — no arguments. Prints one line, `"<gate><sym> <gate><sym>"` (e.g. `audit✓ acceptance—`), or nothing, to stdout. Always exits 0. This is what `bin/studious-statusline` (Task 2) shells out to.

- [ ] **Step 1: Write the failing tests**

Open `tests/test_gate_ledger.sh` and insert this block immediately after the existing `# --- status: no ledger -> empty (hook uses default) ---` section (i.e. right after the line `check "status empty when no ledger" "" "$out"` and its blank line, before the `# --- hook surfaces the ledger reason and always asks ---` comment):

```bash
# --- statusline: silent when the project has never used the gate ledger ---
dsl0=$(sandbox)
out=$(cd "$dsl0" && "$LEDGER" statusline)
check "statusline empty when ledger dir does not exist" "" "$out"

# --- statusline: ledger dir exists (another branch used it) but not this branch ---
dsl1=$(sandbox)
( cd "$dsl1" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl1" && git checkout -q -b feat/other )
out=$(cd "$dsl1" && "$LEDGER" statusline)
check "statusline shows both never-ran for a branch with no ledger file" "audit— acceptance—" "$out"

# --- statusline: both gates pass at HEAD ---
dsl2=$(sandbox)
( cd "$dsl2" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl2" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$dsl2" && "$LEDGER" statusline)
check "statusline shows both passing" "audit✓ acceptance✓" "$out"

# --- statusline: gate never ran shows the dash symbol ---
dsl3=$(sandbox)
( cd "$dsl3" && "$LEDGER" record --gate audit --verdict PASS )
out=$(cd "$dsl3" && "$LEDGER" statusline)
check "statusline shows never-ran acceptance alongside a passing audit" "audit✓ acceptance—" "$out"

# --- statusline: stale sha shows the warning symbol ---
dsl4=$(sandbox)
( cd "$dsl4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dsl4" && git commit -q --allow-empty -m more )
out=$(cd "$dsl4" && "$LEDGER" statusline)
check "statusline flags a stale gate with the warning symbol" "audit⚠ acceptance⚠" "$out"

# --- statusline: non-passing verdict at HEAD shows the warning symbol ---
dsl5=$(sandbox)
( cd "$dsl5" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
( cd "$dsl5" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$dsl5" && "$LEDGER" statusline)
check "statusline flags a non-passing verdict with the warning symbol" "audit⚠ acceptance✓" "$out"

# --- statusline: branch-slug collision treated as never-ran, not a false pass ---
dsl6=$(sandbox)
( cd "$dsl6" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl6" && "$LEDGER" record --gate acceptance --verdict SHIP )
f6="$dsl6/.studious/gates/feat-foo.json"
tmp6=$(mktemp)
jq '.branch = "feat-foo"' "$f6" > "$tmp6" && mv "$tmp6" "$f6"
out=$(cd "$dsl6" && "$LEDGER" statusline)
check "statusline treats a branch-slug collision as never-ran" "audit— acceptance—" "$out"

# --- statusline: silent when jq is unavailable ---
dsl7=$(sandbox)
( cd "$dsl7" && "$LEDGER" record --gate audit --verdict PASS )
fakebin_sl=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat sed; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$fakebin_sl/$tool"
done
out=$(cd "$dsl7" && PATH="$fakebin_sl" "$LEDGER" statusline)
check "statusline empty when jq is unavailable" "" "$out"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash tests/test_gate_ledger.sh 2>&1 | grep -A2 statusline`

Expected: every `statusline` check reports `FAIL`, with actual output like `gate-ledger: unknown arg` or similar — because the `statusline` subcommand doesn't exist yet (the dispatch `case` falls through to `usage`, which currently prints to stderr and exits 2, and `check` receives whatever came through the command substitution — the point is these currently fail, not that they fail with one specific message).

- [ ] **Step 3: Implement `cmd_statusline`**

In `bin/gate-ledger`, insert this function immediately after `cmd_status` (i.e. right after its closing `}` on the line before `cmd_gate_get() {`):

```bash
cmd_statusline() {
  # Terse, symbol-only rendering for the Claude Code statusline (see
  # bin/studious-statusline). Distinct from cmd_status's prose: stays silent
  # unless this project has used the gate ledger at all (a ledger dir exists).
  if ! have jq || ! have git; then return 0; fi
  local dir; dir=$(ledger_dir)
  [ -d "$dir" ] || return 0
  local file; file="$dir/$(branch_slug).json"

  local head cur_branch stored_branch usable
  head=$(head_sha)
  cur_branch=$(branch_name)
  usable=1
  if [ -f "$file" ]; then
    stored_branch=$(jq -r '.branch // empty' "$file")
    [ "$stored_branch" = "$cur_branch" ] || usable=0
  else
    usable=0
  fi

  local gates=("audit:PASS" "acceptance:SHIP")
  local parts=()
  local gate pass v s entry sym
  for entry in "${gates[@]}"; do
    gate="${entry%%:*}"
    pass="${entry##*:}"
    sym="—"
    if [ "$usable" -eq 1 ]; then
      v=$(jq -r --arg g "$gate" '.gates[$g].verdict // empty' "$file")
      if [ -n "$v" ]; then
        s=$(jq -r --arg g "$gate" '.gates[$g].sha // empty' "$file")
        if [ "$s" = "$head" ] && [ "$v" = "$pass" ]; then
          sym="✓"
        else
          sym="⚠"
        fi
      fi
    fi
    parts+=("${gate}${sym}")
  done

  printf '%s %s' "${parts[0]}" "${parts[1]}"
}
```

Then update the dispatch `case` block at the bottom of the file — change:

```bash
case "${1:-}" in
  record)    shift; cmd_record "$@" ;;
  status)    shift; cmd_status "$@" ;;
  gate-get)  shift; cmd_gate_get "$@" ;;
  work-set)  shift; cmd_work_set "$@" ;;
  work-log)  shift; cmd_work_log "$@" ;;
  work-get)  shift; cmd_work_get "$@" ;;
  work-list) shift; cmd_work_list "$@" ;;
  gc)        shift; cmd_gc "$@" ;;
  *) echo "usage: gate-ledger {record --gate G --verdict V | status | gate-get [--branch B] | work-set --slug S [--title T] [--source SRC] [--branch B] [--design-doc P] [--phase PH] | work-log --slug S --step ST --outcome O [--phase PH] | work-get --slug S | work-list | gc}" >&2; exit 2 ;;
esac
```

to:

```bash
case "${1:-}" in
  record)     shift; cmd_record "$@" ;;
  status)     shift; cmd_status "$@" ;;
  statusline) shift; cmd_statusline "$@" ;;
  gate-get)   shift; cmd_gate_get "$@" ;;
  work-set)   shift; cmd_work_set "$@" ;;
  work-log)   shift; cmd_work_log "$@" ;;
  work-get)   shift; cmd_work_get "$@" ;;
  work-list)  shift; cmd_work_list "$@" ;;
  gc)         shift; cmd_gc "$@" ;;
  *) echo "usage: gate-ledger {record --gate G --verdict V | status | statusline | gate-get [--branch B] | work-set --slug S [--title T] [--source SRC] [--branch B] [--design-doc P] [--phase PH] | work-log --slug S --step ST --outcome O [--phase PH] | work-get --slug S | work-list | gc}" >&2; exit 2 ;;
esac
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash tests/test_gate_ledger.sh`

Expected: `all gate-ledger tests passed` and exit code 0. Every `statusline`-prefixed check line reads `ok`.

- [ ] **Step 5: Shellcheck**

Run: `shellcheck bin/gate-ledger`

Expected: no output, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add bin/gate-ledger tests/test_gate_ledger.sh
git commit -m "feat: add gate-ledger statusline subcommand"
```

---

### Task 2: `bin/studious-statusline` render wrapper

**Files:**
- Create: `bin/studious-statusline`
- Create: `tests/test_studious_statusline.sh`
- Modify: `.github/workflows/ci.yml` (wire the new test file into the `ledger` job and the `shellcheck` job)

**Interfaces:**
- Consumes: `gate-ledger statusline` (Task 1) — resolved as `"$(dirname "$0")/gate-ledger"` (sibling file in the same installed `bin/` dir, no PATH dependency).
- Consumes: `<repo-root>/.studious/statusline-prev-command` — a plain-text file containing zero or one shell command (no trailing requirements; empty/missing file means "no previous command").
- Produces: `bin/studious-statusline` — reads Claude Code's statusline JSON on stdin, writes the composed line to stdout. This is what Task 3's installed snippet `exec`s.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_studious_statusline.sh`:

```bash
#!/usr/bin/env bash
# Integration tests for bin/studious-statusline and bin/studious-statusline-install.
# Requires git + jq.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RENDER="$ROOT/bin/studious-statusline"
INSTALL="$ROOT/bin/studious-statusline-install"
LEDGER="$ROOT/bin/gate-ledger"
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

json_input() { # dir -> stdin JSON the way Claude Code would send it
  printf '{"cwd":"%s","workspace":{"current_dir":"%s"}}' "$1" "$1"
}

# ============================================================
# bin/studious-statusline (render wrapper)
# ============================================================

# --- no previous command, no gate ledger: empty output ---
d1=$(sandbox)
out=$(json_input "$d1" | "$RENDER")
check "render is empty with nothing to show" "" "$out"

# --- gate segment alone when there's no previous command ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d2" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(json_input "$d2" | "$RENDER")
check "render shows the gate segment alone" "audit✓ acceptance✓" "$out"

# --- previous command output passes through unchanged when there's no gate data ---
d3=$(sandbox)
mkdir -p "$d3/.studious"
printf 'echo "[Opus] some-dir"' > "$d3/.studious/statusline-prev-command"
out=$(json_input "$d3" | "$RENDER")
check "render passes through the previous command with no gate segment" "[Opus] some-dir" "$out"

# --- previous command output and gate segment are composed with a separator ---
d4=$(sandbox)
mkdir -p "$d4/.studious"
printf 'echo "[Opus] some-dir"' > "$d4/.studious/statusline-prev-command"
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(json_input "$d4" | "$RENDER")
check "render composes the previous command output with the gate segment" \
  "[Opus] some-dir | audit✓ acceptance✓" "$out"

# --- the previous command receives the same stdin JSON ---
d5=$(sandbox)
mkdir -p "$d5/.studious"
printf 'jq -r .cwd' > "$d5/.studious/statusline-prev-command"
out=$(json_input "$d5" | "$RENDER")
check "render's previous command sees the same stdin JSON" "$d5" "$out"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all studious-statusline tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash tests/test_studious_statusline.sh`

Expected: every check `FAIL`s (or the script errors immediately) because `bin/studious-statusline` doesn't exist yet.

- [ ] **Step 3: Implement `bin/studious-statusline`**

Create `bin/studious-statusline`:

```bash
#!/usr/bin/env bash
# studious-statusline — statusline renderer installed by studious-statusline-install.
# Replays whatever statusLine command was configured before install (saved to
# .studious/statusline-prev-command), then appends the gate-ledger status segment.
set -uo pipefail

input=$(cat)

script_dir="$(cd "$(dirname "$0")" && pwd)"
gate_ledger="$script_dir/gate-ledger"

cwd=$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty' 2>/dev/null)
[ -n "$cwd" ] && [ -d "$cwd" ] && cd "$cwd" 2>/dev/null

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
prev_file="$repo_root/.studious/statusline-prev-command"

prev_out=""
if [ -s "$prev_file" ]; then
  prev_out=$(printf '%s' "$input" | bash -c "$(cat "$prev_file")" 2>/dev/null)
fi

gate_seg=""
if [ -x "$gate_ledger" ]; then
  gate_seg=$("$gate_ledger" statusline 2>/dev/null)
fi

if [ -n "$prev_out" ] && [ -n "$gate_seg" ]; then
  printf '%s | %s\n' "$prev_out" "$gate_seg"
elif [ -n "$prev_out" ]; then
  printf '%s\n' "$prev_out"
else
  printf '%s\n' "$gate_seg"
fi
```

Make it executable:

```bash
chmod +x bin/studious-statusline
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash tests/test_studious_statusline.sh`

Expected: `ok` for all five checks listed so far, `all studious-statusline tests passed`, exit 0. (Task 3 appends more checks to this same file — it's expected to still say "all ... passed" after that task, just with more `ok` lines.)

- [ ] **Step 5: Wire CI**

In `.github/workflows/ci.yml`, under the `ledger` job, change:

```yaml
      - name: Gate-ledger integration tests
        run: bash tests/test_gate_ledger.sh
```

to:

```yaml
      - name: Gate-ledger integration tests
        run: bash tests/test_gate_ledger.sh
      - name: Studious-statusline integration tests
        run: bash tests/test_studious_statusline.sh
```

Under the `shellcheck` job, change:

```yaml
      - run: shellcheck bin/gate-ledger hooks/gate-reminder.sh tests/test_gate_ledger.sh scripts/install-dev.sh
```

to:

```yaml
      - run: shellcheck bin/gate-ledger bin/studious-statusline hooks/gate-reminder.sh tests/test_gate_ledger.sh tests/test_studious_statusline.sh scripts/install-dev.sh
```

- [ ] **Step 6: Shellcheck locally**

Run: `shellcheck bin/studious-statusline tests/test_studious_statusline.sh`

Expected: no output, exit code 0.

- [ ] **Step 7: Commit**

```bash
git add bin/studious-statusline tests/test_studious_statusline.sh .github/workflows/ci.yml
git commit -m "feat: add studious-statusline render wrapper"
```

---

### Task 3: `bin/studious-statusline-install` (install / remove)

**Files:**
- Create: `bin/studious-statusline-install`
- Modify: `tests/test_studious_statusline.sh` (append install/remove test section)

**Interfaces:**
- Produces: `<repo-root>/.studious/statusline-prev-command` — consumed by Task 2's `bin/studious-statusline`.
- Produces: `<repo-root>/.claude/settings.local.json`'s `.statusLine.command` — a fixed, self-resolving snippet string (glob for `~/.claude/plugins/cache/*/studious/*/bin`, newest by version sort, `exec` its `studious-statusline`; fall back to replaying `.studious/statusline-prev-command` if not found). This exact snippet is what Task 4's command tells the user to invoke by running this tool.
- CLI: `studious-statusline-install` (install, default) / `studious-statusline-install remove` (uninstall).

- [ ] **Step 1: Write the failing tests**

Append this section to the end of `tests/test_studious_statusline.sh`, replacing the final summary block (`echo "----"` / `if [ "$fails" -eq 0 ]...`) — i.e. insert the new section *before* that block, then repeat the (unchanged) summary block after it:

```bash
# ============================================================
# bin/studious-statusline-install (install / remove)
# ============================================================

# --- fresh install with no previous statusLine anywhere ---
d6=$(sandbox)
fakehome6=$(mktemp -d); mkdir -p "$fakehome6/.claude"
out=$(cd "$d6" && HOME="$fakehome6" "$INSTALL")
contains "install reports no previous statusLine" "no previous statusLine found" "$out"
settings6="$d6/.claude/settings.local.json"
check "install creates settings.local.json" "yes" "$([ -f "$settings6" ] && echo yes || echo no)"
contains "install wires the self-resolving snippet" "studious-statusline" "$(jq -r '.statusLine.command' "$settings6")"
check "install writes an empty previous-command file" "" "$(cat "$d6/.studious/statusline-prev-command")"
contains "install self-heals .gitignore for .studious/" ".studious/" "$(cat "$d6/.gitignore")"
contains "install self-heals .gitignore for settings.local.json" ".claude/settings.local.json" "$(cat "$d6/.gitignore")"

# --- install wraps an existing project-level statusLine ---
d7=$(sandbox)
fakehome7=$(mktemp -d); mkdir -p "$fakehome7/.claude"
mkdir -p "$d7/.claude"
printf '{"statusLine":{"type":"command","command":"echo mine"}}' > "$d7/.claude/settings.json"
out=$(cd "$d7" && HOME="$fakehome7" "$INSTALL")
contains "install reports wrapping an existing statusLine" "wrapped your existing statusLine" "$out"
check "install saves the previous command" "echo mine" "$(cat "$d7/.studious/statusline-prev-command")"

# --- install falls back to the user's global statusLine when no project one exists ---
d8=$(sandbox)
fakehome8=$(mktemp -d); mkdir -p "$fakehome8/.claude"
printf '{"statusLine":{"type":"command","command":"echo global"}}' > "$fakehome8/.claude/settings.json"
out=$(cd "$d8" && HOME="$fakehome8" "$INSTALL")
check "install saves the user-level previous command" "echo global" "$(cat "$d8/.studious/statusline-prev-command")"

# --- re-running install is idempotent ---
d9=$(sandbox)
fakehome9=$(mktemp -d); mkdir -p "$fakehome9/.claude"
( cd "$d9" && HOME="$fakehome9" "$INSTALL" >/dev/null )
saved9=$(cat "$d9/.studious/statusline-prev-command")
out=$(cd "$d9" && HOME="$fakehome9" "$INSTALL")
contains "second install reports already installed" "already installed" "$out"
check "second install does not touch the saved previous command" "$saved9" "$(cat "$d9/.studious/statusline-prev-command")"

# --- remove restores a previously wrapped statusLine ---
d10=$(sandbox)
fakehome10=$(mktemp -d); mkdir -p "$fakehome10/.claude"
mkdir -p "$d10/.claude"
printf '{"statusLine":{"type":"command","command":"echo mine"}}' > "$d10/.claude/settings.json"
( cd "$d10" && HOME="$fakehome10" "$INSTALL" >/dev/null )
out=$(cd "$d10" && HOME="$fakehome10" "$INSTALL" remove)
contains "remove reports restoring the previous statusLine" "restored your previous statusLine" "$out"
check "remove restores the previous command" "echo mine" "$(jq -r '.statusLine.command' "$d10/.claude/settings.local.json")"
check "remove deletes the saved previous-command file" "no" "$([ -f "$d10/.studious/statusline-prev-command" ] && echo yes || echo no)"

# --- remove deletes the statusLine key entirely when there was no previous command ---
d11=$(sandbox)
fakehome11=$(mktemp -d); mkdir -p "$fakehome11/.claude"
( cd "$d11" && HOME="$fakehome11" "$INSTALL" >/dev/null )
out=$(cd "$d11" && HOME="$fakehome11" "$INSTALL" remove)
contains "remove reports no previous statusLine to restore" "no previous statusLine to restore" "$out"
check "remove deletes the statusLine key" "null" "$(jq -r '.statusLine // "null"' "$d11/.claude/settings.local.json")"

# --- remove on a project that was never installed is a no-op ---
d12=$(sandbox)
fakehome12=$(mktemp -d); mkdir -p "$fakehome12/.claude"
out=$(cd "$d12" && HOME="$fakehome12" "$INSTALL" remove)
contains "remove on a never-installed project reports nothing to remove" "not installed, nothing to remove" "$out"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash tests/test_studious_statusline.sh`

Expected: the five checks from Task 2 still pass (`ok`), but every new `install`/`remove` check fails or the script aborts, because `bin/studious-statusline-install` doesn't exist yet.

- [ ] **Step 3: Implement `bin/studious-statusline-install`**

Create `bin/studious-statusline-install`:

```bash
#!/usr/bin/env bash
# studious-statusline-install — wires (or unwires) the gate-status segment into
# this project's Claude Code statusline. Installs to .claude/settings.local.json
# only — gitignored, project-scoped, never touches the user's global settings or
# a shared, checked-in .claude/settings.json.
set -uo pipefail

have() { command -v "$1" >/dev/null 2>&1; }

if ! have jq || ! have git; then
  echo "studious-statusline-install: jq and git are required" >&2
  exit 1
fi

root=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "studious-statusline-install: not a git repository" >&2
  exit 1
}

settings="$root/.claude/settings.local.json"
prev_file="$root/.studious/statusline-prev-command"

# The exact command wired into settings.local.json. Self-resolving: globs for
# the newest installed studious plugin's bin/ dir at *render* time (not baked
# in here) because ${CLAUDE_PLUGIN_ROOT} does not expand in statusLine.command
# and the plugin cache path is versioned, changing on every `/plugin update`.
# Falls back to replaying the saved previous command if the plugin isn't found
# (disabled/removed), so the statusline never goes blank.
SNIPPET='r=$(git rev-parse --show-toplevel 2>/dev/null || pwd); p=$(ls -d "$HOME/.claude/plugins/cache"/*/studious/*/bin 2>/dev/null | sort -V | tail -1); if [ -n "$p" ] && [ -x "$p/studious-statusline" ]; then exec "$p/studious-statusline"; elif [ -s "$r/.studious/statusline-prev-command" ]; then bash -c "$(cat "$r/.studious/statusline-prev-command")"; fi'

ensure_gitignore_line() { # pattern, message
  local gi="$root/.gitignore"
  if [ ! -f "$gi" ] || ! grep -qxF "$1" "$gi" 2>/dev/null; then
    printf '\n# %s\n%s\n' "$2" "$1" >> "$gi"
  fi
}

current_statusline_command() {
  local f
  for f in "$root/.claude/settings.local.json" "$root/.claude/settings.json" "$HOME/.claude/settings.json"; do
    [ -f "$f" ] || continue
    local c; c=$(jq -r '.statusLine.command // empty' "$f" 2>/dev/null)
    if [ -n "$c" ]; then
      printf '%s' "$c"
      return 0
    fi
  done
  return 0
}

write_settings_statusline() { # command string
  mkdir -p "$root/.claude"
  local existing="{}"
  [ -f "$settings" ] && existing=$(cat "$settings")
  local tmp; tmp=$(mktemp "$root/.claude/.tmp.XXXXXX")
  printf '%s' "$existing" | jq --arg cmd "$1" \
    '.statusLine = {type: "command", command: $cmd}' > "$tmp" && mv "$tmp" "$settings"
}

cmd_install() {
  if [ -f "$settings" ]; then
    local existing_cmd; existing_cmd=$(jq -r '.statusLine.command // empty' "$settings" 2>/dev/null)
    case "$existing_cmd" in
      *studious-statusline*)
        echo "studious-statusline-install: already installed"
        exit 0
        ;;
    esac
  fi

  local prev; prev=$(current_statusline_command)

  mkdir -p "$root/.studious"
  printf '%s' "$prev" > "$prev_file"
  ensure_gitignore_line ".studious/" "Studious local gate ledger (do not commit)"

  write_settings_statusline "$SNIPPET"
  ensure_gitignore_line ".claude/settings.local.json" "Claude Code local settings (do not commit)"

  if [ -n "$prev" ]; then
    echo "studious-statusline-install: wrapped your existing statusLine and added the gate segment"
  else
    echo "studious-statusline-install: installed the gate segment (no previous statusLine found)"
  fi
}

cmd_remove() {
  local existing_cmd=""
  [ -f "$settings" ] && existing_cmd=$(jq -r '.statusLine.command // empty' "$settings" 2>/dev/null)
  case "$existing_cmd" in
    *studious-statusline*) ;;
    *)
      echo "studious-statusline-install: not installed, nothing to remove"
      exit 0
      ;;
  esac

  local prev=""
  [ -f "$prev_file" ] && prev=$(cat "$prev_file")

  local tmp; tmp=$(mktemp "$root/.claude/.tmp.XXXXXX")
  if [ -n "$prev" ]; then
    jq --arg cmd "$prev" '.statusLine.command = $cmd' "$settings" > "$tmp" && mv "$tmp" "$settings"
  else
    jq 'del(.statusLine)' "$settings" > "$tmp" && mv "$tmp" "$settings"
  fi
  rm -f "$prev_file"

  if [ -n "$prev" ]; then
    echo "studious-statusline-install: removed, restored your previous statusLine"
  else
    echo "studious-statusline-install: removed, no previous statusLine to restore"
  fi
}

case "${1:-}" in
  remove) cmd_remove ;;
  "")     cmd_install ;;
  *)      echo "usage: studious-statusline-install [remove]" >&2; exit 2 ;;
esac
```

Make it executable:

```bash
chmod +x bin/studious-statusline-install
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash tests/test_studious_statusline.sh`

Expected: `all studious-statusline tests passed`, exit 0, every check `ok`.

- [ ] **Step 5: Shellcheck**

Run: `shellcheck bin/studious-statusline-install`

Expected: no output, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add bin/studious-statusline-install tests/test_studious_statusline.sh
git commit -m "feat: add studious-statusline-install"
```

---

### Task 4: `/install-statusline` command + docs

**Files:**
- Create: `commands/install-statusline.md`
- Modify: `CLAUDE.md` (recommend-only invariant — new exception)
- Modify: `README.md` (mention the command)

**Interfaces:**
- Consumes: `studious-statusline-install` (Task 3), invoked by bare name via the Bash tool (plugin `bin/` is on the Bash tool's `PATH` while the plugin is enabled).

- [ ] **Step 1: Create the command**

Create `commands/install-statusline.md`:

```markdown
---
description: Install an optional statusline segment showing gate status (audit/acceptance) for this project
argument-hint: "[remove] (omit to install)"
allowed-tools: Bash
---

# Install statusline gate segment

Wire (or remove) a terse gate-status segment — `audit✓ acceptance—` — into this
project's Claude Code statusline. Optional and project-scoped: it writes only to
`.claude/settings.local.json` (gitignored, personal), never to your global
`~/.claude/settings.json` or a shared, checked-in `.claude/settings.json`. If you
already have a statusline command configured, it's preserved — the gate segment
is appended after it, nothing is replaced.

Run:

```bash
studious-statusline-install
```

Or, to remove it and restore whatever statusline command was configured before
(when `$ARGUMENTS` is `remove`):

```bash
studious-statusline-install remove
```

Report the tool's own output to the user verbatim — it already states what
happened (installed fresh, wrapped an existing command, already installed,
restored, or nothing to remove).

If `studious-statusline-install` is not found (the plugin's `bin/` isn't on
`PATH` in this environment), tell the user the install couldn't run — do not
silently skip.
```

- [ ] **Step 2: Update CLAUDE.md's recommend-only invariant**

In `CLAUDE.md`, find this bullet under "Key invariants when adding or changing prompts":

```markdown
- **Recommend-only.** Commands report; they never modify external state (issues, PRs, files outside `docs/studious/` in the consuming project). The sole exception: gate commands record verdicts, and `/work-on` records flow position, to local, gitignored `.studious/` state.
```

Replace it with:

```markdown
- **Recommend-only.** Commands report; they never modify external state (issues, PRs, files outside `docs/studious/` in the consuming project). Two exceptions: gate commands record verdicts, and `/work-on` records flow position, to local, gitignored `.studious/` state; `/install-statusline` writes to `.claude/settings.local.json` (Claude Code's own config, gitignored but outside `.studious/`) to wire its optional statusline segment.
```

- [ ] **Step 3: Mention the command in README.md**

In `README.md`, find this paragraph (in the "Building a feature" section):

```markdown
When you run `gh pr create`, a PR-time hook reads the gate verdicts recorded to a local `.studious/` ledger (which Studious adds to your `.gitignore` on first run) and gives a specific reminder — naming gates that never ran, ran on an older commit, or didn't pass — while staying non-blocking.
```

Add this paragraph immediately after it:

```markdown
Optionally, `/install-statusline` wires the same gate state into your Claude Code statusline as a terse segment (`audit✓ acceptance—`) so it's visible without asking. It's per-project (writes only to a gitignored `.claude/settings.local.json`, never your global config) and preserves whatever statusline command you already have — `/install-statusline remove` reverses it.
```

- [ ] **Step 4: Lint and link-check**

Run: `npx -y markdownlint-cli2@0.23.0`

Expected: no errors reported for `commands/install-statusline.md`, `CLAUDE.md`, or `README.md`.

Run: `uv run --no-project python scripts/check_references.py`

Expected: exit code 0 (the new command file references no `@agent-*` or `reference/*.md` paths, so nothing new to check).

- [ ] **Step 5: Commit**

```bash
git add commands/install-statusline.md CLAUDE.md README.md
git commit -m "docs: add /install-statusline command and doc updates"
```

---

### Task 5: Full local check suite

**Files:** none (verification only)

- [ ] **Step 1: Run every CI-equivalent check locally, in order**

```bash
npx -y markdownlint-cli2@0.23.0
uv run --no-project python scripts/check_references.py
uv run --no-project python scripts/validate_plugin.py
uv run --no-project --with pytest pytest tests/python -v
bash tests/test_gate_ledger.sh
bash tests/test_studious_statusline.sh
shellcheck bin/gate-ledger bin/studious-statusline bin/studious-statusline-install hooks/gate-reminder.sh tests/test_gate_ledger.sh tests/test_studious_statusline.sh scripts/install-dev.sh
```

Expected: every command exits 0, with `all gate-ledger tests passed` and `all studious-statusline tests passed` in the two bash test outputs.

- [ ] **Step 2: Manual smoke test in a real sandbox**

```bash
d=$(mktemp -d) && cd "$d" && git init -q && git commit -q --allow-empty -m init
"$OLDPWD/bin/gate-ledger" record --gate audit --verdict PASS
HOME="$(mktemp -d)" "$OLDPWD/bin/studious-statusline-install"
cat .claude/settings.local.json
printf '{"cwd":"%s","workspace":{"current_dir":"%s"}}' "$d" "$d" | "$OLDPWD/bin/studious-statusline"
cd "$OLDPWD"
```

Expected: `.claude/settings.local.json` contains a `statusLine.command` mentioning `studious-statusline`, and the final piped command prints `audit✓ acceptance—` (acceptance never ran).

- [ ] **Step 3: Commit if anything was fixed**

If any check above required a fix, stage and commit it with a message describing what was wrong, before moving on.
