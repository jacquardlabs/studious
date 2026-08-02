#!/usr/bin/env bash
# Integration tests for hooks/dispatch-telemetry.sh (the PreToolUse hook wired to
# the Task tool in hooks.json). Requires git + jq.
#
# What this file does and doesn't prove, in the same terms as
# tests/test_evidence_capture.sh: every test feeds the hook a crafted JSON payload
# on stdin, shaped as code.claude.com/docs/en/hooks documents PreToolUse input.
# That deterministically proves the hook's own logic — roster filter, skill
# mapping, sentinel suppression, identity derivation, defensive exits. It does NOT
# prove that a real Task dispatch produces a `subagent_type` field under that name;
# the docs do not enumerate the Task tool's tool_input, and no Task tool is
# available to this suite to observe a real one (reference/telemetry-format.md,
# "What the hook can and cannot see", records that as assumed, not verified).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER="$ROOT/bin/gate-ledger"
HOOK="$ROOT/hooks/dispatch-telemetry.sh"
fails=0

check() { # description, expected, actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1"; echo "       expected: $2"; echo "       actual:   $3"; fails=$((fails + 1))
  fi
}

sandbox() { # create a throwaway git repo on the given branch, echo its path
  local d branch; d=$(mktemp -d); branch="${1:-feat/foo}"
  git -C "$d" init -q
  git -C "$d" config user.email t@t.t
  git -C "$d" config user.name t
  git -C "$d" commit -q --allow-empty -m init
  git -C "$d" checkout -q -b "$branch"
  printf '%s' "$d"
}

run_hook() { # dir, stdin-json -> stdout captured
  ( cd "$1" && CLAUDE_PLUGIN_ROOT="$ROOT" bash "$HOOK" <<<"$2" )
}

telemetry_file() { printf '%s/.studious/telemetry/%s.jsonl' "$1" "$(printf '%s' "$2" | tr '/' '-')"; }

payload() { # subagent_type, prompt, [extra top-level json fields]
  local extra="{}"; [ $# -ge 3 ] && extra="$3"
  jq -nc --arg st "$1" --arg p "$2" --argjson extra "$extra" \
    '{hook_event_name: "PreToolUse", tool_name: "Task", session_id: "sess-1",
      tool_use_id: "toolu_01ABC", tool_input: {subagent_type: $st, prompt: $p, description: "d"}}
     + $extra'
}

lines() { [ -f "$1" ] && wc -l < "$1" | tr -d ' ' || echo 0; }

# --- a rostered auditor produces one dispatch record with resolved identity ---
d=$(sandbox)
f=$(telemetry_file "$d" feat/foo)
out=$(run_hook "$d" "$(payload studious:security-auditor 'audit this changeset')")
check "hook is silent on the happy path" "" "$out"
check "one dispatch record written" "1" "$(lines "$f")"
check "role strips the studious: prefix" "security-auditor" "$(jq -r '.role' "$f")"
check "capturer is hook" "hook" "$(jq -r '.capturer' "$f")"
check "kind is dispatch" "dispatch" "$(jq -r '.kind' "$f")"
check "run_id is the session id" "sess-1" "$(jq -r '.run_id' "$f")"
check "step_id is the tool_use_id" "toolu_01ABC" "$(jq -r '.step_id' "$f")"
check "parent_step_id empty at top level" "" "$(jq -r '.parent_step_id' "$f")"
check "task_id is the branch" "feat/foo" "$(jq -r '.task_id' "$f")"
check "routing_reason is static" "static" "$(jq -r '.routing_reason' "$f")"
check "model resolves from agent frontmatter" "opus" "$(jq -r '.model' "$f")"
check "effort resolves from agent frontmatter" "high" "$(jq -r '.effort' "$f")"
check "prompt_bytes recorded as a number" "20" "$(jq -r '.features.prompt_bytes' "$f")"

# --- inherit is recorded verbatim, never normalized away (#136 signal) ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload studious:doc-auditor 'x')" >/dev/null
check "model: inherit recorded verbatim" "inherit" "$(jq -r '.model' "$f")"

# --- skill mapping per surface ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload security-auditor x)" >/dev/null
run_hook "$d" "$(payload review-readme x)" >/dev/null
run_hook "$d" "$(payload product-reviewer x)" >/dev/null
run_hook "$d" "$(payload code-auditor x)" >/dev/null
check "auditor maps to gate-audit" "gate-audit" "$(jq -r 'select(.role=="security-auditor").skill' "$f")"
check "review-* maps to deep-review" "deep-review" "$(jq -r 'select(.role=="review-readme").skill' "$f")"
check "product-reviewer maps to gate-acceptance" "gate-acceptance" "$(jq -r 'select(.role=="product-reviewer").skill' "$f")"
check "dual-surface code-auditor leaves skill empty" "" "$(jq -r 'select(.role=="code-auditor").skill' "$f")"

# --- parent_step_id comes from agent_id when nested in a subagent ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload security-auditor x '{"agent_id":"agt-9","agent_type":"general-purpose"}')" >/dev/null
check "parent_step_id is the enclosing agent_id" "agt-9" "$(jq -r '.parent_step_id' "$f")"

# --- everything the hook must ignore ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload general-purpose 'do a thing')" >/dev/null
check "unrostered agent writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload backlog-hygiene 'triage')" >/dev/null
check "a Studious agent off the review surfaces writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload not-a-real-auditor 'x')" >/dev/null
check "a pattern match with no agent file writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload '' 'do a thing')" >/dev/null
check "missing subagent_type writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Bash",session_id:"s",tool_input:{command:"pytest"}}')" >/dev/null
check "a non-Task tool writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Task",tool_use_id:"t",tool_input:{subagent_type:"security-auditor",prompt:"x"}}')" >/dev/null
check "missing session_id writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload security-auditor 'audit this STUDIOUS-TELEMETRY-SELF-REPORT and report it yourself')" >/dev/null
check "driver-stamped prompt is suppressed" "0" "$(lines "$f")"

# --- no plugin root, no ledger: silent no-op, never an error ---
d=$(sandbox)
out=$( cd "$d" && bash "$HOOK" <<<"$(payload security-auditor x)" 2>&1 ); rc=$?
check "no CLAUDE_PLUGIN_ROOT exits 0 silently" "0:" "$rc:$out"

# --- the store is gitignored, like every other .studious/ store ---
d=$(sandbox)
run_hook "$d" "$(payload security-auditor x)" >/dev/null
check "telemetry store is gitignored" "" "$(cd "$d" && git status --porcelain .studious 2>/dev/null)"

# --- a hook-written run makes a later verdict joinable with no prompt involved ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload security-auditor x)" >/dev/null
( cd "$d" && "$LEDGER" record --gate audit --verdict "FIX AND RE-REVIEW" >/dev/null )
check "outcome inherits the run id the hook wrote" "sess-1" "$(jq -r 'select(.kind=="outcome").run_id' "$f")"
check "outcome step_id is the gate step" "feat-foo:audit" "$(jq -r 'select(.kind=="outcome").step_id' "$f")"
check "dispatch and outcome share one store" "2" "$(lines "$f")"

if [ "$fails" -gt 0 ]; then echo "$fails test(s) failed"; exit 1; fi
echo "all dispatch-telemetry tests passed"
