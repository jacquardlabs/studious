#!/usr/bin/env bash
# Studious flow-position heads-up — SessionStart hook.
#
# Fires on startup/resume only: a fresh `clear`, a `compact`, and a `fork`
# are not "arriving new to this project" (compact especially — the whole
# point of compaction is a smaller context, not a bigger one). Reads
# `gate-ledger work-list` and, when something is active, emits
# one to three lines of hookSpecificOutput.additionalContext naming counts
# and the single most-recently-updated item — never the full list, same
# "counts, never the full list" rule commands/doctor.md's flow-state-hygiene
# check already follows. Degrades silently in every other case: no
# gate-ledger, nothing active, or jq missing (work-list already
# no-op without jq — same posture as every other hook here).

input=$(cat)

reason=$(printf '%s' "$input" | jq -r '.reason // ""' 2>/dev/null)
if [ -z "$reason" ]; then
  # jq-less fallback: pull the "reason" field out of flat top-level JSON by
  # hand. Good enough for this one field; we never need to parse anything
  # else without jq (see the ledger-output note below).
  reason=$(printf '%s' "$input" | grep -o '"reason"[[:space:]]*:[[:space:]]*"[^"]*"' | sed -E 's/.*:[[:space:]]*"([^"]*)"/\1/')
fi

case "$reason" in
  startup|resume) : ;;
  *) exit 0 ;;
esac

ledger="${CLAUDE_PLUGIN_ROOT:-}/bin/gate-ledger"
[ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -x "$ledger" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

work_list=$("$ledger" work-list 2>/dev/null)

active_work=$(printf '%s\n' "$work_list" | awk -F'\t' '$1!="" && $2!="done" && $2!="stopped"')

work_count=0
[ -n "$active_work" ] && work_count=$(printf '%s\n' "$active_work" | grep -c .)
[ "$work_count" -eq 0 ] && exit 0

# Most-recently-updated item: work-list carries no timestamp, so pull
# `updatedAt`/`createdAt` per active item via work-get (the ledger tool,
# never a raw .studious/ file read) and
# sort. Bounded by the same active count doctor already flags as unusual
# past 10, so this loop never runs long.
candidates=""
if [ -n "$active_work" ]; then
  while IFS=$'\t' read -r slug phase _branch title; do
    [ -n "$slug" ] || continue
    updated=$("$ledger" work-get --slug "$slug" 2>/dev/null | jq -r '.updatedAt // .createdAt // ""' 2>/dev/null)
    [ -n "$updated" ] || continue
    candidates="${candidates}${updated}$(printf '\t')work$(printf '\t')${slug}$(printf '\t')${phase}$(printf '\t')${title}
"
  done <<<"$active_work"
fi
recent_line=$(printf '%s' "$candidates" | sort -r | head -n1)

summary="Studious: $work_count feature(s) in flight."
if [ -n "$recent_line" ]; then
  IFS=$'\t' read -r _ recent_kind recent_slug recent_state _recent_title <<<"$recent_line"
  case "$recent_kind" in
    work) recent_line_text="Most recent: $recent_slug, at the $recent_state phase." ;;
    *) recent_line_text="" ;;
  esac
else
  recent_line_text=""
fi

context="$summary"
[ -n "$recent_line_text" ] && context="$context
$recent_line_text"
context="$context
/studious:next picks it up."

jq -n --arg c "$context" '{hookSpecificOutput: {hookEventName: "SessionStart", additionalContext: $c}}'

exit 0
