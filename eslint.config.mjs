// Flat config, scoped to workflows/**/*.js. No shareable config, no plugin
// package — every rule here is either an ESLint core rule or a hand-written
// local rule, so `npx eslint@<pin>` (see .github/workflows/ci.yml) is the
// only dependency this repo takes on for JS linting.
//
// workflows/epic-driver.js is executed by the Workflow harness, not by Node
// directly: the harness reads `export const meta` for metadata, strips the
// `export` keyword, and runs the remainder as the body of an async function
// it supplies. That means the file legitimately mixes top-level `await`
// (module-only syntax) with a top-level `return` (function-body-only syntax)
// — no single parser goal accepts it as written, and `node --check` passing
// on it today is an accident of there being no package.json in this file's
// directory ancestry, not a real guarantee. The `harnessShape` processor
// below lints the file in the same shape the harness actually executes it
// in: strip the one `export` keyword, wrap the remainder in an async
// function, then map reported locations back to the original file.
// The processor's wrapper (`preprocess` below) prepends exactly this many synthetic
// lines before the original file's own line 1 — `(async function () {` on its own
// line, nothing more. Every place that maps a wrapped-source line back to the real
// file (postprocess below) or reasons about "the wrapped line the real first
// statement sits on" (checkFileLevelDisableExemption / checkRuleConfigCommentBypass
// further down) must derive from this ONE constant, never repeat the arithmetic as
// its own hardcoded literal (#270 fix-and-recheck round 3, architecture-auditor):
// a future change to the wrapper (e.g. an added synthetic line) would otherwise
// silently mis-anchor every report these functions produce, with nothing here
// tying them together to catch it.
const HARNESS_PREAMBLE_LINES = 1

const harnessShape = {
  preprocess(text) {
    const stripped = text.replace(/^export\s+/, '')
    return [`(async function () {\n${stripped}\n})()`]
  },
  postprocess(messagesList) {
    return messagesList[0].map(m => ({
      ...m,
      line: m.line - HARNESS_PREAMBLE_LINES,
      endLine: typeof m.endLine === 'number' ? m.endLine - HARNESS_PREAMBLE_LINES : m.endLine,
    }))
  },
  supportsAutofix: false,
}

// Two of the four defect-class rules are plain AST-shape matches, expressed
// with core ESLint's `no-restricted-syntax` selector escape hatch (see
// `rules` below). The other two — fail-open null handling and unpinned
// agent() dispatch — each need to check something a selector can't express
// (whether a flag is ever referenced in negated form anywhere in its scope;
// whether a suppression comment on the preceding line carries a non-empty
// rationale), so they're small hand-written local rules. A third hand-written
// rule, no-rule-config-bypass, closes a loophole in enforcing the fourth
// defect class rather than naming a fifth: it exists only because a report
// from no-unpinned-agent-dispatch about its own bypass mechanism is provably
// unable to survive that mechanism (see the rule's own comment below).
const localRules = {
  'no-fail-open-boolean': {
    meta: {
      type: 'problem',
      docs: {
        description:
          'A boolean assigned from an `&&` chain must be checked in negated form (`!flag`) somewhere in scope, or carry a `// eslint-disable-next-line local/no-fail-open-boolean -- fail-closed: <why>` justification. Otherwise a nullable/died dispatch result silently collapses into the same value as an explicit negative, with nothing downstream distinguishing "checked and clear" from "never checked."',
      },
      schema: [],
      messages: {
        neverNegated:
          "'{{name}}' is derived from an `&&` chain but is never checked in negated form (`!{{name}}`). If a died/null dispatch result should be treated as fail-closed, either check `!{{name}}` somewhere, or justify why not with a suppression comment (see rule description).",
      },
    },
    create(context) {
      return {
        VariableDeclarator(node) {
          if (
            node.id.type !== 'Identifier' ||
            !node.init ||
            node.init.type !== 'LogicalExpression' ||
            node.init.operator !== '&&'
          ) {
            return
          }
          const name = node.id.name
          const scope = context.sourceCode.getScope(node)
          const variable =
            scope.variables.find(v => v.name === name) ||
            scope.references.find(r => r.identifier === node.id)?.resolved
          const references = variable ? variable.references : []
          const negated = references.some(ref => {
            const id = ref.identifier
            return (
              id.parent &&
              id.parent.type === 'UnaryExpression' &&
              id.parent.operator === '!' &&
              id.parent.argument === id
            )
          })
          if (!negated) {
            context.report({ node: node.id, messageId: 'neverNegated', data: { name } })
          }
        },
      }
    },
  },
  // #270: `inherit` is a known defect (#136), not a cheap tier — an agent() dispatch
  // with no explicit model silently takes on the session model, so the same call can
  // be judged by two different models on two different days. Every dispatch must
  // either pin one (`model`), route through a registered agentType, or carry a
  // `// eslint-disable-next-line local/no-unpinned-agent-dispatch -- <why>` comment
  // recording that the gap is a deliberate, not-yet-made decision — never a silent
  // default. Routing through an agentType only pins the model if that agent's own
  // frontmatter does — 4 of the 11 in workflows/epic-driver.js's AUDITORS array
  // (code-auditor, doc-auditor, test-auditor, frontend-reviewer) are `model: inherit`
  // today (see the comment beside AUDITORS), so this rule cannot statically verify
  // those four are pinned; it can only verify the dispatch names a registered agent
  // and leaves the agent's own pin to #136's A/B, which is explicitly out of scope
  // here.
  'no-unpinned-agent-dispatch': {
    meta: {
      type: 'problem',
      docs: {
        description:
          'Every agent() dispatch must carry an explicit `model` or `agentType` option in its options object, or a `// eslint-disable-next-line local/no-unpinned-agent-dispatch -- <why>` justification. An unpinned dispatch silently inherits the session model (#136) rather than a deliberately chosen one. Note: `agentType` only satisfies this statically — it does not guarantee the referenced agent itself is pinned. 4 of the 11 agents in workflows/epic-driver.js\'s AUDITORS array (code-auditor, doc-auditor, test-auditor, frontend-reviewer) are `model: inherit`; fixing that is #136\'s A/B, not this rule\'s job.',
      },
      schema: [],
      messages: {
        unpinned:
          'agent() dispatch has no explicit `model` or `agentType` option. Pin one, or justify why not with `// eslint-disable-next-line local/no-unpinned-agent-dispatch -- <why>`.',
        bareExemption:
          'eslint-disable-next-line local/no-unpinned-agent-dispatch has no reason after `--`. A bare disable is exactly the silent default this rule exists to prevent — add a reason, e.g. `-- deliberately unpinned: <why>`.',
        bareFileExemption:
          'A file-level eslint-disable comment (bare, or naming local/no-unpinned-agent-dispatch) covers an unpinned agent() dispatch in this file with no reason after `--`. Add a reason after `--` on the file-level comment, the same as a disable-next-line exemption must.',
      },
    },
    create(context) {
      // Tracks whether this file actually contains an unpinned dispatch, so the
      // file-level check below (which can't cheaply tell "no such comment" from
      // "comment present but nothing needed it") only fires when something in
      // this file actually depends on the suppression it found.
      let sawUnpinned = false
      // Shared by both "can't statically verify a pin" branches below (the missing/
      // non-literal-options case and the literal-but-unpinned case) — previously
      // duplicated inline at each call site.
      function flagUnpinned(node) {
        sawUnpinned = true
        context.report({ node, messageId: 'unpinned' })
        checkExemptionRationale(context, node)
      }
      return {
        CallExpression(node) {
          if (node.callee.type !== 'Identifier' || node.callee.name !== 'agent') return
          const opts = node.arguments[1]
          // No second argument, or one that isn't a literal object, can't be
          // statically verified as pinned — fail closed (report) rather than
          // silently pass on a shape this rule can't read, matching
          // no-fail-open-boolean's own posture above.
          if (!opts || opts.type !== 'ObjectExpression') {
            flagUnpinned(node)
            return
          }
          const pinned = opts.properties.some(p => {
            if (p.type !== 'Property' || p.computed) return false
            if (p.key.type === 'Identifier') return p.key.name === 'model' || p.key.name === 'agentType'
            if (p.key.type === 'Literal') return p.key.value === 'model' || p.key.value === 'agentType'
            return false
          })
          if (!pinned) flagUnpinned(node)
        },
        'Program:exit'() {
          if (sawUnpinned) checkFileLevelDisableExemption(context)
        },
      }
    },
  },
  // #270 fix-and-recheck round 3 (architecture-auditor): an ESLint inline rule-
  // CONFIGURATION comment (`/* eslint local/no-unpinned-agent-dispatch: "off" */`, or
  // `: 0` / `: false`) is a wholly different directive from `eslint-disable`/
  // `eslint-disable-next-line` — it silences the named rule for the rest of the file,
  // with no `-- reason` convention at all, so nothing above could ever check it for a
  // rationale. `noInlineConfig: true` looks like the obvious fix but is not one —
  // verified empirically, it also disables every legitimate `eslint-disable-next-line
  // ... -- <why>` exemption no-unpinned-agent-dispatch's whole design depends on, which
  // would make every documented suppression already in workflows/epic-driver.js start
  // failing lint (see this story's commit message for the empirical check).
  //
  // This MUST be its own rule, never a check bolted onto no-unpinned-agent-dispatch's
  // own Program:exit: verified empirically (a built-in-rule probe, same story's commit
  // message) that an inline `/* eslint <rule>: "off" */` comment disables that rule's
  // reports for the WHOLE file, retroactively — not merely from the comment's position
  // onward, the way an eslint-disable comment's forward-only suppression range works.
  // A report from no-unpinned-agent-dispatch itself about the very comment that
  // disables it would be swallowed by the same mechanism, at any anchor line, first
  // statement included — the firstStatementLine trick that keeps
  // checkFileLevelDisableExemption's report alive against a bare eslint-disable does
  // NOT transfer here. A sibling rule's reports are unaffected, because the comment
  // only names no-unpinned-agent-dispatch.
  'no-rule-config-bypass': {
    meta: {
      type: 'problem',
      docs: {
        description:
          'An inline `/* eslint local/no-unpinned-agent-dispatch: "off" */`-style rule-configuration comment disables that rule file-wide with no rationale check at all. Use `// eslint-disable-next-line local/no-unpinned-agent-dispatch -- <why>` instead, which IS checked for a reason.',
      },
      schema: [],
      messages: {
        ruleConfigBypass:
          'An inline `/* eslint local/no-unpinned-agent-dispatch: "off" */`-style rule-configuration comment disables that rule for the rest of the file with no rationale check at all — unlike eslint-disable(-next-line), it has no `-- <why>` convention to check. Use `// eslint-disable-next-line local/no-unpinned-agent-dispatch -- <why>` instead.',
      },
    },
    create(context) {
      return {
        'Program:exit'() {
          checkRuleConfigCommentBypass(context)
        },
      }
    },
  },
}

// Shared by both exemption checks below. `directiveName` is
// 'eslint-disable-next-line' or 'eslint-disable'; `value` is a comment's
// trimmed text. Returns null if `value` isn't that directive at all (covers
// e.g. 'eslint-disable-next-line' not matching a plain 'eslint-disable'
// comment, and vice versa — the `(?:\s+...)?` anchor to `$` means a
// same-named-but-longer directive like '-next-line' can't be mistaken for
// its shorter prefix). Otherwise `{ coversRule, why }`: coversRule is true
// when the directive names no rules at all (an ESLint bare disable applies
// to everything) or explicitly names local/no-unpinned-agent-dispatch.
function parseDisableDirective(value, directiveName) {
  const match = new RegExp(`^${directiveName}(?:\\s+([\\s\\S]*))?$`).exec(value)
  if (!match) return null
  const rest = match[1] || ''
  const dashIndex = rest.indexOf('--')
  const ruleList = (dashIndex === -1 ? rest : rest.slice(0, dashIndex)).trim()
  const why = (dashIndex === -1 ? '' : rest.slice(dashIndex + 2)).trim()
  const names = ruleList === '' ? [] : ruleList.split(',').map(s => s.trim())
  return { coversRule: names.length === 0 || names.includes('local/no-unpinned-agent-dispatch'), why }
}

// Two ESLint-valid suppression forms can cover the `unpinned` report above with no
// rationale, and both need checking regardless of comment syntax (`//` or `/* */`):
// an `eslint-disable-next-line` directive on the line above the call, or a trailing
// `eslint-disable-line` directive on the call's own line. Neither is filtered by
// comment type — `/* eslint-disable-next-line ... */` is exactly as valid as its
// `//` form, so checking only `c.type === 'Line'` silently let the block form
// through with zero rationale check.
//
// A bare disable with no `-- why` would otherwise pass silently — the exact default
// this rule exists to prevent. The next-line report is anchored to the comment's own
// line, since eslint-disable-next-line's suppression window covers only the line
// immediately following the comment and cannot reach back to swallow it. The
// disable-line report can't use the same trick — that comment sits ON the very line
// it suppresses, so an anchor there is swallowed by the same (ruleId, line) filtering
// `checkFileLevelDisableExemption` documents below. Anchor one line earlier instead:
// `targetLine - 1` is always >= 1 here (harnessShape's wrapper guarantees at least one
// synthetic line before any real statement, so no call site can sit on wrapped line 1),
// and is distinct per call site the same way the next-line anchor already is.
function checkExemptionRationale(context, node) {
  const targetLine = node.loc.start.line
  const comments = context.sourceCode.getAllComments()
  const nextLineComment = comments.find(c => c.loc.start.line === targetLine - 1)
  if (nextLineComment) {
    const parsed = parseDisableDirective(nextLineComment.value.trim(), 'eslint-disable-next-line')
    if (parsed && parsed.coversRule && !parsed.why) {
      context.report({ loc: nextLineComment.loc, messageId: 'bareExemption' })
      return
    }
  }
  const sameLineComment = comments.find(c => c.loc.start.line === targetLine)
  if (sameLineComment) {
    const parsed = parseDisableDirective(sameLineComment.value.trim(), 'eslint-disable-line')
    if (parsed && parsed.coversRule && !parsed.why) {
      context.report({
        loc: { start: { line: targetLine - 1, column: 0 }, end: { line: targetLine - 1, column: 1 } },
        messageId: 'bareExemption',
      })
    }
  }
}

// A file-level `/* eslint-disable */` (bare, or naming this rule) suppresses every
// `unpinned` report for the rest of the file, same as the disable-next-line case
// above — but unlike that case, no report from THIS rule anchored on or after the
// disable comment's own line can survive it (verified empirically: even an
// unconditional report placed exactly on the disable comment's own line is
// swallowed, because ESLint filters by (ruleId, line) after every rule has run,
// not by which report call produced the message). The one place immune to this is
// earlier in the file than the disable comment can legally be: the harnessShape
// processor above requires the file's literal first character to be `export`
// (`text.replace(/^export\s+/, '')`), so nothing can precede that first statement
// without breaking the strip-and-wrap parse entirely — anchoring there survives
// every disable-comment placement a real file can have.
function checkFileLevelDisableExemption(context) {
  // harnessShape.preprocess (top of this file) wraps the original source as
  // `(async function () {\n${stripped}\n})()` — HARNESS_PREAMBLE_LINES synthetic
  // line(s) before the original file's own line 1. So wrapped-source line
  // HARNESS_PREAMBLE_LINES + 1 is always original line 1, in every file this config
  // lints, regardless of that file's own content. Not context.sourceCode.ast.body[0]:
  // that's the single top-level ExpressionStatement wrapping the whole IIFE, which
  // starts at the wrapper's own opening line (the synthetic `(async function () {`
  // itself), not at the real content HARNESS_PREAMBLE_LINES below it.
  const firstStatementLine = HARNESS_PREAMBLE_LINES + 1
  const comments = context.sourceCode.getAllComments()
  const disable = comments.find(c => {
    if (c.type !== 'Block') return false
    const parsed = parseDisableDirective(c.value.trim(), 'eslint-disable')
    return parsed && parsed.coversRule
  })
  if (!disable) return
  const parsed = parseDisableDirective(disable.value.trim(), 'eslint-disable')
  if (!parsed.why) {
    context.report({
      loc: { start: { line: firstStatementLine, column: 0 }, end: { line: firstStatementLine, column: 1 } },
      messageId: 'bareFileExemption',
    })
  }
}

// ESLint's inline rule-CONFIGURATION comment (`/* eslint local/no-unpinned-agent-dispatch:
// "off" */`, or `: 0` / `: false`) is a wholly different directive from `eslint-disable`/
// `eslint-disable-next-line` — it silences this rule for the rest of the file exactly like
// a bare `eslint-disable` does, but carries no `-- reason` convention at all, so nothing
// here could ever satisfy the rationale checks above for it. `noInlineConfig: true` looks
// like the obvious fix but is not one — verified empirically, it disables every legitimate
// `eslint-disable-next-line ... -- <why>` exemption this rule's whole design depends on,
// which would make every documented suppression already in workflows/epic-driver.js start
// failing lint. Flagging this specific construct directly, unconditionally (see the
// Program:exit call site above), closes the actual bypass without that collateral damage.
//
// Anchored at `firstStatementLine`, same trick as checkFileLevelDisableExemption above,
// for the same reason applied one level up: a bare file-level `/* eslint-disable */`
// would disable no-rule-config-bypass's own reports too (it disables every rule), and
// no report anchored at or after such a comment's own line survives it — earlier than
// any comment can legally be is the one place immune to that.
function checkRuleConfigCommentBypass(context) {
  const firstStatementLine = HARNESS_PREAMBLE_LINES + 1
  const comments = context.sourceCode.getAllComments()
  // Deliberately requires whitespace after `eslint` (`eslint ` never `eslint-`), so
  // eslint-disable*/eslint-enable/eslint-env — unrelated directives already handled by
  // the checks above — can never match this pattern.
  const configComment = /^eslint\s+([\s\S]+)$/
  const targetsRuleOff = /local\/no-unpinned-agent-dispatch\s*:\s*"?(?:off|0|false)\b"?/
  const found = comments.some(c => {
    const match = configComment.exec(c.value.trim())
    return match && targetsRuleOff.test(match[1])
  })
  if (found) {
    context.report({
      loc: { start: { line: firstStatementLine, column: 0 }, end: { line: firstStatementLine, column: 1 } },
      messageId: 'ruleConfigBypass',
    })
  }
}

export default [
  {
    files: ['workflows/**/*.js'],
    plugins: {
      local: { rules: localRules },
    },
    processor: harnessShape,
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'script',
      globals: {
        // Injected by the Workflow harness at call time — see the args
        // contract comment at the top of epic-driver.js.
        args: 'readonly',
        agent: 'readonly',
        parallel: 'readonly',
        log: 'readonly',
        phase: 'readonly',
        // Built-ins this file actually uses. Hand-declared rather than
        // pulled from an env/globals package, per the "one dependency-free
        // file" design — extend this list if a future workflows/ file uses
        // another built-in.
        Boolean: 'readonly',
        JSON: 'readonly',
        Object: 'readonly',
        Promise: 'readonly',
        Set: 'readonly',
        String: 'readonly',
        process: 'readonly',
      },
    },
    rules: {
      // Generic correctness floor — hand-picked, not eslint:recommended, so
      // the rule surface stays exactly as wide as the failure classes being
      // defended against and nothing wider.
      'no-undef': 'error',
      // varsIgnorePattern: 'meta' is the one binding the harness itself
      // consumes via the `export` keyword the processor strips before
      // parsing — inside the wrapped shape it's structurally unused, but
      // it's read by the harness before the export ever gets to that point.
      'no-unused-vars': ['error', { varsIgnorePattern: '^meta$' }],
      'no-unreachable': 'error',
      'no-unsafe-negation': 'error',
      'no-unsafe-optional-chaining': 'error',
      'no-dupe-keys': 'error',
      'no-dupe-args': 'error',
      'no-fallthrough': 'error',
      'no-constant-condition': 'error',
      'no-dupe-else-if': 'error',
      'no-duplicate-case': 'error',
      'no-self-compare': 'error',
      'no-const-assign': 'error',
      'no-func-assign': 'error',
      'use-isnan': 'error',
      'valid-typeof': 'error',

      'no-restricted-syntax': [
        'error',
        {
          // Index-misalignment on dead agents: a `.filter().map()` chain
          // whose `.map()` callback takes an index parameter lets a
          // post-filter index drift out of alignment with a parallel,
          // unfiltered array (the exact shape the joinReports rewrite fixed).
          selector:
            "CallExpression[callee.property.name='map'][callee.object.callee.property.name='filter'] > FunctionExpression[params.length>=2], CallExpression[callee.property.name='map'][callee.object.callee.property.name='filter'] > ArrowFunctionExpression[params.length>=2]",
          message:
            "Don't index inside .map() over a .filter() result — the index is post-filter but any array it's used to look up (zip, siblings, original list) is pre-filter, so they drift out of alignment. Zip the index in before filtering, or filter without also indexing.",
        },
        {
          // Unshift-ordering: sequential bare .unshift() calls silently
          // reverse the intended order (the shape collapsed into a single
          // spread unshift when parkedThisRun was fixed).
          selector:
            "CallExpression[callee.type='MemberExpression'][callee.property.name='unshift'][arguments.0.type!='SpreadElement']",
          message:
            "Don't call .unshift() with plain arguments — sequential unshift() calls silently reverse the intended order. Build the ordered list first, then unshift it once via spread: arr.unshift(...ordered).",
        },
      ],
      'local/no-fail-open-boolean': 'error',
      'local/no-unpinned-agent-dispatch': 'error',
      'local/no-rule-config-bypass': 'error',
    },
  },
]
