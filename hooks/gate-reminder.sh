#!/usr/bin/env bash
# Studious gate reminder — PreToolUse hook for `gh pr create`.
# Always returns "ask" (non-blocking). If a gate ledger exists for the branch
# (.studious/gates/<branch>.json, from /review), names the
# specific missing/stale/failing gate; otherwise falls back to the generic prompt.

input=$(cat)

printf '%s' "$input" | grep -Eq 'gh[[:space:]]+pr[[:space:]]+create' || exit 0

default_reason="Studious: opening a PR. Did /review run on this branch? Proceed if the gates passed or don't apply to this change."

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
    "permissionDecisionReason": "Studious: opening a PR. Did /review run on this branch? Proceed if the gates passed or don't apply to this change."
  }
}
JSON
fi

exit 0
