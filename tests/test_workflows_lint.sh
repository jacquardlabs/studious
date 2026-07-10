#!/usr/bin/env bash
# Regression tests for eslint.config.mjs (workflows/**/*.js). Proves the
# config catches the three historically-real defect classes named in
# docs/superpowers/specs/2026-07-09-workflows-js-lint-design.md — index-
# misalignment on dead agents, unshift-ordering, fail-open null handling —
# on reconstructed bad patterns, stays quiet on their fixed equivalents, and
# lints the real workflows/epic-driver.js clean (documented suppressions and
# all). Requires network (npx fetches the pinned eslint release; see
# .github/workflows/ci.yml for the same pin).
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
