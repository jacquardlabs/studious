#!/usr/bin/env bash
# Jaqal gate reminder — a PreToolUse hook that fires before `gh pr create`.
#
# It surfaces a non-blocking confirmation at PR-create time so you don't merge
# work that skipped the gates. It is unconditional by design: it always asks,
# it does not try to detect whether a gate actually ran. Answer "yes" if the
# gates passed or don't apply to this change.
#
# Wired into a project's .claude/settings.json by `/jaqal-init`, scoped to
# `gh pr create` via the hook's `if` rule. The grep below is defense in depth
# in case the hook is ever invoked on a broader matcher.

input=$(cat)

if printf '%s' "$input" | grep -q 'gh pr create'; then
  cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "Jaqal: opening a PR. Did /gate-audit and /gate-acceptance run on this branch? Proceed if the gates passed or don't apply to this change."
  }
}
JSON
fi

exit 0
