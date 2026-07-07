#!/usr/bin/env bash
# Integration tests for bin/gate-ledger. Requires git + jq.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER="$ROOT/bin/gate-ledger"
fails=0

check() { # description, expected, actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1"; echo "       expected: $2"; echo "       actual:   $3"; fails=$((fails + 1))
  fi
}
contains() { # description, needle, haystack
  case "$3" in
    *"$2"*) echo "ok   - $1" ;;
    *) echo "FAIL - $1"; echo "       expected substring: $2"; echo "       in: $3"; fails=$((fails + 1)) ;;
  esac
}

sandbox() { # create a throwaway git repo, echo its path
  local d; d=$(mktemp -d)
  git -C "$d" init -q
  git -C "$d" config user.email t@t.t
  git -C "$d" config user.name t
  git -C "$d" commit -q --allow-empty -m init
  git -C "$d" checkout -q -b feat/foo
  printf '%s' "$d"
}

# --- record writes the expected shape ---
d=$(sandbox)
( cd "$d" && "$LEDGER" record --gate audit --verdict PASS )
f="$d/.studious/gates/feat-foo.json"
check "record creates branch-slug ledger file" "yes" "$([ -f "$f" ] && echo yes || echo no)"
check "record stores verdict token" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "record stores branch name" "feat/foo" "$(jq -r '.branch' "$f")"
check "record stores HEAD sha" "$(git -C "$d" rev-parse --short HEAD)" "$(jq -r '.gates.audit.sha' "$f")"

# --- record self-heals .gitignore ---
contains "record adds .studious/ to .gitignore" ".studious/" "$(cat "$d/.gitignore")"
check "ledger is gitignored (not in status)" "" "$(cd "$d" && git status --porcelain .studious 2>/dev/null)"

# --- second record upserts (latest wins, second gate added) ---
( cd "$d" && "$LEDGER" record --gate acceptance --verdict SHIP )
check "upsert keeps audit" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "upsert adds acceptance" "SHIP" "$(jq -r '.gates.acceptance.verdict' "$f")"

# --- gate-get prints the raw ledger JSON for the current branch ---
out=$(cd "$d" && "$LEDGER" gate-get)
contains "gate-get prints the current branch's ledger" '"branch": "feat/foo"' "$out"
contains "gate-get includes recorded verdicts" '"verdict": "PASS"' "$out"

# --- gate-get is empty when no ledger exists for the branch ---
dgg=$(sandbox)
out=$(cd "$dgg" && "$LEDGER" gate-get)
check "gate-get empty when no ledger recorded" "" "$out"

# --- gate-get --branch reads another branch's ledger without checking it out ---
( cd "$dgg" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dgg" && git checkout -q -b feat/other )
out=$(cd "$dgg" && "$LEDGER" gate-get --branch feat/foo)
contains "gate-get --branch reads the named branch's ledger" '"branch": "feat/foo"' "$out"
out=$(cd "$dgg" && "$LEDGER" gate-get)
check "gate-get with no --branch still reads the current (different) branch" "" "$out"

# --- status: both passing at HEAD ---
out=$(cd "$d" && "$LEDGER" status)
contains "status reports clean pass" "proceed" "$out"

# --- status: missing gate ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" record --gate audit --verdict PASS )
out=$(cd "$d2" && "$LEDGER" status)
contains "status names the missing gate" "acceptance never ran" "$out"

# --- status: non-passing verdict ---
d3=$(sandbox)
( cd "$d3" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
( cd "$d3" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$d3" && "$LEDGER" status)
contains "status surfaces non-passing audit" "FIX AND RE-AUDIT" "$out"

# --- status: stale sha ---
d4=$(sandbox)
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$d4" && git commit -q --allow-empty -m more )
out=$(cd "$d4" && "$LEDGER" status)
contains "status flags stale gate" "re-run" "$out"

# --- status: no ledger -> empty (hook uses default) ---
d5=$(sandbox)
out=$(cd "$d5" && "$LEDGER" status)
check "status empty when no ledger" "" "$out"

# --- statusline: silent when the project has never used the gate ledger ---
dsl0=$(sandbox)
out=$(cd "$dsl0" && "$LEDGER" statusline)
check "statusline empty when ledger dir does not exist" "" "$out"

# --- statusline: ledger dir exists (another branch used it) but not this branch ---
dsl1=$(sandbox)
( cd "$dsl1" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl1" && git checkout -q -b feat/other )
out=$(cd "$dsl1" && "$LEDGER" statusline)
check "statusline shows both never-ran for a branch with no ledger file" "audit— acceptance—" "$out"

# --- statusline: both gates pass at HEAD ---
dsl2=$(sandbox)
( cd "$dsl2" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl2" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$dsl2" && "$LEDGER" statusline)
check "statusline shows both passing" "audit✓ acceptance✓" "$out"

# --- statusline: gate never ran shows the dash symbol ---
dsl3=$(sandbox)
( cd "$dsl3" && "$LEDGER" record --gate audit --verdict PASS )
out=$(cd "$dsl3" && "$LEDGER" statusline)
check "statusline shows never-ran acceptance alongside a passing audit" "audit✓ acceptance—" "$out"

# --- statusline: stale sha shows the warning symbol ---
dsl4=$(sandbox)
( cd "$dsl4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dsl4" && git commit -q --allow-empty -m more )
out=$(cd "$dsl4" && "$LEDGER" statusline)
check "statusline flags a stale gate with the warning symbol" "audit⚠ acceptance⚠" "$out"

# --- statusline: non-passing verdict at HEAD shows the warning symbol ---
dsl5=$(sandbox)
( cd "$dsl5" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
( cd "$dsl5" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$dsl5" && "$LEDGER" statusline)
check "statusline flags a non-passing verdict with the warning symbol" "audit⚠ acceptance✓" "$out"

# --- statusline: branch-slug collision treated as never-ran, not a false pass ---
dsl6=$(sandbox)
( cd "$dsl6" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dsl6" && "$LEDGER" record --gate acceptance --verdict SHIP )
f6="$dsl6/.studious/gates/feat-foo.json"
tmp6=$(mktemp)
jq '.branch = "feat-foo"' "$f6" > "$tmp6" && mv "$tmp6" "$f6"
out=$(cd "$dsl6" && "$LEDGER" statusline)
check "statusline treats a branch-slug collision as never-ran" "audit— acceptance—" "$out"

# --- statusline: silent when jq is unavailable ---
dsl7=$(sandbox)
( cd "$dsl7" && "$LEDGER" record --gate audit --verdict PASS )
fakebin_sl=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat sed; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$fakebin_sl/$tool"
done
out=$(cd "$dsl7" && PATH="$fakebin_sl" "$LEDGER" statusline)
check "statusline empty when jq is unavailable" "" "$out"

# --- hook surfaces the ledger reason and always asks ---
HOOK="$ROOT/hooks/gate-reminder.sh"
d6=$(sandbox)
( cd "$d6" && "$LEDGER" record --gate audit --verdict PASS )
hook_out=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh pr create"}}')
contains "hook decision is ask" '"permissionDecision": "ask"' "$hook_out"
contains "hook reason names missing acceptance" "acceptance never ran" "$hook_out"

# --- hook stays silent for non-PR commands ---
hook_noop=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"ls -la"}}')
check "hook ignores non-PR commands" "" "$hook_noop"

# --- hook matches spacing variants that would evade a literal-string grep ---
hook_spacing=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh  pr   create"}}')
contains "hook matches gh pr create with irregular spacing" '"permissionDecision": "ask"' "$hook_spacing"

# --- hook still matches when the phrase is embedded in a longer command ---
hook_embedded=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"git log --grep=\"gh pr create\""}}')
contains "hook matches gh pr create embedded in a longer command" '"permissionDecision": "ask"' "$hook_embedded"

# --- command prompts invoke the ledger by its bare name, not via ${CLAUDE_PLUGIN_ROOT} ---
# ${CLAUDE_PLUGIN_ROOT} only expands in JSON-config-driven processes (hooks.json,
# MCP/LSP configs) that the harness spawns directly — never in commands/*.md body
# text, which the model runs verbatim through the Bash tool (upstream Claude Code
# limitation, anthropics/claude-code#9354). A plugin's bin/ IS added to the Bash
# tool's PATH while the plugin is enabled, so the bare name is what actually
# resolves at runtime (see #83).
prefixed=$(grep -rnF "\${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger" "$ROOT/commands" 2>/dev/null || true)
check "no command invokes gate-ledger via \${CLAUDE_PLUGIN_ROOT}" "" "$prefixed"

# --- record from a subdirectory still anchors the ledger at the repo root (#55) ---
d7=$(sandbox)
mkdir -p "$d7/sub/dir"
( cd "$d7/sub/dir" && "$LEDGER" record --gate audit --verdict PASS )
check "record from a subdirectory writes the ledger at the repo root" "yes" \
  "$([ -f "$d7/.studious/gates/feat-foo.json" ] && echo yes || echo no)"
check "record from a subdirectory does not write under the subdirectory" "no" \
  "$([ -f "$d7/sub/dir/.studious/gates/feat-foo.json" ] && echo yes || echo no)"
out=$(cd "$d7" && "$LEDGER" status)
contains "status run from repo root sees a ledger written from a subdirectory" "acceptance never ran" "$out"

# --- record stamps schemaVersion, and preserves it on upsert (#55) ---
f7="$d7/.studious/gates/feat-foo.json"
check "record sets schemaVersion on the new file" "1" "$(jq -r '.schemaVersion' "$f7")"
( cd "$d7/sub/dir" && "$LEDGER" record --gate acceptance --verdict SHIP )
check "record preserves schemaVersion on upsert" "1" "$(jq -r '.schemaVersion' "$f7")"

# --- status treats a branch-slug collision as no record, not a stale/wrong verdict (#41) ---
d9=$(sandbox)
( cd "$d9" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d9" && "$LEDGER" record --gate acceptance --verdict SHIP )
f9="$d9/.studious/gates/feat-foo.json"
# Simulate the collision: feat/foo and feat-foo both slug to feat-foo.json. Rewrite
# the stored .branch to a different branch than the one we're actually on.
tmp9=$(mktemp)
jq '.branch = "feat-foo"' "$f9" > "$tmp9" && mv "$tmp9" "$f9"
out=$(cd "$d9" && "$LEDGER" status)
contains "branch-slug collision reports audit as never ran" "audit never ran on this branch" "$out"
contains "branch-slug collision reports acceptance as never ran" "acceptance never ran on this branch" "$out"

# --- gc prunes ledgers for branches that no longer exist, keeps live ones (#42) ---
d10=$(sandbox)
( cd "$d10" && "$LEDGER" record --gate audit --verdict PASS )
stale10="$d10/.studious/gates/ghost-branch.json"
printf '{"schemaVersion":1,"branch":"ghost/branch","gates":{}}' > "$stale10"
out=$(cd "$d10" && "$LEDGER" gc)
contains "gc reports the removed stale ledger" "removed stale ledger: ghost-branch.json (branch ghost/branch no longer exists)" "$out"
check "gc deletes the stale ledger file" "no" "$([ -f "$stale10" ] && echo yes || echo no)"
check "gc keeps the ledger for a live branch" "yes" \
  "$([ -f "$d10/.studious/gates/feat-foo.json" ] && echo yes || echo no)"

# --- record signals on stderr (but still returns 0) when jq is unavailable (#43) ---
d11=$(sandbox)
fakebin=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$fakebin/$tool"
done
stderr11=$(cd "$d11" && PATH="$fakebin" "$LEDGER" record --gate audit --verdict PASS 2>&1 1>/dev/null)
contains "record signals on stderr when jq is unavailable" "gate-ledger: record skipped (jq and git required)" "$stderr11"
check "record does not create a ledger file when jq is unavailable" "no" \
  "$([ -f "$d11/.studious/gates/feat-foo.json" ] && echo yes || echo no)"

# --- work-set creates a slugged work file with fields and timestamps ---
d12=$(sandbox)
( cd "$d12" && "$LEDGER" work-set --slug "Fancy Feature!!" --title "Fancy feature" --source "issue #7" --phase decide )
wf12="$d12/.studious/work/fancy-feature.json"
check "work-set slugs the filename" "yes" "$([ -f "$wf12" ] && echo yes || echo no)"
check "work-set stores title" "Fancy feature" "$(jq -r '.title' "$wf12")"
check "work-set stores source" "issue #7" "$(jq -r '.source' "$wf12")"
check "work-set stores phase" "decide" "$(jq -r '.phase' "$wf12")"
check "work-set stamps schemaVersion" "1" "$(jq -r '.schemaVersion' "$wf12")"
check "work-set stamps createdAt" "yes" "$([ "$(jq -r '.createdAt' "$wf12")" != "null" ] && echo yes || echo no)"
contains "work-set self-heals .gitignore" ".studious/" "$(cat "$d12/.gitignore")"

# --- work-set upserts: later fields land, earlier fields survive ---
( cd "$d12" && "$LEDGER" work-set --slug fancy-feature --branch feat/foo --phase build )
check "work-set upsert adds branch" "feat/foo" "$(jq -r '.branch' "$wf12")"
check "work-set upsert moves phase" "build" "$(jq -r '.phase' "$wf12")"
check "work-set upsert keeps title" "Fancy feature" "$(jq -r '.title' "$wf12")"

# --- work-log appends history with the HEAD sha and can set phase ---
( cd "$d12" && "$LEDGER" work-log --slug fancy-feature --step audit --outcome PASS --phase acceptance )
check "work-log appends a history entry" "1" "$(jq -r '.history | length' "$wf12")"
check "work-log stores step" "audit" "$(jq -r '.history[0].step' "$wf12")"
check "work-log stores outcome" "PASS" "$(jq -r '.history[0].outcome' "$wf12")"
check "work-log stores HEAD sha" "$(git -C "$d12" rev-parse --short HEAD)" "$(jq -r '.history[0].sha' "$wf12")"
check "work-log sets phase" "acceptance" "$(jq -r '.phase' "$wf12")"

# --- work-get prints the file; work-list summarizes it ---
out=$(cd "$d12" && "$LEDGER" work-get --slug fancy-feature)
contains "work-get prints the work file" '"slug": "fancy-feature"' "$out"
out=$(cd "$d12" && "$LEDGER" work-list)
contains "work-list reports slug and phase" "$(printf 'fancy-feature\tacceptance')" "$out"

# --- gc prunes work files for deleted branches, keeps branchless and live ones ---
d13=$(sandbox)
( cd "$d13" && "$LEDGER" work-set --slug live-work --branch feat/foo --phase build )
( cd "$d13" && "$LEDGER" work-set --slug ghost-work --branch ghost/branch --phase build )
( cd "$d13" && "$LEDGER" work-set --slug early-work --phase decide )
out=$(cd "$d13" && "$LEDGER" gc)
contains "gc reports the removed stale work file" "removed stale work file: ghost-work.json (branch ghost/branch no longer exists)" "$out"
check "gc deletes the stale work file" "no" "$([ -f "$d13/.studious/work/ghost-work.json" ] && echo yes || echo no)"
check "gc keeps the work file for a live branch" "yes" "$([ -f "$d13/.studious/work/live-work.json" ] && echo yes || echo no)"
check "gc keeps a branchless (pre-branch) work file" "yes" "$([ -f "$d13/.studious/work/early-work.json" ] && echo yes || echo no)"

# --- work-set signals on stderr (but still returns 0) when jq is unavailable ---
d14=$(sandbox)
stderr14=$(cd "$d14" && PATH="$fakebin" "$LEDGER" work-set --slug x --phase decide 2>&1 1>/dev/null)
contains "work-set signals on stderr when jq is unavailable" "gate-ledger: work-set skipped (jq and git required)" "$stderr14"
check "work-set does not create a work file when jq is unavailable" "no" \
  "$([ -f "$d14/.studious/work/x.json" ] && echo yes || echo no)"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
