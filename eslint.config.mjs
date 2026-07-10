// Flat config, scoped to workflows/**/*.js. No shareable config, no plugin
// package — every rule here is either an ESLint core rule or a hand-written
// local rule, so `npx eslint@<pin>` (see .github/workflows/ci.yml) is the
// only dependency this repo takes on for JS linting. See
// docs/superpowers/specs/2026-07-09-workflows-js-lint-design.md for the full
// rationale.
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
const harnessShape = {
  preprocess(text) {
    const stripped = text.replace(/^export\s+/, '')
    return [`(async function () {\n${stripped}\n})()`]
  },
  postprocess(messagesList) {
    return messagesList[0].map(m => ({
      ...m,
      line: m.line - 1,
      endLine: typeof m.endLine === 'number' ? m.endLine - 1 : m.endLine,
    }))
  },
  supportsAutofix: false,
}

// Two of the three defect-class rules are plain AST-shape matches, expressed
// with core ESLint's `no-restricted-syntax` selector escape hatch (see
// `rules` below). The third — fail-open null handling — needs to check
// whether a flag is ever referenced in negated form anywhere in its scope,
// which a selector can't express, so it's a small hand-written local rule.
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
    },
  },
]
