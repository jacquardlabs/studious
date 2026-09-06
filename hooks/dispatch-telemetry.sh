#!/usr/bin/env bash
# PreToolUse hook on `Task` (wired in hooks.json): appends one `dispatch`
# record per review agent sent out — studious's or gauntlet's — to
# .studious/telemetry/<branch-slug>.jsonl via gate-ledger. Contract:
# reference/telemetry-format.md; this script only calls `telemetry-dispatch`.
#
# Fully silent: no stdout, no permission decision, never blocks — same
# posture as hooks/gate-reminder.sh and hooks/evidence-capture.sh. An
# unrecognized dispatch produces no record.
#
# Per code.claude.com/docs/en/hooks: agent_id/agent_type appear only when the
# hook fires inside a subagent call (used for parent_step_id below). The
# `Task` tool's own tool_input field names (`subagent_type`, `prompt`) are
# NOT documented; a wrong assumption there degrades to zero telemetry, not
# wrong telemetry.
#
# No armed-branch check (unlike evidence-capture.sh): /health runs on main
# with no story/work file, and an armed check would silence half of what
# this store exists to record. The roster table below is the whole filter.

input=$(cat)

command -v jq  >/dev/null 2>&1 || exit 0
command -v git >/dev/null 2>&1 || exit 0

ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ] || exit 0

# --- one jq spawn, not six: fires on every Task dispatch, most not
# Studious reviewers. The prompt itself never crosses the boundary, only
# its byte length (utf8bytelength) and whether it carries the driver's
# sentinel. Malformed payload fails the parse and exits silently.
#
# Joined on US (), not @tsv: bash's IFS treats tab as whitespace and
# collapses consecutive delimiters, so an absent field (agent_id, empty
# outside a subagent call) would shift every later field by one.
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

# --- self-report suppression: epic-driver.js stamps the ledger call into its
# own dispatch prompts with values no hook can observe (round, narrowed
# roster); recording here too would double-count. Matching on
# "telemetry-dispatch" instead would false-positive on any prompt quoting
# reference/telemetry-format.md.
[ "${self_report:-}" = "true" ] && exit 0

# --- role is the agent's own `name`, never the qualified dispatch string;
# `fleet` records which plugin that name belongs to. A `gauntlet:` prefix
# names one of gauntlet's judges (#334): the prefix is the allow-list, since
# its roster lives in gauntlet's charter and there is no agents/<role>.md
# here — so `telemetry-dispatch` leaves model/effort empty, even when a local
# agent shares the name. A local role is allow-listed by its agent file
# existing (the review-* agents stay local until #334 S4; never zero them).
case "$subagent" in
  gauntlet:*) fleet="gauntlet"; role="${subagent#gauntlet:}" ;;
  *)          fleet="studious"; role="${subagent#studious:}"
              [ -f "${CLAUDE_PLUGIN_ROOT}/agents/${role}.md" ] || exit 0 ;;
esac

# --- roster: which dispatch surface each agent belongs to. Two exception
# lists plus a pattern, not a fourth hand-maintained copy of the auditor
# roster (epic-driver.js's AUDITORS comment already names three as a drift
# risk, #271) — the pattern self-heals, the exceptions carry what it can't.
# Both fleets map alike: gauntlet's acceptance lanes carry the same names.
#
# ORDER IS LOAD-BEARING: product-reviewer, premortem-auditor, and
# code-auditor all match *-reviewer/*-auditor, so both exception lists must
# be tested first; the posture judges end in -auditor/-reviewer too, so
# *-posture-* precedes that pattern; review-outcomes matches review-* but
# runs under /retro, not the retired local sweep, so its case precedes that
# pattern as well. code-auditor serves both /review lane 2 and the old idiom
# step and the hook can't see which dispatched it, so its lines carry an
# empty `skill` (reference/telemetry-format.md says how a joiner resolves
# that).
ACCEPTANCE_ROLES="product-reviewer premortem-auditor"
AMBIGUOUS_ROLES="code-auditor"
in_list() { case " $2 " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
if   in_list "$role" "$ACCEPTANCE_ROLES"; then skill="gate-acceptance"
elif in_list "$role" "$AMBIGUOUS_ROLES";  then skill=""
else
  case "$role" in
    *-posture-*)          skill="health" ;;
    review-outcomes)      skill="review-outcomes" ;;
    review-*)             skill="deep-review" ;;
    *-auditor|*-reviewer) skill="gate-audit" ;;
    *) exit 0 ;;
  esac
fi

# --- identity. run_id is the session; step_id is the harness's own id for
# this tool call. parent_step_id is the enclosing subagent, if any.
[ -n "${run_id:-}" ] || exit 0
[ -n "${step_id:-}" ] || step_id="$run_id:$role:$(date -u +%s)"

# model/effort not read here: Task input carries no model field, and
# resolving from agents/<role>.md (local roles only) belongs in
# `telemetry-dispatch` itself.
# routing_reason is `static`: interactive fan-out always dispatches a fixed
# roster; only the driver narrows one, and it reports its own dispatches.
args=(--run-id "$run_id" --step-id "$step_id" --role "$role" --fleet "$fleet"
      --skill "$skill" --routing-reason static --capturer hook
      --feature "prompt_bytes=${prompt_bytes:-0}")
[ -n "${parent_step_id:-}" ] && args+=(--parent-step-id "$parent_step_id")
"$ledger" telemetry-dispatch "${args[@]}" >/dev/null 2>&1

exit 0
