#!/usr/bin/env bash
# Regression tests for eslint.config.mjs (workflows/**/*.js). Proves the
# config catches the four historically-real defect classes that motivated it —
# index-misalignment on dead agents, unshift-ordering, fail-open null handling,
# unpinned agent() dispatch — on reconstructed bad patterns, stays quiet on
# their fixed equivalents, and lints the real workflows/epic-driver.js clean
# (documented suppressions and all). Requires network (npx fetches the pinned
# eslint release; see .github/workflows/ci.yml for the same pin).
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ESLINT_VERSION="10.6.0"
fails=0

# lint_stdin <fake-path-under-workflows/> <<< "<source>"
# Feeds source on stdin, pretending it lives at the given path so it matches
# the config's `files: ['workflows/**/*.js']` glob, without ever writing a
# fixture file that CI's own `eslint workflows/` sweep would then lint too.
lint_stdin() {
  ( cd "$ROOT" && npx -y "eslint@$ESLINT_VERSION" --report-unused-disable-directives --stdin --stdin-filename "workflows/$1" - )
}

expect_fail() { # description, rule-substring, source (stdin)
  local desc="$1" needle="$2" out rc
  out=$(lint_stdin "fixture.js" 2>&1)
  rc=$?
  if [ "$rc" -ne 0 ] && case "$out" in *"$needle"*) true ;; *) false ;; esac; then
    echo "ok   - $desc"
  else
    echo "FAIL - $desc"; echo "       expected exit!=0 and output containing: $needle"; echo "       exit=$rc output: $out"
    fails=$((fails + 1))
  fi
}

expect_pass() { # description, source (stdin)
  local desc="$1" out rc
  out=$(lint_stdin "fixture.js" 2>&1)
  rc=$?
  if [ "$rc" -eq 0 ]; then
    echo "ok   - $desc"
  else
    echo "FAIL - $desc"; echo "       expected exit=0"; echo "       exit=$rc output: $out"
    fails=$((fails + 1))
  fi
}

# --- defect class 1: index-misalignment on dead agents ---
expect_fail "flags .filter().map() with an index param" "no-restricted-syntax" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const reports = [null, { name: 'a' }, null, { name: 'b' }]
const agentsList = ['agent-1', 'agent-2', 'agent-3', 'agent-4']
const joined = reports.filter(Boolean).map((r, i) => `${agentsList[i]}: ${r.name}`)
return { joined }
EOF

expect_pass "index zipped in before filtering is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const reports = [null, { name: 'a' }, null, { name: 'b' }]
const agentsList = ['agent-1', 'agent-2', 'agent-3', 'agent-4']
const joined = reports.map((r, i) => (r ? `${agentsList[i]}: ${r.name}` : null)).filter(Boolean)
return { joined }
EOF

# --- defect class 2: unshift-ordering ---
expect_fail "flags a bare (non-spread) .unshift() call" "no-restricted-syntax" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const parkedThisRun = []
parkedThisRun.unshift('third')
parkedThisRun.unshift('second')
parkedThisRun.unshift('first')
return { parkedThisRun }
EOF

expect_pass "a single spread .unshift() is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const parkedThisRun = []
const ordered = ['first', 'second', 'third']
parkedThisRun.unshift(...ordered)
return { parkedThisRun }
EOF

# --- defect class 3: fail-open null handling ---
expect_fail "flags an &&-derived boolean never checked in negated form" "no-fail-open-boolean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const auditVerdict = { verdict: 'PASS' }
const auditOk = auditVerdict && auditVerdict.verdict === 'PASS'
return { auditOk }
EOF

expect_pass "an &&-derived boolean checked via !flag is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const auditVerdict = { verdict: 'PASS' }
const auditOk = auditVerdict && auditVerdict.verdict === 'PASS'
const notes = !auditOk ? 'audit did not pass' : ''
return { auditOk, notes }
EOF

expect_pass "an &&-derived boolean with a justified suppression is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const auditVerdict = { verdict: 'PASS' }
// eslint-disable-next-line local/no-fail-open-boolean -- fail-closed: fed into Boolean(auditOk && ...) below, never used bare
const auditOk = auditVerdict && auditVerdict.verdict === 'PASS'
const ready = Boolean(auditOk)
return { ready }
EOF

# --- defect class 4: unpinned agent() dispatch (#270) ---
expect_fail "flags an agent() call with no model or agentType option" "no-unpinned-agent-dispatch" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "flags an agent() call with only one argument" "no-unpinned-agent-dispatch" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it')
return { r }
EOF

expect_fail "flags an agent() call whose options come from a variable, not a literal" "no-unpinned-agent-dispatch" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const opts = { label: 'x', phase: 'y', model: 'haiku' }
const r = await agent('do it', opts)
return { r }
EOF

expect_fail "flags a spread inside the options object even if the spread source is pinned" "no-unpinned-agent-dispatch" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const base = { model: 'haiku' }
const r = await agent('do it', { ...base, label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "an agent() call pinned with an explicit model is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y', model: 'haiku', effort: 'low' })
return { r }
EOF

expect_pass "an agent() call routed through an agentType is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { agentType: 'studious:some-auditor', label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "an unpinned agent() call with a justified suppression is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line local/no-unpinned-agent-dispatch -- deliberately unpinned: pending an A/B, not a default
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "a bare suppression with no reason after -- is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line local/no-unpinned-agent-dispatch
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "a suppression with a dash marker but blank text after it is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line local/no-unpinned-agent-dispatch --
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

# --- a bare disable-next-line (no rule list at all) covers every rule, ours
# included, and is just as silent a default as one that names our rule with
# no reason ---
expect_fail "a bare eslint-disable-next-line with no rule list at all is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "a bare eslint-disable-next-line with a reason after -- is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line -- deliberately unpinned: pending an A/B, not a default
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

# --- a file-level eslint-disable covers every later line, ours included, and
# is checked for a rationale the same way (#270 fix-and-recheck finding 3) ---
expect_fail "a file-level bare eslint-disable with no reason is itself flagged" "A file-level eslint-disable" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "a file-level bare eslint-disable with a reason is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable -- deliberately unpinned: pending an A/B, not a default */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "a file-level eslint-disable naming our rule with no reason is itself flagged" "A file-level eslint-disable" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable local/no-unpinned-agent-dispatch */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "a file-level eslint-disable naming an unrelated rule doesn't suppress a real unpinned dispatch" "no explicit \`model\` or \`agentType\` option" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable local/no-fail-open-boolean */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

# --- suppression directives are still checked for staleness ---
expect_fail "a stale suppression (rule wouldn't have fired) is itself flagged" "Unused eslint-disable directive" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
// eslint-disable-next-line local/no-fail-open-boolean -- fail-closed: stale, x is checked below
const x = true && false
const y = !x
return { y }
EOF

# --- generic correctness floor: catches what node --check structurally can't ---
expect_fail "no-undef catches a misspelled identifier" "no-undef" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x' })
log(reslt)
return { r }
EOF

# --- the real file lints clean (documented suppressions and all) ---
out=$(cd "$ROOT" && npx -y "eslint@$ESLINT_VERSION" --report-unused-disable-directives workflows/epic-driver.js 2>&1)
rc=$?
if [ "$rc" -eq 0 ]; then
  echo "ok   - workflows/epic-driver.js lints clean"
else
  echo "FAIL - workflows/epic-driver.js lints clean"; echo "       exit=$rc output: $out"
  fails=$((fails + 1))
fi

# --- node --check still passes (belt-and-suspenders with the CI job) ---
if (cd "$ROOT" && node --check workflows/epic-driver.js) >/dev/null 2>&1; then
  echo "ok   - node --check passes on workflows/epic-driver.js"
else
  echo "FAIL - node --check on workflows/epic-driver.js"
  fails=$((fails + 1))
fi

echo "----"
if [ "$fails" -eq 0 ]; then echo "all workflows lint tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
