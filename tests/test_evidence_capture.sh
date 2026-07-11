#!/usr/bin/env bash
# Integration tests for hooks/evidence-capture.sh (the PostToolUse/PostToolUseFailure
# hook wired to Bash in hooks.json). Requires git + jq.
#
# What this file does and doesn't prove (reference/evidence-format.md, "Open item:
# origin and /work-through's actual dispatch mechanism" has the full account): every
# test here feeds the hook a crafted JSON payload on stdin, exactly as Claude Code's
# own hooks reference documents PostToolUse/PostToolUseFailure input for Bash — this
# deterministically proves the hook's own logic (armed check, allow-list, exit-code
# derivation per event, digest source, cross-worktree resolution) is correct given
# that input shape. It does NOT prove a real /work-through dispatch actually produces
# an agent_id-bearing payload — no Task tool is available to this suite to dispatch a
# real nested subagent and observe the hook fire from inside it.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER="$ROOT/bin/gate-ledger"
HOOK="$ROOT/hooks/evidence-capture.sh"
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

sandbox() { # create a throwaway git repo, arm it on the given branch, echo its path
  local d branch; d=$(mktemp -d); branch="${1:-feat/foo}"
  git -C "$d" init -q
  git -C "$d" config user.email t@t.t
  git -C "$d" config user.name t
  git -C "$d" commit -q --allow-empty -m init
  git -C "$d" checkout -q -b "$branch"
  printf '%s' "$d"
}

arm() { # dir, branch -> gate-ledger work-set so the hook's armed check finds it
  ( cd "$1" && "$LEDGER" work-set --slug "demo-$(basename "$1")" --branch "$2" --phase build >/dev/null 2>&1 )
}

run_hook() { # dir, stdin-json -> stdout captured
  ( cd "$1" && CLAUDE_PLUGIN_ROOT="$ROOT" bash "$HOOK" <<<"$2" )
}

evidence_file() { printf '%s/.studious/evidence/%s' "$1" "$(printf '%s' "$2" | tr '/' '-').jsonl"; }

posttooluse() { # command -> a PostToolUse (success) payload
  printf '{"hook_event_name":"PostToolUse","tool_input":{"command":"%s"},"tool_response":{"stdout":"ok","stderr":"","interrupted":false,"isImage":false}}' "$1"
}
posttoolusefailure() { # command -> a PostToolUseFailure payload, exit code 1
  printf '{"hook_event_name":"PostToolUseFailure","tool_input":{"command":"%s"},"error":"Command exited with non-zero status code 1","is_interrupt":false}' "$1"
}

# --- unarmed branch: verification command produces no record ---
d1=$(sandbox feat/foo)
run_hook "$d1" "$(posttooluse "pytest tests/")"
check "unarmed branch: no evidence dir at all" "no" "$([ -d "$d1/.studious/evidence" ] && echo yes || echo no)"

# --- armed branch, non-verification command: no record ---
d2=$(sandbox feat/foo); arm "$d2" feat/foo
run_hook "$d2" "$(posttooluse "ls -la")"
check "armed branch, non-verification command: no evidence dir" "no" "$([ -d "$d2/.studious/evidence" ] && echo yes || echo no)"

# --- armed branch, verification command via PostToolUse: PASSED record ---
d3=$(sandbox feat/foo); arm "$d3" feat/foo
run_hook "$d3" "$(posttooluse "pytest tests/")"
f3=$(evidence_file "$d3" feat/foo)
check "PostToolUse success: evidence file created" "yes" "$([ -f "$f3" ] && echo yes || echo no)"
check "PostToolUse success: exitCode 0" "0" "$(jq -r '.exitCode' "$f3")"
check "PostToolUse success: predicate.result PASSED" "PASSED" "$(jq -r '.predicate.result' "$f3")"
check "PostToolUse success: origin interactive (no agent_id in payload)" "interactive" "$(jq -r '.origin' "$f3")"
check "PostToolUse success: capturer is hook" "hook" "$(jq -r '.capturer' "$f3")"
check "PostToolUse success: command captured verbatim" "pytest tests/" "$(jq -r '.command' "$f3")"
contains "PostToolUse success: outputDigest is sha256:<64 hex>" "sha256:" "$(jq -r '.outputDigest' "$f3")"
check "PostToolUse success: digest hex is 64 chars" "64" "$(jq -r '.outputDigest' "$f3" | sed 's/^sha256://' | tr -d '\n' | wc -c | tr -d ' ')"

# --- armed branch, verification command via PostToolUseFailure: FAILED record ---
d4=$(sandbox feat/foo); arm "$d4" feat/foo
run_hook "$d4" "$(posttoolusefailure "pytest tests/")"
f4=$(evidence_file "$d4" feat/foo)
check "PostToolUseFailure: evidence file created" "yes" "$([ -f "$f4" ] && echo yes || echo no)"
check "PostToolUseFailure: exitCode parsed from the error string" "1" "$(jq -r '.exitCode' "$f4")"
check "PostToolUseFailure: predicate.result FAILED" "FAILED" "$(jq -r '.predicate.result' "$f4")"
check "PostToolUseFailure: origin interactive" "interactive" "$(jq -r '.origin' "$f4")"

# --- PostToolUseFailure with an unparseable error (e.g. interrupted/timed out):
# still FAILED, exitCode falls back to the documented 1 sentinel ---
d4b=$(sandbox feat/foo); arm "$d4b" feat/foo
run_hook "$d4b" '{"hook_event_name":"PostToolUseFailure","tool_input":{"command":"pytest tests/"},"error":"Command was interrupted","is_interrupt":true}'
f4b=$(evidence_file "$d4b" feat/foo)
check "PostToolUseFailure unparseable error: still records FAILED" "FAILED" "$(jq -r '.predicate.result' "$f4b")"
check "PostToolUseFailure unparseable error: exitCode sentinel is 1" "1" "$(jq -r '.exitCode' "$f4b")"

# --- agent_id present -> origin subagent, agentType captured ---
d5=$(sandbox feat/foo); arm "$d5" feat/foo
run_hook "$d5" '{"hook_event_name":"PostToolUse","tool_input":{"command":"pytest tests/"},"tool_response":{"stdout":"ok","stderr":"","interrupted":false,"isImage":false},"agent_id":"sub-1","agent_type":"epic-driver:build-worker"}'
f5=$(evidence_file "$d5" feat/foo)
check "agent_id present: origin subagent" "subagent" "$(jq -r '.origin' "$f5")"
check "agent_id present: agentType captured verbatim" "epic-driver:build-worker" "$(jq -r '.agentType' "$f5")"

# --- allow-list: representative verification commands ARE captured ---
for cmd in \
  "pytest tests/" "npx jest" "npx vitest run" "bundle exec rspec" "phpunit" \
  "npx eslint ." "ruff check ." "flake8 ." "shellcheck bin/gate-ledger" "npx -y markdownlint-cli2" \
  "npx tsc --noEmit" "mypy ." "pyright" "make" "go test ./..." "cargo test" "cargo build" \
  "npm test" "npm run test" "npm run build" \
  "bash tests/test_gate_ledger.sh" "uv run --no-project python scripts/check_references.py"
do
  dN=$(sandbox feat/foo); arm "$dN" feat/foo
  run_hook "$dN" "$(posttooluse "$cmd")"
  fN=$(evidence_file "$dN" feat/foo)
  check "allow-list captures: $cmd" "yes" "$([ -f "$fN" ] && echo yes || echo no)"
done

# --- allow-list: representative non-verification / false-positive-guard commands
# are NOT captured ---
for cmd in \
  "ls -la" "pwd" "cd /tmp" "git status" "git checkout -q -b feat/foo" "cmake ." \
  "echo hello" "cat README.md" "git log --oneline"
do
  dN=$(sandbox feat/foo); arm "$dN" feat/foo
  run_hook "$dN" "$(posttooluse "$cmd")"
  fN=$(evidence_file "$dN" feat/foo)
  check "allow-list ignores: $cmd" "no" "$([ -f "$fN" ] && echo yes || echo no)"
done

# --- hook is silent: no stdout on either the capturing or no-op path ---
d6=$(sandbox feat/foo); arm "$d6" feat/foo
out_capture=$(run_hook "$d6" "$(posttooluse "pytest tests/")")
check "hook prints nothing on the capturing path" "" "$out_capture"
d7=$(sandbox feat/foo)
out_noop=$(run_hook "$d7" "$(posttooluse "pytest tests/")")
check "hook prints nothing on the no-op path" "" "$out_noop"

# --- two verification commands in one session append two lines, not overwrite ---
d8=$(sandbox feat/foo); arm "$d8" feat/foo
run_hook "$d8" "$(posttooluse "pytest tests/")"
run_hook "$d8" "$(posttooluse "npx eslint .")"
f8=$(evidence_file "$d8" feat/foo)
check "sequential verification commands append (jsonl grows)" "2" "$(wc -l < "$f8" | tr -d ' ')"
check "second line is independently valid JSON" "yes" "$(sed -n '2p' "$f8" | jq -e . >/dev/null 2>&1 && echo yes || echo no)"

# --- missing jq/git: silent no-op, exit 0, no file ---
d9=$(sandbox feat/foo); arm "$d9" feat/foo
fakebin=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat cut awk sed tr wc sha256sum shasum; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$fakebin/$tool"
done
out9=$(cd "$d9" && PATH="$fakebin" CLAUDE_PLUGIN_ROOT="$ROOT" bash "$HOOK" \
  <<<"$(posttooluse "pytest tests/")" 2>&1; echo "rc=$?")
check "jq unavailable: hook exits 0 with no output" "rc=0" "$out9"
check "jq unavailable: no evidence dir created" "no" "$([ -d "$d9/.studious/evidence" ] && echo yes || echo no)"

# --- CLAUDE_PLUGIN_ROOT missing/unresolved: silent no-op (mirrors gate-reminder.sh) ---
d10=$(sandbox feat/foo); arm "$d10" feat/foo
out10=$(cd "$d10" && bash "$HOOK" <<<"$(posttooluse "pytest tests/")" 2>&1; echo "rc=$?")
check "no CLAUDE_PLUGIN_ROOT: hook exits 0 with no output" "rc=0" "$out10"
check "no CLAUDE_PLUGIN_ROOT: no evidence dir created" "no" "$([ -d "$d10/.studious/evidence" ] && echo yes || echo no)"

# --- async-launched / non-standard tool_response shape (no stdout key): skipped
# rather than mis-recorded as a completed, passing run ---
d11=$(sandbox feat/foo); arm "$d11" feat/foo
run_hook "$d11" '{"hook_event_name":"PostToolUse","tool_input":{"command":"pytest tests/"},"tool_response":{"status":"async_launched","agentId":"x"}}'
check "non-stdout tool_response shape: no evidence file" "no" "$([ -d "$d11/.studious/evidence" ] && echo yes || echo no)"

# --- dispatched-worker-shaped path: hook invoked from a LINKED WORKTREE cwd
# (mirroring a story worker's own process cwd) with a subagent-shaped payload.
# Confirms the hook resolves the armed check and writes to the SHARED main-tree
# evidence store, not a worktree-local one — the mechanically checkable half of
# dogfood item zero (see file header and reference/evidence-format.md). ---
d12=$(sandbox)
( cd "$d12" && git worktree add -q "$d12/.studious/worktrees/e/s" -b epic/e--s )
arm "$d12" epic/e--s
run_hook "$d12/.studious/worktrees/e/s" \
  '{"hook_event_name":"PostToolUse","tool_input":{"command":"pytest tests/"},"tool_response":{"stdout":"ok","stderr":"","interrupted":false,"isImage":false},"agent_id":"sub-1","agent_type":"epic-driver:build-worker"}'
f12="$d12/.studious/evidence/epic-e--s.jsonl"
check "linked worktree: record lands in the MAIN tree's evidence store" "yes" "$([ -f "$f12" ] && echo yes || echo no)"
check "linked worktree: no worktree-local evidence store created" "no" \
  "$([ -d "$d12/.studious/worktrees/e/s/.studious/evidence" ] && echo yes || echo no)"
check "linked worktree: origin resolved subagent" "subagent" "$(jq -r '.origin' "$f12" 2>/dev/null)"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all evidence-capture tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
