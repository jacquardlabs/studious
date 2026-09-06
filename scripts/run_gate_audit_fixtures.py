"""Golden-fixture behavioral eval for /review.

For each directory under tests/fixtures/, builds an ephemeral git repo from
its base/ (faked origin/main tip) and changeset/ (the branch under review),
wires this repo's commands/agents in as project-level Claude Code config,
runs `/review` headless via the `claude` CLI, and checks the report's
verdict and finding categories against the fixture's expected.json.

Git setup and report parsing/assertion are pure and unit tested
(tests/python/test_run_gate_audit_fixtures.py); only the `claude -p`
invocation needs a live model and only runs in CI.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gitutil import run as _gitutil_run

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

VERDICT_TOKENS: tuple[str, ...] = ("PASS", "FIX AND RE-REVIEW", "NEEDS DISCUSSION")
KNOWN_CATEGORIES: tuple[str, ...] = (
    "security",
    "code quality",
    "documentation",
    "architecture",
    "ux",
    "frontend",
    "accessibility",
)


@dataclasses.dataclass(frozen=True)
class Expectation:
    verdict_any_of: tuple[str, ...]
    min_critical_findings: int = 0
    min_important_findings: int = 0
    max_critical_findings: int | None = None
    max_important_findings: int | None = None
    required_categories: tuple[str, ...] = ()

    @staticmethod
    def from_dict(data: dict) -> Expectation:
        return Expectation(
            verdict_any_of=tuple(data["verdict_any_of"]),
            min_critical_findings=data.get("min_critical_findings", 0),
            min_important_findings=data.get("min_important_findings", 0),
            max_critical_findings=data.get("max_critical_findings"),
            max_important_findings=data.get("max_important_findings"),
            required_categories=tuple(data.get("required_categories", ())),
        )


@dataclasses.dataclass(frozen=True)
class ParsedReport:
    verdict: str | None
    critical_count: int
    important_count: int
    categories_mentioned: frozenset[str]


def extract_section(text: str, heading: str) -> str | None:
    """Return a markdown section's body, up to the next heading at the same or a shallower level.

    Must stop at same-or-shallower, not *any* heading: a real report nests
    `###` findings under `## Critical findings`, so an any-heading terminator
    would stop at the first finding and read the section as empty.
    """
    start = re.compile(
        rf"^(#{{1,6}})\s*{re.escape(heading)}\b.*$",
        re.MULTILINE | re.IGNORECASE,
    )
    match = start.search(text)
    if not match:
        return None
    level = len(match.group(1))
    rest = text[match.end() :]
    terminator = re.compile(rf"^#{{1,{level}}}\s", re.MULTILINE).search(rest)
    return (rest[: terminator.start()] if terminator else rest).lstrip("\n")


def count_findings(section: str | None) -> int:
    """Count findings in a section body, across both shapes reports use.

    Prefer subheadings when present (`/review`'s shape: one `###` per finding,
    bullets beneath are detail, not separate findings); fall back to counting
    bullets for shorter flat-list reports.
    """
    if not section:
        return 0
    stripped = section.strip()
    if not stripped or re.match(r"(?i)^(none|no critical|no important|n/a)\b", stripped):
        return 0
    subheadings = re.findall(r"^#{1,6}\s+\S", section, re.MULTILINE)
    if subheadings:
        return len(subheadings)
    return len(re.findall(r"^\s*[-*]\s+\S", section, re.MULTILINE))


def extract_verdict(text: str) -> str | None:
    """Find the assigned verdict token, preferring the bolded one.

    Rubric prose can mention a token in passing (e.g. "not safe to PASS"), so
    a naive substring search is unreliable; the actual verdict is bolded
    (`**FIX AND RE-REVIEW**`). Fall back to first plain occurrence otherwise.
    """
    section = extract_section(text, "Verdict") or text
    bolded = re.search(
        r"\*\*\s*(PASS|FIX AND RE-REVIEW|NEEDS DISCUSSION)\s*\*\*", section
    )
    if bolded:
        return bolded.group(1)
    positions = [(section.find(token), token) for token in VERDICT_TOKENS if token in section]
    if not positions:
        return None
    return min(positions, key=lambda pair: pair[0])[1]


def detect_categories(text: str) -> frozenset[str]:
    lower = text.lower()
    return frozenset(category for category in KNOWN_CATEGORIES if category in lower)


def parse_audit_report(text: str) -> ParsedReport:
    critical_section = extract_section(text, "Critical findings")
    important_section = extract_section(text, "Important findings")
    combined = "\n".join(section for section in (critical_section, important_section) if section)
    return ParsedReport(
        verdict=extract_verdict(text),
        critical_count=count_findings(critical_section),
        important_count=count_findings(important_section),
        categories_mentioned=detect_categories(combined),
    )


def evaluate(parsed: ParsedReport, expected: Expectation) -> list[str]:
    """Return a list of human-readable failure reasons; empty means the fixture passed."""
    failures: list[str] = []

    if parsed.verdict not in expected.verdict_any_of:
        failures.append(
            f"verdict {parsed.verdict!r} not in expected {expected.verdict_any_of!r}"
        )
    if parsed.critical_count < expected.min_critical_findings:
        failures.append(
            f"expected >= {expected.min_critical_findings} critical finding(s), "
            f"parsed {parsed.critical_count}"
        )
    if parsed.important_count < expected.min_important_findings:
        failures.append(
            f"expected >= {expected.min_important_findings} important finding(s), "
            f"parsed {parsed.important_count}"
        )
    if (
        expected.max_critical_findings is not None
        and parsed.critical_count > expected.max_critical_findings
    ):
        failures.append(
            f"expected <= {expected.max_critical_findings} critical finding(s), "
            f"parsed {parsed.critical_count}"
        )
    if (
        expected.max_important_findings is not None
        and parsed.important_count > expected.max_important_findings
    ):
        failures.append(
            f"expected <= {expected.max_important_findings} important finding(s), "
            f"parsed {parsed.important_count}"
        )
    failures.extend(
        f"expected category {category!r} not mentioned in findings"
        for category in expected.required_categories
        if category not in parsed.categories_mentioned
    )

    return failures


def discover_fixtures() -> list[Path]:
    return sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())


def _copy_tree_overlay(src: Path, dst: Path) -> None:
    """Copy every file under src into dst, overwriting/adding, never deleting."""
    for path in src.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _run_git(repo: Path, *args: str) -> str:
    return _gitutil_run(["git", *args], cwd=repo, check=True).stdout.strip()


def setup_fixture_repo(
    fixture_dir: Path, workdir: Path, source_root: Path = REPO_ROOT
) -> Path:
    """Build an ephemeral git repo: base/ as the fake origin/main, changeset/ overlaid as HEAD.

    ``source_root`` is the plugin root whose commands/agents/skills get wired
    in; ``run_ab_eval`` passes a shadow root so an arm can vary a prompt or
    model pin without mutating checked-in files. Returns the repo path (==
    workdir).
    """
    workdir.mkdir(parents=True, exist_ok=True)
    _copy_tree_overlay(fixture_dir / "base", workdir)

    _run_git(workdir, "init", "-q", "-b", "main")
    _run_git(workdir, "config", "user.email", "gate-audit-fixtures@example.com")
    _run_git(workdir, "config", "user.name", "gate-audit-fixtures")
    _run_git(workdir, "add", "-A")
    _run_git(workdir, "commit", "-q", "-m", "base")
    base_sha = _run_git(workdir, "rev-parse", "HEAD")

    # Fake a remote-tracking ref so `git merge-base HEAD origin/main` resolves
    # without a real remote.
    _run_git(workdir, "update-ref", "refs/remotes/origin/main", base_sha)

    _run_git(workdir, "checkout", "-q", "-b", "changeset")
    _copy_tree_overlay(fixture_dir / "changeset", workdir)
    _run_git(workdir, "add", "-A")
    _run_git(workdir, "commit", "-q", "-m", "changeset under review")

    _wire_plugin_config(workdir, source_root)
    return workdir


def _wire_plugin_config(workdir: Path, source_root: Path = REPO_ROOT) -> None:
    """Expose this repo's commands/agents/skills as project-level Claude Code config.

    Deliberately does NOT symlink reference/: the fan-out command reads the
    shared prompt contract from ``${CLAUDE_PLUGIN_ROOT}/reference/`` and
    injects it into each agent dispatch, so a dispatched auditor needs no
    reference/ on disk — matching a real consuming project. Symlinking it here
    would mask a runtime gap where the posture silently drops in users' repos.
    """
    claude_dir = workdir / ".claude"
    for name in ("commands", "agents", "skills"):
        src = source_root / name
        if src.is_dir():
            (claude_dir).mkdir(parents=True, exist_ok=True)
            os.symlink(src, claude_dir / name)


def run_claude_headless(
    cwd: Path, timeout_seconds: int = 900, plugin_root: Path = REPO_ROOT
) -> str:
    """Invoke `/review` headless and return the report text."""
    text, _cost = run_claude_headless_json(cwd, timeout_seconds, plugin_root)
    return text


def run_claude_headless_json(
    cwd: Path, timeout_seconds: int = 900, plugin_root: Path = REPO_ROOT
) -> tuple[str, float | None]:
    """Invoke `/review` headless; return (report text, cost in USD if reported).

    ``plugin_root`` becomes ``CLAUDE_PLUGIN_ROOT``, which the fan-out command
    resolves ``reference/`` against; a shadow root is how an A/B arm swaps
    that contract for a variant.

    Never raises on a failed/timed-out/missing `claude` invocation — the
    failure detail is returned as the "report" so evaluate() scores it as a
    normal failing mismatch instead of aborting the whole fixture loop.
    """
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    command = [
        "claude",
        "-p",
        "/review",
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
    ]
    try:
        result = subprocess.run(
            command,
            check=False,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return f"[harness error] claude timed out after {timeout_seconds}s: {exc}", None
    except FileNotFoundError as exc:
        return f"[harness error] claude CLI not found: {exc}", None

    stdout = result.stdout.strip()
    if result.returncode != 0:
        return (
            f"[harness error] claude exited {result.returncode}\n"
            f"stderr:\n{result.stderr}\nstdout:\n{stdout}"
        ), None
    return parse_cli_json(stdout)


def parse_cli_json(stdout: str) -> tuple[str, float | None]:
    """Pull (final text, cost) out of `claude -p --output-format json` stdout.

    Claude Code 2.1.x emits a JSON array of stream events (last `type:
    "result"` element carries text + `total_cost_usd`); older builds emit a
    single object with a `result` key. Handle both; fall back to raw stdout
    on an unrecognized shape rather than crashing the fixture loop.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout, None

    if isinstance(payload, list):
        finals = [
            event
            for event in payload
            if isinstance(event, dict) and event.get("type") == "result"
        ]
        if not finals:
            return stdout, None
        payload = finals[-1]

    if not isinstance(payload, dict):
        return stdout, None
    return str(payload.get("result", stdout)), _as_cost(payload.get("total_cost_usd"))


def _as_cost(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="Fixture directory name to run (repeatable). Default: all fixtures.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Directory to write each fixture's raw report text to, for CI upload.",
    )
    args = parser.parse_args(argv)

    fixture_dirs = discover_fixtures()
    if args.fixtures:
        wanted = set(args.fixtures)
        fixture_dirs = [f for f in fixture_dirs if f.name in wanted]

    if not fixture_dirs:
        print("No fixtures found.", file=sys.stderr)
        return 1

    overall_ok = True
    for fixture_dir in fixture_dirs:
        name = fixture_dir.name
        expected = Expectation.from_dict(json.loads((fixture_dir / "expected.json").read_text()))

        with tempfile.TemporaryDirectory(prefix=f"gate-audit-fixture-{name}-") as tmp:
            repo = setup_fixture_repo(fixture_dir, Path(tmp))
            report_text = run_claude_headless(repo)

        if args.artifacts_dir:
            args.artifacts_dir.mkdir(parents=True, exist_ok=True)
            (args.artifacts_dir / f"{name}.txt").write_text(report_text)

        parsed = parse_audit_report(report_text)
        failures = evaluate(parsed, expected)

        if failures:
            overall_ok = False
            print(f"FAIL {name}")
            for failure in failures:
                print(f"  - {failure}")
        else:
            print(f"PASS {name} (verdict={parsed.verdict})")

    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
