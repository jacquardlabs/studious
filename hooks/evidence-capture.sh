#!/usr/bin/env bash
# Studious evidence capture — PostToolUse/PostToolUseFailure hook (both wired
# in hooks.json to this script) that appends one record per verification
# command to .studious/evidence/<branch-slug>.jsonl while the current branch
# is armed (known to gate-ledger).
#
# Fully silent: no stdout, no permission decision, never blocks. An unarmed
# branch or non-verification command produces no record, same as
# hooks/gate-reminder.sh's no-op.
#
# Two events because Claude Code's hook schema splits a Bash call's outcome
# across them (code.claude.com/docs/en/hooks; details in
# reference/evidence-format.md's "Resolved: PostToolUse vs PostToolUseFailure"):
#   - PostToolUse fires only on exit 0. tool_response has stdout/stderr/
#     interrupted/isImage, no exit-code field.
#   - PostToolUseFailure fires on non-zero exit or interrupt. It carries an
#     `error` string (e.g. "Command exited with non-zero status code 1") and
#     `is_interrupt` instead — no stdout/stderr. Without this event, failing
#     verification runs would be silently dropped rather than mislabeled,
#     defeating the point of a FAILED record.

input=$(cat)

command -v jq  >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ] || exit 0

event=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')
command_str=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -n "$command_str" ] || exit 0

# --- verification-relevant filter: conservative, over-inclusive allow-list.
# Edit this array to add tokens (see reference/evidence-format.md's Open
# questions). Word-boundary matched ('_','.','/','-',space,edges count as
# boundaries) so "test" catches tests/test_gate_ledger.sh and "check" catches
# scripts/check_references.py, while "checkout"/"cmake" don't match. go
# test/cargo test|build/npm test|build need no extra entry — the bare
# "test"/"build" token already covers them.
# Runs before the armed check (git + gate-ledger spawn) so a non-verification
# command exits cheaply.
VERIFICATION_TOKENS=(
  pytest jest vitest rspec phpunit                    # test runners (named)
  eslint ruff flake8 shellcheck 'markdownlint(-cli2)?' # lint/static analysis
  tsc mypy pyright                                     # type checkers
  make                                                 # build tool (named)
  test lint typecheck check build                      # catch-all standalone tokens
)
alt=""
for tok in "${VERIFICATION_TOKENS[@]}"; do
  alt="${alt:+$alt|}$tok"
done
pattern="(^|[^A-Za-z0-9])(${alt})(\$|[^A-Za-z0-9])"
printf '%s' "$command_str" | grep -Eq "$pattern" || exit 0

# --- armed check: branch must be one gate-ledger already knows about (a work
# file's .branch, written by /next). work-list's column 3
# is the branch; exact string match against full branch names.
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ -n "$branch" ] && [ "$branch" != "HEAD" ] || exit 0
armed=$("$ledger" work-list 2>/dev/null | cut -f3 | grep -qxF "$branch" && echo yes || echo no)
[ "$armed" = "yes" ] || exit 0

# --- origin: agent_id is present only when the hook fires inside a subagent
# call (code.claude.com/docs/en/hooks). See reference/evidence-format.md for
# what this does/doesn't prove about /next's dispatch mechanism.
agent_id=$(printf '%s' "$input" | jq -r '.agent_id // empty')
agent_type=$(printf '%s' "$input" | jq -r '.agent_type // empty')
origin="interactive"
[ -n "$agent_id" ] && origin="subagent"

# --- hash helper: first hashing tool found wins. If none exist, no-op rather
# than write a record with a fabricated digest.
sha256_of() { # reads stdin, prints lowercase hex digest or nothing
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 | awk '{print $1}'
  elif command -v openssl >/dev/null 2>&1; then
    openssl dgst -sha256 | awk '{print $NF}'
  fi
}

# --- exit code + digest source: derived differently per event (see header).
exit_code="" digest=""
case "$event" in
  PostToolUse)
    # Exit code is inferred zero (no such field exists). Guard has("stdout")
    # so an async/background Bash call (different tool_response shape) is
    # skipped rather than mis-recorded as a passing run.
    has_stdout=$(printf '%s' "$input" | jq -r '.tool_response | has("stdout")' 2>/dev/null)
    [ "$has_stdout" = "true" ] || exit 0
    exit_code=0
    digest=$(printf '%s' "$input" | jq -cr '.tool_response | {stdout, stderr}' 2>/dev/null | sha256_of)
    ;;
  PostToolUseFailure)
    # No exit-code field on this event — parse it from the `error` string
    # ("Command exited with non-zero status code N"); fall back to sentinel 1
    # when it doesn't parse (e.g. interrupted/timed out). FAILED verdict
    # doesn't depend on this parse succeeding, only the exact code would.
    err=$(printf '%s' "$input" | jq -r '.error // empty')
    [ -n "$err" ] || exit 0
    exit_code=$(printf '%s' "$err" | grep -oE '[0-9]+$' || true)
    [ -n "$exit_code" ] || exit_code=1
    digest=$(printf '%s' "$err" | sha256_of)
    ;;
  *) exit 0 ;;
esac
[ -n "$digest" ] || exit 0

args=(--command "$command_str" --exit-code "$exit_code" --output-digest "sha256:$digest" --origin "$origin")
[ -n "$agent_type" ] && args+=(--agent-type "$agent_type")
"$ledger" evidence-append "${args[@]}" >/dev/null 2>&1

exit 0
