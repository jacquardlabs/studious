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

# --- evidence-list is a plain passthrough of the branch's evidence log
# (gates-cite-evidence, #worker-evidence-and-board). Mirrors gate-get's exact
# shape: raw cat when the file exists, zero bytes on stdout otherwise — the
# empty case is load-bearing (pre-mortem #2): any stray byte here would falsely
# trigger the "Evidence log for this branch" stamp on a logless branch. ---
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

# --- evidence-list --branch reads another branch's log without checking it out
# (mirrors gate-get --branch's existing precedent) ---
d23=$(sandbox)
( cd "$d23" && "$LEDGER" evidence-append --command "pytest tests/" --exit-code 0 \
    --output-digest "sha256:deadbeef" --origin interactive )
( cd "$d23" && git checkout -q -b feat/other )
out=$(cd "$d23" && "$LEDGER" evidence-list)
check "evidence-list with no --branch reads the current (different, logless) branch" "" "$out"
out=$(cd "$d23" && "$LEDGER" evidence-list --branch feat/foo)
check "evidence-list --branch reads the named branch's log" "pytest tests/" \
  "$(printf '%s' "$out" | jq -r '.command')"

# --- evidence-list anchors to the MAIN working tree across linked worktrees,
# reusing the identical repo_root()/branch_slug() the write path uses (pre-mortem
# #1) — a gate run in a story worktree must read back the same log a worker
# writing from that same worktree just appended to. ---
d24=$(sandbox)
( cd "$d24" && git worktree add -q "$d24/.studious/worktrees/e/s" -b epic/e--s )
( cd "$d24/.studious/worktrees/e/s" && "$LEDGER" evidence-append --command "pytest tests/" \
    --exit-code 0 --output-digest "sha256:deadbeef" --origin subagent --agent-type "epic-driver:build-worker" )
out=$(cd "$d24/.studious/worktrees/e/s" && "$LEDGER" evidence-list)
check "evidence-list from a linked worktree reads the MAIN root evidence file" "pytest tests/" \
  "$(printf '%s' "$out" | jq -r '.command')"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
