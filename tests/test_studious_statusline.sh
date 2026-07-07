#!/usr/bin/env bash
# Integration tests for bin/studious-statusline and bin/studious-statusline-install.
# Requires git + jq.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RENDER="$ROOT/bin/studious-statusline"
# shellcheck disable=SC2034
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
# shellcheck disable=SC2329
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

# --- render refuses to replay a git-tracked prev-command file (security) ---
d3t=$(sandbox)
mkdir -p "$d3t/.studious"
printf 'echo "[Opus] some-dir"' > "$d3t/.studious/statusline-prev-command"
( cd "$d3t" && git add .studious/statusline-prev-command && git commit -q -m "track it" )
out=$(json_input "$d3t" | "$RENDER")
check "render does not replay a git-tracked prev-command file" "" "$out"

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

# --- install wraps an existing project-level (personal, local) statusLine ---
d7=$(sandbox)
fakehome7=$(mktemp -d); mkdir -p "$fakehome7/.claude"
mkdir -p "$d7/.claude"
printf '{"statusLine":{"type":"command","command":"echo mine"}}' > "$d7/.claude/settings.local.json"
out=$(cd "$d7" && HOME="$fakehome7" "$INSTALL")
contains "install reports wrapping an existing statusLine" "wrapped your existing statusLine" "$out"
check "install saves the previous command" "echo mine" "$(cat "$d7/.studious/statusline-prev-command")"

# --- install ignores a checked-in, shared .claude/settings.json (security) ---
d7s=$(sandbox)
fakehome7s=$(mktemp -d); mkdir -p "$fakehome7s/.claude"
mkdir -p "$d7s/.claude"
printf '{"statusLine":{"type":"command","command":"echo attacker-controlled"}}' > "$d7s/.claude/settings.json"
out=$(cd "$d7s" && HOME="$fakehome7s" "$INSTALL")
contains "install ignores a shared, checked-in settings.json statusLine" "no previous statusLine found" "$out"
check "install does not capture the checked-in statusLine command" "" "$(cat "$d7s/.studious/statusline-prev-command")"

# --- install warns (but does not mutate the git index) when the prev-command file is already tracked ---
d7u=$(sandbox)
fakehome7u=$(mktemp -d); mkdir -p "$fakehome7u/.claude"
mkdir -p "$d7u/.studious"
printf 'echo stale' > "$d7u/.studious/statusline-prev-command"
( cd "$d7u" && git add .studious/statusline-prev-command && git commit -q -m "pre-existing tracked file" )
stderr7u=$(cd "$d7u" && HOME="$fakehome7u" "$INSTALL" 2>&1 1>/dev/null)
contains "install warns about an already-tracked prev-command file" "is tracked in git and will be ignored" "$stderr7u"
tracked7u=$(cd "$d7u" && git ls-files -- .studious/statusline-prev-command)
contains "install does not touch the git index (still tracked)" "statusline-prev-command" "$tracked7u"

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
printf '{"statusLine":{"type":"command","command":"echo mine"}}' > "$d10/.claude/settings.local.json"
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

# --- the installed SNIPPET's own fallback branch enforces the same git-tracked-file
# guard as bin/studious-statusline (locks the two authorship sites in sync — a future
# edit that desyncs them fails here, not silently) ---
d13=$(sandbox)
fakehome13=$(mktemp -d); mkdir -p "$fakehome13/.claude"
( cd "$d13" && HOME="$fakehome13" "$INSTALL" >/dev/null )
snippet13=$(jq -r '.statusLine.command' "$d13/.claude/settings.local.json")

printf 'echo untracked-ok' > "$d13/.studious/statusline-prev-command"
out13=$(cd "$d13" && HOME="$fakehome13" bash -c "$snippet13")
check "SNIPPET fallback replays an untracked prev-command" "untracked-ok" "$out13"

printf 'echo TRACKED-SHOULD-NOT-RUN' > "$d13/.studious/statusline-prev-command"
# -f: by this point install has already gitignored .studious/, so this
# simulates a file that was committed despite (or before) that rule existing.
( cd "$d13" && git add -f .studious/statusline-prev-command && git commit -q -m "track it" )
out13b=$(cd "$d13" && HOME="$fakehome13" bash -c "$snippet13")
check "SNIPPET fallback refuses a tracked prev-command" "" "$out13b"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all studious-statusline tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
