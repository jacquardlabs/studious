# Dependency checklist — lookup data

Not a detection crutch — a capable model already knows these supply-chain risk classes.
This file is the **lookup data** it won't recall verbatim: the per-ecosystem
manifest↔lockfile pair table, advisory lookup command shapes with their read-only
caveats, the license-family compatibility table, typosquat heuristics, and per-ecosystem
drift signatures. The five dimensions live inline in `agents/dependency-auditor.md`;
consult this for the specifics. CLAUDE.md's documented dependency or licensing posture
overrides anything here. Severity stays reachability-gated: no plausible path from the
codebase to the vulnerable API → `Potential`, drop a tier.

## Manifest ↔ lockfile pairs (per ecosystem)

A manifest edit without its paired lockfile regenerated (or the reverse) is dimension
5's core signal. "Regenerated" means the lockfile's resolved versions, integrity hashes,
and transitive set moved consistently with the manifest change — not a hand-edited
version string.

| Ecosystem | Manifest | Lockfile(s) | Regenerated looks like |
|---|---|---|---|
| JS/TS (npm) | `package.json` | `package-lock.json`, `npm-shrinkwrap.json` | `packages` entries with `resolved` + `integrity` (sha512) updated together |
| JS/TS (yarn) | `package.json` | `yarn.lock` | resolution blocks with `resolved`/`integrity` or `checksum` updated together |
| JS/TS (pnpm) | `package.json` | `pnpm-lock.yaml` | `importers` + `packages` entries updated together |
| JS/TS (bun) | `package.json` | `bun.lockb` (binary) | binary diff present alongside the manifest change |
| Python (uv/PEP 621) | `pyproject.toml` | `uv.lock` | `[[package]]` entries with `wheels`/`sdist` hashes updated together |
| Python (poetry) | `pyproject.toml` | `poetry.lock` | `[[package]]` + `[metadata]` `content-hash` updated together |
| Python (pip) | `requirements*.txt`, `setup.py`, `setup.cfg` | often none — pinned requirements files are their own lock | `--hash=` lines when hash-pinning is in use |
| Python (pipenv) | `Pipfile` | `Pipfile.lock` | `_meta.hash` + per-package `hashes` updated together |
| Go | `go.mod` | `go.sum` | paired `h1:` module + `/go.mod` hash lines added/removed together |
| Rust | `Cargo.toml` | `Cargo.lock` | `[[package]]` entries with `checksum` updated together |
| Ruby | `Gemfile`, `*.gemspec` | `Gemfile.lock` | `GEM`/`specs` graph + `BUNDLED WITH` updated together |
| PHP | `composer.json` | `composer.lock` | `content-hash` + per-package `dist.reference` updated together |
| JVM (Maven) | `pom.xml` | usually none | version properties/`dependencyManagement` are the pinning surface |
| JVM (Gradle) | `build.gradle`, `build.gradle.kts`, `libs.versions.toml` | `gradle.lockfile` (opt-in) | lockfile entries updated alongside the version catalog |
| .NET | `*.csproj`, `Directory.Packages.props`, `packages.config` | `packages.lock.json` (opt-in) | `dependencies` entries with `contentHash` updated together |
| Elixir | `mix.exs` | `mix.lock` | tuple entries with sha256 hashes updated together |
| Vendored trees | `vendor/`, `third_party/` | the tree is its own lock | review the vendoring event: source, version, license, provenance |

## Advisory lookup command shapes (read-only)

None of these resolve or install anything. Never run an ecosystem's install/audit
command that builds a dependency tree from the network (`npm audit` without an existing
lockfile, `pip-audit` against an environment it must first populate, any `install`
variant) — postinstall and build scripts run attacker-controlled code.

- **osv.dev query (primary)** — one unauthenticated POST per changed package@version,
  no token, reachable wherever plain HTTPS is:

  ```bash
  curl -s -X POST https://api.osv.dev/v1/query \
    -d '{"package":{"name":"<name>","ecosystem":"<npm|PyPI|Go|crates.io|RubyGems|Packagist|Maven|NuGet|Hex>"},"version":"<version>"}'
  ```

  Empty `{}` response = no known advisory for that exact version; a `vulns` array
  carries id, severity, affected ranges, and fixed versions.
- **GitHub Advisory Database via `gh api` (fallback when osv.dev is unreachable but
  `gh` is authenticated):**

  ```bash
  gh api /advisories -X GET -f ecosystem=<npm|pip|go|rubygems|composer|maven|nuget|rust> -f affects=<name>
  ```

  In sandboxed environments REST GETs can be proxied or blocked while GraphQL still
  answers; the GraphQL equivalent is `gh api graphql` with a `securityVulnerabilities`
  query on `package: "<name>"`.
- **osv-scanner, when installed (batch, still read-only):**

  ```bash
  osv-scanner --lockfile <path-to-lockfile>
  ```

- **Degrade path:** if every route above fails (offline gate run, blocked egress),
  report "could not verify — advisory data unreachable" in the residual line and mark
  affected findings `Potential`. Never imply clean, and never guess a CVE id you cannot
  cite from a lookup that actually ran.

## License-family compatibility

Judge the *incoming* package's license family against the *project's* regime (its
LICENSE file, or CLAUDE.md's documented posture when that predates the changeset).
Rows: incoming family. Columns: project regime.

| Incoming ↓ / Project → | Permissive (MIT/BSD/Apache-2.0) | Proprietary / closed | Strong copyleft (GPL) |
|---|---|---|---|
| Permissive (MIT, BSD, ISC, Apache-2.0) | OK | OK (keep notices; Apache-2.0 adds patent terms) | OK |
| Weak copyleft (LGPL, MPL-2.0, EPL) | Caution — file/library-level obligations on modification | Caution — dynamic linking usually OK, static/embedded triggers obligations | OK |
| Strong copyleft (GPL-2.0/3.0) | Flag — distribution pulls the combined work copyleft | Flag — incompatible with closed distribution | OK (check 2.0 vs 3.0 compatibility) |
| Network copyleft (AGPL) | Flag — network use counts as distribution | Flag — highest-risk family for a service | Caution |
| No license / "all rights reserved" | Flag — no grant to use at all | Flag | Flag |

Internal-only tools that never distribute soften a distribution-triggered violation one
tier — say so in the finding rather than silently downgrading.

## Typosquat heuristics

- Edit distance 1–2 from a popular package the project doesn't otherwise use
  (`lodash` → `1odash`, `requests` → `requsts`), including homoglyphs and swapped
  separators (`python-dateutil` vs `python_dateutil` vs `dateutil`).
- Namespace confusion: an unscoped npm package shadowing a well-known scoped one (or
  the reverse); a PyPI name matching an internal package (dependency confusion).
- Fresh publish (days old) + install scripts + a name adjacent to something popular —
  the classic triad; any two of the three warrants a finding.
- A version far above the ecosystem norm for a new name (e.g. a first-seen package at
  `99.x`) — the dependency-confusion resolver-preference trick.

## Per-ecosystem drift signatures

- **npm/yarn/pnpm** — `resolved` pointing at a non-registry host or a git/tarball URL;
  `integrity` removed or downgraded (sha512 → sha1); `package.json` range the lockfile
  version doesn't satisfy; new `postinstall`/`preinstall`/`prepare` scripts in the diff.
- **Python** — `uv.lock`/`poetry.lock` hash entries removed; `requirements.txt`
  `--hash=` lines dropped while others keep them; a direct URL or `git+` requirement
  replacing a registry pin; `[tool.uv.sources]`/`[tool.poetry.source]` adding a custom
  index.
- **Go** — `go.sum` entries deleted without the corresponding `go.mod` removal;
  `replace` directives pointing at forks or local paths entering the diff.
- **Rust** — `Cargo.lock` `checksum` removed; `[patch]`/`[replace]` sections or git
  dependencies replacing crates.io versions.
- **Ruby/PHP** — `Gemfile.lock`/`composer.lock` present in the repo but untouched by a
  manifest-changing diff; `composer.lock` `dist.url` off-registry.
- **Any ecosystem** — a lockfile-only change with no manifest change and no
  regeneration rationale in the changeset (dependency swapped under an unchanged
  declared range).
