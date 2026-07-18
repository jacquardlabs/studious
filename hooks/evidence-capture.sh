#!/usr/bin/env bash
# Studious evidence capture — a PostToolUse/PostToolUseFailure hook (both wired
# in hooks.json to this same script) that silently appends one record per
# verification command to .studious/evidence/<branch-slug>.jsonl while the
# current branch is a story gate-ledger already knows about ("armed").
#
# Fully silent by design, on every path: no stdout, no permission decision,
# never blocks, never adds a decision Claude Code would surface. A branch
# nobody armed, or a Bash call that doesn't look like verification, produces
# no record and no side effect — same posture as hooks/gate-reminder.sh's
# no-op on a non-`gh pr create` command.
#
# Two events, one script, because Claude Code's own hook schema splits a Bash
# call's outcome across them (verified against code.claude.com/docs/en/hooks,
# not guessed — see reference/evidence-format.md's "Resolved: PostToolUse vs
# PostToolUseFailure" section for the full finding):
#   - PostToolUse   fires ONLY when the command exited zero. tool_response has
#     stdout/stderr/interrupted/isImage — no exit-code field, because success
#     is the only reason this event fired at all.
#   - PostToolUseFailure fires when the command exited non-zero (or was
#     interrupted). It carries a different shape entirely: an `error` string
#     (e.g. "Command exited with non-zero status code 1") and `is_interrupt`
#     — no stdout/stderr. A hook registered on PostToolUse alone never sees a
#     failing verification run, which would silently defeat the one property
#     this story exists to add (a FAILED record actually means something
#     failed) — it wouldn't mislabel failures as PASSED, it would drop them
#     entirely, which is worse.

input=$(cat)

command -v jq  >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ] || exit 0

event=$(printf '%s' "$input" | jq -r '.hook_event_name // empty')
command_str=$(printf '%s' "$input" | jq -r '.tool_input.command // empty')
[ -n "$command_str" ] || exit 0

# --- verification-relevant filter: conservative, over-inclusive allow-list.
# Data, not prose — edit this array to tune coverage for a toolchain this list
# misses (see reference/evidence-format.md's Open questions). Word-boundary
# matched (a token must not be glued to another alnum char on either side;
# '_', '.', '/', '-', space, and string edges all count as boundaries — this
# is what lets "test" catch bash tests/test_gate_ledger.sh and "check" catch
# scripts/check_references.py, while "checkout" and "cmake" still miss).
# go test / cargo test|build / npm test / npm run test|build need no explicit
# entry: they already contain the bare "test"/"build" token, so the catch-all
# alone covers them — do not add a redundant compound pattern for these.
# Runs BEFORE the armed check: this hook fires on every Bash call in the
# session, and this filter is pure bash + one grep, while the armed check
# spawns git and gate-ledger — the common non-verification command must exit
# here without ever paying those spawns.
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

# --- armed check: current branch must be a branch gate-ledger already knows
# about (a work file's .branch, written by /work-on or /work-through's driver
# when the story was set up — an existing step, not a new one). work-list's
# column 3 is the branch, exact string match (not the gates ledger's slug —
# no collision risk here, this compares full branch names).
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ -n "$branch" ] && [ "$branch" != "HEAD" ] || exit 0
armed=$("$ledger" work-list 2>/dev/null | cut -f3 | grep -qxF "$branch" && echo yes || echo no)
[ "$armed" = "yes" ] || exit 0

# --- origin: agent_id is documented as present only when the hook fires
# inside a subagent call (code.claude.com/docs/en/hooks, "Common input
# fields"). reference/evidence-format.md records what this does and doesn't
# prove about /work-through's own dispatch mechanism.
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
    # Only fires on success: the exit code IS zero, not read from a field
    # that doesn't exist. Guard the expected shape (has stdout) so an
    # async-launched background Bash call (a different tool_response shape)
    # is skipped rather than mis-recorded as a completed, passing run.
    has_stdout=$(printf '%s' "$input" | jq -r '.tool_response | has("stdout")' 2>/dev/null)
    [ "$has_stdout" = "true" ] || exit 0
    exit_code=0
    digest=$(printf '%s' "$input" | jq -cr '.tool_response | {stdout, stderr}' 2>/dev/null | sha256_of)
    ;;
  PostToolUseFailure)
    # No exit-code field exists on this event at all — only a human-readable
    # `error` string. Best-effort parse the documented phrasing
    # ("Command exited with non-zero status code N"); fall back to a non-zero
    # sentinel when it doesn't parse (e.g. interrupted/timed-out). The FAILED
    # verdict below never depends on this parse succeeding — only the exact
    # numeric code would be approximate in the fallback case.
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
