"""Golden-fixture behavioral eval for /gate-audit.

For each directory under tests/fixtures/, builds an ephemeral git repo from
its base/ (committed as the tip of a faked origin/main) and changeset/
(overlaid and committed as the branch under review), wires this repo's own
commands/agents in as project-level Claude Code config, runs `/gate-audit`
headless via the `claude` CLI, and checks the resulting report's verdict
token and finding categories against the fixture's expected.json.

The git setup and the report-parsing/assertion logic are pure and unit
tested (tests/python/test_run_gate_audit_fixtures.py). Only the `claude -p`
invocation itself requires a live model and is not exercised outside CI.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

VERDICT_TOKENS: tuple[str, ...] = ("PASS", "FIX AND RE-AUDIT", "NEEDS DISCUSSION")
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
    def from_dict(data: dict) -> "Expectation":
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
    """Return the body of a markdown '### <heading>' section, up to the next heading."""
    pattern = re.compile(
        rf"^#{{1,6}}\s*{re.escape(heading)}\b.*?$\n(.*?)(?=^#{{1,6}}\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def count_bullet_findings(section: str | None) -> int:
    if not section:
        return 0
    stripped = section.strip()
    if not stripped or re.match(r"(?i)^(none|no critical|no important|n/a)\b", stripped):
        return 0
    return len(re.findall(r"^\s*[-*]\s+\S", section, re.MULTILINE))


def extract_verdict(text: str) -> str | None:
    """Find the assigned verdict token, preferring the bolded one.

    gate-audit.md's own rubric text lists all three tokens, and surrounding
    prose can mention a token in passing (e.g. "not safe to PASS"), so a
    naive substring search is unreliable. The agent's actual verdict is
    bolded (`**FIX AND RE-AUDIT**`); fall back to the first plain occurrence
    only if no bolded token is present.
    """
    section = extract_section(text, "Verdict") or text
    bolded = re.search(
        r"\*\*\s*(PASS|FIX AND RE-AUDIT|NEEDS DISCUSSION)\s*\*\*", section
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
        critical_count=count_bullet_findings(critical_section),
        important_count=count_bullet_findings(important_section),
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
    for category in expected.required_categories:
        if category not in parsed.categories_mentioned:
            failures.append(f"expected category {category!r} not mentioned in findings")

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
    result = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def setup_fixture_repo(fixture_dir: Path, workdir: Path) -> Path:
    """Build an ephemeral git repo: base/ as the fake origin/main, changeset/ overlaid as HEAD.

    Returns the repo path (== workdir).
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

    _wire_plugin_config(workdir)
    return workdir


def _wire_plugin_config(workdir: Path) -> None:
    """Expose this repo's commands/agents/skills as project-level Claude Code config."""
    claude_dir = workdir / ".claude"
    for name in ("commands", "agents", "skills"):
        src = REPO_ROOT / name
        if src.is_dir():
            (claude_dir).mkdir(parents=True, exist_ok=True)
            os.symlink(src, claude_dir / name)
    # Agents reference reference/*.md by relative path; make it resolvable
    # from the fixture repo root too.
    os.symlink(REPO_ROOT / "reference", workdir / "reference")


def run_claude_headless(cwd: Path, timeout_seconds: int = 900) -> str:
    """Invoke `/gate-audit` headless and return the report text.

    Never raises for a failed/timed-out/missing `claude` invocation — the
    failure detail is returned as the "report" so it lands in the uploaded
    artifact and evaluate() reports it as a normal (failing) mismatch instead
    of crashing the whole fixture loop before other fixtures' results are
    saved.
    """
    env = os.environ.copy()
    env["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
    command = [
        "claude",
        "-p",
        "/gate-audit",
        "--dangerously-skip-permissions",
        "--output-format",
        "json",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return f"[harness error] claude timed out after {timeout_seconds}s: {exc}"
    except FileNotFoundError as exc:
        return f"[harness error] claude CLI not found: {exc}"

    stdout = result.stdout.strip()
    if result.returncode != 0:
        return (
            f"[harness error] claude exited {result.returncode}\n"
            f"stderr:\n{result.stderr}\nstdout:\n{stdout}"
        )
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return stdout
    return str(payload.get("result", stdout))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="Fixture directory name to run (repeatable). Default: all fixtures.",
    )
    parser.add_argument(
        "--skip-claude",
        action="store_true",
        help="Build each fixture repo and print its diff without invoking claude. "
        "Useful for verifying fixture git setup locally without a live model.",
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

            if args.skip_claude:
                diff = _run_git(repo, "diff", "origin/main...changeset")
                print(f"=== {name}: changeset diff vs faked origin/main ===")
                print(diff)
                continue

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

    if args.skip_claude:
        return 0
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
