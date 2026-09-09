#!/usr/bin/env bash
# Integration tests for hooks/session-start.sh (the SessionStart hook wired to
# `startup|resume` in hooks.json). Requires git + jq.
#
# Feeds the hook crafted JSON payloads matching Claude Code's documented
# SessionStart input shape (`{session_id, cwd, permission_mode, reason}`),
# proving the hook's own logic (reason gate, gate-ledger presence check,
# active-count math, most-recent selection) — not that a real session
# delivers this exact payload shape.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER="$ROOT/bin/gate-ledger"
HOOK="$ROOT/hooks/session-start.sh"
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

payload() { # reason -> a SessionStart payload
  jq -nc --arg r "$1" '{session_id: "sess-1", cwd: "/tmp", permission_mode: "default", reason: $r}'
}

run_hook() { # dir, plugin_root (empty string means unset), stdin-json -> stdout captured
  if [ -n "$2" ]; then
    ( cd "$1" && CLAUDE_PLUGIN_ROOT="$2" bash "$HOOK" <<<"$3" )
  else
    ( cd "$1" && bash "$HOOK" <<<"$3" )
  fi
}

# --- no gate-ledger on the resolvable plugin root: silent ---
d=$(sandbox)
out=$(run_hook "$d" "" "$(payload startup)")
check "no CLAUDE_PLUGIN_ROOT: silent" "" "$out"

# --- gate-ledger present, nothing in flight: silent ---
d=$(sandbox)
out=$(run_hook "$d" "$ROOT" "$(payload startup)")
check "nothing in flight: silent" "" "$out"

# --- gate-ledger present, one active work file: emits additionalContext ---
d=$(sandbox)
( cd "$d" && "$LEDGER" work-set --slug demo-feature --title "Demo feature" --branch feat/foo --phase build >/dev/null 2>&1 )
out=$(run_hook "$d" "$ROOT" "$(payload startup)")
check "hookEventName is SessionStart" "SessionStart" "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.hookEventName')"
ctx=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext')
contains "names one active work file" "1 active work file(s)" "$ctx"
contains "names the active slug" "demo-feature" "$ctx"
contains "names the phase" "build" "$ctx"

# --- reason=resume, same ledger: also emits ---
out=$(run_hook "$d" "$ROOT" "$(payload resume)")
contains "resume also surfaces the active work file" "demo-feature" "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext')"

# --- a done work file doesn't count as active ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" work-set --slug finished-feature --title "Finished" --branch feat/foo --phase "done" ) >/dev/null 2>&1
out=$(run_hook "$d2" "$ROOT" "$(payload startup)")
check "a done work file alone: silent" "" "$out"

# --- reason=compact: silent regardless of ledger state ---
out=$(run_hook "$d" "$ROOT" "$(payload compact)")
check "reason=compact: silent even with active work" "" "$out"

# --- reason=clear and reason=fork: silent too ---
out=$(run_hook "$d" "$ROOT" "$(payload clear)")
check "reason=clear: silent" "" "$out"
out=$(run_hook "$d" "$ROOT" "$(payload fork)")
check "reason=fork: silent" "" "$out"

echo
if [ "$fails" -eq 0 ]; then
  echo "all tests passed"
else
  echo "$fails test(s) failed"
  exit 1
fi
