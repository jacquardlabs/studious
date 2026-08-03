#!/usr/bin/env bash
# Regression tests for eslint.config.mjs (workflows/**/*.js). Proves the
# config catches the five historically-real defect classes that motivated it —
# index-misalignment on dead agents, unshift-ordering, fail-open null handling,
# unpinned agent() dispatch, and the Workflow runtime's forbidden
# nondeterminism APIs (Date.now / Math.random / argless new Date) — on
# reconstructed bad patterns, stays quiet on their fixed equivalents, and lints
# the real workflows/epic-driver.js clean (documented suppressions and all).
# Requires network (npx fetches the pinned eslint release; see
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

# --- eslint-disable-next-line as a block comment suppresses exactly like the `//`
# form above, but the rationale check used to filter on `c.type === 'Line'` and
# silently missed it (#270 fix-and-recheck finding 1) ---
expect_fail "a block-comment eslint-disable-next-line with no reason is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable-next-line local/no-unpinned-agent-dispatch */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "a block-comment eslint-disable-next-line with a reason is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable-next-line local/no-unpinned-agent-dispatch -- deliberately unpinned: pending an A/B, not a default */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

# --- a trailing eslint-disable-line, on the call's own line rather than the line
# above, is the other silently-missed form (#270 fix-and-recheck finding 1) — both
# `//` and `/* */` syntax ---
expect_fail "a trailing eslint-disable-line with no reason is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y' }) // eslint-disable-line local/no-unpinned-agent-dispatch
return { r }
EOF

expect_pass "a trailing eslint-disable-line with a reason is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y' }) // eslint-disable-line local/no-unpinned-agent-dispatch -- deliberately unpinned: pending an A/B, not a default
return { r }
EOF

expect_fail "a trailing block-comment eslint-disable-line with no reason is itself flagged" "has no reason after" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y' }) /* eslint-disable-line local/no-unpinned-agent-dispatch */
return { r }
EOF

expect_pass "a trailing block-comment eslint-disable-line with a reason is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x', phase: 'y' }) /* eslint-disable-line local/no-unpinned-agent-dispatch -- deliberately unpinned: pending an A/B, not a default */
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

# --- a bare file-level eslint-disable with zero unpinned agent() calls to hide is
# still clean: nothing needed the suppression, so no rationale is owed (test-auditor
# finding 5, #270 fix-and-recheck round 3 — the sawUnpinned guard existed but had no
# fixture covering the exact case it exists for) ---
expect_pass "a bare file-level eslint-disable with no unpinned agent() calls at all is clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint-disable */
const ok = true && false
const r = await agent('do it', { label: 'x', model: 'haiku' })
return { r, ok }
EOF

# --- an inline rule-CONFIGURATION comment (`/* eslint <rule>: "off" */`) is a
# different directive from eslint-disable(-next-line) entirely, with no `-- reason`
# convention at all — it silences the named rule file-wide with nothing here able to
# check it for a rationale (architecture-auditor finding 1, #270 fix-and-recheck
# round 3). Caught by its own sibling rule, local/no-rule-config-bypass: verified
# empirically that a report from no-unpinned-agent-dispatch itself about the very
# comment disabling it is swallowed file-wide, at any anchor line — a same-rule fix
# is not viable here, unlike the eslint-disable case above. ---
expect_fail "a rule-configuration comment disabling our rule is itself flagged" "no-rule-config-bypass" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint local/no-unpinned-agent-dispatch: "off" */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_fail "a rule-configuration comment using bare 0 instead of \"off\" is also flagged" "no-rule-config-bypass" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint local/no-unpinned-agent-dispatch: 0 */
const r = await agent('do it', { label: 'x', phase: 'y' })
return { r }
EOF

expect_pass "a rule-configuration comment naming an unrelated rule doesn't trip our check" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
/* eslint local/no-fail-open-boolean: "off" */
const r = await agent('do it', { label: 'x', model: 'haiku' })
return { r }
EOF

# --- defect class 5: Workflow-runtime forbidden nondeterminism APIs ---
# The runtime THROWS on Date.now(), Math.random(), and an argless new Date():
# each would hand a resumed re-execution a different value than the original
# run observed, breaking the resume contract. CI and the Python driver tests
# execute workflows/epic-driver.js under plain node — where all three work
# fine — which is exactly how a module-scope Date.now() once shipped green:
# nothing in this config banned the class until these rules did.
expect_fail "flags Date.now()" "no-restricted-properties" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const startedAt = Date.now()
return { startedAt }
EOF

expect_fail "flags Math.random()" "no-restricted-properties" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const jitter = Math.random()
return { jitter }
EOF

expect_fail "flags an argless new Date()" "no-restricted-syntax" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const when = new Date()
return { when: String(when) }
EOF

expect_pass "an arg-carrying new Date() and deterministic Math members are clean" <<'EOF'
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const when = new Date(1722470400000)
const wider = Math.max(1, 2)
return { when: String(when), wider }
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

# --- harnessShape's line-remap arithmetic (:HARNESS_PREAMBLE_LINES, consumed by
# postprocess and by firstStatementLine in both exemption checkers) is tied to one
# shared constant, not three independently hardcoded literals — but a "message
# substring" fixture like the one above can't actually prove the remap is correct,
# only that no-undef fired at all. Assert the ACTUAL reported line number instead:
# `log(reslt)` sits on the real file's own line 3, so a wrapper change that silently
# added or dropped a preamble line (mis-anchoring every report these functions
# produce) would shift this to 2 or 4 while the message-substring check above stayed
# green (architecture-auditor finding 2, #270 fix-and-recheck round 3) ---
reported_line=$(cd "$ROOT" && npx -y "eslint@$ESLINT_VERSION" --report-unused-disable-directives --format json --stdin --stdin-filename "workflows/fixture.js" - <<'EOF' 2>&1 | node -e "let d=''; process.stdin.on('data',c=>d+=c); process.stdin.on('end',()=>{try{const j=JSON.parse(d); const m=j[0].messages.find(m=>m.ruleId==='no-undef'); console.log(m ? m.line : 'MISSING')}catch(e){console.log('PARSE-ERROR: '+e.message)}})"
export const meta = { name: 'x', description: 'x', whenToUse: 'x', phases: [] }
const r = await agent('do it', { label: 'x' })
log(reslt)
return { r }
EOF
)
if [ "$reported_line" = "3" ]; then
  echo "ok   - no-undef's reported line maps back to the real file's own line 3, not a wrapper-shifted one"
else
  echo "FAIL - expected no-undef reported at the real file's own line 3, got: $reported_line"
  fails=$((fails + 1))
fi

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
