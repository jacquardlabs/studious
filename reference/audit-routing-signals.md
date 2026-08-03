# Audit routing signals — canonical file-pattern lists

Canonical source for the deterministic (non-content-judged) first-round changeset-routing
rules `commands/review.md` (auditor 9, auditor 11, auditor 12, and auditors 6–8's
per-changeset clause) and `workflows/epic-driver.js`'s mechanical routing dispatch both apply. Neither restates these
lists inline — both point here, so there is exactly one list to ever drift from.
`reference/epic-orchestration.md`'s plan piece reads the same lists a third time, against a
story's *stated* file surface, for the two reads `reference/epic-plan-contract.md`
specifies: which lanes a proposed gate profile is priced for ("Gate profile"), and
whether a story's surface is majority prompt-prose and therefore `story-supervised`
rather than unattended ("Story class", which cites the Prompt signal section below).
Neither restates a list either. The pricing read is display-only and never recorded: the
driver still derives every actual routing decision from the real changeset. The
story-class read *is* recorded, as the story's class at plan approval. Auditor 10
(operability) is deliberately not covered here: its skip condition is content-judged ("Judge
from the diff's content… not file paths alone" — the "Auditor 10 (operability) is
changeset-routed" paragraph under `commands/review.md`'s "Launch all auditors in
parallel" heading), not a
file-pattern rule, and there is no reliable file-name proxy for "does this code serve
requests, consume queues, or perform network I/O" the way there is for IaC, frontend,
dependency, or prompt file types. That paragraph stays the canonical statement
of the rule; `workflows/epic-driver.js`'s routing dispatch mirrors it as a content judgment
made inline in its own prompt (`routingScopeCheckPrompt`'s `operabilityMatch`, issue #271),
not as a pattern list added here.

**When ambiguous, apply the pattern anyway — default to running the lane, not skipping it.**
A file that loosely or partially matches a pattern below counts as a match.

## Infrastructure signal (auditor 9 / `infra-auditor`)

A changeset matches this signal if any changed file is:

- IaC: `*.tf`, `*.tfvars`, `*.hcl`, a CloudFormation/SAM template, `cdk.json` or a CDK stack
  source, `Pulumi.yaml`
- Kubernetes manifests or Helm charts
- `Dockerfile*`, `docker-compose*`, `compose.*`
- CI pipeline configs: `.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/`
- Deploy configs: `serverless.*`, `Procfile`, `fly.toml`, `render.yaml`, Ansible playbooks

No match on any of these → no infrastructure signal.

## Frontend signal (auditors 6–8 per-changeset clause / `ux-reviewer`, `frontend-reviewer`, Web Interface Guidelines)

A changeset matches this signal if any changed file is:

- Templates: `*.html`, `*.erb`, `*.ejs`, `*.hbs`, `*.pug`
- Components: `*.jsx`, `*.tsx`, `*.vue`, `*.svelte`
- Stylesheets: `*.css`, `*.scss`, `*.sass`, `*.less`

No match on any of these → no frontend signal.

Deliberately excludes bare `.js`/`.ts` files: unlike the framework-specific extensions
above, a plain `.js`/`.ts` file is not a reliable frontend-only signal — it's the same
extension backend services, CLI tools, and this very repository's own `workflows/*.js`
scripts use. `/review`'s own agent-executed check (auditors 6–8) can still use judgment
beyond this list when it reads a `.js`/`.ts` file's actual content and surrounding context;
`workflows/epic-driver.js`'s mechanical routing dispatch, which has no such judgment,
applies this list literally and therefore does not treat a bare `.js`/`.ts` change as a
frontend signal by itself.

This is the *per-changeset* half of `gate-audit.md`'s auditors 6–8 rule only — the
*project-level* "DESIGN.md has no `## Surfaces` web entry, and the repo confirms it" half is
a separate check `gate-audit.md`'s own prose still owns directly (see
`/setup` Step 1's canonical web-signal list); it is not part of this file
and not applied by `workflows/epic-driver.js`'s routing dispatch (see the design doc for
issue #138, Out of scope).

## Dependency signal (auditor 11 / `dependency-auditor`)

A changeset matches this signal if any changed file is:

- JS/TS: `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `bun.lockb`,
  `npm-shrinkwrap.json`
- Python: `pyproject.toml`, `requirements*.txt`, `uv.lock`, `poetry.lock`, `Pipfile`,
  `Pipfile.lock`, `setup.py`, `setup.cfg`
- Go: `go.mod`, `go.sum`
- Rust: `Cargo.toml`, `Cargo.lock`
- Ruby: `Gemfile`, `Gemfile.lock`, `*.gemspec`
- PHP: `composer.json`, `composer.lock`
- JVM: `pom.xml`, `build.gradle`, `build.gradle.kts`, `gradle.lockfile`, `libs.versions.toml`
- .NET: `*.csproj`, `packages.config`, `packages.lock.json`, `Directory.Packages.props`
- Elixir: `mix.exs`, `mix.lock`
- Vendored trees: anything under `vendor/` or `third_party/`

No match on any of these → no dependency signal.

A file-level match deliberately over-fires: a `pyproject.toml` edited only in `[tool.*]`
tables, or a `package.json` edited only in `scripts`, still routes the lane in — the
agent's own content-level self-skip (see `agents/dependency-auditor.md`) is the second
layer, the same way a CI-config-comment-only edit still dispatches `infra-auditor`.
Routing stays deterministic so the mechanical dispatch can apply it without judgment.

## Prompt signal (auditor 12 / `prompt-auditor`)

A changeset matches this signal if any changed file is:

- Claude Code prompt surfaces: `agents/*.md`, `commands/*.md`, `skills/**` (any
  `SKILL.md`), `.claude/agents/**`, `.claude/commands/**`, `.claude/skills/**`,
  `output-styles/**`
- Model-facing instruction docs: `CLAUDE.md` (at any depth), `AGENTS.md`,
  `.cursorrules`, `.cursor/rules/**`, `.github/copilot-instructions.md`, `GEMINI.md`
- Prompt templates and named prompt files: any file or directory whose name contains
  `prompt` (`prompts/`, `prompt_templates/`, `system_prompt.py`, `*.prompt`,
  `*.prompt.md`)
- Plugin reference rubrics consumed by agents at run time: `reference/**` when the repo
  is a Claude Code plugin (a `.claude-plugin/` manifest exists)

No match on any of these → no prompt signal.

Deliberately excludes bare source files, mirroring the Frontend signal's bare-`.js`/`.ts`
precedent: a plain `.py`/`.ts`/`.go` file is not a reliable prompt signal even when it
embeds an LLM call — it's the same extension every non-LLM module uses. `/review`'s
own agent-executed check may still route the lane in on judgment when the diff's content
shows prompt strings at an SDK call site; `workflows/epic-driver.js`'s mechanical routing
dispatch, which has no such judgment, applies this list literally and does not. The
`*prompt*`-name pattern keeps the common embedded-prompt convention deterministic without
that judgment.

A file-level match deliberately over-fires: a CLAUDE.md hunk that only fixes a typo'd
command example still routes the lane in — the agent's own content-level self-skip (see
`agents/prompt-auditor.md`) is the second layer, the same two-layer shape the Dependency
signal uses.
