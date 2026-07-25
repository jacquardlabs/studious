# Security health review — 2026-07-17

Whole-repo periodic review, run on `main` (not diff-scoped). Baseline cycle — no
prior reports in `docs/studious/security-reviews/`.

## Summary

Strong posture for a local-developer CLI/plugin repo: no network surface, no
secrets processed, no injection sinks reachable by a lower-privilege actor. The
one intentional code-execution path (`shell=True` on project-/plan-supplied
commands) is a documented, accepted trust boundary (issue #48), scoped to the
operator's own machine and their own plan — equivalent to `make`/`tox` running a
project-defined command. Biggest strength: git history is secret-clean and every
git shell-out uses argv-form lists, so user text never reaches a shell. Biggest
exposure: the release workflow installs an unpinned dependency inside a privileged
context (`contents: write` + a cross-repo-dispatch PAT).

## Critical (this week)

None.

## Important (this month)

| # | field | value |
|---|-------|-------|
| I-1 | severity | Important |
| | location | `.github/workflows/release.yml:27` |
| | dimension | ci-supply-chain |
| | finding | `pip install python-semantic-release` unpinned, runs in a `contents:write` job holding `RELEASE_TOKEN` that dispatches the marketplace repo's workflow |
| | confidence | Confirmed (config); exploit needs upstream/registry compromise |
| | recommendation | Pin to an exact version + hash (constraints file or `==x.y.z` with `--require-hashes`); the PAT's blast radius (tag push + cross-repo `workflow run`) makes an unpinned install in this job the highest-value hardening target |

## Track (next review)

| # | field | value |
|---|-------|-------|
| T-1 | severity | Track |
| | location | `.github/workflows/release.yml:17,22` |
| | dimension | ci-pinning |
| | finding | `actions/checkout@v4`, `actions/setup-python@v5` pinned to mutable major-version tags, not commit SHA |
| | confidence | Confirmed |
| | recommendation | Pin GitHub-owned actions to full commit SHA for tamper-evidence; acceptable-but-improvable as-is |
| T-2 | severity | Track |
| | location | `scripts/_gitutil.py:63`, `scripts/verify:52`, `scripts/worktree-setup:20` |
| | dimension | trust-boundary |
| | finding | `shell=True` executes project-/plan-supplied commands verbatim — no allowlist/sandbox |
| | confidence | Confirmed — evaluated, not a vuln |
| | recommendation | No action. Documented accepted deviation (issue #48): same actor authors plan and runs `/build`, on their own machine; "only run /build on plans you would run by hand" is stated at every sink. Logged so the record shows it was assessed, not missed |

## Metrics snapshot

- **Security: Critical/High findings** — 0
- **Exposed secrets (git history)** — 0 (Confirmed clean; strict `git log --all -p` sweep for AWS/GitHub/Slack/Google/OpenAI/PEM key patterns returned empty)
- **Security-config violations** — 1 (I-1, unpinned install in privileged release workflow; T-1 action SHA-pinning is hardening, not a baseline violation)

## Trend vs last cycle

Baseline — no prior report to compare against. All metrics establish the starting line.

## Residual

Verified clean: git history (no secrets), injection sinks (all git calls argv-form,
no `os.system`/`eval`/`exec`/`pickle`/`yaml.load`), no network/SSRF surface (zero
`urllib`/`requests`/socket calls), path traversal (evidence-capture defends with an
allowlist regex plus explicit `.`/`..` rejection, issues #51/#60), and parser regexes
(no catastrophic-backtracking quantifiers). Lanes skipped: web session/cookie/CSRF/
CORS/TLS and authn/authz — this repo has no web surface, server, or auth boundary
(local CLI plugin). Dependency-CVE counting is out of scope here by contract and lives
in `review-codebase-health` (`docs/studious/health-reviews/` — currently only a
`.gitkeep`, no report to cross-reference yet); dependency-confusion is N/A (repo ships
no installable package namespace — `plugin.json` is a Claude Code manifest, not a
registry package). Limitation: `gitleaks`, `osv-scanner`, and `semgrep` are not
installed in this environment; secret scanning used a history-aware pattern grep and
sink analysis was manual — high-entropy-only secrets with no keyword marker could
evade a pattern grep, though the small, secret-free history makes this low-risk.
