#!/usr/bin/env bash
# Studious dispatch telemetry — a PreToolUse hook on the `Task` tool (wired in
# hooks.json) that silently appends one `dispatch` record per Studious review
# agent sent out, to .studious/telemetry/<branch-slug>.jsonl via gate-ledger.
# reference/telemetry-format.md is the contract; this script is one caller of
# `telemetry-dispatch`, never a second writer or a second schema.
#
# Fully silent by design, on every path: no stdout, no permission decision,
# never blocks, never adds a decision Claude Code would surface — same posture
# as hooks/gate-reminder.sh and hooks/evidence-capture.sh. A dispatch this
# script does not recognize produces no record and no side effect.
#
# What the hook input actually carries, verified against
# code.claude.com/docs/en/hooks (Common input fields; PreToolUse), not guessed:
#   - every hook gets session_id, transcript_path, cwd, permission_mode,
#     hook_event_name; PreToolUse adds tool_name, tool_input, tool_use_id.
#   - agent_id/agent_type are present ONLY when the hook fires inside a subagent
#     call — which is exactly the nesting this record's parent_step_id wants.
#   - PreToolUse matchers match the TOOL NAME, so "Task" is a valid matcher.
# NOT verified, because the docs do not enumerate it: the `Task` tool's own
# tool_input field names. This script reads `subagent_type` and `prompt` and
# exits silently when subagent_type is absent or empty, so a wrong assumption
# here degrades to zero telemetry rather than to wrong telemetry.
#
# Deliberately NO armed-branch check, unlike evidence-capture.sh: /deep-review
# runs on main against no story with no work file, and an armed check would
# silence half of what this store exists to record. The roster table below is
# the whole filter — a dispatch of a named Studious reviewer is itself the
# signal.

input=$(cat)

command -v jq  >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ] || exit 0

# --- one jq spawn, not six. This hook fires on EVERY Task dispatch in the
# session, most of which are not Studious reviewers at all; evidence-capture.sh's
# own comment is explicit that the common rejected call must not pay a per-field
# process each. Everything the decision needs comes out of one @tsv row: the
# prompt itself never crosses the boundary, only its byte length (jq's
# utf8bytelength, not bash's character count) and whether it carries the driver's
# sentinel. A malformed payload fails the parse and exits silently.
#
# Joined on US (), NOT @tsv: bash treats tab as IFS *whitespace*, which
# collapses a run of delimiters, so a single absent field (agent_id, present only
# inside a subagent call — the common case) would silently shift every field after
# it by one. A non-whitespace separator preserves empty fields positionally.
fields=$(printf '%s' "$input" | jq -r '
  [.tool_name // "", .tool_input.subagent_type // "", .session_id // "",
   .tool_use_id // "", .agent_id // "",
   ((.tool_input.prompt // "") | utf8bytelength),
   ((.tool_input.prompt // "") | contains("STUDIOUS-TELEMETRY-SELF-REPORT"))]
  | map(tostring) | join("")
' 2>/dev/null) || exit 0
IFS=$'\037' read -r tool subagent run_id step_id parent_step_id prompt_bytes self_report <<<"$fields"

[ "${tool:-}" = "Task" ] || exit 0
[ -n "${subagent:-}" ] || exit 0

# --- self-report suppression: workflows/epic-driver.js stamps the ledger call
# into its own dispatch prompts with values no hook can observe (which round,
# whether the roster was narrowed). A driver-stamped prompt carries the sentinel
# matched above; recording it here too would double-count the dispatch. The token
# is deliberately unlikely in ordinary prose — matching on "telemetry-dispatch"
# would suppress on any prompt that happened to quote reference/telemetry-format.md.
[ "${self_report:-}" = "true" ] && exit 0

role="${subagent#studious:}"   # the agent's own `name`, never the qualified dispatch string

# --- roster: which dispatch surface each agent belongs to. Two short exception
# lists plus a pattern, deliberately not a fourth hand-maintained copy of the
# auditor roster — epic-driver.js's AUDITORS comment already names three copies of
# that list as a standing drift risk (#271), and a lane added tomorrow would go
# silently unrecorded here. The pattern self-heals; the exceptions are the two
# facts a pattern cannot carry. Backed by an agents/<role>.md existence check, so
# an unrelated general-purpose Task never lands in this store.
#
# ORDER IS LOAD-BEARING: product-reviewer, premortem-auditor, and code-auditor all
# match the *-reviewer/*-auditor pattern, so both exception lists must be tested
# before it, and review-outcomes matches review-* but is dispatched by its own
# /review-outcomes command, which runs OUTSIDE the /deep-review sweep — its case
# branch must precede that pattern. The one genuine ambiguity is recorded as an
# ambiguity, not guessed — code-auditor serves both /gate-audit's lane 2 and
# /deep-review's idiom feedback step, and the hook cannot see which command
# dispatched it, so its lines carry an empty `skill`
# (reference/telemetry-format.md says how a joiner resolves them).
[ -f "${CLAUDE_PLUGIN_ROOT}/agents/${role}.md" ] || exit 0
ACCEPTANCE_ROLES="product-reviewer premortem-auditor"
AMBIGUOUS_ROLES="code-auditor"
in_list() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
if   in_list "$role" "$ACCEPTANCE_ROLES"; then skill="gate-acceptance"
elif in_list "$role" "$AMBIGUOUS_ROLES";  then skill=""
else
  case "$role" in
    review-outcomes)      skill="review-outcomes" ;;
    review-*)             skill="deep-review" ;;
    *-auditor|*-reviewer) skill="gate-audit" ;;
    *) exit 0 ;;
  esac
fi

# --- identity. run_id is the session; step_id is the harness's own id for this
# tool call, unique by construction and needing no invention here. parent_step_id
# is the enclosing subagent when there is one (agent_id is documented as present
# only inside a subagent call) and empty at top level.
[ -n "${run_id:-}" ] || exit 0
[ -n "${step_id:-}" ] || step_id="$run_id:$role:$(date -u +%s)"

# model/effort are deliberately NOT read here: the Task input carries no model
# field, and resolving them from agents/<role>.md belongs in one place, which is
# `telemetry-dispatch` itself. routing_reason is `static` because every
# interactive fan-out dispatches from a fixed roster in the command's own prose;
# only the driver can narrow one, and the driver reports its own dispatches.
args=(--run-id "$run_id" --step-id "$step_id" --role "$role" --skill "$skill"
      --routing-reason static --capturer hook
      --feature "prompt_bytes=${prompt_bytes:-0}")
[ -n "${parent_step_id:-}" ] && args+=(--parent-step-id "$parent_step_id")
"$ledger" telemetry-dispatch "${args[@]}" >/dev/null 2>&1

exit 0
