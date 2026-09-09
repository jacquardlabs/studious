#!/usr/bin/env bash
# Integration tests for hooks/dispatch-telemetry.sh (the PreToolUse hook wired to
# the Task tool in hooks.json). Requires git + jq.
#
# Each test feeds the hook a crafted JSON payload shaped per code.claude.com/docs/en/hooks'
# PreToolUse input, proving the hook's own logic (roster filter, skill mapping, sentinel
# suppression, identity derivation, defensive exits). It does NOT prove a real Task dispatch
# uses `subagent_type` under that name — unverified per reference/telemetry-format.md,
# "What the hook can and cannot see".
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
check "fleet is studious for a local agent" "studious" "$(jq -r '.fleet' "$f")"
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

# --- the frontmatter value is recorded verbatim, never normalized to a tier (#136) ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload studious:doc-auditor 'x')" >/dev/null
check "a full model ID is recorded verbatim, not normalized to a tier" "claude-opus-5" "$(jq -r '.model' "$f")"
check "a local agent still resolves its fleet as studious" "studious" "$(jq -r '.fleet' "$f")"

# --- a gauntlet: prefix is its own allow-list: no local file, no local pin ---
# security-auditor has a local agents/ file too, so an empty model here proves the
# fleet suppressed the lookup rather than the file being absent.
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
out=$(run_hook "$d" "$(payload gauntlet:security-auditor 'audit this changeset')")
check "gauntlet dispatch is silent on the happy path" "" "$out"
check "gauntlet dispatch writes one record" "1" "$(lines "$f")"
check "role strips the gauntlet: prefix" "security-auditor" "$(jq -r '.role' "$f")"
check "fleet is gauntlet" "gauntlet" "$(jq -r '.fleet' "$f")"
check "gauntlet auditor maps to gate-audit" "gate-audit" "$(jq -r '.skill' "$f")"
check "gauntlet role records no model, even with a same-named local agent" "" "$(jq -r '.model' "$f")"
check "gauntlet role records no effort" "" "$(jq -r '.effort' "$f")"
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload gauntlet:product-posture-reviewer x)" >/dev/null
run_hook "$d" "$(payload gauntlet:product-reviewer x)" >/dev/null
run_hook "$d" "$(payload gauntlet:premortem-auditor x)" >/dev/null
run_hook "$d" "$(payload gauntlet:code-auditor x)" >/dev/null
run_hook "$d" "$(payload gauntlet:falsifiability-auditor x)" >/dev/null
check "gauntlet posture reviewer maps to the /health key, not gate-acceptance" "health" "$(jq -r 'select(.role=="product-posture-reviewer").skill' "$f")"
check "gauntlet product-reviewer maps to gate-acceptance like the local lane" "gate-acceptance" "$(jq -r 'select(.role=="product-reviewer").skill' "$f")"
check "gauntlet premortem-auditor maps to gate-acceptance like the local lane" "gate-acceptance" "$(jq -r 'select(.role=="premortem-auditor").skill' "$f")"
check "gauntlet code-auditor maps to gate-audit, its only dispatcher since /review took the lane" "gate-audit" "$(jq -r 'select(.role=="code-auditor").skill' "$f")"
check "a gauntlet judge with no local counterpart still records" "gate-audit" "$(jq -r 'select(.role=="falsifiability-auditor").skill' "$f")"
check "every gauntlet line names its fleet" "5" "$(jq -r 'select(.fleet=="gauntlet") | .role' "$f" | wc -l | tr -d ' ')"
# the ledger refuses a qualified string as a role: the prefix belongs in --fleet
check "a gauntlet role with a colon is rejected by gate-ledger" "2" \
  "$(cd "$d" && CLAUDE_PLUGIN_ROOT="$ROOT" "$LEDGER" telemetry-dispatch --run-id r --step-id s \
      --role gauntlet:security-auditor --routing-reason static >/dev/null 2>&1; echo $?)"
check "the rejected role wrote no line" "5" "$(lines "$f")"

# --- skill mapping per surface ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload security-auditor x)" >/dev/null
run_hook "$d" "$(payload review-readme x)" >/dev/null
run_hook "$d" "$(payload product-reviewer x)" >/dev/null
run_hook "$d" "$(payload code-auditor x)" >/dev/null
run_hook "$d" "$(payload review-outcomes x)" >/dev/null
check "auditor maps to gate-audit" "gate-audit" "$(jq -r 'select(.role=="security-auditor").skill' "$f")"
check "review-* maps to deep-review" "deep-review" "$(jq -r 'select(.role=="review-readme").skill' "$f")"
check "product-reviewer maps to gate-acceptance" "gate-acceptance" "$(jq -r 'select(.role=="product-reviewer").skill' "$f")"
check "code-auditor maps to gate-audit like every other auditor (the idiom step reads a posture judge now)" "gate-audit" "$(jq -r 'select(.role=="code-auditor").skill' "$f")"
check "review-outcomes maps to its own command, not deep-review" "review-outcomes" "$(jq -r 'select(.role=="review-outcomes").skill' "$f")"

# --- a gauntlet posture judge (#334 S3): the prefix is the allow-list, no agent file to pin from ---
d=$(sandbox); f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(payload gauntlet:codebase-posture-auditor 'inspect the repository')" >/dev/null
check "gauntlet posture judge writes one record" "1" "$(lines "$f")"
check "role strips the gauntlet: prefix" "codebase-posture-auditor" "$(jq -r '.role' "$f")"
check "posture lane maps to health" "health" "$(jq -r '.skill' "$f")"
check "model is empty with no local agent file" "" "$(jq -r '.model' "$f")"
check "effort is empty with no local agent file" "" "$(jq -r '.effort' "$f")"

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
run_hook "$d" "$(payload studious:not-a-real-auditor 'x')" >/dev/null
check "a studious: prefix does not bypass the local file check" "0" "$(lines "$f")"
run_hook "$d" "$(payload gauntlet:general-purpose 'x')" >/dev/null
check "a gauntlet: prefix on a non-judge name writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload '' 'do a thing')" >/dev/null
check "missing subagent_type writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Bash",session_id:"s",tool_input:{command:"pytest"}}')" >/dev/null
check "a non-dispatch tool writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Task",tool_use_id:"t",tool_input:{subagent_type:"security-auditor",prompt:"x"}}')" >/dev/null
check "missing session_id writes nothing" "0" "$(lines "$f")"
run_hook "$d" "$(payload security-auditor 'audit this STUDIOUS-TELEMETRY-SELF-REPORT and report it yourself')" >/dev/null
check "driver-stamped prompt is suppressed" "0" "$(lines "$f")"

# --- the dispatch tool is named Agent in current Claude Code (#367): both names record ---
d=$(sandbox)
f=$(telemetry_file "$d" feat/foo)
run_hook "$d" "$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Agent",session_id:"sess-1",tool_use_id:"toolu_02",tool_input:{subagent_type:"studious:security-auditor",prompt:"x"}}')" >/dev/null
check "the Agent tool name writes a record" "1" "$(lines "$f")"
check "hooks.json matches both dispatch tool names" "Agent|Task" "$(jq -r '.hooks.PreToolUse[] | select(.hooks[0].command | contains("dispatch-telemetry")) | .matcher' "$ROOT/hooks/hooks.json")"

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
