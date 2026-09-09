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
( cd "$d" && "$LEDGER" record --gate decide --verdict BUILD )
check "upsert keeps audit" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "upsert adds decide" "BUILD" "$(jq -r '.gates.decide.verdict' "$f")"

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
( cd "$d2" && "$LEDGER" record --gate decide --verdict BUILD )
out=$(cd "$d2" && "$LEDGER" status)
contains "status names the missing gate" "audit never ran" "$out"

# --- status: non-passing verdict ---
d3=$(sandbox)
( cd "$d3" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
out=$(cd "$d3" && "$LEDGER" status)
contains "status surfaces non-passing audit" "FIX AND RE-AUDIT" "$out"

# --- status: stale sha ---
d4=$(sandbox)
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && git commit -q --allow-empty -m more )
out=$(cd "$d4" && "$LEDGER" status)
contains "status flags stale gate" "re-run" "$out"

# --- status: no ledger -> empty ---
d5=$(sandbox)
out=$(cd "$d5" && "$LEDGER" status)
check "status empty when no ledger" "" "$out"

# --- command prompts invoke the ledger by its bare name, not via ${CLAUDE_PLUGIN_ROOT} ---
# ${CLAUDE_PLUGIN_ROOT} only expands in JSON-config-driven processes, not in commands/*.md
# body text the model runs verbatim (claude-code#9354); a plugin's bin/ is on PATH instead (#83).
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
contains "status run from repo root sees a ledger written from a subdirectory" "audit (PASS) ran on this branch at HEAD" "$out"

# --- record stamps schemaVersion, and preserves it on upsert (#55) ---
f7="$d7/.studious/gates/feat-foo.json"
check "record sets schemaVersion on the new file" "1" "$(jq -r '.schemaVersion' "$f7")"
( cd "$d7/sub/dir" && "$LEDGER" record --gate decide --verdict BUILD )
check "record preserves schemaVersion on upsert" "1" "$(jq -r '.schemaVersion' "$f7")"

# --- status treats a branch-slug collision as no record, not a stale/wrong verdict (#41) ---
d9=$(sandbox)
( cd "$d9" && "$LEDGER" record --gate audit --verdict PASS )
f9="$d9/.studious/gates/feat-foo.json"
# Simulate the collision: feat/foo and feat-foo both slug to feat-foo.json. Rewrite
# the stored .branch to a different branch than the one we're actually on.
tmp9=$(mktemp)
jq '.branch = "feat-foo"' "$f9" > "$tmp9" && mv "$tmp9" "$f9"
out=$(cd "$d9" && "$LEDGER" status)
contains "branch-slug collision reports audit as never ran" "audit never ran on this branch" "$out"

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

# --- json_update regression (#102): exit code isn't provable by file content alone —
# a RETURN trap in a shared writer could produce correct output yet still corrupt the
# calling verb's exit status when it re-fires in the caller's frame under `set -u`.
# Also confirms no temp file survives a successful write.
drc=$(sandbox)
( cd "$drc" && "$LEDGER" record --gate audit --verdict PASS ); rc=$?
check "record exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" work-set --slug rc-work --phase decide ); rc=$?
check "work-set exits 0 on a successful write" "0" "$rc"
( cd "$drc" && "$LEDGER" work-log --slug rc-work --step build --outcome BUILT ); rc=$?
check "work-log exits 0 on a successful write" "0" "$rc"
check "no stray temp files left in the gates store after successful writes" "" \
  "$(find "$drc/.studious/gates" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the work store after successful writes" "" \
  "$(find "$drc/.studious/work" -name '.tmp.*' 2>/dev/null)"

# --- json_update regression (fix-and-re-audit on #102): the original
# `if jq ... && mv ...; then return 0; fi` always read exit 0 — POSIX defines a
# no-else `if` with a false condition as exit 0, not the condition's own status —
# so every mutating verb reported success even when jq failed. Corrupting the
# on-disk JSON forces a deterministic jq parse-error, independent of filesystem
# permissions (which root bypasses in CI).
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

check "no stray temp files left in the gates store after failed writes" "" \
  "$(find "$dfail/.studious/gates" -name '.tmp.*' 2>/dev/null)"
check "no stray temp files left in the work store after failed writes" "" \
  "$(find "$dfail/.studious/work" -name '.tmp.*' 2>/dev/null)"

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

# --dedupe on another branch still resolves through the same store_dir(evidence)/
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

# --- work-log validates the build step's outcome vocabulary (#213) ---
# Three writers had drifted into two dialects (epic driver: DONE; /build and the worker
# contract: BUILT|PAUSED|ESCALATED) and commands/next.md branched on only the latter three,
# leaving epic story branches with an uncaught token. Now checked at the write.
d37=$(sandbox)

for ok_outcome in BUILT PAUSED ESCALATED HANDED-OFF SKIPPED; do
  ( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome "$ok_outcome" ) >/dev/null 2>&1
  check "work-log accepts build outcome $ok_outcome" "0" "$?"
done

( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome DONE ) >/dev/null 2>&1; rc=$?
check "work-log rejects the superseded DONE dialect for --step build" "2" "$rc"

( cd "$d37" && "$LEDGER" work-log --slug enum-work --step build --outcome built ) >/dev/null 2>&1; rc=$?
check "the build outcome check is case-sensitive" "2" "$rc"

# The rejection names the accepted set — a caller that hits this mis-authored a prompt.
# grep, not `case` inside `$( )`: bash 3.2 (macOS's shipped bash, and CI's macos-latest
# runner) fails to parse a case statement inside command substitution.
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
# The epic path keeps a story's branch after landing it, so the branch-gone rule alone
# never fired: 34 of 35 work files sat pinned at phase `merge`, all counted as active by /next.
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

# --- gc keeps a finished work file with a measured scope-delta cohort (#244,
# pre-mortem register item 7): it's the only copy of declaredFiles/scopeDelta/amendments,
# so an unconditional collect would discard the measurement cohort for good. ---
d46=$(sandbox)
( cd "$d46" && "$LEDGER" work-set --slug sd-done --title "finished with scope-delta" --phase "done" ) >/dev/null 2>&1
( cd "$d46" && "$LEDGER" work-log --slug sd-done --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
wf46="$d46/.studious/work/sd-done.json"

out46=$( cd "$d46" && "$LEDGER" gc 2>&1 )
check "gc keeps a finished work file with a measured scope-delta cohort" "yes" \
  "$([ -f "$wf46" ] && echo yes || echo no)"
check "gc names the kept file and its scope-delta moment count" "yes" \
  "$(printf '%s' "$out46" | grep -q 'kept: sd-done still holds 1 measured scope-delta moment' && echo yes || echo no)"

# --- Acceptance round 9 (fix-and-retry): the "kept:" message must interpolate
# SCOPE_DELTA_RETENTION_DAYS, not hardcode it — round 7's fix regressed this by
# hardcoding "14". Fix-and-retry finding 2 (#244 round 9) scoped the guard to
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
# Fix-and-retry finding 1: the destroying path used to print only the generic "removed
# finished work file:" line with no hint anything measured was lost. --force must name
# what it threw away.
check "gc --force names the measured scope-delta moment(s) it discarded" "yes" \
  "$(printf '%s' "$out46f" | grep -q 'removed finished work file: sd-done.json (phase done, --force discarded 1 measured scope-delta moment(s))' && echo yes || echo no)"

# --- Fix-and-retry finding 2 (#244 round 9): the measured-scope-delta guard applies
# to the terminal-phase rule only — a parked story whose branch was deleted never
# reached acceptance, so its cohort is incomplete by construction and gets no keep.
# Plain gc still collects it outright, as before #244. ---
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

# --- gc's guard only arms on a MEASURED scope-delta entry (fix-and-retry finding 2):
# a dead scope check writes --scope-delta-unmeasured (`computeScopeDelta`'s dead-end
# path, workflows/epic-driver.js); a work file whose cohort is only that must not be
# pinned by a cohort never actually measured. ---
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

# --- gc's keep is bounded by SCOPE_DELTA_RETENTION_DAYS (fix-and-retry finding 1,
# BLOCKER): the guard's first cut had no terminating condition, so a landed story's
# work file never released back to plain gc. Now collects once past the retention window. ---
d46r=$(sandbox)
( cd "$d46r" && "$LEDGER" work-set --slug sd-stale --title "past its keep window" --phase "done" ) >/dev/null 2>&1
( cd "$d46r" && "$LEDGER" work-log --slug sd-stale --scope-delta-phase build --scope-delta-files "a.py" ) >/dev/null 2>&1
wf46r="$d46r/.studious/work/sd-stale.json"
# A fixed, far-past timestamp (not `date` arithmetic) avoids the BSD/GNU `date -d`/`-j`
# divide this suite has no precedent for.
tmp46r=$(mktemp)
jq '.updatedAt = "2020-01-01T00:00:00Z"' "$wf46r" > "$tmp46r" && mv "$tmp46r" "$wf46r"
out46r=$( cd "$d46r" && "$LEDGER" gc 2>&1 )
check "gc collects (no --force) a work file whose measured scope-delta cohort is past its retention window" "no" \
  "$([ -f "$wf46r" ] && echo yes || echo no)"
check "gc names the retention-window collection distinctly from an ordinary finished-file collection" "yes" \
  "$(printf '%s' "$out46r" | grep -q 'removed work file past its 14-day scope-delta keep window: sd-stale.json' && echo yes || echo no)"

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

# --- a corrupt gates file is named by episode-open, not leaked as a raw jq error ---
# Read verbs swallow the parse failure and report "no open episode" (exit 2), which
# the door routes to episode-open — so that's where the diagnostic has to land.
dcor=$(sandbox)
mkdir -p "$dcor/.studious/gates"
echo "not json" > "$dcor/.studious/gates/feat-foo.json"
err=$(cd "$dcor" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "a corrupt gates file still reads as 'no open episode' to episode-round" "run episode-open first" "$err"
contains "which is the exit 2 the door routes onward to episode-open" "rc=2" "$err"
err=$(cd "$dcor" && "$LEDGER" episode-open --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "episode-open names the unparseable gates file by path" \
  ".studious/gates/feat-foo.json is not valid JSON" "$err"
contains "episode-open tells the operator to repair or remove it" "repair or remove it before continuing" "$err"
contains "episode-open refuses a corrupt gates file with exit 1, not jq's exit 5" "rc=1" "$err"
check "no raw jq parse error reaches the operator" "no" \
  "$(case "$err" in (*"jq: parse error"*) echo yes ;; (*) echo no ;; esac)"
check "the corrupt file is left exactly as found (never repaired or deleted)" "not json" \
  "$(cat "$dcor/.studious/gates/feat-foo.json")"

# --- a fresh episode-open replaces the finished episode: the round cap bounds
# one episode, never the branch's lifetime ---
( cd "$dep1" && "$LEDGER" episode-open --gate audit )
check "reopening resets the round to 1" "1" "$(jq -r '.episodes.audit.round' "$fep1")"
check "reopening drops the prior episode's verdict (fresh episode)" "null" "$(jq -r '.episodes.audit.verdict // "null"' "$fep1")"
check "reopening leaves the prior dual-written legacy record in place" "PASS" "$(jq -r '.gates.audit.verdict' "$fep1")"

# --- status for an episode-written branch matches the per-gate shape the
# `status` parses today — the dual-write keeps legacy readers untouched ---
dep4=$(sandbox)
( cd "$dep4" && "$LEDGER" episode-open --gate audit )
( cd "$dep4" && "$LEDGER" episode-verdict --gate audit --verdict PASS )
out=$(cd "$dep4" && "$LEDGER" status)
check "status for an episode-written branch matches the legacy proceed message verbatim" \
  "audit (PASS) ran on this branch at HEAD — proceed." "$out"

# an episode-written branch missing the gate reports it exactly like a record-written one
dep5=$(sandbox)
( cd "$dep5" && "$LEDGER" episode-open --gate design-review )
( cd "$dep5" && "$LEDGER" episode-verdict --gate design-review --verdict "PROCEED TO PLAN" )
out=$(cd "$dep5" && "$LEDGER" status)
contains "episode-written branch missing audit reports it in the legacy shape" \
  "audit never ran on this branch" "$out"
( cd "$dep5" && "$LEDGER" episode-open --gate audit )
( cd "$dep5" && "$LEDGER" episode-verdict --gate audit --verdict PASS )

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

# --- the widening rule holds on the UPDATE path too: a round-2 finding cannot reach
# `open` in two calls when one call is refused. Own sandbox, so def1's counts below
# stay the ones its own sequence produced. ---
dwid=$(sandbox)
fwid="$dwid/.studious/gates/feat-foo.json"
( cd "$dwid" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Important --fingerprint r1-known --status open ) >/dev/null
( cd "$dwid" && "$LEDGER" episode-round --gate audit ) >/dev/null

# a round-2 finding parked as `carried` first (which the rule does not refuse)...
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint r2-sneak --status carried ); rc=$?
check "a new round-2 Important records as carried (not blocking, not refused)" "0" "$rc"
# ...cannot then be flipped `open`: that is the same widening the first-record path refuses
err=$(cd "$dwid" && "$LEDGER" episode-finding --gate audit --fingerprint r2-sneak \
    --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "re-recording a round-2 finding as open is refused as widening" "--regression-of" "$err"
contains "the update-path widening refusal exits non-zero" "rc=1" "$err"
check "the refused update leaves the finding carried" "carried" \
  "$(jq -r '.episodes.audit.findings["r2-sneak"].status' "$fwid")"

# a round-1 finding restated as still-standing on round 2 is NOT widening — it is the
# whole point of round 2, and the rule keys on the first-record round to let it through
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --fingerprint r1-known --status carried ) >/dev/null
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --fingerprint r1-known --status open ); rc=$?
check "a round-1 finding may be re-opened on round 2" "0" "$rc"
check "the re-opened round-1 finding keeps its original round" "1" \
  "$(jq -r '.episodes.audit.findings["r1-known"].round' "$fwid")"

# a round-2 finding admitted as a classified regression stays updatable to open
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --lane code-auditor --severity Important \
    --fingerprint r2-regression --status open --regression-of r1-known ) >/dev/null
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --fingerprint r2-regression --status closed ) >/dev/null
( cd "$dwid" && "$LEDGER" episode-finding --gate audit --fingerprint r2-regression --status open ); rc=$?
check "a classified round-2 regression may be re-opened" "0" "$rc"

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

# --lane carries the same guard: it is a field of a tab-separated detail line that
# /review injects verbatim into the next round's lane dispatch prompts
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane "$(printf 'x\tforged\tline')" \
    --severity Track --fingerprint lane-tabs --status open 2>&1 1>/dev/null; echo "rc=$?")
contains "a lane with tabs is refused" "--lane must be a single token" "$err"
contains "the lane refusal is a usage error" "rc=2" "$err"
check "the refused lane records nothing" "null" "$(jq -r '.episodes.audit.findings["lane-tabs"] // "null"' "$fcl")"

# --waiver is prose, so spaces must survive — only control characters are refused,
# because those are what forge an extra episode-get --history line
err=$(cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane security-auditor --severity Critical \
    --fingerprint waiver-nl --status carried \
    --waiver "$(printf 'ok\nwaiver\tforged\tline\tinjected')" 2>&1 1>/dev/null; echo "rc=$?")
contains "a waiver with a newline is refused" "--waiver must not contain control characters" "$err"
contains "the waiver refusal is a usage error" "rc=2" "$err"
check "the refused waiver records nothing" "null" "$(jq -r '.episodes.audit.findings["waiver-nl"] // "null"' "$fcl")"
( cd "$dcl" && "$LEDGER" episode-finding --gate audit --lane security-auditor --severity Critical \
    --fingerprint waiver-prose --status carried --waiver "accepted risk, tracked in #300" ); rc=$?
check "a multi-word waiver reason is still accepted (spaces are not the attack)" "0" "$rc"
# the discriminating assertion is on the rendered SHAPE, not on the refusal: one waiver
# recorded must render as exactly one waiver line, and a detail line must carry exactly
# its four fields. A control character reaching either render breaks these counts, which
# is the failure mode the guards above exist to prevent.
histinj=$(cd "$dcl" && "$LEDGER" episode-get --gate audit --history)
findinj=$(cd "$dcl" && "$LEDGER" episode-get --gate audit --findings)
check "--history renders exactly one waiver line for the one waiver recorded" "1" \
  "$(printf '%s\n' "$histinj" | grep -c '^waiver' || true)"
check "no refused waiver forged a history line" "0" \
  "$(printf '%s\n' "$histinj" | grep -c 'forged' || true)"
check "--findings detail lines carry exactly four tab-separated fields" "4" \
  "$(printf '%s\n' "$findinj" | sed -n 2p | awk -F'\t' '{print NF}')"
check "--findings emits exactly the summary plus one detail line" "2" \
  "$(printf '%s\n' "$findinj" | wc -l | tr -d ' ')"

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

# --- rule 2 at the verdict: an episode does not close over an open Critical ---
dvg=$(sandbox)
fvg="$dvg/.studious/gates/feat-foo.json"
( cd "$dvg" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dvg" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/rce --status open ) >/dev/null
err=$(cd "$dvg" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "a closing verdict over an open Critical is refused" "1 Critical finding(s) are still 'open'" "$err"
contains "the refusal names both exits (close it, or waive it)" "--waiver <reason>" "$err"
contains "the verdict refusal exits non-zero" "rc=1" "$err"
check "no verdict lands on the refused episode" "null" "$(jq -r '.episodes.audit.verdict // "null"' "$fvg")"
check "no legacy record is dual-written by a refused verdict" "null" \
  "$(jq -r '.gates.audit.verdict // "null"' "$fvg")"

# the stop/rethink token is refused too — closing IS the accountable act, whatever it is called
err=$(cd "$dvg" && "$LEDGER" episode-verdict --gate audit --verdict "NEEDS DISCUSSION" 2>&1 1>/dev/null; echo "rc=$?")
contains "a stop/rethink verdict over an open Critical is refused the same way" "still 'open'" "$err"

# the retry verdict is exempt: it is the round outcome that MEANS these are open
( cd "$dvg" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ); rc=$?
check "the retry verdict records over an open Critical" "0" "$rc"

# waive it on the operator's word and the episode closes
( cd "$dvg" && "$LEDGER" episode-round --gate audit ) >/dev/null
( cd "$dvg" && "$LEDGER" episode-finding --gate audit --fingerprint security-auditor/rce \
    --status carried --waiver "exploit needs cluster-admin; tracked in #999" ) >/dev/null
( cd "$dvg" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "a waived Critical lets the episode close" "0" "$rc"
check "the closing verdict is recorded" "PASS" "$(jq -r '.episodes.audit.verdict' "$fvg")"

# an open Important never blocks a verdict — gate-vocabulary.md is explicit that it may
# ride out a terminal PASS still open
dvg2=$(sandbox)
fvg2="$dvg2/.studious/gates/feat-foo.json"
( cd "$dvg2" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dvg2" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/dup --status open ) >/dev/null
( cd "$dvg2" && "$LEDGER" episode-finding --gate audit --lane doc-auditor \
    --severity Track --fingerprint doc-auditor/typo --status open ) >/dev/null
( cd "$dvg2" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "an open Important does not block a terminal PASS" "0" "$rc"
check "that PASS is recorded with the Important still open" "PASS/open" \
  "$(jq -r '.episodes.audit.verdict + "/" + .episodes.audit.findings["code-auditor/dup"].status' "$fvg2")"

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

# --- convergence (#291), the natural path: episode-open, findings, then two plain
# episode-round calls. The first banks blockingByRound["1"], so the second reads a
# real predecessor and fires at round 2 with no hand-seeding — proof the guard isn't
# dead code. Synthetic-seed cases below cover arms this path can't reach.
dnat=$(sandbox)
fnat="$dnat/.studious/gates/feat-foo.json"
( cd "$dnat" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dnat" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/sqli --status open ) >/dev/null
( cd "$dnat" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/dup --status open ) >/dev/null
( cd "$dnat" && "$LEDGER" episode-round --gate audit ); rc=$?
check "natural path: the first episode-round advances (no predecessor to compare)" "0" "$rc"
# nothing was fixed between the rounds, so the blocking set is unchanged at 2 against 2
err=$(cd "$dnat" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "natural path: the second episode-round is refused as non-convergence" "not converging" "$err"
contains "natural path: that refusal is exit 3, reached without any hand-seeded state" "rc=3" "$err"
check "natural path: the refused round does not advance past 2" "2" \
  "$(jq -r '.episodes.audit.round' "$fnat")"
check "natural path: the episode is marked escalated at round 2" "2" \
  "$(jq -r '.episodes.audit.escalated.round' "$fnat")"
check "natural path: the escalation records both counts" "2/2" \
  "$(jq -r '.episodes.audit.escalated | (.blocking|tostring) + "/" + (.priorBlocking|tostring)' "$fnat")"

# the same natural sequence converges when round 2 actually closed something: one
# finding closed drops the set to 1 against 2, so the convergence check passes it
# through and the cap is what stops it — exit 1, no escalation
dnatc=$(sandbox)
fnatc="$dnatc/.studious/gates/feat-foo.json"
( cd "$dnatc" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dnatc" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/sqli --status open ) >/dev/null
( cd "$dnatc" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/dup --status open ) >/dev/null
( cd "$dnatc" && "$LEDGER" episode-round --gate audit ) >/dev/null
( cd "$dnatc" && "$LEDGER" episode-finding --gate audit --fingerprint code-auditor/dup \
    --status closed ) >/dev/null
err=$(cd "$dnatc" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "natural path: a converging round reaches the cap instead" "2-round cap" "$err"
contains "natural path: the cap's refusal is exit 1" "rc=1" "$err"
check "natural path: a converging round records no escalation" "null" \
  "$(jq -r '.episodes.audit.escalated // "null"' "$fnatc")"

# --- convergence (#291): a round that does not strictly reduce the blocking set is
# refused and the episode is marked escalated, ahead of the cap ---
# Synthetic seeds drive the comparison at round 3, past what the cap lets an episode
# reach naturally — the guard's behavior once the cap moves.
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

# --- a failed escalation write is reported as a failed write, never as an escalation ---
# The store is made read-only (dir r-x; mktemp can't write) so the convergence branch
# runs with real counts but its write fails. Skipped when the test runs as root.
dwf=$(sandbox)
fwf="$dwf/.studious/gates/feat-foo.json"
( cd "$dwf" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dwf" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/sqli --status open ) >/dev/null
( cd "$dwf" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/dup --status open ) >/dev/null
jq '.episodes.audit.blockingByRound = {"1": 2, "2": 2} | .episodes.audit.round = 3' "$fwf" > "$fwf.t" && mv "$fwf.t" "$fwf"
chmod 555 "$dwf/.studious/gates"
if : > "$dwf/.studious/gates/.probe" 2>/dev/null; then
  rm -f "$dwf/.studious/gates/.probe"; chmod 755 "$dwf/.studious/gates"
  echo "ok   - (skipped: this user writes through a read-only directory)"
else
  err=$(cd "$dwf" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
  chmod 755 "$dwf/.studious/gates"
  contains "a failed escalation write says the record could NOT be written" "could NOT be written" "$err"
  contains "and states plainly that no episode is marked escalated" "no episode is marked escalated" "$err"
  check "it never claims the episode is now marked escalated" "no" \
    "$(case "$err" in (*"is now marked"*) echo yes ;; (*) echo no ;; esac)"
  contains "a failed escalation write exits 1, not the escalation's 3" "rc=1" "$err"
  check "and nothing was in fact written" "null" "$(jq -r '.episodes.audit.escalated // "null"' "$fwf")"
fi

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
check "--history prints nothing for a gate with no episode" "" "$(cd "$dhi" && "$LEDGER" episode-get --gate decide --history)"
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

# --- the escalated-state wedge has a real exit: while the retry outcome rides, a
# set-aside disposition lands, and at the cap a terminal verdict closes the episode.
# Before this, "waive what will not be fixed" bounced in a circular refusal —
# episode-finding pointed at episode-round, which re-refused at exit 3, pointing back —
# with no exit but episode-open, which archives the findings a waiver must land on. ---
dwedge=$(sandbox)
fwedge="$dwedge/.studious/gates/feat-foo.json"
( cd "$dwedge" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --lane security-auditor \
    --severity Critical --fingerprint security-auditor/hole --status open ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --lane code-auditor \
    --severity Important --fingerprint code-auditor/mess --status open ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --lane test-auditor \
    --severity Important --fingerprint test-auditor/gap --status open ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-round --gate audit ) >/dev/null
( cd "$dwedge" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
err=$(cd "$dwedge" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "the wedge opens: the non-converging round is refused as escalation" "rc=3" "$err"

# the door admits ONLY set-aside dispositions of findings already on the episode
err=$(cd "$dwedge" && "$LEDGER" episode-finding --gate audit --lane doc-auditor \
    --severity Track --fingerprint doc-auditor/new --status waived 2>&1 1>/dev/null; echo "rc=$?")
contains "a NEW fingerprint still cannot enter while the retry outcome rides" "rc=1" "$err"
contains "that refusal names the one door that is open" "set-aside disposition" "$err"
err=$(cd "$dwedge" && "$LEDGER" episode-finding --gate audit \
    --fingerprint code-auditor/mess --status closed 2>&1 1>/dev/null; echo "rc=$?")
contains "a non-set-aside status is still round work, refused while the outcome rides" "rc=1" "$err"
check "the refused close left the finding open" "open" \
  "$(jq -r '.episodes.audit.findings["code-auditor/mess"].status' "$fwedge")"

# the prescribed exits now work — and rule 2 still holds through the door
err=$(cd "$dwedge" && "$LEDGER" episode-finding --gate audit \
    --fingerprint security-auditor/hole --status waived 2>&1 1>/dev/null; echo "rc=$?")
contains "a Critical still waives only with --waiver, even through the door" "rc=1" "$err"
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --fingerprint security-auditor/hole \
    --status waived --waiver "accepted: legacy surface, tracked in #999" ); rc=$?
check "waiving the blocking Critical now succeeds in the escalated state" "0" "$rc"
check "the waiver reason landed on the finding" "accepted: legacy surface, tracked in #999" \
  "$(jq -r '.episodes.audit.findings["security-auditor/hole"].waiver' "$fwedge")"
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --fingerprint code-auditor/mess \
    --status rejected-as-noise ); rc=$?
check "dismissing an Important as noise succeeds through the door" "0" "$rc"
( cd "$dwedge" && "$LEDGER" episode-finding --gate audit --fingerprint test-auditor/gap \
    --status carried ); rc=$?
check "carrying an Important (the messages' own prescribed spelling) succeeds too" "0" "$rc"

# ...and the terminal verdict is recordable at the cap, over the spent retry outcome
( cd "$dwedge" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "the terminal verdict closes the wedged episode" "0" "$rc"
check "the episode records the terminal verdict" "PASS" "$(jq -r '.episodes.audit.verdict' "$fwedge")"
check "the legacy record is dual-written on the way out" "PASS" "$(jq -r '.gates.audit.verdict' "$fwedge")"
check "the escalation record survives as the episode's accountability trail" "2" \
  "$(jq -r '.episodes.audit.escalated.round' "$fwedge")"

# --- the same exit un-wedges the pre-existing cap state: a retry outcome riding
# at the cap used to bounce between "record a verdict" (episode-round's cap
# refusal) and "run episode-round" (episode-verdict's retry refusal) ---
dcw=$(sandbox)
fcw="$dcw/.studious/gates/feat-foo.json"
( cd "$dcw" && "$LEDGER" episode-open --gate audit && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" \
    && "$LEDGER" episode-round --gate audit && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
err=$(cd "$dcw" && "$LEDGER" episode-round --gate audit 2>&1 1>/dev/null; echo "rc=$?")
contains "the cap still refuses the third round, prescribing a verdict" "record a verdict" "$err"
err=$(cd "$dcw" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" 2>&1 1>/dev/null; echo "rc=$?")
contains "re-recording the retry outcome at the cap is refused as movement-free" "rc=1" "$err"
contains "and that refusal prescribes the terminal verdict, not episode-round" "record a terminal verdict" "$err"
( cd "$dcw" && "$LEDGER" episode-verdict --gate audit --verdict "NEEDS DISCUSSION" ); rc=$?
check "a terminal verdict is recordable at the cap over the riding retry outcome" "0" "$rc"
check "the cap-state verdict lands on the episode" "NEEDS DISCUSSION" "$(jq -r '.episodes.audit.verdict' "$fcw")"
check "and dual-writes the legacy record" "NEEDS DISCUSSION" "$(jq -r '.gates.audit.verdict' "$fcw")"

# below the cap the retry outcome still routes through episode-round — the
# verdict door is cap-only
dcw1=$(sandbox)
( cd "$dcw1" && "$LEDGER" episode-open --gate audit && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
err=$(cd "$dcw1" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "below the cap a verdict over the retry outcome still points at episode-round" "run episode-round" "$err"
contains "and still refuses" "rc=1" "$err"

# --- episode-verdict names the exact repair when the legacy dual-write fails ---
# A jq shim fails only the legacy-record write (the one filter touching `.gates[$g]`),
# so the episode write lands but the dual-write doesn't — leaving half-written state
# whose re-run refuses as "already closed," and whose repair the message must name.
ddw=$(sandbox)
fdw="$ddw/.studious/gates/feat-foo.json"
( cd "$ddw" && "$LEDGER" episode-open --gate audit ) >/dev/null
shimbin=$(mktemp -d)
cat > "$shimbin/jq" <<'SHIM'
#!/bin/bash
for a in "$@"; do
  case "$a" in
    (*'.gates[$g]'*) echo "shim: refusing the legacy-record write" >&2; exit 5 ;;
  esac
done
exec "$REAL_JQ" "$@"
SHIM
chmod +x "$shimbin/jq"
err=$(cd "$ddw" && REAL_JQ="$(command -v jq)" PATH="$shimbin:$PATH" \
    "$LEDGER" episode-verdict --gate audit --verdict PASS 2>&1 1>/dev/null; echo "rc=$?")
contains "a failed dual-write names the exact repair command" \
  "record --gate audit --verdict 'PASS'" "$err"
contains "and says a re-run would refuse as already closed" "already closed" "$err"
contains "the failure keeps the dual-write's non-zero exit" "rc=5" "$err"
check "the episode write itself landed (the verdict is recorded)" "PASS" \
  "$(jq -r '.episodes.audit.verdict' "$fdw")"
check "no legacy record was written by the failed dual-write" "null" \
  "$(jq -r '.gates.audit // "null"' "$fdw")"
err=$(cd "$ddw" && "$LEDGER" episode-verdict --gate audit --verdict PASS 2>&1 1>/dev/null; echo "rc=$?")
contains "re-running episode-verdict indeed refuses as already closed" "already closed" "$err"
( cd "$ddw" && "$LEDGER" record --gate audit --verdict PASS ); rc=$?
check "the named repair command heals the legacy record" "0" "$rc"
check "after the repair the legacy verdict matches the episode's" "PASS" \
  "$(jq -r '.gates.audit.verdict' "$fdw")"


# --- episode-get --branch (#330): read another branch's episodes from main ---
# scripts/retro-stats runs on main and reads every story branch's record from
# there, the same way gate-get and evidence-list already take --branch.
deb=$(sandbox)
( cd "$deb" && "$LEDGER" episode-open --gate audit \
    && "$LEDGER" episode-finding --gate audit --lane security-auditor --severity Critical \
         --fingerprint eb-1 --status waived --waiver "accepted for the fixture" ) >/dev/null
git -C "$deb" checkout -q -b other/branch
check "episode-get on a branch with no episodes prints nothing" "" \
  "$(cd "$deb" && "$LEDGER" episode-get --gate audit --history)"
ebhist=$(cd "$deb" && "$LEDGER" episode-get --gate audit --history --branch feat/foo)
contains "episode-get --branch --history reads the named branch's episode" "episode 1 (current)" "$ebhist"
contains "episode-get --branch --history carries that branch's waiver line" "eb-1" "$ebhist"
contains "episode-get --branch --findings reads the named branch's digest" $'digest\tsecurity-auditor\teb-1\twaived' \
  "$(cd "$deb" && "$LEDGER" episode-get --gate audit --findings --branch feat/foo)"
contains "episode-get --branch (summary) reads the named branch" "round 1 of" \
  "$(cd "$deb" && "$LEDGER" episode-get --gate audit --branch feat/foo)"

# --- #368: a Critical found and closed in the same round cannot close the episode ---
d368=$(sandbox)
f368="$d368/.studious/gates/feat-foo.json"
( cd "$d368" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$d368" && "$LEDGER" episode-finding --gate audit --lane product-reviewer \
    --severity Critical --fingerprint product-reviewer/spec --status open ) >/dev/null
( cd "$d368" && "$LEDGER" episode-finding --gate audit --fingerprint product-reviewer/spec --status closed ) >/dev/null
check "closing a finding stamps the round it closed in" "1" "$(jq -r '.episodes.audit.findings["product-reviewer/spec"].closedRound' "$f368")"
err=$(cd "$d368" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "a PASS over a same-round-closed Critical is refused" "found AND closed in round 1" "$err"
contains "the refusal names the fingerprint" "product-reviewer/spec" "$err"
contains "the refusal names the path: retry, re-enter, close there" "run episode-round to" "$err"
contains "the same-round refusal exits 1" "rc=1" "$err"
check "no verdict lands" "null" "$(jq -r '.episodes.audit.verdict // "null"' "$f368")"
( cd "$d368" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ); rc=$?
check "the retry token still records over it" "0" "$rc"
( cd "$d368" && "$LEDGER" episode-round --gate audit ) >/dev/null
( cd "$d368" && "$LEDGER" episode-finding --gate audit --fingerprint product-reviewer/spec --status closed ) >/dev/null
check "re-closing in round 2 restamps closedRound" "2" "$(jq -r '.episodes.audit.findings["product-reviewer/spec"].closedRound' "$f368")"
( cd "$d368" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "a Critical found in round 1 and closed in round 2 lets round 2 close the episode" "0" "$rc"

# --- #368/#361: a terminal verdict certifies the sha the round's judges read ---
d361=$(sandbox)
f361="$d361/.studious/gates/feat-foo.json"
( cd "$d361" && "$LEDGER" episode-open --gate audit ) >/dev/null
opened=$(jq -r '.episodes.audit.roundSha' "$f361")
check "episode-open stamps the sha round 1 judges" "$(git -C "$d361" rev-parse --short HEAD)" "$opened"
( cd "$d361" && git commit -q --allow-empty -m "a fix nobody reviewed" )
err=$(cd "$d361" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "a PASS at a HEAD the round never judged is refused below the cap" "no judge has reviewed HEAD" "$err"
contains "the sha refusal names both shas" "$opened" "$err"
contains "the sha refusal exits 1" "rc=1" "$err"
( cd "$d361" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ); rc=$?
check "the retry token records at the moved HEAD" "0" "$rc"
( cd "$d361" && "$LEDGER" episode-round --gate audit ) >/dev/null
check "episode-round restamps the sha round 2 judges" "$(git -C "$d361" rev-parse --short HEAD)" "$(jq -r '.episodes.audit.roundSha' "$f361")"
( cd "$d361" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" ); rc=$?
check "a PASS at the re-entered round's sha lands" "0" "$rc"
check "the verdict records the sha the judges read" "$(jq -r '.episodes.audit.sha' "$f361")" "$(jq -r '.episodes.audit.reviewedSha' "$f361")"

# at the cap the terminal verdict is the operator's explicit choice: it lands, both shas recorded, gap said aloud
dcap=$(sandbox)
fcap="$dcap/.studious/gates/feat-foo.json"
( cd "$dcap" && "$LEDGER" episode-open --gate audit ) >/dev/null
( cd "$dcap" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
( cd "$dcap" && "$LEDGER" episode-round --gate audit ) >/dev/null
judged=$(jq -r '.episodes.audit.roundSha' "$fcap")
( cd "$dcap" && "$LEDGER" episode-verdict --gate audit --verdict "FIX AND RE-REVIEW" ) >/dev/null
( cd "$dcap" && git commit -q --allow-empty -m "fix after round 2" )
err=$(cd "$dcap" && "$LEDGER" episode-verdict --gate audit --verdict "PASS" 2>&1 1>/dev/null; echo "rc=$?")
contains "at the cap the terminal verdict lands over a moved HEAD" "rc=0" "$err"
contains "and says the gap aloud" "the cap is the operator's explicit choice" "$err"
check "the verdict sha is HEAD" "$(git -C "$dcap" rev-parse --short HEAD)" "$(jq -r '.episodes.audit.sha' "$fcap")"
check "the reviewed sha is what round 2 judged" "$judged" "$(jq -r '.episodes.audit.reviewedSha' "$fcap")"
contains "episode-get --history names the judged sha when it differs" "(judged $judged)" \
  "$(cd "$dcap" && "$LEDGER" episode-get --gate audit --history)"

# --- #399: concurrent writers on one branch both land (json_update takes a lock) ---
d399=$(sandbox)
f399="$d399/.studious/gates/feat-foo.json"
( cd "$d399" && "$LEDGER" record --gate audit --verdict PASS ) >/dev/null
for i in $(seq 1 8); do
  ( cd "$d399" && "$LEDGER" work-set --slug "s$i" --title "t$i" --source "#$i" --phase build ) >/dev/null &
  ( cd "$d399" && "$LEDGER" record --gate "g$i" --verdict OK ) >/dev/null &
done
wait
check "eight concurrent record calls all land on one gates file" "9" "$(jq '.gates | length' "$f399")"
check "eight concurrent work-set calls all land" "8" "$(cd "$d399" && "$LEDGER" work-list | wc -l | tr -d ' ')"
check "no lock directory is left behind" "no" "$([ -d "$f399.lock" ] && echo yes || echo no)"
mkdir "$f399.lock"; touch -t 202001010000 "$f399.lock"
( cd "$d399" && "$LEDGER" record --gate stale --verdict OK ) >/dev/null; rc=$?
check "a stale lock (crashed writer) is reclaimed" "0" "$rc"
check "the write behind the reclaimed lock landed" "OK" "$(jq -r '.gates.stale.verdict' "$f399")"

# --- #346 rule 3: a merged-but-present branch's work file resolves to done ---
d346=$(sandbox)
def346=$(git -C "$d346" branch --list main master | tr -d ' *' | head -1)
( cd "$d346" && git commit -q --allow-empty -m "story work" )
( cd "$d346" && "$LEDGER" work-set --slug landed --title "landed" --branch feat/foo --phase build ) >/dev/null
( cd "$d346" && "$LEDGER" work-set --slug kept --title "kept" --branch feat/foo --phase build --declared-files a.py ) >/dev/null
( cd "$d346" && "$LEDGER" work-log --slug kept --scope-delta-phase build --scope-delta-files b.py ) >/dev/null
( cd "$d346" && "$LEDGER" work-set --slug unmerged --title "unmerged" --branch feat/bar --phase build ) >/dev/null
( cd "$d346" && git checkout -q -b feat/bar && git commit -q --allow-empty -m "other" && git checkout -q feat/foo )
( cd "$d346" && git checkout -q "$def346" && git merge -q --ff-only feat/foo && git checkout -q feat/foo )
out346=$(cd "$d346" && "$LEDGER" gc 2>&1)
contains "gc names the merged-but-present branch it resolved" "resolved to done: landed (branch feat/foo is merged into $def346 and still present)" "$out346"
check "the resolved work file is collected on the same run" "no" "$([ -f "$d346/.studious/work/landed.json" ] && echo yes || echo no)"
check "a merged file under the scope-delta guard is kept, reading done" "done" "$(jq -r '.phase' "$d346/.studious/work/kept.json")"
check "the resolution leaves a merge/MERGED history entry naming the default branch" "$def346" "$(jq -r '.history[-1] | select(.step == "merge" and .outcome == "MERGED") | .into' "$d346/.studious/work/kept.json")"
check "an unmerged branch's work file stays active" "build" "$(jq -r '.phase' "$d346/.studious/work/unmerged.json")"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
