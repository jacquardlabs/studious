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

# --- record --blocking-lanes (delta-scoped re-audit, #130) ---
dbl=$(sandbox)
fbl="$dbl/.studious/gates/feat-foo.json"
( cd "$dbl" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" --blocking-lanes "security-auditor, test-auditor" )
check "blockingLanes stored as a trimmed JSON array" '["security-auditor","test-auditor"]' "$(jq -c '.gates.audit.blockingLanes' "$fbl")"
( cd "$dbl" && "$LEDGER" record --gate audit --verdict PASS )
check "a later record with no --blocking-lanes drops the field (no stale carryover)" "null" "$(jq -c '.gates.audit.blockingLanes' "$fbl")"
( cd "$dbl" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
check "--blocking-lanes is optional even on FIX AND RE-AUDIT (field absent, not empty array)" "null" "$(jq -c '.gates.audit.blockingLanes' "$fbl")"
( cd "$dbl" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" --blocking-lanes "  security-auditor ,, code-auditor  " )
check "blockingLanes trims whitespace and drops empty entries from stray commas" '["security-auditor","code-auditor"]' "$(jq -c '.gates.audit.blockingLanes' "$fbl")"

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

# --- status: pre-mortem is an advisory gate — silent when absent (#100) ---
dpm1=$(sandbox)
( cd "$dpm1" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm1" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$dpm1" && "$LEDGER" status)
check "status is unchanged on a branch with no recorded pre-mortem verdict" \
  "audit (PASS) and acceptance (SHIP) ran on this branch at HEAD — proceed." "$out"

# --- status: pre-mortem CLEAR at HEAD is also silent — the clean state, like absence (#100) ---
dpm2=$(sandbox)
( cd "$dpm2" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm2" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dpm2" && "$LEDGER" record --gate pre-mortem --verdict CLEAR )
out=$(cd "$dpm2" && "$LEDGER" status)
check "a recorded CLEAR pre-mortem verdict does not change the proceed message" \
  "audit (PASS) and acceptance (SHIP) ran on this branch at HEAD — proceed." "$out"

# --- status: pre-mortem REALIZED at HEAD is flagged (#100) ---
dpm3=$(sandbox)
( cd "$dpm3" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm3" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dpm3" && "$LEDGER" record --gate pre-mortem --verdict REALIZED )
out=$(cd "$dpm3" && "$LEDGER" status)
contains "status flags a REALIZED pre-mortem verdict recorded at HEAD" "pre-mortem returned REALIZED" "$out"

# --- status: stale pre-mortem verdict reuses the existing staleness wording verbatim (#100) ---
dpm4=$(sandbox)
( cd "$dpm4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dpm4" && "$LEDGER" record --gate pre-mortem --verdict REALIZED )
( cd "$dpm4" && git commit -q --allow-empty -m more )
out=$(cd "$dpm4" && "$LEDGER" status)
contains "status flags a stale pre-mortem verdict" "pre-mortem ran 1 commit ago — re-run before merging" "$out"

# --- status: branch-slug collision voids a recorded pre-mortem verdict too, silently (#100) ---
dpm5=$(sandbox)
( cd "$dpm5" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm5" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dpm5" && "$LEDGER" record --gate pre-mortem --verdict REALIZED )
fpm5="$dpm5/.studious/gates/feat-foo.json"
tmppm5=$(mktemp)
jq '.branch = "feat-foo"' "$fpm5" > "$tmppm5" && mv "$tmppm5" "$fpm5"
out=$(cd "$dpm5" && "$LEDGER" status)
check "branch-slug collision voids a REALIZED pre-mortem verdict without warning about it" \
  "Studious gate check — audit never ran on this branch; acceptance never ran on this branch. Proceed anyway?" "$out"

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

# --- hook warns when a REALIZED pre-mortem verdict is recorded at HEAD (#100) ---
dpm6=$(sandbox)
( cd "$dpm6" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$dpm6" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$dpm6" && "$LEDGER" record --gate pre-mortem --verdict REALIZED )
hook_pm=$(cd "$dpm6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh pr create"}}')
contains "hook reason names a REALIZED pre-mortem verdict recorded at HEAD" "pre-mortem returned REALIZED" "$hook_pm"

# --- hook does not regress to a false pre-mortem warning on a plain, non-epic branch (#100) ---
hook_plain=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh pr create"}}')
check "hook reason on a plain branch with no pre-mortem key never mentions pre-mortem" "no" \
  "$(case "$hook_plain" in (*pre-mortem*) echo yes ;; (*) echo no ;; esac)"

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

# --- epic-set creates a slugged epic file with fields and defaults ---
d15=$(sandbox)
( cd "$d15" && "$LEDGER" epic-set --slug "Checkout Revamp!!" --title "Checkout revamp" \
    --source "milestone 4" --goal "Users can pay without leaving the cart" \
    --branch epic/checkout-revamp --concurrency 3 --status approved )
ef15="$d15/.studious/epics/checkout-revamp.json"
check "epic-set slugs the filename" "yes" "$([ -f "$ef15" ] && echo yes || echo no)"
check "epic-set stores title" "Checkout revamp" "$(jq -r '.title' "$ef15")"
check "epic-set stores goal" "Users can pay without leaving the cart" "$(jq -r '.goal' "$ef15")"
check "epic-set stores branch" "epic/checkout-revamp" "$(jq -r '.branch' "$ef15")"
check "epic-set stores concurrency as a number" "3" "$(jq '.concurrency' "$ef15")"
check "epic-set stores status" "approved" "$(jq -r '.status' "$ef15")"
check "epic-set initializes empty stories" "{}" "$(jq -c '.stories' "$ef15")"
check "epic-set stamps schemaVersion" "1" "$(jq -r '.schemaVersion' "$ef15")"
check "epic-set stamps createdAt" "yes" "$([ "$(jq -r '.createdAt' "$ef15")" != "null" ] && echo yes || echo no)"
contains "epic-set self-heals .gitignore" ".studious/" "$(cat "$d15/.gitignore")"

# --- epic-set upserts: later fields land, earlier fields survive ---
( cd "$d15" && "$LEDGER" epic-set --slug checkout-revamp --status running )
check "epic-set upsert moves status" "running" "$(jq -r '.status' "$ef15")"
check "epic-set upsert keeps title" "Checkout revamp" "$(jq -r '.title' "$ef15")"

# --- epic-get prints the epic file; empty when absent ---
out=$(cd "$d15" && "$LEDGER" epic-get --slug checkout-revamp)
contains "epic-get prints the epic file" '"slug": "checkout-revamp"' "$out"
check "epic-get empty when no epic exists" "" "$(cd "$d15" && "$LEDGER" epic-get --slug nope)"

# --- epic-set rejects a non-integer --concurrency before touching any file ---
derr=$(sandbox)
err=$(cd "$derr" && "$LEDGER" epic-set --slug x --concurrency banana 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-set rejects non-integer --concurrency" "gate-ledger: --concurrency must be a positive integer" "$err"
contains "epic-set --concurrency banana exits 2" "rc=2" "$err"
check "epic-set does not create an epic file for a rejected --concurrency" "no" \
  "$([ -f "$derr/.studious/epics/x.json" ] && echo yes || echo no)"

# --- epic-set rejects zero --concurrency ---
err0=$(cd "$derr" && "$LEDGER" epic-set --slug x --concurrency 0 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-set rejects zero --concurrency" "gate-ledger: --concurrency must be a positive integer" "$err0"
contains "epic-set --concurrency 0 exits 2" "rc=2" "$err0"
check "epic-set does not create an epic file for --concurrency 0" "no" \
  "$([ -f "$derr/.studious/epics/x.json" ] && echo yes || echo no)"

# --- epic-set signals on stderr (but still returns 0) when jq is unavailable ---
d16=$(sandbox)
stderr16=$(cd "$d16" && PATH="$fakebin" "$LEDGER" epic-set --slug x 2>&1 1>/dev/null)
contains "epic-set signals on stderr when jq is unavailable" "gate-ledger: epic-set skipped (jq and git required)" "$stderr16"
check "epic-set does not create an epic file when jq is unavailable" "no" \
  "$([ -f "$d16/.studious/epics/x.json" ] && echo yes || echo no)"

# --- epic-story-set requires an existing epic file ---
err=$(cd "$d15" && "$LEDGER" epic-story-set --epic missing-epic --slug s1 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-story-set errors on unknown epic" "no epic file" "$err"
contains "epic-story-set exits 2 on unknown epic" "rc=2" "$err"

# --- epic-story-set adds a story with defaults ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --title "Cart API" \
    --source "issue #12" --criteria "POST /cart returns 201 with a cart id" \
    --gates "design,design-review,build,audit,acceptance" )
check "story lands under its slug" "Cart API" "$(jq -r '.stories["cart-api"].title' "$ef15")"
check "story stores criteria" "POST /cart returns 201 with a cart id" "$(jq -r '.stories["cart-api"].criteria' "$ef15")"
check "story status defaults to pending" "pending" "$(jq -r '.stories["cart-api"].status' "$ef15")"
check "story deps default to empty array" "[]" "$(jq -c '.stories["cart-api"].deps' "$ef15")"
check "story retries default to empty object" "{}" "$(jq -c '.stories["cart-api"].retries' "$ef15")"
check "story gates split to an array" "5" "$(jq '.stories["cart-api"].gates | length' "$ef15")"

# --- deps split on commas, trimming whitespace ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug checkout-ui --title "Checkout UI" \
    --deps "cart-api, payment-svc" )
check "deps split to a trimmed array" '["cart-api","payment-svc"]' "$(jq -c '.stories["checkout-ui"].deps' "$ef15")"

# --- decisions: the Plan piece's front-loaded fork answers ride alongside criteria ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --decisions "surface: REST not GraphQL; guest carts: out of scope" )
check "story stores decisions" "surface: REST not GraphQL; guest carts: out of scope" \
  "$(jq -r '.stories["cart-api"].decisions' "$ef15")"
check "decisions do not disturb criteria" "POST /cart returns 201 with a cart id" \
  "$(jq -r '.stories["cart-api"].criteria' "$ef15")"

# --- a later criteria-only write must not clobber decisions (they are separate fields) ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --criteria "POST /cart returns 201 and a Location header" )
check "criteria update leaves decisions intact" "surface: REST not GraphQL; guest carts: out of scope" \
  "$(jq -r '.stories["cart-api"].decisions' "$ef15")"

# --- a story with no answered forks carries no decisions key at all ---
check "decisions absent when never set" "null" "$(jq -r '.stories["checkout-ui"].decisions // "null"' "$ef15")"

# --- carried-findings: a diagnosis carried forward from a prior gate round,
# stored distinctly from decisions (issue #245) ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --carried-findings "round-2 walkthrough: missing null check on cart.items, file:line" )
check "story stores carried-findings" "round-2 walkthrough: missing null check on cart.items, file:line" \
  "$(jq -r '.stories["cart-api"].carriedFindings' "$ef15")"
check "carried-findings do not disturb decisions" "surface: REST not GraphQL; guest carts: out of scope" \
  "$(jq -r '.stories["cart-api"].decisions' "$ef15")"
check "carried-findings do not disturb criteria" "POST /cart returns 201 and a Location header" \
  "$(jq -r '.stories["cart-api"].criteria' "$ef15")"

# --- a later decisions-only write must not clobber carried-findings (separate fields) ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --decisions "surface: REST not GraphQL; guest carts: out of scope" )
check "decisions update leaves carried-findings intact" "round-2 walkthrough: missing null check on cart.items, file:line" \
  "$(jq -r '.stories["cart-api"].carriedFindings' "$ef15")"

# --- a story with no carried findings carries no carriedFindings key at all ---
check "carried-findings absent when never set" "null" "$(jq -r '.stories["checkout-ui"].carriedFindings // "null"' "$ef15")"

# --- story upsert: status/reason land, earlier fields survive ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --status parked --reason "audit: NEEDS DISCUSSION - auth model unclear" )
check "story upsert moves status" "parked" "$(jq -r '.stories["cart-api"].status' "$ef15")"
check "story upsert stores reason" "audit: NEEDS DISCUSSION - auth model unclear" "$(jq -r '.stories["cart-api"].reason' "$ef15")"
check "story upsert keeps title" "Cart API" "$(jq -r '.stories["cart-api"].title' "$ef15")"

# --- bump-retry increments a per-gate counter ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --bump-retry audit )
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --bump-retry audit )
check "bump-retry increments the gate counter" "2" "$(jq '.stories["cart-api"].retries.audit' "$ef15")"

# --- reset-retry zeroes a bumped gate counter ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --reset-retry audit )
check "reset-retry zeroes the gate counter" "0" "$(jq '.stories["cart-api"].retries.audit' "$ef15")"

# --- reset-retry on a never-bumped gate yields 0 without error ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --reset-retry design )
check "reset-retry on a never-bumped gate yields 0" "0" "$(jq '.stories["cart-api"].retries.design' "$ef15")"

# --- epic-list summarizes landed/total per epic ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug checkout-ui --status landed )
out=$(cd "$d15" && "$LEDGER" epic-list)
contains "epic-list reports slug, status, and landed count" "$(printf 'checkout-revamp\trunning\t1/2')" "$out"

# --- epic-reconcile: basic shape — stories keyed by bare slug, .epic
# byte-identical to a bare epic-get call, work/gate null when absent,
# storyBranchHeadSha empty when the branch doesn't exist yet, designDocExists
# null when no designDoc is recorded, landedButUnmerged false for a
# non-landed story (#160) ---
d40=$(sandbox)
( cd "$d40" && "$LEDGER" epic-set --slug er-epic --title "ER Epic" --status running )
( cd "$d40" && "$LEDGER" epic-story-set --epic er-epic --slug s1 --title "S1" )
( cd "$d40" && "$LEDGER" epic-story-set --epic er-epic --slug s2 --title "S2" )
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "epic-reconcile keys stories by the bare story slug" "s1,s2" \
  "$(printf '%s' "$out" | jq -r '.stories | keys | sort | join(",")')"
epicget=$(cd "$d40" && "$LEDGER" epic-get --slug er-epic | jq -S .)
epicin=$(printf '%s' "$out" | jq -S '.epic')
check "epic-reconcile's .epic is byte-identical to a bare epic-get call" "$epicget" "$epicin"
check "a story with no work file recorded gets a null .work" "null" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.work')"
check "a story with no gate ever recorded gets a null .gate" "null" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.gate')"
check "a story whose branch doesn't exist yet gets an empty storyBranchHeadSha" "" \
  "$(printf '%s' "$out" | jq -r '.stories.s1.storyBranchHeadSha')"
check "a story with no designDoc recorded gets a null designDocExists" "null" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.designDocExists')"
check "a pending story gets landedButUnmerged: false" "false" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.landedButUnmerged')"

# --- epic-reconcile: work and gate are populated verbatim, and
# storyBranchHeadSha resolves once the story branch exists (#160) ---
( cd "$d40" && git checkout -q -b epic/er-epic--s1 )
( cd "$d40" && "$LEDGER" work-set --slug "er-epic--s1" --design-doc "docs/design-s1.md" )
( cd "$d40" && "$LEDGER" record --gate audit --verdict PASS )
s1sha=$(git -C "$d40" rev-parse --short epic/er-epic--s1)
git -C "$d40" checkout -q feat/foo
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "epic-reconcile carries the story's work-get payload verbatim" "docs/design-s1.md" \
  "$(printf '%s' "$out" | jq -r '.stories.s1.work.designDoc')"
check "epic-reconcile carries the story's gate-get payload verbatim" "PASS" \
  "$(printf '%s' "$out" | jq -r '.stories.s1.gate.gates.audit.verdict')"
check "epic-reconcile resolves storyBranchHeadSha once the story branch exists" "$s1sha" \
  "$(printf '%s' "$out" | jq -r '.stories.s1.storyBranchHeadSha')"

# --- epic-reconcile: designDocExists — true when the recorded path exists in
# the story's own worktree, false when recorded but absent, and null (not a
# crash or a false "false") when the worktree directory itself is gone —
# the graceful-degrade path the design doc's open questions called out (#160) ---
mkdir -p "$d40/.studious/worktrees/er-epic/s1/docs"
echo "design doc" > "$d40/.studious/worktrees/er-epic/s1/docs/design-s1.md"
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "designDocExists is true when the recorded path exists in the story worktree" "true" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.designDocExists')"
rm "$d40/.studious/worktrees/er-epic/s1/docs/design-s1.md"
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "designDocExists is false when recorded but the file is absent" "false" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.designDocExists')"
rm -rf "$d40/.studious/worktrees/er-epic/s1"
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "designDocExists degrades to null (not a crash, not false) when the story worktree itself is gone" "null" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.designDocExists')"

# --- epic-reconcile: designDocExists checks the __epic worktree, not the
# story's own, once a story is recorded landed (its own worktree is removed
# on merge — see the design doc) ---
( cd "$d40" && "$LEDGER" epic-story-set --epic er-epic --slug s1 --status landed )
mkdir -p "$d40/.studious/worktrees/er-epic/__epic/docs"
echo "design doc" > "$d40/.studious/worktrees/er-epic/__epic/docs/design-s1.md"
out=$(cd "$d40" && "$LEDGER" epic-reconcile --slug er-epic)
check "designDocExists checks the __epic worktree for a landed story" "true" \
  "$(printf '%s' "$out" | jq -c '.stories.s1.designDocExists')"

# --- epic-reconcile: landedButUnmerged — a story recorded landed IS flagged
# false when its branch is a real ancestor of the epic branch, and flagged
# true when it isn't (mirrors today's `git log --oneline` check; a landed
# story whose merge isn't actually on the epic branch is still surfaced, not
# silently trusted — acceptance criterion 3, #160) ---
d41=$(sandbox)
git -C "$d41" checkout -q -b epic/lbu
git -C "$d41" checkout -q -b epic/lbu--merged
git -C "$d41" commit -q --allow-empty -m "merged story work"
git -C "$d41" checkout -q epic/lbu
git -C "$d41" merge -q --no-ff epic/lbu--merged -m "merge merged story"
git -C "$d41" checkout -q -b epic/lbu--unmerged
git -C "$d41" commit -q --allow-empty -m "unmerged story work"
git -C "$d41" checkout -q epic/lbu
( cd "$d41" && "$LEDGER" epic-set --slug lbu --title "LBU Epic" --status running )
( cd "$d41" && "$LEDGER" epic-story-set --epic lbu --slug merged --title "Merged" --status landed )
( cd "$d41" && "$LEDGER" epic-story-set --epic lbu --slug unmerged --title "Unmerged" --status landed )
out=$(cd "$d41" && "$LEDGER" epic-reconcile --slug lbu)
check "landedButUnmerged is false when the landed story's merge is a real ancestor of the epic branch" "false" \
  "$(printf '%s' "$out" | jq -c '.stories.merged.landedButUnmerged')"
check "landedButUnmerged is true when a landed story's branch was never actually merged" "true" \
  "$(printf '%s' "$out" | jq -c '.stories.unmerged.landedButUnmerged')"

# --- epic-reconcile: empty stories object round-trips as {} ---
d42=$(sandbox)
( cd "$d42" && "$LEDGER" epic-set --slug empty-epic --title "Empty Epic" --status approved )
out=$(cd "$d42" && "$LEDGER" epic-reconcile --slug empty-epic)
check "epic-reconcile on an epic with no stories yet returns an empty stories object" "{}" \
  "$(printf '%s' "$out" | jq -c '.stories')"

# --- epic-reconcile: --slug is required ---
d43=$(sandbox)
err=$(cd "$d43" && "$LEDGER" epic-reconcile 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-reconcile requires --slug" "gate-ledger: --slug required" "$err"
contains "epic-reconcile --slug missing exits 2" "rc=2" "$err"

# --- epic-reconcile: unknown epic slug prints nothing (mirrors epic-get) ---
out=$(cd "$d43" && "$LEDGER" epic-reconcile --slug nope)
check "epic-reconcile on an unknown epic prints nothing" "" "$out"

# --- epic-reconcile signals on stderr (but still returns 0) when jq is
# unavailable, mirroring every other verb's degrade behavior ---
( cd "$d43" && "$LEDGER" epic-set --slug jq-epic --title "JQ Epic" --status approved )
stderr43=$(cd "$d43" && PATH="$fakebin" "$LEDGER" epic-reconcile --slug jq-epic 2>&1 1>/dev/null)
contains "epic-reconcile signals on stderr when jq is unavailable" \
  "gate-ledger: epic-reconcile skipped (jq and git required)" "$stderr43"

# --- epic-reconcile fails closed (non-zero exit, stderr naming the story and
# epic) when a per-story sub-read hits a corrupted stored file, rather than
# silently guessing whether an absent/false value means "legitimately
# absent" or "read failed" (build-phase resolution of the design doc's open
# question, #160) ---
d44=$(sandbox)
( cd "$d44" && "$LEDGER" epic-set --slug corrupt-epic --title "Corrupt Epic" --status running )
( cd "$d44" && "$LEDGER" epic-story-set --epic corrupt-epic --slug s1 --title "S1" )
mkdir -p "$d44/.studious/work"
echo "not json" > "$d44/.studious/work/corrupt-epic-s1.json"
err=$(cd "$d44" && "$LEDGER" epic-reconcile --slug corrupt-epic 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-reconcile fails closed on a corrupted work file" \
  "corrupted work file for story 's1' (epic 'corrupt-epic')" "$err"
contains "epic-reconcile exits non-zero on a corrupted work file" "rc=1" "$err"

d45=$(sandbox)
( cd "$d45" && "$LEDGER" epic-set --slug corrupt-epic2 --title "Corrupt Epic 2" --status running )
( cd "$d45" && "$LEDGER" epic-story-set --epic corrupt-epic2 --slug s1 --title "S1" )
mkdir -p "$d45/.studious/gates"
echo "not json" > "$d45/.studious/gates/epic-corrupt-epic2--s1.json"
err=$(cd "$d45" && "$LEDGER" epic-reconcile --slug corrupt-epic2 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-reconcile fails closed on a corrupted gate ledger file" \
  "corrupted gate ledger for story 's1' (epic 'corrupt-epic2')" "$err"
contains "epic-reconcile exits non-zero on a corrupted gate ledger file" "rc=1" "$err"

d46=$(sandbox)
mkdir -p "$d46/.studious/epics"
echo "not json" > "$d46/.studious/epics/corrupt-epic3.json"
err=$(cd "$d46" && "$LEDGER" epic-reconcile --slug corrupt-epic3 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-reconcile fails closed on a corrupted epic file" \
  "corrupted epic file for 'corrupt-epic3'" "$err"
contains "epic-reconcile exits non-zero on a corrupted epic file" "rc=1" "$err"

# --- epic-reconcile anchors to the MAIN working tree across linked
# worktrees, exactly like every other read verb (#98) ---
d47=$(sandbox)
( cd "$d47" && "$LEDGER" epic-set --slug anchor-epic --title "Anchor Epic" --status running )
( cd "$d47" && "$LEDGER" epic-story-set --epic anchor-epic --slug s1 --title "S1" )
( cd "$d47" && git worktree add -q "$d47/.studious/worktrees/anchor-epic/s1" -b epic/anchor-epic--s1 )
out=$(cd "$d47/.studious/worktrees/anchor-epic/s1" && "$LEDGER" epic-reconcile --slug anchor-epic)
check "epic-reconcile from a linked worktree still reads the MAIN root epic state" "anchor-epic" \
  "$(printf '%s' "$out" | jq -r '.epic.slug')"
check "epic-reconcile from a linked worktree still sees the story's own branch head sha" \
  "$(git -C "$d47" rev-parse --short epic/anchor-epic--s1)" \
  "$(printf '%s' "$out" | jq -r '.stories.s1.storyBranchHeadSha')"

# --- worktree-path: the single owner of .studious/worktrees/<epic>/{__epic,<story>}
# (#166). Everything that used to compose this layout by hand — epic-driver.js
# (via work-through.md and the args boundary), work-through.md's own worktree
# add/remove steps, and epic-reconcile's designDocExists lookup — asks here. ---
d48=$(sandbox)
check "worktree-path with no --story resolves the __epic integration worktree" \
  "$d48/.studious/worktrees/wp-epic/__epic" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic)"
check "worktree-path --story resolves that story's worktree" \
  "$d48/.studious/worktrees/wp-epic/s1" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --story s1)"
check "worktree-path answers for an epic with no recorded state at all" \
  "$d48/.studious/worktrees/never-recorded/__epic" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug never-recorded)"
check "worktree-path slugifies its --slug at the boundary like every sibling verb" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic)" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug "WP Epic")"
check "worktree-path slugifies its --story at the boundary too" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --story story-one)" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --story "Story One")"

err=$(cd "$d48" && "$LEDGER" worktree-path 2>&1 1>/dev/null; echo "rc=$?")
contains "worktree-path requires --slug" "--slug required" "$err"
contains "worktree-path exits 2 without --slug" "rc=2" "$err"
err=$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --story s1 --json 2>&1 1>/dev/null; echo "rc=$?")
contains "worktree-path refuses --story together with --json" "mutually exclusive" "$err"
contains "worktree-path exits 2 on --story with --json" "rc=2" "$err"

# --json: the whole layout for one epic, the form work-through.md hands the
# driver (which has no exec access of its own and so cannot ask for paths).
( cd "$d48" && "$LEDGER" epic-set --slug wp-epic --title "WP Epic" --status running )
( cd "$d48" && "$LEDGER" epic-story-set --epic wp-epic --slug s1 --title "S1" )
( cd "$d48" && "$LEDGER" epic-story-set --epic wp-epic --slug s2 --title "S2" )
out=$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --json)
check "worktree-path --json names the __epic worktree" "$d48/.studious/worktrees/wp-epic/__epic" \
  "$(printf '%s' "$out" | jq -r '.epic')"
check "worktree-path --json carries every recorded story" "s1 s2" \
  "$(printf '%s' "$out" | jq -r '.stories | keys | join(" ")')"
check "worktree-path --json agrees with the single-path form for a story" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug wp-epic --story s1)" \
  "$(printf '%s' "$out" | jq -r '.stories.s1')"
check "worktree-path --json prints nothing for an epic that was never recorded" "" \
  "$(cd "$d48" && "$LEDGER" worktree-path --slug no-such-epic --json)"

d49=$(sandbox)
mkdir -p "$d49/.studious/epics"
echo "not json" > "$d49/.studious/epics/wp-corrupt.json"
err=$(cd "$d49" && "$LEDGER" worktree-path --slug wp-corrupt --json 2>&1 1>/dev/null; echo "rc=$?")
contains "worktree-path --json fails closed on a corrupted epic file" \
  "corrupted epic file for 'wp-corrupt'" "$err"
contains "worktree-path --json exits non-zero on a corrupted epic file" "rc=1" "$err"

# worktree-path anchors to the MAIN working tree like every other verb (#98):
# a story worker running inside its own linked checkout must name its siblings'
# checkouts exactly as the driver does, not relative to where it happens to stand.
d50=$(sandbox)
( cd "$d50" && "$LEDGER" epic-set --slug anchor-wp --title "Anchor WP" --status running )
( cd "$d50" && "$LEDGER" epic-story-set --epic anchor-wp --slug s1 --title "S1" )
( cd "$d50" && git worktree add -q "$d50/.studious/worktrees/anchor-wp/s1" -b epic/anchor-wp--s1 )
wp_linked="$d50/.studious/worktrees/anchor-wp/s1"
# Compared against the PHYSICALLY resolved main root: repo_root() reads a linked
# worktree's gitdir, which git stores fully resolved, so on macOS the answer comes
# back under /private/var where the main root's own answer says /var. Same
# directory, different spelling — pre-existing, shared by all five stores, and not
# what this test is about.
wp_main_phys=$(cd "$d50" && pwd -P)
check "worktree-path from a linked worktree still resolves against the MAIN root" \
  "$wp_main_phys/.studious/worktrees/anchor-wp/__epic" \
  "$(cd "$wp_linked" && "$LEDGER" worktree-path --slug anchor-wp)"
check "worktree-path --json from a linked worktree still resolves against the MAIN root" \
  "$wp_main_phys/.studious/worktrees/anchor-wp/s1" \
  "$(cd "$wp_linked" && "$LEDGER" worktree-path --slug anchor-wp --json | jq -r '.stories.s1')"
# The failure this actually guards: a CWD-relative implementation would answer with
# a path nested inside the caller's own checkout, fragmenting the layout per worktree.
case "$(cd "$wp_linked" && "$LEDGER" worktree-path --slug anchor-wp --story s2)" in
  "$wp_linked"/*) wp_nested=yes ;;
  *)              wp_nested=no ;;
esac
check "worktree-path never nests its answer inside the caller's own checkout" "no" "$wp_nested"

# --- state anchors to the main working tree across linked worktrees ---
d17=$(sandbox)
( cd "$d17" && git worktree add -q "$d17/.studious/worktrees/e/s" -b epic/e--s )
( cd "$d17/.studious/worktrees/e/s" && "$LEDGER" record --gate audit --verdict PASS )
check "record from a linked worktree writes the MAIN root ledger" "yes" \
  "$([ -f "$d17/.studious/gates/epic-e--s.json" ] && echo yes || echo no)"
check "record from a linked worktree does not write under the worktree" "no" \
  "$([ -f "$d17/.studious/worktrees/e/s/.studious/gates/epic-e--s.json" ] && echo yes || echo no)"
out=$(cd "$d17" && "$LEDGER" gate-get --branch epic/e--s)
contains "gate-get from the main root sees the worktree-recorded verdict" '"verdict": "PASS"' "$out"
check "self-heal touched only the main .gitignore" "no" \
  "$([ -f "$d17/.studious/worktrees/e/s/.gitignore" ] && echo yes || echo no)"
contains "main .gitignore self-healed" ".studious/" "$(cat "$d17/.gitignore")"

# --- json_update regression (#102): a mutating verb's exit code is 0
# immediately after a successful write. The written JSON's content alone
# doesn't prove this — a RETURN trap armed inside a shared writer function
# would still produce correct file content (the write happens before the
# trap could re-fire) while nonetheless corrupting the caller's exit status
# once the trap re-fires in the *calling* verb's frame under `set -u`. Also
# confirms the shared writer's temp file never survives a successful write.
drc=$(sandbox)
( cd "$drc" && "$LEDGER" record --gate audit --verdict PASS ); rc=$?
check "record exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" work-set --slug rc-work --phase decide ); rc=$?
check "work-set exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" work-log --slug rc-work --step build --outcome BUILT ); rc=$?
check "work-log exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" epic-set --slug rc-epic --title "RC Epic" ); rc=$?
check "epic-set exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" epic-story-set --epic rc-epic --slug rc-story --title "RC Story" ); rc=$?
check "epic-story-set exits 0 on a successful write" "0" "$rc"
check "no stray temp files left in the gates store after successful writes" "" \
  "$(find "$drc/.studious/gates" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the work store after successful writes" "" \
  "$(find "$drc/.studious/work" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the epics store after successful writes" "" \
  "$(find "$drc/.studious/epics" -name '.tmp.*' 2>/dev/null)"

# --- json_update regression (fix-and-re-audit on #102): a mutating verb's
# exit code is nonzero when the underlying jq/mv write actually fails. The
# original `if jq ... && mv ...; then return 0; fi` compound read $? on the
# statement right after the `if`/`fi` — but POSIX defines the exit status of
# an `if` whose condition is false and has no `else` as zero, not the
# condition's own status, so that read always saw 0 and every mutating verb
# reported success even when jq failed. Corrupting the on-disk JSON before a
# second write is a deterministic, permission-independent way to force jq to
# fail (a parse error), without relying on filesystem permission checks that
# root can bypass in CI.
dfail=$(sandbox)

( cd "$dfail" && "$LEDGER" record --gate audit --verdict PASS )
frec="$dfail/.studious/gates/feat-foo.json"
printf 'not json' > "$frec"
( cd "$dfail" && "$LEDGER" record --gate audit --verdict FAIL ) >/dev/null 2>&1; rc=$?
check "record exits nonzero when the write fails" "no" "$([ "$rc" -eq 0 ] && echo yes || echo no)"
check "record leaves a corrupted ledger untouched on failure" "not json" "$(cat "$frec")"

( cd "$dfail" && "$LEDGER" work-set --slug fail-work --phase decide )
fws="$dfail/.studious/work/fail-work.json"
printf 'not json' > "$fws"
( cd "$dfail" && "$LEDGER" work-set --slug fail-work --phase build ) >/dev/null 2>&1; rc=$?
check "work-set exits nonzero when the write fails" "no" "$([ "$rc" -eq 0 ] && echo yes || echo no)"
check "work-set leaves a corrupted work file untouched on failure" "not json" "$(cat "$fws")"

printf 'not json' > "$fws"
( cd "$dfail" && "$LEDGER" work-log --slug fail-work --step build --outcome BUILT ) >/dev/null 2>&1; rc=$?
check "work-log exits nonzero when the write fails" "no" "$([ "$rc" -eq 0 ] && echo yes || echo no)"
check "work-log leaves a corrupted work file untouched on failure" "not json" "$(cat "$fws")"

( cd "$dfail" && "$LEDGER" epic-set --slug fail-epic --title "Fail Epic" )
fes="$dfail/.studious/epics/fail-epic.json"
printf 'not json' > "$fes"
( cd "$dfail" && "$LEDGER" epic-set --slug fail-epic --status running ) >/dev/null 2>&1; rc=$?
check "epic-set exits nonzero when the write fails" "no" "$([ "$rc" -eq 0 ] && echo yes || echo no)"
check "epic-set leaves a corrupted epic file untouched on failure" "not json" "$(cat "$fes")"

# epic-story-set's own file-exists guard only checks presence, not validity —
# create the epic file while healthy, then corrupt it so the guard passes
# and json_update's own read is what fails.
( cd "$dfail" && "$LEDGER" epic-set --slug fail-story-epic --title "Fail Story Epic" )
fse="$dfail/.studious/epics/fail-story-epic.json"
printf 'not json' > "$fse"
( cd "$dfail" && "$LEDGER" epic-story-set --epic fail-story-epic --slug s1 --title "S1" ) >/dev/null 2>&1; rc=$?
check "epic-story-set exits nonzero when the write fails" "no" "$([ "$rc" -eq 0 ] && echo yes || echo no)"
check "epic-story-set leaves a corrupted epic file untouched on failure" "not json" "$(cat "$fse")"

check "no stray temp files left in the gates store after failed writes" "" \
  "$(find "$dfail/.studious/gates" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the work store after failed writes" "" \
  "$(find "$dfail/.studious/work" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the epics store after failed writes" "" \
  "$(find "$dfail/.studious/epics" -name '.tmp.*' 2>/dev/null)"

# --- evidence-append writes the pinned shape (reference/evidence-format.md) ---
d18=$(sandbox)
( cd "$d18" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:deadbeef" --origin interactive )
ef18="$d18/.studious/evidence/feat-foo.jsonl"
check "evidence-append creates the branch-slug .jsonl file" "yes" "$([ -f "$ef18" ] && echo yes || echo no)"
check "evidence-append writes exactly one line" "1" "$(wc -l < "$ef18" | tr -d ' ')"
line1=$(sed -n '1p' "$ef18")
check "record is valid single-line JSON" "yes" "$(printf '%s' "$line1" | jq -e . >/dev/null 2>&1 && echo yes || echo no)"
check "capturer is the hardcoded constant" "hook" "$(printf '%s' "$line1" | jq -r '.capturer')"
check "origin stores the given value" "interactive" "$(printf '%s' "$line1" | jq -r '.origin')"
check "agentType is omitted (not null) when not given" "yes" \
  "$(printf '%s' "$line1" | jq -e 'has("agentType") | not' >/dev/null 2>&1 && echo yes || echo no)"
check "command stores the given value" "pytest tests/" "$(printf '%s' "$line1" | jq -r '.command')"
check "exitCode stores the given value" "0" "$(printf '%s' "$line1" | jq -r '.exitCode')"
check "outputDigest stores the given value" "sha256:deadbeef" "$(printf '%s' "$line1" | jq -r '.outputDigest')"
check "predicateType is the in-toto test-result URL" "https://in-toto.io/attestation/test-result/v0.1" \
  "$(printf '%s' "$line1" | jq -r '.predicateType')"
check "predicate.result is PASSED for exit code 0" "PASSED" "$(printf '%s' "$line1" | jq -r '.predicate.result')"
check "predicate.configuration mirrors command" '["pytest tests/"]' \
  "$(printf '%s' "$line1" | jq -c '[.predicate.configuration[].name]')"
check "capturedAt is stamped (not null)" "yes" \
  "$([ "$(printf '%s' "$line1" | jq -r '.capturedAt')" != "null" ] && echo yes || echo no)"
check "record key order matches reference/evidence-format.md" \
  '["capturedAt","capturer","origin","command","exitCode","outputDigest","predicateType","predicate"]' \
  "$(printf '%s' "$line1" | jq -c 'keys_unsorted')"
contains "evidence-append self-heals .gitignore" ".studious/" "$(cat "$d18/.gitignore")"

# --- evidence-append: exit code 0 -> PASSED, non-zero -> FAILED ---
( cd "$d18" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 1 \
    --output-digest "sha256:cafebabe" --origin subagent --agent-type "epic-driver:build-worker" )
check "evidence-append appends (jsonl, not overwrite)" "2" "$(wc -l < "$ef18" | tr -d ' ')"
line2=$(sed -n '2p' "$ef18")
check "non-zero exit code maps to predicate.result FAILED" "FAILED" "$(printf '%s' "$line2" | jq -r '.predicate.result')"
check "exitCode stores the non-zero value" "1" "$(printf '%s' "$line2" | jq -r '.exitCode')"
check "origin stores subagent" "subagent" "$(printf '%s' "$line2" | jq -r '.origin')"
check "agentType is included when given" "epic-driver:build-worker" "$(printf '%s' "$line2" | jq -r '.agentType')"
check "agentType lands between origin and command (key order)" \
  '["capturedAt","capturer","origin","agentType","command","exitCode","outputDigest","predicateType","predicate"]' \
  "$(printf '%s' "$line2" | jq -c 'keys_unsorted')"

# --- evidence-append validates required args before writing anything ---
d19=$(sandbox)
err=$(cd "$d19" && "$LEDGER" evidence-append --command x 2>&1 1>/dev/null; echo "rc=$?")
contains "evidence-append requires all four flags" \
  "gate-ledger: --command, --exit-code, --output-digest, and --origin required" "$err"
contains "evidence-append missing-args exits 2" "rc=2" "$err"
check "evidence-append does not create a file on a rejected call" "no" \
  "$([ -f "$d19/.studious/evidence/feat-foo.jsonl" ] && echo yes || echo no)"

err=$(cd "$d19" && "$LEDGER" evidence-append --command x --exit-code abc \
  --output-digest sha256:x --origin interactive 2>&1 1>/dev/null; echo "rc=$?")
contains "evidence-append rejects a non-integer --exit-code" \
  "gate-ledger: --exit-code must be a non-negative integer" "$err"
contains "evidence-append non-integer --exit-code exits 2" "rc=2" "$err"

err=$(cd "$d19" && "$LEDGER" evidence-append --command x --exit-code 0 \
  --output-digest sha256:x --origin bogus 2>&1 1>/dev/null; echo "rc=$?")
contains "evidence-append rejects an --origin outside interactive|subagent" \
  "gate-ledger: --origin must be 'interactive' or 'subagent'" "$err"
contains "evidence-append invalid --origin exits 2" "rc=2" "$err"
check "no evidence file exists after every rejected call" "no" \
  "$([ -f "$d19/.studious/evidence/feat-foo.jsonl" ] && echo yes || echo no)"

# --- evidence-append signals on stderr (but still returns 0) when jq is unavailable ---
d20=$(sandbox)
stderr20=$(cd "$d20" && PATH="$fakebin" "$LEDGER" evidence-append --command x --exit-code 0 \
  --output-digest sha256:x --origin interactive 2>&1 1>/dev/null)
contains "evidence-append signals on stderr when jq is unavailable" \
  "gate-ledger: evidence-append skipped (jq and git required)" "$stderr20"
check "evidence-append does not create a file when jq is unavailable" "no" \
  "$([ -f "$d20/.studious/evidence/feat-foo.jsonl" ] && echo yes || echo no)"

# --- evidence-append anchors to the MAIN working tree across linked worktrees,
# exactly like record/work-set/epic-set (#worker-evidence-and-board) — this is
# the property a dispatched story worker's own process depends on: its cwd is
# a linked worktree, but the evidence it writes must land where the rest of
# the story's ledger state already lives. ---
d21=$(sandbox)
( cd "$d21" && git worktree add -q "$d21/.studious/worktrees/e/s" -b epic/e--s )
( cd "$d21/.studious/worktrees/e/s" && "$LEDGER" evidence-append --command "pytest tests/" \
    --exit-code 0 --output-digest "sha256:deadbeef" --origin subagent --agent-type "epic-driver:build-worker" )
check "evidence-append from a linked worktree writes the MAIN root evidence file" "yes" \
  "$([ -f "$d21/.studious/evidence/epic-e--s.jsonl" ] && echo yes || echo no)"
check "evidence-append from a linked worktree does not write under the worktree" "no" \
  "$([ -f "$d21/.studious/worktrees/e/s/.studious/evidence/epic-e--s.jsonl" ] && echo yes || echo no)"

# --- evidence-list is a plain passthrough of the branch's evidence log ---
d22=$(sandbox)
out=$(cd "$d22" && "$LEDGER" evidence-list)
check "evidence-list is empty (zero bytes) when no log exists for the branch" "" "$out"

( cd "$d22" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:deadbeef" --origin interactive )
out=$(cd "$d22" && "$LEDGER" evidence-list)
check "evidence-list returns exactly one line for one appended record" "1" \
  "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
check "evidence-list output is the raw record (command field readable via jq)" \
  "pytest tests/" "$(printf '%s' "$out" | jq -r '.command')"

( cd "$d22" && "$LEDGER" evidence-append --command "npm test" --exit-code 1 \
    --output-digest "sha256:cafebabe" --origin subagent --agent-type "epic-driver:build-worker" )
out=$(cd "$d22" && "$LEDGER" evidence-list)
check "evidence-list returns every appended record, in append order" "2" \
  "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
check "evidence-list's second line is the second appended record" "npm test" \
  "$(printf '%s' "$out" | sed -n '2p' | jq -r '.command')"

# byte-for-byte equivalence against the pre-populated file from evidence-append tests
out=$(cd "$d18" && "$LEDGER" evidence-list)
check "evidence-list output matches the raw .jsonl file byte-for-byte" \
  "$(cat "$ef18")" "$out"

# --- evidence-list --branch reads another branch's log without checking it out ---
d23=$(sandbox)
( cd "$d23" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:deadbeef" --origin interactive )
( cd "$d23" && git checkout -q -b feat/other )
out=$(cd "$d23" && "$LEDGER" evidence-list)
check "evidence-list with no --branch reads the current (different, logless) branch" "" "$out"
out=$(cd "$d23" && "$LEDGER" evidence-list --branch feat/foo)
check "evidence-list --branch reads the named branch's log" "pytest tests/" \
  "$(printf '%s' "$out" | jq -r '.command')"

# --- evidence-list validates unknown flags ---
d24=$(sandbox)
err=$(cd "$d24" && "$LEDGER" evidence-list --bogus x 2>&1 1>/dev/null; echo "rc=$?")
contains "evidence-list rejects an unknown flag" "unknown arg" "$err"
contains "evidence-list unknown-flag exits 2" "rc=2" "$err"

# --- evidence-list anchors to the MAIN working tree across linked worktrees ---
d25=$(sandbox)
( cd "$d25" && git worktree add -q "$d25/.studious/worktrees/e/s" -b epic/e--s )
( cd "$d25/.studious/worktrees/e/s" && "$LEDGER" evidence-append --command "pytest tests/" \
    --exit-code 0 --output-digest "sha256:deadbeef" --origin subagent --agent-type "epic-driver:build-worker" )
out=$(cd "$d25/.studious/worktrees/e/s" && "$LEDGER" evidence-list)
check "evidence-list from a linked worktree reads the MAIN root evidence file" "pytest tests/" \
  "$(printf '%s' "$out" | jq -r '.command')"

# --- evidence-list --dedupe collapses to one record per distinct command,
# keeping the most recent (last-appended) one, in the survivors' original
# order (evidence-list-dedupe, #162) ---
d27=$(sandbox)
( cd "$d27" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 1 \
    --output-digest "sha256:deadbeef" --origin interactive )
( cd "$d27" && "$LEDGER" evidence-append --command "npm test" --exit-code 0 \
    --output-digest "sha256:cafebabe" --origin interactive )
( cd "$d27" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:f00dface" --origin interactive )

raw27=$(cd "$d27" && "$LEDGER" evidence-list)
check "evidence-list (no flag) line count equals every evidence-append call — unchanged by this story" \
  "3" "$(printf '%s\n' "$raw27" | wc -l | tr -d ' ')"

dedup27=$(cd "$d27" && "$LEDGER" evidence-list --dedupe)
dedup27_count=$(printf '%s\n' "$dedup27" | wc -l | tr -d ' ')
check "evidence-list --dedupe returns fewer records than the raw form (acceptance criterion 3)" \
  "yes" "$([ "$dedup27_count" -lt 3 ] && echo yes || echo no)"
check "evidence-list --dedupe record count equals the number of distinct commands" \
  "2" "$dedup27_count"
check "evidence-list --dedupe keeps the last-appended record's predicate.result for a repeated command" \
  "PASSED" "$(printf '%s' "$dedup27" | jq -r 'select(.command == "pytest tests/") | .predicate.result')"
check "evidence-list --dedupe still includes a once-only command exactly once" \
  "1" "$(printf '%s' "$dedup27" | jq -r 'select(.command == "npm test") | .command' | wc -l | tr -d ' ')"

# --dedupe on another branch still resolves through the same evidence_dir()/
# branch_slug() anchoring the plain --branch read already relies on (line ~618).
( cd "$d27" && git checkout -q -b feat/other )
out27other=$(cd "$d27" && "$LEDGER" evidence-list --dedupe --branch feat/foo)
check "evidence-list --dedupe --branch reads the named branch's log through the same anchoring" \
  "2" "$(printf '%s\n' "$out27other" | wc -l | tr -d ' ')"

# --- evidence-list --dedupe fails closed when jq is unavailable: nothing to
# stdout, a stderr line naming the requirement, non-zero exit ---
d28=$(sandbox)
( cd "$d28" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:deadbeef" --origin interactive )
stdout28=$(cd "$d28" && PATH="$fakebin" "$LEDGER" evidence-list --dedupe 2>/dev/null)
err28=$(cd "$d28" && PATH="$fakebin" "$LEDGER" evidence-list --dedupe 2>&1 1>/dev/null)
rc28=$(cd "$d28" && PATH="$fakebin" "$LEDGER" evidence-list --dedupe >/dev/null 2>&1; echo $?)
check "evidence-list --dedupe prints nothing to stdout when jq is unavailable" "" "$stdout28"
contains "evidence-list --dedupe signals on stderr when jq is unavailable" \
  "gate-ledger: evidence-list --dedupe requires jq" "$err28"
check "evidence-list --dedupe exits non-zero when jq is unavailable" "yes" \
  "$([ "$rc28" -ne 0 ] && echo yes || echo no)"

# --- evidence-list --dedupe fails closed on a malformed line: nothing to
# stdout, non-zero exit (fail closed, never a plausible-looking partial result) ---
d29=$(sandbox)
mkdir -p "$d29/.studious/evidence"
printf '{"command":"pytest tests/"\n' > "$d29/.studious/evidence/feat-foo.jsonl"
stdout29=$(cd "$d29" && "$LEDGER" evidence-list --dedupe 2>/dev/null)
err29=$(cd "$d29" && "$LEDGER" evidence-list --dedupe 2>&1 1>/dev/null)
rc29=$(cd "$d29" && "$LEDGER" evidence-list --dedupe >/dev/null 2>&1; echo $?)
check "evidence-list --dedupe prints nothing to stdout on a malformed line" "" "$stdout29"
contains "evidence-list --dedupe signals on stderr on a malformed line, naming the file" \
  "failed to parse" "$err29"
check "evidence-list --dedupe exits non-zero on a malformed line" "yes" \
  "$([ "$rc29" -ne 0 ] && echo yes || echo no)"

# --- record appends a gate-verdict event to the epic's events.jsonl
# (board-events-log, #98; reference/events-format.md) ---
d26=$(sandbox)
git -C "$d26" checkout -q -b "epic/ev-epic--ev-story"
( cd "$d26" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
evf26="$d26/.studious/epics/ev-epic.events.jsonl"
check "record creates the epic's events.jsonl" "yes" "$([ -f "$evf26" ] && echo yes || echo no)"
check "record appends exactly one event line" "1" "$(wc -l < "$evf26" | tr -d ' ')"
line1=$(sed -n '1p' "$evf26")
check "event is valid single-line JSON" "yes" "$(printf '%s' "$line1" | jq -e . >/dev/null 2>&1 && echo yes || echo no)"
check "event epic is the branch's epic slug" "ev-epic" "$(printf '%s' "$line1" | jq -r '.epic')"
check "event story is the branch's story slug" "ev-story" "$(printf '%s' "$line1" | jq -r '.story')"
check "event kind is gate-verdict" "gate-verdict" "$(printf '%s' "$line1" | jq -r '.kind')"
check "event stores the gate" "audit" "$(printf '%s' "$line1" | jq -r '.gate')"
check "event stores the verdict" "FIX AND RE-AUDIT" "$(printf '%s' "$line1" | jq -r '.verdict')"
check "event stores HEAD sha" "$(git -C "$d26" rev-parse --short HEAD)" "$(printf '%s' "$line1" | jq -r '.sha')"
check "event at is stamped (not null)" "yes" "$([ "$(printf '%s' "$line1" | jq -r '.at')" != "null" ] && echo yes || echo no)"
check "gate-verdict event key order matches reference/events-format.md" \
  '["at","epic","story","kind","gate","verdict","sha"]' "$(printf '%s' "$line1" | jq -c 'keys_unsorted')"

# --- record appends (not overwrites) on a second call ---
( cd "$d26" && "$LEDGER" record --gate audit --verdict PASS )
check "second record appends a second event line" "2" "$(wc -l < "$evf26" | tr -d ' ')"
line2=$(sed -n '2p' "$evf26")
check "first event line is untouched after the second append" "FIX AND RE-AUDIT" "$(sed -n '1p' "$evf26" | jq -r '.verdict')"
check "second event line stores the new verdict" "PASS" "$(printf '%s' "$line2" | jq -r '.verdict')"

# --- record on the epic's own integration branch (no --story suffix) fires
# a finale-level event: story is "" ---
d27=$(sandbox)
git -C "$d27" checkout -q -b "epic/fin-epic"
( cd "$d27" && "$LEDGER" record --gate acceptance --verdict SHIP )
evf27="$d27/.studious/epics/fin-epic.events.jsonl"
check "finale-branch record creates the epic's events.jsonl" "yes" "$([ -f "$evf27" ] && echo yes || echo no)"
check "finale-branch event has an empty story (epic-level event)" "" "$(jq -r '.story' "$evf27")"
check "finale-branch event still stores epic/gate/verdict" "fin-epic acceptance SHIP" \
  "$(jq -r '[.epic, .gate, .verdict] | join(" ")' "$evf27")"

# --- record on a plain, never-epic-qualified branch produces zero events —
# the "unarmed branch" no-op, mirroring evidence-capture-hook's own posture ---
d28=$(sandbox)
( cd "$d28" && "$LEDGER" record --gate audit --verdict PASS )
check "record on a non-epic branch creates no .studious/epics directory at all" "no" \
  "$([ -d "$d28/.studious/epics" ] && echo yes || echo no)"

# --- epic-set appends an epic-status event only when --status is given ---
d29=$(sandbox)
( cd "$d29" && "$LEDGER" epic-set --slug ev-epic2 --title "Title only" )
check "epic-set with no --status appends no event" "no" \
  "$([ -f "$d29/.studious/epics/ev-epic2.events.jsonl" ] && echo yes || echo no)"
( cd "$d29" && "$LEDGER" epic-set --slug ev-epic2 --status approved )
evf29="$d29/.studious/epics/ev-epic2.events.jsonl"
check "epic-set --status appends one epic-status event" "1" "$(wc -l < "$evf29" | tr -d ' ')"
eline1=$(sed -n '1p' "$evf29")
check "epic-status event kind" "epic-status" "$(printf '%s' "$eline1" | jq -r '.kind')"
check "epic-status event has an empty story" "" "$(printf '%s' "$eline1" | jq -r '.story')"
check "epic-status event stores the status" "approved" "$(printf '%s' "$eline1" | jq -r '.status')"
check "epic-status event key order matches reference/events-format.md" \
  '["at","epic","story","kind","status"]' "$(printf '%s' "$eline1" | jq -c 'keys_unsorted')"
( cd "$d29" && "$LEDGER" epic-set --slug ev-epic2 --status running )
check "a second --status call appends a second epic-status event" "2" "$(wc -l < "$evf29" | tr -d ' ')"
check "second epic-status event stores the new status" "running" "$(sed -n '2p' "$evf29" | jq -r '.status')"

# --- epic-story-set appends a story event only for --status/--reason/
# --bump-retry/--reset-retry; a plan-only call (title/deps/gates) appends
# nothing, keeping the log a runtime transition trail, not a plan mirror ---
d30=$(sandbox)
( cd "$d30" && "$LEDGER" epic-set --slug story-epic --status approved )
evf30="$d30/.studious/epics/story-epic.events.jsonl"
check "epic-set --status seeded one epic-status event" "1" "$(wc -l < "$evf30" | tr -d ' ')"
( cd "$d30" && "$LEDGER" epic-story-set --epic story-epic --slug st1 --title "St1" --gates "build,audit" )
check "a plan-only epic-story-set call (no status/reason/retry) appends no event" "1" "$(wc -l < "$evf30" | tr -d ' ')"

( cd "$d30" && "$LEDGER" epic-story-set --epic story-epic --slug st1 --status parked --reason "audit: unclear" )
check "epic-story-set --status/--reason appends a story event" "2" "$(wc -l < "$evf30" | tr -d ' ')"
sline1=$(sed -n '2p' "$evf30")
check "story event kind" "story" "$(printf '%s' "$sline1" | jq -r '.kind')"
check "story event's story is the story's own slug" "st1" "$(printf '%s' "$sline1" | jq -r '.story')"
check "story event's epic is the epic's slug" "story-epic" "$(printf '%s' "$sline1" | jq -r '.epic')"
check "story event stores status" "parked" "$(printf '%s' "$sline1" | jq -r '.status')"
check "story event stores reason" "audit: unclear" "$(printf '%s' "$sline1" | jq -r '.reason')"
check "status+reason story event key order matches reference/events-format.md" \
  '["at","epic","story","kind","status","reason"]' "$(printf '%s' "$sline1" | jq -c 'keys_unsorted')"

( cd "$d30" && "$LEDGER" epic-story-set --epic story-epic --slug st1 --bump-retry audit )
check "bump-retry appends a story event" "3" "$(wc -l < "$evf30" | tr -d ' ')"
sline2=$(sed -n '3p' "$evf30")
check "bump-retry story event stores the gate" "audit" "$(printf '%s' "$sline2" | jq -r '.bumpRetryGate')"
check "bump-retry story event stores the post-write retry count" "1" "$(printf '%s' "$sline2" | jq -r '.retries')"
check "bump-retry story event key order matches reference/events-format.md" \
  '["at","epic","story","kind","bumpRetryGate","retries"]' "$(printf '%s' "$sline2" | jq -c 'keys_unsorted')"
( cd "$d30" && "$LEDGER" epic-story-set --epic story-epic --slug st1 --bump-retry audit )
check "a second bump-retry stores the incremented post-write count" "2" "$(sed -n '4p' "$evf30" | jq -r '.retries')"

( cd "$d30" && "$LEDGER" epic-story-set --epic story-epic --slug st1 --reset-retry audit )
sline5=$(sed -n '5p' "$evf30")
check "reset-retry story event stores the gate" "audit" "$(printf '%s' "$sline5" | jq -r '.resetRetryGate')"
check "reset-retry story event stores the zeroed post-write count" "0" "$(printf '%s' "$sline5" | jq -r '.retries')"

# --- work-set appends a phase event only when --phase is given AND the
# slug is epic-qualified (<epic>--<story>) ---
d31=$(sandbox)
( cd "$d31" && "$LEDGER" work-set --slug "ws-epic--ws-story" --title "T" )
check "work-set with no --phase appends no event" "no" \
  "$([ -f "$d31/.studious/epics/ws-epic.events.jsonl" ] && echo yes || echo no)"
( cd "$d31" && "$LEDGER" work-set --slug "ws-epic--ws-story" --phase decide )
evf31="$d31/.studious/epics/ws-epic.events.jsonl"
check "work-set --phase on an epic-qualified slug appends a phase event" "1" "$(wc -l < "$evf31" | tr -d ' ')"
psline=$(sed -n '1p' "$evf31")
check "phase event kind" "phase" "$(printf '%s' "$psline" | jq -r '.kind')"
check "phase event epic" "ws-epic" "$(printf '%s' "$psline" | jq -r '.epic')"
check "phase event story" "ws-story" "$(printf '%s' "$psline" | jq -r '.story')"
check "phase event stores the phase" "decide" "$(printf '%s' "$psline" | jq -r '.phase')"
check "phase event key order matches reference/events-format.md" \
  '["at","epic","story","kind","phase"]' "$(printf '%s' "$psline" | jq -c 'keys_unsorted')"
( cd "$d31" && "$LEDGER" work-set --slug "plain-feature-x" --phase decide )
check "work-set --phase on a non-epic-qualified slug appends no event (only ws-epic's file exists)" \
  "ws-epic.events.jsonl" "$(cd "$d31/.studious/epics" && printf '%s\n' *.events.jsonl)"

# --- work-log always tries to append (its --step/--outcome are required),
# but only when the slug is epic-qualified; --phase is optional and omitted
# (not null/empty) from the event when not given this call ---
d32=$(sandbox)
( cd "$d32" && "$LEDGER" work-log --slug "wl-epic--wl-story" --step build --outcome BUILT )
evf32="$d32/.studious/epics/wl-epic.events.jsonl"
check "work-log on an epic-qualified slug appends a step event" "1" "$(wc -l < "$evf32" | tr -d ' ')"
stline1=$(sed -n '1p' "$evf32")
check "step event kind" "step" "$(printf '%s' "$stline1" | jq -r '.kind')"
check "step event stores step" "build" "$(printf '%s' "$stline1" | jq -r '.step')"
check "step event stores outcome" "BUILT" "$(printf '%s' "$stline1" | jq -r '.outcome')"
check "step event stores HEAD sha" "$(git -C "$d32" rev-parse --short HEAD)" "$(printf '%s' "$stline1" | jq -r '.sha')"
check "step event omits phase (not null) when --phase wasn't given" "yes" \
  "$(printf '%s' "$stline1" | jq -e 'has("phase") | not' >/dev/null 2>&1 && echo yes || echo no)"
check "phase-less step event key order matches reference/events-format.md" \
  '["at","epic","story","kind","step","outcome","sha"]' "$(printf '%s' "$stline1" | jq -c 'keys_unsorted')"

( cd "$d32" && "$LEDGER" work-log --slug "wl-epic--wl-story" --step audit --outcome PASS --phase merge )
check "a second work-log --phase call appends a second step event" "2" "$(wc -l < "$evf32" | tr -d ' ')"
stline2=$(sed -n '2p' "$evf32")
check "step event includes phase when given" "merge" "$(printf '%s' "$stline2" | jq -r '.phase')"
check "phase-bearing step event key order matches reference/events-format.md" \
  '["at","epic","story","kind","step","outcome","phase","sha"]' "$(printf '%s' "$stline2" | jq -c 'keys_unsorted')"

( cd "$d32" && "$LEDGER" work-log --slug "plain-feature-y" --step build --outcome BUILT )
check "work-log on a non-epic-qualified slug appends no event (only wl-epic's file exists)" \
  "wl-epic.events.jsonl" "$(cd "$d32/.studious/epics" && printf '%s\n' *.events.jsonl)"

# --- events.jsonl anchors to the MAIN working tree across linked worktrees,
# exactly like the other four stores (#98) ---
d33=$(sandbox)
git -C "$d33" worktree add -q "$d33/.studious/worktrees/e/s" -b epic/e--s
( cd "$d33/.studious/worktrees/e/s" && "$LEDGER" work-log --slug "e--s" --step build --outcome BUILT )
check "events append from a linked worktree writes the MAIN root events file" "yes" \
  "$([ -f "$d33/.studious/epics/e.events.jsonl" ] && echo yes || echo no)"
check "events append from a linked worktree does not write under the worktree" "no" \
  "$([ -f "$d33/.studious/worktrees/e/s/.studious/epics/e.events.jsonl" ] && echo yes || echo no)"

# --- events append is skipped, silently, when jq is unavailable — the
# calling verb's own existing "skipped" message already covers this path,
# since append_event() is never reached ---
d34=$(sandbox)
git -C "$d34" checkout -q -b "epic/jq-epic--jq-story"
stderr34=$(cd "$d34" && PATH="$fakebin" "$LEDGER" record --gate audit --verdict PASS 2>&1 1>/dev/null)
contains "record (jq unavailable) still signals its existing skip message" \
  "gate-ledger: record skipped (jq and git required)" "$stderr34"
check "no events file is created when jq is unavailable" "no" \
  "$([ -d "$d34/.studious/epics" ] && echo yes || echo no)"

# --- append_event() is best-effort: a failure appending the events line
# signals on stderr but never fails the calling verb's own exit code, and
# never touches the primary snapshot write (#98; reference/events-format.md
# "Failure behavior"). Simulated by pre-creating the events path as a
# directory, so the >> redirect fails without touching gate-ledger's own
# permission model. ---
d35=$(sandbox)
git -C "$d35" checkout -q -b "epic/coll-epic--coll-story"
mkdir -p "$d35/.studious/epics/coll-epic.events.jsonl"
stderr35=$(cd "$d35" && "$LEDGER" record --gate audit --verdict PASS 2>&1 1>/dev/null); rc35=$?
check "record still exits 0 when the events append fails" "0" "$rc35"
contains "record signals the events-append failure on stderr" \
  "gate-ledger: events-append failed for epic 'coll-epic' (kind gate-verdict) — primary write unaffected" "$stderr35"
check "the primary gate ledger write still succeeded despite the events-append failure" "PASS" \
  "$(jq -r '.gates.audit.verdict' "$d35/.studious/gates/epic-coll-epic--coll-story.json")"

# --- append_event(): concurrent writers to the same epic's events file
# don't corrupt or drop lines — POSIX O_APPEND atomicity, the same property
# cmd_evidence_append's own precedent relies on (#98) ---
d36=$(sandbox)
pids=()
for i in $(seq 1 12); do
  ( cd "$d36" && "$LEDGER" work-log --slug "cc-epic--cc-story" --step "step-$i" --outcome DONE ) &
  pids+=("$!")
done
for pid in "${pids[@]}"; do wait "$pid"; done
evf36="$d36/.studious/epics/cc-epic.events.jsonl"
check "concurrent writers produce exactly one line per call" "12" "$(wc -l < "$evf36" | tr -d ' ')"
check "every concurrently-written line is valid, single-object JSON" "12" \
  "$(while IFS= read -r line; do printf '%s' "$line" | jq -e . >/dev/null 2>&1 && echo ok; done < "$evf36" | wc -l | tr -d ' ')"
check "every distinct step value survives exactly once (no lost or merged writes)" "12" \
  "$(jq -r '.step' "$evf36" | sort -u | wc -l | tr -d ' ')"
check "every concurrently-written line has a stamped at timestamp" "12" \
  "$(jq -r 'select(.at != null and .at != "") | .at' "$evf36" | wc -l | tr -d ' ')"

# --- work-log validates the build step's outcome vocabulary (#213) ---
# Three writers had drifted into two dialects: the epic driver wrote DONE, /build and
# the worker contract wrote BUILT|PAUSED|ESCALATED, and work-on.md branched on exactly
# the latter three — so an epic story branch read back a token with no case. The slot
# was a free string with nothing to catch it. It is now checked at the write.
d37=$(sandbox)

for ok_outcome in BUILT PAUSED ESCALATED HANDED-OFF SKIPPED; do
  ( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome "$ok_outcome" ) >/dev/null 2>&1
  check "work-log accepts build outcome $ok_outcome" "0" "$?"
done

( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome DONE ) >/dev/null 2>&1; rc=$?
check "work-log rejects the superseded DONE dialect for --step build" "2" "$rc"

( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome built ) >/dev/null 2>&1; rc=$?
check "the build outcome check is case-sensitive" "2" "$rc"

# The rejection names the accepted set and where it is specified — a caller that hits
# this is a mis-authored prompt, and the message is what points at the fix.
# grep, not a `case` inside `$( )`: bash 3.2 (what macOS ships, and what CI's
# macos-latest runner uses) fails to parse a case statement inside command
# substitution. This suite has to pass on both runners.
msg37=$( ( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome DONE ) 2>&1 )
check "the rejection names the accepted set" "yes" \
  "$(printf '%s' "$msg37" | grep -q 'BUILT.*PAUSED.*ESCALATED' && echo yes || echo no)"
check "the rejection names the contract that owns the vocabulary" "yes" \
  "$(printf '%s' "$msg37" | grep -q 'worker-contract\.md' && echo yes || echo no)"

# A rejected write leaves no trace: history must not carry the bad token.
check "a rejected outcome appends no history entry" "0" \
  "$(jq -r '[.history[] | select(.outcome == "DONE")] | length' "$d37/.studious/work/enum-work.json")"

# Only the build step is constrained. Gate verdicts belong to
# reference/gate-vocabulary.md and markers like run-boundary to their own writers —
# validating those here would duplicate a vocabulary this tool doesn't own.
( cd "$d37" && "$LEDGER" work-log --slug enum-work --step audit --outcome "FIX AND RE-AUDIT" ) >/dev/null 2>&1
check "a gate step's outcome stays free-form" "0" "$?"
( cd "$d37" && "$LEDGER" work-log --slug enum-work --step run-boundary --outcome DISPATCHED ) >/dev/null 2>&1
check "a non-build marker step's outcome stays free-form" "0" "$?"

# --- scope-delta measurement (#244): --declared-files on work-set ---
d40=$(sandbox)
( cd "$d40" && "$LEDGER" work-set --slug sd-story --design-doc "notes/sd-story.md" --declared-files "a.py, b.py ,a.py" )
wf40="$d40/.studious/work/sd-story.json"
check "declared-files stored as a trimmed, deduped JSON array" '["a.py","b.py"]' "$(jq -c '.declaredFiles' "$wf40")"
check "designDoc is untouched by the new flag" "notes/sd-story.md" "$(jq -r '.designDoc' "$wf40")"

d41=$(sandbox)
( cd "$d41" && "$LEDGER" work-set --slug sd-empty --declared-files "" )
check "an explicit empty --declared-files records a real zero-file declaration, not absence" \
  '[]' "$(jq -c '.declaredFiles' "$d41/.studious/work/sd-empty.json")"

d42=$(sandbox)
( cd "$d42" && "$LEDGER" work-set --slug sd-none --title "no declaration" )
check "a story that never declares has no declaredFiles field at all (distinct from [])" \
  "null" "$(jq -c '.declaredFiles' "$d42/.studious/work/sd-none.json")"

# --- scope-delta measurement (#244): work-log --scope-delta-* / --amend-* ---
d43=$(sandbox)
( cd "$d43" && "$LEDGER" work-log --slug sd-moments --step audit --outcome PASS --scope-delta-phase build --scope-delta-files "x.py,y.py" )
wf43="$d43/.studious/work/sd-moments.json"
check "--outcome vocabulary is untouched by the new flags (history still records the step)" \
  "PASS" "$(jq -r '.history[0].outcome' "$wf43")"
check "the step never carries the scope-delta value (own field, not the outcome token)" \
  '["x.py","y.py"]' "$(jq -c '.scopeDelta[0].outsideFiles' "$wf43")"
check "a measured moment records unmeasured: false" "false" "$(jq -c '.scopeDelta[0].unmeasured' "$wf43")"

( cd "$d43" && "$LEDGER" work-log --slug sd-moments --scope-delta-phase audit-fix-1 --scope-delta-unmeasured )
check "--scope-delta-unmeasured records unmeasured: true with an empty file list, never absence" \
  '{"unmeasured":true,"outsideFiles":[]}' \
  "$(jq -c '.scopeDelta[1] | {unmeasured, outsideFiles}' "$wf43")"
check "a scope-delta-only call (no --step) writes no new history entry" \
  "1" "$(jq '.history | length' "$wf43")"

( cd "$d43" && "$LEDGER" work-log --slug sd-moments --scope-delta-phase build --amend-file "x.py" --amend-reason "shared parsing with verify" )
check "an amendment is stored, keyed by file and phase, with its own reason" \
  '{"file":"x.py","phase":"build","reason":"shared parsing with verify"}' \
  "$(jq -c '.amendments[0] | {file, phase, reason}' "$wf43")"
check "an amendment never touches the outsideFiles it annotates (total unaffected)" \
  '["x.py","y.py"]' "$(jq -c '.scopeDelta[0].outsideFiles' "$wf43")"
check "an amendment appends no scopeDelta entry of its own (still exactly 2 moments)" \
  "2" "$(jq '.scopeDelta | length' "$wf43")"

# --- work-log: --step/--outcome combined with --step build's closed vocabulary,
# alongside the new scope-delta flags in the SAME call — pre-mortem risk #4's own
# detection hint (the outcome vocabulary check must never see, or be bypassed by,
# a scope-delta value riding on the same call). ---
d44=$(sandbox)
( cd "$d44" && "$LEDGER" work-log --slug sd-build --step build --outcome BUILT \
    --scope-delta-phase build --scope-delta-files "z.py" --amend-file "z.py" --amend-reason "unforeseen shared module" ) >/dev/null 2>&1
rc44=$?
check "--step build --outcome BUILT succeeds alongside scope-delta/amend flags" "0" "$rc44"
wf44="$d44/.studious/work/sd-build.json"
check "the build outcome itself is still exactly BUILT" "BUILT" "$(jq -r '.history[0].outcome' "$wf44")"
check "the scope-delta write landed in the same call" '["z.py"]' "$(jq -c '.scopeDelta[0].outsideFiles' "$wf44")"
check "the amendment write landed in the same call" "z.py" "$(jq -r '.amendments[0].file' "$wf44")"

# --- amendment as a standalone call (scope-delta-phase + amend-file/reason, no
# --step/--outcome) should append to .amendments and not touch .history ---
( cd "$d44" && "$LEDGER" work-log --slug sd-build --scope-delta-phase build \
    --amend-file "unexpected.py" --amend-reason "discovered during verify stage" ) >/dev/null 2>&1
rc44_amend=$?
check "amendment as a standalone call succeeds" "0" "$rc44_amend"
check "standalone amendment appends a second amendment entry" "2" "$(jq '.amendments | length' "$wf44")"
check "standalone amendment does not add a history entry" "1" "$(jq '.history | length' "$wf44")"
check "standalone amendment file is recorded" "unexpected.py" "$(jq -r '.amendments[1].file' "$wf44")"

# --- multiple amendments in sequence (one per file, as the instruction prescribes) ---
( cd "$d44" && "$LEDGER" work-log --slug sd-build --scope-delta-phase build \
    --amend-file "other.py" --amend-reason "another unforeseen module" ) >/dev/null 2>&1
check "second amendment also succeeds" "0" "$?"
check "total amendments now reach three" "3" "$(jq '.amendments | length' "$wf44")"
check "history still has only one entry (no amendment duplication)" "1" "$(jq '.history | length' "$wf44")"

( cd "$d44" && "$LEDGER" work-log --slug sd-build --step build --outcome BOGUS \
    --scope-delta-phase build --scope-delta-files "z.py" ) >/dev/null 2>&1
rc44b=$?
check "the build outcome vocabulary check still rejects an unrecognized token even with scope-delta flags present" "2" "$rc44b"
check "the rejected call appended no second scope-delta entry" "1" "$(jq '.scopeDelta | length' "$wf44")"

# --- work-log: validation of the new flags ---
d45=$(sandbox)
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-phase build --scope-delta-files "a.py" --scope-delta-unmeasured ) >/dev/null 2>&1
check "--scope-delta-files and --scope-delta-unmeasured are mutually exclusive" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-files "a.py" ) >/dev/null 2>&1
check "--scope-delta-files without --scope-delta-phase is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-phase build --amend-file "a.py" ) >/dev/null 2>&1
check "--amend-file without --amend-reason is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --amend-reason "why" ) >/dev/null 2>&1
check "--amend-reason without --amend-file is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --step build ) >/dev/null 2>&1
check "--step without --outcome is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid ) >/dev/null 2>&1
check "a work-log call with nothing to record at all is rejected" "2" "$?"

# --- work-log: --scope-delta-reason (fix-and-retry finding 3, #244) ---
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-phase build \
    --scope-delta-files "a.py" --scope-delta-reason dispatch-failed ) >/dev/null 2>&1
check "--scope-delta-reason without --scope-delta-unmeasured is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-phase build \
    --scope-delta-reason dispatch-failed ) >/dev/null 2>&1
check "--scope-delta-reason alone (no --scope-delta-unmeasured) is rejected" "2" "$?"
( cd "$d45" && "$LEDGER" work-log --slug sd-invalid --scope-delta-phase build \
    --scope-delta-unmeasured --scope-delta-reason bogus-reason ) >/dev/null 2>&1
check "--scope-delta-reason rejects a token outside the closed vocabulary" "2" "$?"

d45r=$(sandbox)
( cd "$d45r" && "$LEDGER" work-log --slug sd-reason --scope-delta-phase build \
    --scope-delta-unmeasured --scope-delta-reason dispatch-failed ) >/dev/null 2>&1
wf45r="$d45r/.studious/work/sd-reason.json"
check "--scope-delta-reason records on the unmeasured entry" "dispatch-failed" \
  "$(jq -r '.scopeDelta[0].reason' "$wf45r")"

d45u=$(sandbox)
( cd "$d45u" && "$LEDGER" work-log --slug sd-no-reason --scope-delta-phase build \
    --scope-delta-unmeasured ) >/dev/null 2>&1
wf45u="$d45u/.studious/work/sd-no-reason.json"
check "an unmeasured entry with no --scope-delta-reason given carries no reason key" "absent" \
  "$(jq -r '.scopeDelta[0].reason // "absent"' "$wf45u")"

# --- gc collects finished flow state, not only branch-orphaned state (#237) ---
# The epic path deliberately keeps a story's branch after landing it, so the
# branch-gone rule alone could never fire: 34 of 35 work files sat pinned at phase
# `merge` forever, and /work-on counted every one as an active feature.
d38=$(sandbox)

( cd "$d38" && "$LEDGER" work-set --slug done-feature --title "finished" --branch "$(git -C "$d38" rev-parse --abbrev-ref HEAD)" --phase "done" ) >/dev/null 2>&1
( cd "$d38" && "$LEDGER" work-set --slug stopped-feature --title "abandoned" --phase "stopped" ) >/dev/null 2>&1
( cd "$d38" && "$LEDGER" work-set --slug live-feature --title "in flight" --branch "$(git -C "$d38" rev-parse --abbrev-ref HEAD)" --phase build ) >/dev/null 2>&1
( cd "$d38" && "$LEDGER" work-set --slug fresh-feature --title "no branch yet" --phase decide ) >/dev/null 2>&1

out38=$( cd "$d38" && "$LEDGER" gc 2>&1 )
check "gc collects a work file at phase done, branch still present" "no" \
  "$([ -f "$d38/.studious/work/done-feature.json" ] && echo yes || echo no)"
check "gc collects a work file at phase stopped" "no" \
  "$([ -f "$d38/.studious/work/stopped-feature.json" ] && echo yes || echo no)"
check "gc keeps a work file still in flight" "yes" \
  "$([ -f "$d38/.studious/work/live-feature.json" ] && echo yes || echo no)"
# decide/design happen before a branch exists; a branchless file is not orphaned.
check "gc keeps a branchless non-terminal work file" "yes" \
  "$([ -f "$d38/.studious/work/fresh-feature.json" ] && echo yes || echo no)"
check "gc names the phase it collected on" "yes" \
  "$(printf '%s' "$out38" | grep -q 'removed finished work file.*phase done' && echo yes || echo no)"

# --- gc keeps, rather than collects, a finished work file with a measured
# scope-delta cohort (#244, pre-mortem register item 7): the work file is the
# only copy of declaredFiles/scopeDelta/amendments, so an unconditional
# collect discards a story's measurement cohort for good. ---
d46=$(sandbox)
( cd "$d46" && "$LEDGER" work-set --slug sd-done --title "finished with scope-delta" --phase "done" ) >/dev/null 2>&1
( cd "$d46" && "$LEDGER" work-log --slug sd-done --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
wf46="$d46/.studious/work/sd-done.json"

out46=$( cd "$d46" && "$LEDGER" gc 2>&1 )
check "gc keeps a finished work file with a measured scope-delta cohort" "yes" \
  "$([ -f "$wf46" ] && echo yes || echo no)"
check "gc names the kept file and its scope-delta moment count" "yes" \
  "$(printf '%s' "$out46" | grep -q 'kept: sd-done still holds 1 measured scope-delta moment' && echo yes || echo no)"

# --- Acceptance round 9 (fix-and-retry): the "kept:" message's day-count must
# be driven by SCOPE_DELTA_RETENTION_DAYS, not a hardcoded literal — round 7's
# fix for the "reads as a clock starting now" finding regressed this by
# hardcoding "14" in the message text instead of interpolating the constant
# it had replaced. Fix-and-retry finding 2 (#244 round 9) scoped the guard to
# the terminal-phase path only, so there is exactly one kept: site left. ---
check "the kept: message site interpolates SCOPE_DELTA_RETENTION_DAYS rather than hardcoding its value" "1" \
  "$(grep -c 'collects it %s days after its last write' "$LEDGER")"
check "the kept: message site does not hardcode a bare day count" "0" \
  "$(grep -c 'collects it 14 days after its last write' "$LEDGER")"

# --- Fix-and-retry finding 4 (#244 round 9): the kept: message names the read
# verb the retention exists for, not only the two ways to destroy it. ---
check "the kept: message names gate-ledger work-get as the read verb" "yes" \
  "$(printf '%s' "$out46" | grep -q 'gate-ledger work-get --slug "sd-done" to read it' && echo yes || echo no)"

out46f=$( cd "$d46" && "$LEDGER" gc --force 2>&1 )
check "gc --force collects it anyway" "no" \
  "$([ -f "$wf46" ] && echo yes || echo no)"
# Fix-and-retry finding 1: the destroying path used to print only the generic
# "removed finished work file:" line, with no hint anything measured was lost
# — unlike the keeping path's own "kept: ... still holds N measured
# scope-delta moment(s)" message just above. --force must name what it threw
# away.
check "gc --force names the measured scope-delta moment(s) it discarded" "yes" \
  "$(printf '%s' "$out46f" | grep -q 'removed finished work file: sd-done.json (phase done, --force discarded 1 measured scope-delta moment(s))' && echo yes || echo no)"

# --- Fix-and-retry finding 2 (#244 round 9): the measured-scope-delta guard
# applies to the terminal-phase rule only — a parked, non-terminal-phase story
# whose branch the user deleted never reached acceptance, so its cohort is
# incomplete by construction and gets no keep. Plain gc (no --force) collects
# it outright, same as before #244 ever touched this path — this is the
# regression pin for the option chosen over widening the guard to both rules. ---
d46b=$(sandbox)
git -C "$d46b" branch "epic/gone-branch" >/dev/null 2>&1
( cd "$d46b" && "$LEDGER" work-set --slug sd-branch-gone --title "branch gone, measured, still in flight" --branch "epic/gone-branch" ) >/dev/null 2>&1
( cd "$d46b" && "$LEDGER" work-log --slug sd-branch-gone --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
wf46b="$d46b/.studious/work/sd-branch-gone.json"
git -C "$d46b" branch -D "epic/gone-branch" >/dev/null 2>&1
out46b=$( cd "$d46b" && "$LEDGER" gc 2>&1 )
check "plain gc collects a branch-gone, non-terminal-phase work file outright, even with a measured scope-delta cohort" "no" \
  "$([ -f "$wf46b" ] && echo yes || echo no)"
check "gc names the branch-gone collection with the plain, unguarded message" "yes" \
  "$(printf '%s' "$out46b" | grep -q 'removed stale work file: sd-branch-gone.json (branch epic/gone-branch no longer exists)' && echo yes || echo no)"
check "the branch-gone path names nothing about scope-delta — the guard never armed there" "no" \
  "$(printf '%s' "$out46b" | grep -q 'scope-delta' && echo yes || echo no)"

d47=$(sandbox)
( cd "$d47" && "$LEDGER" work-set --slug sd-done-clean --title "finished, no scope-delta" --phase "done" ) >/dev/null 2>&1
wf47="$d47/.studious/work/sd-done-clean.json"
( cd "$d47" && "$LEDGER" gc ) >/dev/null 2>&1
check "gc still collects a finished work file with no scope-delta data at all, force or not" "no" \
  "$([ -f "$wf47" ] && echo yes || echo no)"

# --- gc's guard only arms on a MEASURED scope-delta entry (fix-and-retry finding
# 2): a scope check that dies or can't resolve a diff on the script path writes
# --scope-delta-unmeasured (`computeScopeDelta`'s dead-end path, workflows/
# epic-driver.js) — the fallback driver (commands/work-through.md) writes no
# scope-delta entries at all — so a work file whose cohort is only that must
# not be pinned by a cohort it never actually measured. ---
d46u=$(sandbox)
( cd "$d46u" && "$LEDGER" work-set --slug sd-unmeasured-only --title "died scope check, never measured" --phase "done" ) >/dev/null 2>&1
( cd "$d46u" && "$LEDGER" work-log --slug sd-unmeasured-only --scope-delta-phase audit --scope-delta-unmeasured ) >/dev/null 2>&1
wf46u="$d46u/.studious/work/sd-unmeasured-only.json"
( cd "$d46u" && "$LEDGER" gc ) >/dev/null 2>&1
check "gc collects (never keeps) a work file whose scope-delta is entirely unmeasured" "no" \
  "$([ -f "$wf46u" ] && echo yes || echo no)"

# A mixed cohort (one measured entry, one unmeasured) still arms the guard on
# the measured entry alone — the narrowing only excuses an ALL-unmeasured file.
d46m=$(sandbox)
( cd "$d46m" && "$LEDGER" work-set --slug sd-mixed --title "one measured, one not" --phase "done" ) >/dev/null 2>&1
( cd "$d46m" && "$LEDGER" work-log --slug sd-mixed --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
( cd "$d46m" && "$LEDGER" work-log --slug sd-mixed --scope-delta-phase audit-fix-1 --scope-delta-unmeasured ) >/dev/null 2>&1
wf46m="$d46m/.studious/work/sd-mixed.json"
( cd "$d46m" && "$LEDGER" gc ) >/dev/null 2>&1
check "gc still keeps a work file with at least one measured entry, even alongside an unmeasured one" "yes" \
  "$([ -f "$wf46m" ] && echo yes || echo no)"

# --- gc's keep is bounded by SCOPE_DELTA_RETENTION_DAYS (fix-and-retry finding
# 1, BLOCKER): the guard's first cut had no terminating condition, so a batch gc
# never released a landed epic story's work file back to the default (no-`--force`)
# path at all. A work file whose last write is older than the retention window
# collects on the next plain `gc`, no `--force` needed. ---
d46r=$(sandbox)
( cd "$d46r" && "$LEDGER" work-set --slug sd-stale --title "past its keep window" --phase "done" ) >/dev/null 2>&1
( cd "$d46r" && "$LEDGER" work-log --slug sd-stale --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
wf46r="$d46r/.studious/work/sd-stale.json"
# A fixed, far-past timestamp — not `date` arithmetic — keeps this
# deterministic and portable across the BSD/GNU `date` divide (no precedent
# for `date -d`/`date -j` elsewhere in this suite) without depending on
# whichever OS runs it.
tmp46r=$(mktemp)
jq '.updatedAt = "2020-01-01T00:00:00Z"' "$wf46r" > "$tmp46r" && mv "$tmp46r" "$wf46r"
out46r=$( cd "$d46r" && "$LEDGER" gc 2>&1 )
check "gc collects (no --force) a work file whose measured scope-delta cohort is past its retention window" "no" \
  "$([ -f "$wf46r" ] && echo yes || echo no)"
check "gc names the retention-window collection distinctly from an ordinary finished-file collection" "yes" \
  "$(printf '%s' "$out46r" | grep -q 'removed work file past its 14-day scope-delta keep window: sd-stale.json' && echo yes || echo no)"

# --- gc collects epic state only once the epic actually shipped ---
# `ready` is the driver's finale status and means "ready for you to PR" — the
# branch is still live and the epic is still the answer to "what's in flight".
# Shipped means ready AND the integration branch is gone.
d39=$(sandbox)
git -C "$d39" branch "epic/shipped-epic" >/dev/null 2>&1
git -C "$d39" branch "epic/live-epic" >/dev/null 2>&1
( cd "$d39" && "$LEDGER" epic-set --slug shipped-epic --title "merged" --branch "epic/shipped-epic" --status ready ) >/dev/null 2>&1
( cd "$d39" && "$LEDGER" epic-set --slug live-epic --title "awaiting PR" --branch "epic/live-epic" --status ready ) >/dev/null 2>&1
( cd "$d39" && "$LEDGER" epic-set --slug running-epic --title "in flight" --branch "epic/running-epic" --status running ) >/dev/null 2>&1
( cd "$d39" && "$LEDGER" epic-story-set --epic shipped-epic --slug s1 --status landed ) >/dev/null 2>&1

check "epic events file exists before gc" "yes" \
  "$([ -f "$d39/.studious/epics/shipped-epic.events.jsonl" ] && echo yes || echo no)"
git -C "$d39" branch -D "epic/shipped-epic" >/dev/null 2>&1   # the PR merged, branch deleted
( cd "$d39" && "$LEDGER" gc ) >/dev/null 2>&1

check "gc collects a ready epic whose branch is gone" "no" \
  "$([ -f "$d39/.studious/epics/shipped-epic.json" ] && echo yes || echo no)"
check "gc collects that epic's events file too" "no" \
  "$([ -f "$d39/.studious/epics/shipped-epic.events.jsonl" ] && echo yes || echo no)"
check "gc keeps a ready epic whose branch is still live" "yes" \
  "$([ -f "$d39/.studious/epics/live-epic.json" ] && echo yes || echo no)"
check "gc keeps a running epic" "yes" \
  "$([ -f "$d39/.studious/epics/running-epic.json" ] && echo yes || echo no)"

# --- episode-open records sha and opens round 1; no legacy record yet (#289) ---
dep1=$(sandbox)
fep1="$dep1/.studious/gates/feat-foo.json"
( cd "$dep1" && "$LEDGER" episode-open --gate audit )
check "episode-open creates the branch-slug ledger file" "yes" "$([ -f "$fep1" ] && echo yes || echo no)"
check "episode-open records HEAD sha" "$(git -C "$dep1" rev-parse --short HEAD)" "$(jq -r '.episodes.audit.sha' "$fep1")"
check "episode-open opens round 1" "1" "$(jq -r '.episodes.audit.round' "$fep1")"
check "episode-open stamps openedAt (not null)" "yes" \
  "$([ "$(jq -r '.episodes.audit.openedAt' "$fep1")" != "null" ] && echo yes || echo no)"
check "episode-open stores the branch name" "feat/foo" "$(jq -r '.branch' "$fep1")"
check "episode-open alone writes no legacy per-gate record" "null" "$(jq -c '.gates.audit' "$fep1")"
contains "episode-open self-heals .gitignore" ".studious/" "$(cat "$dep1/.gitignore")"

# --- episode-verdict records the verdict and dual-writes the legacy per-gate
# record with the same verdict and sha, so status/gate-get readers run untouched ---
( cd "$dep1" && "$LEDGER" episode-verdict --gate audit --verdict PASS )
check "episode-verdict records the verdict on the episode" "PASS" "$(jq -r '.episodes.audit.verdict' "$fep1")"
check "episode-verdict stamps verdictAt (not null)" "yes" \
  "$([ "$(jq -r '.episodes.audit.verdictAt' "$fep1")" != "null" ] && echo yes || echo no)"
check "exactly one episode record exists for the gate" "1" "$(jq '.episodes | length' "$fep1")"
check "episode-verdict dual-writes the legacy verdict" "PASS" "$(jq -r '.gates.audit.verdict' "$fep1")"
check "legacy record sha matches the episode record sha" \
  "$(jq -r '.episodes.audit.sha' "$fep1")" "$(jq -r '.gates.audit.sha' "$fep1")"
check "legacy record shape matches record's own (verdict, sha, ranAt)" \
  '["verdict","sha","ranAt"]' "$(jq -c '.gates.audit | keys_unsorted' "$fep1")"

# --- episode-round increments once; a third round is refused in code (2-round cap) ---
dep2=$(sandbox)
fep2="$dep2/.studious/gates/feat-foo.json"
( cd "$dep2" && "$LEDGER" episode-open --gate audit )
( cd "$dep2" && "$LEDGER" episode-round --gate audit ); rc=$?
check "episode-round exits 0 within the cap" "0" "$rc"
check "episode-round increments the round to 2" "2" "$(jq -r '.episodes.audit.round' "$fep2")"
err=$(cd "$dep2" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a third episode-round is refused naming the 2-round cap" "2-round cap" "$err"
contains "a third episode-round exits non-zero" "rc=1" "$err"
check "a refused round leaves the recorded round at 2" "2" "$(jq -r '.episodes.audit.round' "$fep2")"

# --- episode-round / episode-verdict require an open episode ---
dep3=$(sandbox)
err=$(cd "$dep3" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-round without an open episode names episode-open" "run episode-open first" "$err"
contains "episode-round without an open episode exits 2" "rc=2" "$err"
err=$(cd "$dep3" && "$LEDGER" episode-verdict --gate audit --verdict PASS 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-verdict without an open episode names episode-open" "run episode-open first" "$err"
contains "episode-verdict without an open episode exits 2" "rc=2" "$err"
check "no verdict was recorded without an open episode" "no" \
  "$([ -f "$dep3/.studious/gates/feat-foo.json" ] && [ "$(jq -c '.gates' "$dep3/.studious/gates/feat-foo.json")" != "{}" ] && echo yes || echo no)"

# --- episode verbs validate required args before touching any file ---
err=$(cd "$dep3" && "$LEDGER" episode-open 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-open requires --gate" "--gate required" "$err"
contains "episode-open without --gate exits 2" "rc=2" "$err"
err=$(cd "$dep3" && "$LEDGER" episode-verdict --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-verdict requires --gate and --verdict" "--gate and --verdict required" "$err"
contains "episode-verdict without --verdict exits 2" "rc=2" "$err"

# --- a fresh episode-open replaces the finished episode: the round cap bounds
# one episode, never the branch's lifetime ---
( cd "$dep1" && "$LEDGER" episode-open --gate audit )
check "reopening resets the round to 1" "1" "$(jq -r '.episodes.audit.round' "$fep1")"
check "reopening drops the prior episode's verdict (fresh episode)" "null" "$(jq -r '.episodes.audit.verdict // "null"' "$fep1")"
check "reopening leaves the prior dual-written legacy record in place" "PASS" "$(jq -r '.gates.audit.verdict' "$fep1")"

# --- status for an episode-written branch matches the per-gate shape the
# PR-time hook parses today — the dual-write keeps legacy readers untouched ---
dep4=$(sandbox)
( cd "$dep4" && "$LEDGER" episode-open --gate audit )
( cd "$dep4" && "$LEDGER" episode-verdict --gate audit --verdict PASS )
( cd "$dep4" && "$LEDGER" episode-open --gate acceptance )
( cd "$dep4" && "$LEDGER" episode-verdict --gate acceptance --verdict SHIP )
out=$(cd "$dep4" && "$LEDGER" status)
check "status for an episode-written branch matches the legacy proceed message verbatim" \
  "audit (PASS) and acceptance (SHIP) ran on this branch at HEAD — proceed." "$out"

# an episode-written branch missing a gate reports it exactly like a record-written one
dep5=$(sandbox)
( cd "$dep5" && "$LEDGER" episode-open --gate audit )
( cd "$dep5" && "$LEDGER" episode-verdict --gate audit --verdict PASS )
out=$(cd "$dep5" && "$LEDGER" status)
contains "episode-written branch missing acceptance reports it in the legacy shape" \
  "acceptance never ran on this branch" "$out"

# staleness machinery reads an episode-written record identically
( cd "$dep5" && git commit -q --allow-empty -m more )
out=$(cd "$dep5" && "$LEDGER" status)
contains "status flags a stale episode-written verdict with the legacy wording" \
  "audit ran 1 commit ago — re-run before merging" "$out"

# --- gate-get on an episode-written branch still prints the legacy .gates shape ---
out=$(cd "$dep4" && "$LEDGER" gate-get)
contains "gate-get on an episode-written branch includes the dual-written verdict" '"verdict": "PASS"' "$out"

# --- episode verbs signal on stderr (but still return 0) when jq is unavailable ---
dep6=$(sandbox)
stderr6=$(cd "$dep6" && PATH="$fakebin" "$LEDGER" episode-open --gate audit 2>&1 1>/dev/null)
contains "episode-open signals on stderr when jq is unavailable" \
  "gate-ledger: episode-open skipped (jq and git required)" "$stderr6"
check "episode-open does not create a ledger file when jq is unavailable" "no" \
  "$([ -f "$dep6/.studious/gates/feat-foo.json" ] && echo yes || echo no)"

# --- episode-finding: round 1 records a finding with lane, severity, status,
# and the episode's current round stamped on it ---
def1=$(sandbox)
fef1="$def1/.studious/gates/feat-foo.json"
( cd "$def1" && "$LEDGER" episode-open --gate audit )
( cd "$def1" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Important --fingerprint sqli-login --status open ); rc=$?
check "round-1 episode-finding records with exit 0" "0" "$rc"
check "finding stores lane" "security-auditor" "$(jq -r '.episodes.audit.findings["sqli-login"].lane' "$fef1")"
check "finding stores severity" "Important" "$(jq -r '.episodes.audit.findings["sqli-login"].severity' "$fef1")"
check "finding stores status" "open" "$(jq -r '.episodes.audit.findings["sqli-login"].status' "$fef1")"
check "finding stamps the episode's current round" "1" "$(jq -r '.episodes.audit.findings["sqli-login"].round' "$fef1")"

# --- on round 2 a NEW blocking finding below Critical is refused without
# --regression-of naming a round-1 finding (regression classification in code) ---
( cd "$def1" && "$LEDGER" episode-round --gate audit )
err=$(cd "$def1" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint new-lint-gap --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "a round-2 blocking finding below Critical without --regression-of is refused" "--regression-of" "$err"
contains "the round-2 refusal exits non-zero" "rc=1" "$err"
check "the refused finding is not recorded" "null" "$(jq -c '.episodes.audit.findings["new-lint-gap"]' "$fef1")"

# ...with --regression-of naming a round-1 finding it records, classified as a regression
( cd "$def1" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint sqli-login-again --status open --regression-of sqli-login ); rc=$?
check "a round-2 regression of a round-1 finding records with exit 0" "0" "$rc"
check "the regression names its round-1 finding" "sqli-login" \
  "$(jq -r '.episodes.audit.findings["sqli-login-again"].regressionOf' "$fef1")"
check "the regression is stamped round 2" "2" "$(jq -r '.episodes.audit.findings["sqli-login-again"].round' "$fef1")"

# --regression-of must name a finding that actually exists at round 1
err=$(cd "$def1" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint bogus-reg --status open --regression-of no-such-finding 2>&1 1>/dev/null; echo "rc=$?")
contains "--regression-of naming an unknown fingerprint is refused" "does not name a round-1 finding" "$err"
contains "an unknown --regression-of exits non-zero" "rc=1" "$err"

# a NEW Critical stays recordable on round 2 — it is the stop signal, not a widening
( cd "$def1" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint fresh-critical --status open ); rc=$?
check "a new round-2 Critical records without --regression-of" "0" "$rc"

# a NEW Track is not blocking, so it records freely on round 2
( cd "$def1" && "$LEDGER" episode-finding --gate audit --lane doc-auditor \
    --severity Track --fingerprint stale-comment --status open ); rc=$?
check "a new round-2 Track records without --regression-of" "0" "$rc"

# updating a round-1 finding on round 2 is not a new blocking finding — closing it is the point
( cd "$def1" && "$LEDGER" episode-finding --gate audit --fingerprint sqli-login --status closed ); rc=$?
check "closing a round-1 finding on round 2 exits 0" "0" "$rc"
check "the update moves status to closed" "closed" "$(jq -r '.episodes.audit.findings["sqli-login"].status' "$fef1")"
check "the update keeps the finding's original round" "1" "$(jq -r '.episodes.audit.findings["sqli-login"].round' "$fef1")"
check "the update keeps lane and severity" "security-auditor/Important" \
  "$(jq -r '.episodes.audit.findings["sqli-login"] | .lane + "/" + .severity' "$fef1")"

# --- a Critical reaches carried only with --waiver, recorded on the finding ---
err=$(cd "$def1" && "$LEDGER" episode-finding --gate audit --fingerprint fresh-critical --status carried 2>&1 1>/dev/null; echo "rc=$?")
contains "moving a Critical to carried without --waiver is refused" "--waiver" "$err"
contains "the waiver refusal exits non-zero" "rc=1" "$err"
check "the refused Critical stays open" "open" "$(jq -r '.episodes.audit.findings["fresh-critical"].status' "$fef1")"
check "no waiver key lands on a refused carry" "null" "$(jq -r '.episodes.audit.findings["fresh-critical"].waiver // "null"' "$fef1")"
( cd "$def1" && "$LEDGER" episode-finding --gate audit --fingerprint fresh-critical --status carried \
    --waiver "mitigated by WAF rule; fix scheduled next sprint" ); rc=$?
check "a Critical carries with --waiver, exit 0" "0" "$rc"
check "the waiver reason lands on the finding record" "mitigated by WAF rule; fix scheduled next sprint" \
  "$(jq -r '.episodes.audit.findings["fresh-critical"].waiver' "$fef1")"
check "the waived carry moves status to carried" "carried" "$(jq -r '.episodes.audit.findings["fresh-critical"].status' "$fef1")"

# creating a Critical directly as carried is the same rule, same refusal
err=$(cd "$def1" && "$LEDGER" episode-finding --gate audit --lane infra-auditor \
    --severity Critical --fingerprint born-carried --status carried 2>&1 1>/dev/null; echo "rc=$?")
contains "a Critical recorded directly as carried without --waiver is refused" "--waiver" "$err"
contains "the direct-carry refusal exits non-zero" "rc=1" "$err"

# below Critical, carried needs no waiver
( cd "$def1" && "$LEDGER" episode-finding --gate audit --fingerprint sqli-login-again --status carried ); rc=$?
check "an Important carries without --waiver" "0" "$rc"

# severity is fixed at first record — no laundering a Critical down to dodge the waiver rule
err=$(cd "$def1" && "$LEDGER" episode-finding --gate audit --fingerprint fresh-critical \
    --severity Important --status closed 2>&1 1>/dev/null; echo "rc=$?")
contains "re-recording a finding at a different severity is refused" "fixed at first record" "$err"
contains "a severity change exits non-zero" "rc=2" "$err"

# --- episode-get: one parseable line prose surfaces can quote verbatim ---
out=$(cd "$def1" && "$LEDGER" episode-get --gate audit)
check "episode-get reports round and open/carried counts in one line" \
  "round 2 of 2 — 1 open, 2 carried" "$out"
check "episode-get output is a single line" "1" "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"

# --- episode-get mirrors its sibling read verbs when nothing is recorded ---
defg=$(sandbox)
check "episode-get prints nothing when no episode is open" "" "$(cd "$defg" && "$LEDGER" episode-get --gate audit)"
err=$(cd "$defg" && "$LEDGER" episode-get 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-get requires --gate" "--gate required" "$err"
contains "episode-get without --gate exits 2" "rc=2" "$err"

# --- episode-finding validates args and requires an open episode ---
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Critical \
    --fingerprint f --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-finding without an open episode names episode-open" "run episode-open first" "$err"
contains "episode-finding without an open episode exits 2" "rc=2" "$err"
( cd "$defg" && "$LEDGER" episode-open --gate audit )
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Critical --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-finding requires --fingerprint" "--gate, --fingerprint, and --status required" "$err"
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Serious \
    --fingerprint f --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-finding rejects a severity outside the rubric" "Critical, Important, or Track" "$err"
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Critical \
    --fingerprint f --status fixed 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-finding rejects a status outside the vocabulary" "open, closed, carried, waived, or rejected-as-noise" "$err"
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --fingerprint f2 --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "a first record requires --lane and --severity" "--lane and --severity required" "$err"
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Track \
    --fingerprint f --status open --waiver why 2>&1 1>/dev/null; echo "rc=$?")
contains "--waiver outside carried/waived is rejected" "--waiver requires --status carried" "$err"
err=$(cd "$defg" && "$LEDGER" episode-finding --gate audit --lane x --severity Important \
    --fingerprint r1reg --status open --regression-of f 2>&1 1>/dev/null; echo "rc=$?")
contains "--regression-of on round 1 is refused (no prior round to regress from)" "still on round 1" "$err"

# --- episode-finding signals on stderr (but still returns 0) when jq is unavailable ---
stderrfin=$(cd "$dep6" && PATH="$fakebin" "$LEDGER" episode-finding --gate audit --lane x \
    --severity Critical --fingerprint f --status open 2>&1 1>/dev/null)
contains "episode-finding signals on stderr when jq is unavailable" \
  "gate-ledger: episode-finding skipped (jq and git required)" "$stderrfin"

# --- audit-cleanup (#291-adjacent): waived shares carried's guard; closed episodes refuse; reopen archives ---
dcl=$(sandbox)
fcl="$dcl/.studious/gates/$(cd "$dcl" && git branch --show-current | tr '/' '-').json"
( cd "$dcl" && "$LEDGER" episode-open --gate audit ) >/dev/null

# a fingerprint is a single token — whitespace/control characters are refused at the write boundary
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Track --fingerprint "two words" --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "a fingerprint with whitespace is refused" "single token" "$err"
contains "the fingerprint refusal is a usage error" "rc=2" "$err"

# Rule 2 guards waived exactly as it guards carried — no sibling-status bypass
( cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint crit-a --status open ) >/dev/null
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --fingerprint crit-a --status waived 2>&1 1>/dev/null; echo "rc=$?")
contains "moving a Critical to waived without --waiver is refused" "--waiver" "$err"
contains "the waived refusal exits non-zero" "rc=1" "$err"
check "the refused Critical stays open after the waived attempt" "open" \
  "$(jq -r '.episodes.audit.findings["crit-a"].status' "$fcl")"
( cd "$dcl" && "$LEDGER" episode-finding --gate audit --fingerprint crit-a --status waived \
    --waiver "accepted risk: internal tool, tracked in #291" ); rc=$?
check "a Critical waives with --waiver, exit 0" "0" "$rc"
check "the waiver reason lands on the waived finding" "accepted risk: internal tool, tracked in #291" \
  "$(jq -r '.episodes.audit.findings["crit-a"].waiver' "$fcl")"
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane infra-auditor \
    --severity Critical --fingerprint born-waived --status waived 2>&1 1>/dev/null; echo "rc=$?")
contains "a Critical recorded directly as waived without --waiver is refused" "--waiver" "$err"

# closed by exactly one verdict — enforced, not assumed
( cd "$dcl" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ) >/dev/null
err=$(cd "$dcl" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-round on a closed episode names the closure" "closed" "$err"
contains "episode-round on a closed episode is the fresh-entry signal" "rc=2" "$err"
err=$(cd "$dcl" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" 2>&1 1>/dev/null; echo "rc=$?")
contains "a second verdict on a closed episode is refused" "exactly one verdict" "$err"
contains "the verdict-overwrite refusal exits non-zero" "rc=1" "$err"
check "the refused overwrite leaves the recorded verdict standing" "PASS" \
  "$(jq -r '.episodes.audit.verdict' "$fcl")"
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Track --fingerprint late-finding --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-finding on a closed episode is refused" "closed" "$err"
contains "the late-finding refusal exits non-zero" "rc=1" "$err"

# reopening archives the prior episode — findings, waiver, and verdict survive under episodeHistory
( cd "$dcl" && "$LEDGER" episode-open --gate audit ) >/dev/null
check "reopen starts the fresh episode at round 1" "1" "$(jq -r '.episodes.audit.round' "$fcl")"
check "the fresh episode carries no findings" "null" "$(jq -r '.episodes.audit.findings // "null"' "$fcl")"
check "reopen archives exactly one prior episode" "1" "$(jq -r '.episodeHistory.audit | length' "$fcl")"
check "the archived episode keeps its verdict" "PASS" "$(jq -r '.episodeHistory.audit[0].verdict' "$fcl")"
check "the archived episode keeps the waived Critical and its reason" \
  "waived/accepted risk: internal tool, tracked in #291" \
  "$(jq -r '.episodeHistory.audit[0].findings["crit-a"] | .status + "/" + .waiver' "$fcl")"
check "a first open still writes no history key" "null" \
  "$(cd "$(sandbox)" && "$LEDGER" episode-open --gate audit >/dev/null && jq -r '.episodeHistory // "null"' ".studious/gates/$(git branch --show-current | tr '/' '-').json")"

# --- acceptance-fix regression: the retry verdict is a round outcome — round 2 is reachable ---
drt=$(sandbox)
frt="$drt/.studious/gates/$(cd "$drt" && git branch --show-current | tr '/' '-').json"
( cd "$drt" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$drt" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Important --fingerprint sec-x --status open ) >/dev/null
( cd "$drt" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null

# between the round outcome and re-entry, findings and verdicts still refuse — with the re-entry route named
err=$(cd "$drt" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "a verdict on a retry-outcome episode points at episode-round" "episode-round" "$err"
contains "that refusal exits non-zero" "rc=1" "$err"
err=$(cd "$drt" && "$LEDGER" episode-finding --gate audit --lane x --severity Track \
    --fingerprint late --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "a finding on a retry-outcome episode points at episode-round" "episode-round" "$err"

# re-entry: exit 0, round 2, outcome cleared, findings kept, legacy retry token untouched
( cd "$drt" && "$LEDGER" episode-round --gate audit ); rc=$?
check "episode-round re-enters past the retry outcome" "0" "$rc"
check "re-entry advances to round 2" "2" "$(jq -r '.episodes.audit.round' "$frt")"
check "re-entry clears the round outcome" "null" "$(jq -r '.episodes.audit.verdict // "null"' "$frt")"
check "re-entry keeps round 1's findings" "open" "$(jq -r '.episodes.audit.findings["sec-x"].status' "$frt")"
check "the dual-written legacy retry token survives re-entry" "FIX AND RE-REVIEW" \
  "$(jq -r '.gates.audit.verdict' "$frt")"

# round 2's terminal verdict closes it; a terminal close still refuses re-entry
( cd "$drt" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "round 2's verdict closes the re-entered episode" "0" "$rc"
err=$(cd "$drt" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a terminally closed episode still refuses re-entry" "closed" "$err"
contains "the terminal refusal stays the fresh-entry signal" "rc=2" "$err"

# the cap still binds at the end of round 2's retry outcome
dcap=$(sandbox)
( cd "$dcap" && "$LEDGER" episode-open --gate audit && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" \
    && "$LEDGER" episode-round --gate audit && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
err=$(cd "$dcap" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a retry outcome at the cap still refuses a third round" "cap" "$err"
contains "the cap refusal exits 1 past a retry outcome" "rc=1" "$err"

# episode-get names the bound: "round R of C"
out=$(cd "$dcap" && "$LEDGER" episode-get --gate audit)
check "episode-get names the bound in its readout" "round 2 of 2 — 0 open, 0 carried" "$out"

# --- convergence (#291): a round that does not strictly reduce the blocking set is
# refused and the episode is marked escalated, ahead of the cap ---
#
# The cap permits exactly one advance per episode, so no episode reaches a round that
# HAS a recorded predecessor on its own — the comparison arm is exercised by seeding
# `blockingByRound` directly, the same way the guard will read it when the cap moves.
dcv=$(sandbox)
fcv="$dcv/.studious/gates/feat-foo.json"
( cd "$dcv" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dcv" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/sqli --status open ) >/dev/null
( cd "$dcv" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/dup --status open ) >/dev/null
( cd "$dcv" && "$LEDGER" episode-finding --gate audit --lane doc-auditor \
    --severity Track --fingerprint doc-auditor/typo --status open ) >/dev/null

# first round: no predecessor to compare against, so the check cannot refuse
( cd "$dcv" && "$LEDGER" episode-round --gate audit ); rc=$?
check "the first episode-round has no prior round and is not refused" "0" "$rc"
check "the round it left banks its blocking count (Track never blocks)" "2" \
  "$(jq -r '.episodes.audit.blockingByRound["1"]' "$fcv")"
check "an allowed round records no escalation" "null" "$(jq -r '.episodes.audit.escalated // "null"' "$fcv")"

# non-decrease: the blocking set held at 2 against a prior round of 2 — refused, escalated
jq '.episodes.audit.blockingByRound = {"1": 2, "2": 2} | .episodes.audit.round = 3' "$fcv" > "$fcv.t" && mv "$fcv.t" "$fcv"
err=$(cd "$dcv" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a non-decreasing round is refused as non-convergence" "not converging" "$err"
contains "the convergence refusal exits 3, distinct from the cap's 1" "rc=3" "$err"
check "the refused round does not advance" "3" "$(jq -r '.episodes.audit.round' "$fcv")"
check "the refusal marks the episode escalated at that round" "3" "$(jq -r '.episodes.audit.escalated.round' "$fcv")"
check "the escalation records both counts" "2/2" \
  "$(jq -r '.episodes.audit.escalated | (.blocking|tostring) + "/" + (.priorBlocking|tostring)' "$fcv")"

# decrease: the identical state against a prior round of 3 is converging, so the
# convergence check passes it through — and what stops it is the cap, on its own exit
# code, with no escalation recorded. Same findings, different predecessor, different refusal.
jq '.episodes.audit.blockingByRound = {"1": 2, "2": 3} | del(.episodes.audit.escalated)' "$fcv" > "$fcv.t" && mv "$fcv.t" "$fcv"
err=$(cd "$dcv" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a strictly decreasing round passes the convergence check to the cap" "2-round cap" "$err"
contains "a converging round is refused as the cap's exit 1, never as escalation" "rc=1" "$err"
check "a converging round records no escalation" "null" "$(jq -r '.episodes.audit.escalated // "null"' "$fcv")"

# a prior round of 0 is not a convergence signal — nothing strictly decreases from none,
# and the 2-round cap stays the bound there (the pre-existing no-findings path)
dcv0=$(sandbox)
( cd "$dcv0" && "$LEDGER" episode-open --gate audit && "$LEDGER" episode-round --gate audit ) >/dev/null
err=$(cd "$dcv0" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a zero prior count leaves the cap as the bound, not escalation" "2-round cap" "$err"
contains "that refusal is still the cap's exit 1" "rc=1" "$err"

# --- disposition memory (#292): rejected-as-noise is a recordable disposition ---
drn=$(sandbox)
frn="$drn/.studious/gates/feat-foo.json"
( cd "$drn" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$drn" && "$LEDGER" episode-finding --gate audit --lane doc-auditor --severity Track \
    --fingerprint doc-auditor/nit --status rejected-as-noise --waiver "style preference, not a defect" ); rc=$?
check "a finding records as rejected-as-noise with exit 0" "0" "$rc"
check "the disposition lands on the record" "rejected-as-noise" \
  "$(jq -r '.episodes.audit.findings["doc-auditor/nit"].status' "$frn")"
check "the rejection reason lands with it" "style preference, not a defect" \
  "$(jq -r '.episodes.audit.findings["doc-auditor/nit"].waiver' "$frn")"

# a Critical dismissed as noise is the same accountable act as carrying one
( cd "$drn" && "$LEDGER" episode-finding --gate audit --lane security-auditor --severity Critical \
    --fingerprint security-auditor/xss --status open ) >/dev/null
err=$(cd "$drn" && "$LEDGER" episode-finding --gate audit --fingerprint security-auditor/xss \
    --status rejected-as-noise 2>&1 1>/dev/null; echo "rc=$?")
contains "dismissing a Critical as noise without --waiver is refused" "--waiver" "$err"
contains "the noise-dismissal refusal exits non-zero" "rc=1" "$err"
check "the refused Critical stays open" "open" "$(jq -r '.episodes.audit.findings["security-auditor/xss"].status' "$frn")"
( cd "$drn" && "$LEDGER" episode-finding --gate audit --fingerprint security-auditor/xss \
    --status rejected-as-noise --waiver "reflected in a dev-only fixture page" ); rc=$?
check "a Critical dismissed as noise with --waiver records" "0" "$rc"

# a rejected finding is disposed of, so it is neither open nor carried in the counts
check "rejected-as-noise counts as neither open nor carried" "round 1 of 2 — 0 open, 0 carried" \
  "$(cd "$drn" && "$LEDGER" episode-get --gate audit)"

# --- compaction (#298): disposed findings inherit as one-line digests ---
( cd "$drn" && "$LEDGER" episode-finding --gate audit --lane code-auditor --severity Important \
    --fingerprint code-auditor/leak --status open ) >/dev/null
( cd "$drn" && "$LEDGER" episode-finding --gate audit --lane test-auditor --severity Important \
    --fingerprint test-auditor/gap --status closed ) >/dev/null
out=$(cd "$drn" && "$LEDGER" episode-get --gate audit --findings)
check "--findings keeps full detail for the open finding" \
  "$(printf 'open\tImportant\tcode-auditor\tcode-auditor/leak')" \
  "$(printf '%s\n' "$out" | sed -n 2p)"
check "--findings digests the rejected finding to one line, lane and all" \
  "$(printf 'digest\tdoc-auditor\tdoc-auditor/nit\trejected-as-noise\t1')" \
  "$(printf '%s\n' "$out" | sed -n 3p)"
check "--findings digests the noise-dismissed Critical too" \
  "$(printf 'digest\tsecurity-auditor\tsecurity-auditor/xss\trejected-as-noise\t1')" \
  "$(printf '%s\n' "$out" | sed -n 4p)"
check "--findings digests the closed finding rather than dropping it" \
  "$(printf 'digest\ttest-auditor\ttest-auditor/gap\tclosed\t1')" \
  "$(printf '%s\n' "$out" | sed -n 5p)"
check "--findings emits exactly one line per finding plus the summary" "5" \
  "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"

# --- accountability (#300): episode-get --history reads back what the ledger archived ---
dhi=$(sandbox)
( cd "$dhi" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dhi" && "$LEDGER" episode-finding --gate audit --lane security-auditor --severity Critical \
    --fingerprint security-auditor/ssrf --status carried --waiver "metadata IP blocked at the egress proxy" ) >/dev/null
( cd "$dhi" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ) >/dev/null
( cd "$dhi" && "$LEDGER" episode-open --gate audit ) >/dev/null
hist=$(cd "$dhi" && "$LEDGER" episode-get --gate audit --history)
contains "--history renders the archived episode and its verdict" "episode 1 — opened" "$hist"
contains "--history names the archived verdict" "verdict PASS" "$hist"
contains "--history shows the waiver reason back to the operator" \
  "$(printf 'waiver\tsecurity-auditor/ssrf\tcarried\tmetadata IP blocked at the egress proxy')" "$hist"
contains "--history marks the live episode as current" "episode 2 (current)" "$hist"
contains "--history reports an unfinished episode as such" "no verdict yet" "$hist"
check "--history prints nothing for a gate with no episode" "" "$(cd "$dhi" && "$LEDGER" episode-get --gate acceptance --history)"
err=$(cd "$dhi" && "$LEDGER" episode-get --gate audit --history --findings 2>&1 1>/dev/null; echo "rc=$?")
contains "--history and --findings are separate reads" "pass one" "$err"
contains "asking for both exits 2" "rc=2" "$err"

# an escalated episode reads its escalation back in the same quotable style
( cd "$dhi" && "$LEDGER" episode-finding --gate audit --lane code-auditor --severity Important \
    --fingerprint code-auditor/dead --status open ) >/dev/null
fhi="$dhi/.studious/gates/feat-foo.json"
jq '.episodes.audit.round = 2 | .episodes.audit.blockingByRound = {"1": 1}' "$fhi" > "$fhi.t" && mv "$fhi.t" "$fhi"
( cd "$dhi" && "$LEDGER" episode-round --gate audit ) 2>/dev/null
contains "--history renders an escalation line" \
  "$(printf 'escalated\tround 2\t1 blocking, prior round 1')" \
  "$(cd "$dhi" && "$LEDGER" episode-get --gate audit --history)"


# --- telemetry-dispatch: the routing store's dispatch line (#132) ---
dt=$(sandbox)
tf="$dt/.studious/telemetry/feat-foo.jsonl"
( cd "$dt" && CLAUDE_PLUGIN_ROOT="$ROOT" "$LEDGER" telemetry-dispatch \
    --run-id run-7 --step-id lane-1 --parent-step-id feat-foo:audit \
    --skill gate-audit --role security-auditor --routing-reason static --capturer hook \
    --feature round=2 --feature narrowed=true --feature note=hello ) >/dev/null
check "telemetry-dispatch writes one line" "1" "$(wc -l < "$tf" | tr -d ' ')"
check "dispatch kind" "dispatch" "$(jq -r '.kind' "$tf")"
check "dispatch capturer is the caller-declared path" "hook" "$(jq -r '.capturer' "$tf")"
check "dispatch carries run_id" "run-7" "$(jq -r '.run_id' "$tf")"
check "dispatch carries parent_step_id" "feat-foo:audit" "$(jq -r '.parent_step_id' "$tf")"
check "task_id defaults to the branch" "feat/foo" "$(jq -r '.task_id' "$tf")"
check "model falls back to the agent's frontmatter" "opus" "$(jq -r '.model' "$tf")"
check "effort falls back to the agent's frontmatter" "high" "$(jq -r '.effort' "$tf")"
check "numeric feature coerces to a number" "number" "$(jq -r '.features.round | type' "$tf")"
check "boolean feature coerces to a boolean" "boolean" "$(jq -r '.features.narrowed | type' "$tf")"
check "non-scalar feature stays a string" "string" "$(jq -r '.features.note | type' "$tf")"
check "telemetry store is gitignored" "" "$(cd "$dt" && git status --porcelain .studious 2>/dev/null)"

# an explicit --model/--effort wins over the agent file (the driver pins some lanes itself)
( cd "$dt" && CLAUDE_PLUGIN_ROOT="$ROOT" "$LEDGER" telemetry-dispatch --run-id run-7 --step-id lane-2 \
    --role security-auditor --routing-reason override --model sonnet --effort medium ) >/dev/null
check "explicit --model overrides the frontmatter" "sonnet" "$(jq -rs '.[1].model' "$tf")"
check "override is an accepted routing reason" "override" "$(jq -rs '.[1].routing_reason' "$tf")"

# a role with no agent file records empty tiers rather than inventing them
( cd "$dt" && CLAUDE_PLUGIN_ROOT="$ROOT" "$LEDGER" telemetry-dispatch --run-id run-7 --step-id lane-3 \
    --role fix-delta --routing-reason static ) >/dev/null
check "unknown role leaves model empty" "" "$(jq -rs '.[2].model' "$tf")"

# --- telemetry-dispatch validation ---
check "missing --role exits 2" "2" "$(cd "$dt" && "$LEDGER" telemetry-dispatch --run-id r --step-id s --routing-reason static >/dev/null 2>&1; echo $?)"
check "free-text routing reason exits 2" "2" "$(cd "$dt" && "$LEDGER" telemetry-dispatch --run-id r --step-id s --role x --routing-reason "because" >/dev/null 2>&1; echo $?)"
check "classifier routing reason is accepted" "0" "$(cd "$dt" && "$LEDGER" telemetry-dispatch --run-id r --step-id s4 --role x --routing-reason classifier:v3 >/dev/null 2>&1; echo $?)"
check "ab-arm routing reason is accepted" "0" "$(cd "$dt" && "$LEDGER" telemetry-dispatch --run-id r --step-id s5 --role x --routing-reason ab:control >/dev/null 2>&1; echo $?)"
check "unknown capturer exits 2" "2" "$(cd "$dt" && "$LEDGER" telemetry-dispatch --run-id r --step-id s --role x --routing-reason static --capturer agent >/dev/null 2>&1; echo $?)"

# --- record's outcome label (#133), joinable to the dispatch lines above ---
do_=$(sandbox)
of="$do_/.studious/telemetry/feat-foo.jsonl"
( cd "$do_" && CLAUDE_PLUGIN_ROOT="$ROOT" "$LEDGER" telemetry-dispatch --run-id run-9 --step-id lane-1 \
    --role code-auditor --routing-reason static ) >/dev/null
( cd "$do_" && "$LEDGER" record --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
check "record appends exactly one outcome line" "1" "$(jq -rs '[.[] | select(.kind=="outcome")] | length' "$of")"
check "outcome carries the closed-enum verdict verbatim" "FIX AND RE-REVIEW" "$(jq -rs '.[1].verdict' "$of")"
check "outcome capturer is the ledger itself" "ledger" "$(jq -rs '.[1].capturer' "$of")"
check "outcome joins to the run the dispatch recorded" "run-9" "$(jq -rs '.[1].run_id' "$of")"
check "outcome step_id is the gate step" "feat-foo:audit" "$(jq -rs '.[1].step_id' "$of")"
check "outcome records the verdict's sha" "$(git -C "$do_" rev-parse --short HEAD)" "$(jq -rs '.[1].sha' "$of")"

# a verdict with no dispatch telemetry is still labelled, with nothing to join to
dn=$(sandbox)
( cd "$dn" && "$LEDGER" record --gate acceptance --verdict SHIP ) >/dev/null
nf="$dn/.studious/telemetry/feat-foo.jsonl"
check "an unjoinable verdict is still labelled" "SHIP" "$(jq -r '.verdict' "$nf")"
check "its run_id is empty, not invented" "" "$(jq -r '.run_id' "$nf")"
check "record still reports success" "0" "$(cd "$dn" && "$LEDGER" record --gate audit --verdict PASS >/dev/null 2>&1; echo $?)"

# --- appetite, canary, and the zero-landed stop-loss (#144, #268, #297) ---
da=$(sandbox)
( cd "$da" && "$LEDGER" epic-set --slug pricey --title "Priced epic" --goal g \
    --appetite-tokens 4200000 --appetite-episodes 3 --canary on ) >/dev/null
( cd "$da" && "$LEDGER" epic-story-set --epic pricey --slug alpha --title A ) >/dev/null
ef="$da/.studious/epics/pricey.json"
check "epic-set stores the token appetite" "4200000" "$(jq -r '.appetite.tokens' "$ef")"
check "epic-set stores the open-episode appetite" "3" "$(jq -r '.appetite.openEpisodes' "$ef")"
check "epic-set stores canary as a boolean" "true" "$(jq -r '.canary' "$ef")"
check "--canary off records false, not the string" "false" \
  "$(cd "$da" && "$LEDGER" epic-set --slug pricey --canary off >/dev/null && jq -r '.canary' "$ef")"
# One flag must not clobber the other half of the appetite object.
( cd "$da" && "$LEDGER" epic-set --slug pricey --appetite-tokens 5000000 ) >/dev/null
check "setting tokens alone preserves openEpisodes" "3" "$(jq -r '.appetite.openEpisodes' "$ef")"

check "--appetite-tokens rejects zero" "2" \
  "$(cd "$da" && "$LEDGER" epic-set --slug pricey --appetite-tokens 0 >/dev/null 2>&1; echo $?)"
check "--appetite-tokens rejects a dollar figure" "2" \
  "$(cd "$da" && "$LEDGER" epic-set --slug pricey --appetite-tokens '40USD' >/dev/null 2>&1; echo $?)"
check "--appetite-episodes rejects a negative" "2" \
  "$(cd "$da" && "$LEDGER" epic-set --slug pricey --appetite-episodes -1 >/dev/null 2>&1; echo $?)"
check "--canary rejects anything but on/off" "2" \
  "$(cd "$da" && "$LEDGER" epic-set --slug pricey --canary sometimes >/dev/null 2>&1; echo $?)"

# epic-run-log is the write half of the stop-loss: if /work-through skips it the
# stop-loss never arms, so the append and the computed refusal are both pinned.
check "reconcile reports no stop-loss before any run" "false" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.refuse')"
check "reconcile counts zero consecutive zero-landed runs" "0" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.consecutiveZeroLanded')"
( cd "$da" && "$LEDGER" epic-run-log --slug pricey --landed 0 ) >/dev/null
check "one zero-landed run does not arm the stop-loss" "false" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.refuse')"
( cd "$da" && "$LEDGER" epic-run-log --slug pricey --landed 0 ) >/dev/null
check "two zero-landed runs arm it (the third dispatch is refused)" "true" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.refuse')"
check "the count is the run's own, not a total" "2" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.consecutiveZeroLanded')"
check "the limit travels with the payload" "2" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.limit')"
( cd "$da" && "$LEDGER" epic-run-log --slug pricey --landed 2 ) >/dev/null
check "a landing run resets the streak" "0" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.consecutiveZeroLanded')"
( cd "$da" && "$LEDGER" epic-run-log --slug pricey --landed 0 ) >/dev/null
check "only the trailing run of zeros counts" "1" \
  "$(cd "$da" && "$LEDGER" epic-reconcile --slug pricey | jq -r '.stopLoss.consecutiveZeroLanded')"
check "each invocation appends exactly one run record" "4" "$(jq -r '.runs | length' "$ef")"
check "run records carry a timestamp" "true" \
  "$(jq -r '[.runs[] | (.at | type == "string" and length > 0)] | all' "$ef")"

check "epic-run-log rejects a non-numeric count" "2" \
  "$(cd "$da" && "$LEDGER" epic-run-log --slug pricey --landed many >/dev/null 2>&1; echo $?)"
check "epic-run-log requires --landed" "2" \
  "$(cd "$da" && "$LEDGER" epic-run-log --slug pricey >/dev/null 2>&1; echo $?)"
check "epic-run-log refuses an unrecorded epic" "2" \
  "$(cd "$da" && "$LEDGER" epic-run-log --slug ghost --landed 1 >/dev/null 2>&1; echo $?)"

# Run history is bounded — the stop-loss only ever reads the tail.
db=$(sandbox)
( cd "$db" && "$LEDGER" epic-set --slug longrun --title L ) >/dev/null
for _ in $(seq 1 25); do ( cd "$db" && "$LEDGER" epic-run-log --slug longrun --landed 1 ) >/dev/null; done
check "run history is capped, not unbounded" "20" "$(jq -r '.runs | length' "$db/.studious/epics/longrun.json")"

# An epic recorded before these fields existed must still reconcile.
dc=$(sandbox)
( cd "$dc" && "$LEDGER" epic-set --slug legacy --title L ) >/dev/null
check "an epic with no appetite reconciles" "false" \
  "$(cd "$dc" && "$LEDGER" epic-reconcile --slug legacy | jq -r '.stopLoss.refuse')"
check "absent appetite reads as null, not a default" "null" \
  "$(cd "$dc" && "$LEDGER" epic-reconcile --slug legacy | jq -r '.epic.appetite')"

# --- per-epic findings ledger: epic-finding / epic-attest / epic-findings (#281) ---
df=$(sandbox)
efile="$df/.studious/epics/ledgered.events.jsonl"
( cd "$df" && "$LEDGER" epic-set --slug ledgered --title L ) >/dev/null
sha0=$(git -C "$df" rev-parse --short HEAD)
( cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane security-auditor \
    --severity Critical --fingerprint sec-token-leak --status open ) >/dev/null
( cd "$df" && "$LEDGER" epic-finding --epic ledgered --story beta --lane code-auditor \
    --severity Important --fingerprint code-dup --status open ) >/dev/null
check "epic-finding writes one line into the epic's events log" "2" \
  "$(grep -c '"kind":"finding"' "$efile")"
check "epic-finding stamps HEAD as the raised sha" "$sha0" \
  "$(jq -r 'select(.finding == "sec-token-leak") | .sha' "$efile" | head -1)"
out=$(cd "$df" && "$LEDGER" epic-findings --epic ledgered)
contains "epic-findings summarizes the epic's findings" "epic ledgered — 2 finding(s), 2 unresolved" "$out"
contains "epic-findings prints identity fields per finding" \
  "open	Critical	alpha	security-auditor	sec-token-leak" "$out"

# Closure: the last line's status wins, and its sha becomes the resolved sha.
git -C "$df" commit -q --allow-empty -m fix
sha1=$(git -C "$df" rev-parse --short HEAD)
( cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane security-auditor \
    --severity Critical --fingerprint sec-token-leak --status closed ) >/dev/null
out=$(cd "$df" && "$LEDGER" epic-findings --epic ledgered)
contains "a closed finding carries both the raised and the resolved sha" \
  "closed	Critical	alpha	security-auditor	sec-token-leak	$sha0	$sha1" "$out"
contains "closing one finding drops the unresolved count" "1 unresolved" "$out"
out=$(cd "$df" && "$LEDGER" epic-findings --epic ledgered --unresolved)
contains "--unresolved keeps the open finding" "code-dup" "$out"
check "--unresolved drops the closed one" "" "$(printf '%s' "$out" | grep 'sec-token-leak' || true)"

# Identity is fixed by the FIRST line: a later line cannot launder a Critical down.
( cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane docs \
    --severity Track --fingerprint sec-token-leak --status closed ) >/dev/null
contains "severity folds from the first recorded line, never a later restatement" \
  "closed	Critical	alpha	security-auditor	sec-token-leak" \
  "$(cd "$df" && "$LEDGER" epic-findings --epic ledgered)"

# Attestations (#130 carry-forward): one line per (lane, story) clean read.
( cd "$df" && "$LEDGER" epic-attest --epic ledgered --story alpha --lane doc-auditor ) >/dev/null
( cd "$df" && "$LEDGER" epic-attest --epic ledgered --story beta --lane doc-auditor --sha cafe123 ) >/dev/null
out=$(cd "$df" && "$LEDGER" epic-findings --epic ledgered --attestations)
contains "epic-attest records a clean lane at a sha" "attestation	doc-auditor	beta	cafe123" "$out"
contains "epic-attest defaults its sha to HEAD" "attestation	doc-auditor	alpha	$sha1" "$out"
check "--attestations prints no finding lines" "" \
  "$(printf '%s' "$out" | grep 'code-dup' || true)"

# A malformed line never blinds the reader to the rest of the trail.
printf 'not json at all\n' >> "$efile"
contains "a corrupt line is skipped, not fatal" "code-dup" \
  "$(cd "$df" && "$LEDGER" epic-findings --epic ledgered)"

# Refusals, all before anything is appended.
before=$(wc -l < "$efile")
check "a Critical set aside without --waiver is refused" "1" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Critical \
      --fingerprint fp-x --status waived >/dev/null 2>&1; echo $?)"
check "an unrecognized severity is refused" "2" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Blocker \
      --fingerprint fp-x --status open >/dev/null 2>&1; echo $?)"
check "an unrecognized status is refused" "2" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Track \
      --fingerprint fp-x --status maybe >/dev/null 2>&1; echo $?)"
check "a whitespace-carrying fingerprint is refused" "2" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Track \
      --fingerprint "fp x" --status open >/dev/null 2>&1; echo $?)"
check "--waiver on a non-set-aside status is refused" "2" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Track \
      --fingerprint fp-x --status open --waiver "why" >/dev/null 2>&1; echo $?)"
check "epic-finding requires every identity flag" "2" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --fingerprint fp-x --status open >/dev/null 2>&1; echo $?)"
check "epic-attest requires --lane" "2" \
  "$(cd "$df" && "$LEDGER" epic-attest --epic ledgered --story alpha >/dev/null 2>&1; echo $?)"
check "no refused call appended anything" "$before" "$(wc -l < "$efile")"
check "a Critical set aside WITH --waiver is recorded" "0" \
  "$(cd "$df" && "$LEDGER" epic-finding --epic ledgered --story alpha --lane l --severity Critical \
      --fingerprint fp-x --status waived --waiver "accepted for this epic" >/dev/null 2>&1; echo $?)"
contains "the waiver reason lands on the record" "accepted for this epic" \
  "$(grep '"finding":"fp-x"' "$efile")"

# --unresolved and --attestations are separate reads; an unknown epic is silent.
check "--unresolved and --attestations are mutually exclusive" "2" \
  "$(cd "$df" && "$LEDGER" epic-findings --epic ledgered --unresolved --attestations >/dev/null 2>&1; echo $?)"
check "epic-findings requires --epic" "2" \
  "$(cd "$df" && "$LEDGER" epic-findings >/dev/null 2>&1; echo $?)"
check "epic-findings prints nothing for an epic with no trail" "" \
  "$(cd "$df" && "$LEDGER" epic-findings --epic never-ran)"

# A findings write is a PRIMARY write: it fails loudly rather than degrading to a
# no-op the way the best-effort transition kinds do.
dg=$(sandbox)
nojqbin=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$nojqbin/$tool"
done
check "epic-finding fails (never silently skips) when jq is unavailable" "1" \
  "$(cd "$dg" && PATH="$nojqbin" "$LEDGER" epic-finding --epic e --story s --lane l \
      --severity Track --fingerprint fp --status open >/dev/null 2>&1; echo $?)"
contains "and says why, naming it a primary write" "primary write" \
  "$(cd "$dg" && PATH="$nojqbin" "$LEDGER" epic-finding --epic e --story s --lane l \
      --severity Track --fingerprint fp --status open 2>&1 1>/dev/null)"
check "epic-attest fails the same way" "1" \
  "$(cd "$dg" && PATH="$nojqbin" "$LEDGER" epic-attest --epic e --story s --lane l >/dev/null 2>&1; echo $?)"

# --- epic-set --acceptance-altitude (#269, default off) ---
dh=$(sandbox)
( cd "$dh" && "$LEDGER" epic-set --slug altitude --title A ) >/dev/null
check "an epic with no acceptance altitude records none (default is per-story)" "null" \
  "$(jq -r '.acceptanceAltitude // "null"' "$dh/.studious/epics/altitude.json")"
( cd "$dh" && "$LEDGER" epic-set --slug altitude --acceptance-altitude delivery-boundary ) >/dev/null
check "--acceptance-altitude records the opt-in token" "delivery-boundary" \
  "$(jq -r '.acceptanceAltitude' "$dh/.studious/epics/altitude.json")"
check "an unrecognized altitude token is refused before any write" "2" \
  "$(cd "$dh" && "$LEDGER" epic-set --slug altitude --acceptance-altitude boundary >/dev/null 2>&1; echo $?)"
check "the refused token left the recorded one untouched" "delivery-boundary" \
  "$(jq -r '.acceptanceAltitude' "$dh/.studious/epics/altitude.json")"
check "the altitude rides through epic-reconcile to the driver" "delivery-boundary" \
  "$(cd "$dh" && "$LEDGER" epic-reconcile --slug altitude | jq -r '.epic.acceptanceAltitude')"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
