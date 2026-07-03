#!/usr/bin/env bash
# Studious gate reminder — a PreToolUse hook that fires before `gh pr create`.
#
# Non-blocking by design: it always returns an "ask" decision so a human confirms
# before the PR opens. When a gate ledger exists for the current branch
# (.studious/gates/<branch>.json, written by /gate-audit and /gate-acceptance) it
# makes the reason SPECIFIC — naming a missing, stale, or non-passing gate — instead
# of asking blindly. With no ledger (or no jq) it falls back to the generic prompt.

input=$(cat)

printf '%s' "$input" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+create' || exit 0

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
