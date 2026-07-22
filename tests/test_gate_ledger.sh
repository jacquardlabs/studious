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
( cd "$drc" && "$LEDGER" work-log --slug rc-work --step build --outcome DONE ); rc=$?
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
( cd "$dfail" && "$LEDGER" work-log --slug fail-work --step build --outcome DONE ) >/dev/null 2>&1; rc=$?
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
( cd "$d32" && "$LEDGER" work-log --slug "wl-epic--wl-story" --step build --outcome DONE )
evf32="$d32/.studious/epics/wl-epic.events.jsonl"
check "work-log on an epic-qualified slug appends a step event" "1" "$(wc -l < "$evf32" | tr -d ' ')"
stline1=$(sed -n '1p' "$evf32")
check "step event kind" "step" "$(printf '%s' "$stline1" | jq -r '.kind')"
check "step event stores step" "build" "$(printf '%s' "$stline1" | jq -r '.step')"
check "step event stores outcome" "DONE" "$(printf '%s' "$stline1" | jq -r '.outcome')"
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

( cd "$d32" && "$LEDGER" work-log --slug "plain-feature-y" --step build --outcome DONE )
check "work-log on a non-epic-qualified slug appends no event (only wl-epic's file exists)" \
  "wl-epic.events.jsonl" "$(cd "$d32/.studious/epics" && printf '%s\n' *.events.jsonl)"

# --- events.jsonl anchors to the MAIN working tree across linked worktrees,
# exactly like the other four stores (#98) ---
d33=$(sandbox)
git -C "$d33" worktree add -q "$d33/.studious/worktrees/e/s" -b epic/e--s
( cd "$d33/.studious/worktrees/e/s" && "$LEDGER" work-log --slug "e--s" --step build --outcome DONE )
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

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
