# Audit routing signals — canonical file-pattern lists

Canonical source for the deterministic (non-content-judged) first-round changeset-routing
rules `commands/gate-audit.md` (auditor 9, auditor 11, and auditors 6–8's per-changeset
clause) and `workflows/epic-driver.js`'s mechanical routing dispatch both apply. Neither restates these
lists inline — both point here, so there is exactly one list to ever drift from. Auditor 10
(operability) is deliberately not covered here: its skip condition is content-judged ("Judge
from the diff's content… not file paths alone" — see `commands/gate-audit.md`), not a
file-pattern rule, and stays unconditionally dispatched on the epic-driven path (see the
design doc for issue #138).

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
scripts use. `/gate-audit`'s own agent-executed check (auditors 6–8) can still use judgment
beyond this list when it reads a `.js`/`.ts` file's actual content and surrounding context;
`workflows/epic-driver.js`'s mechanical routing dispatch, which has no such judgment,
applies this list literally and therefore does not treat a bare `.js`/`.ts` change as a
frontend signal by itself.

This is the *per-changeset* half of `gate-audit.md`'s auditors 6–8 rule only — the
*project-level* "DESIGN.md has no `## Surfaces` web entry, and the repo confirms it" half is
a separate check `gate-audit.md`'s own prose still owns directly (see
`/extract-design-system` Step 1's canonical web-signal list); it is not part of this file
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
