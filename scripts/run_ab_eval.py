"""Comparative A/B eval for gate-audit prompt and model changes.

`run_gate_audit_fixtures.py` answers "does the current configuration still pass
its golden fixtures?" — one run per fixture, pass/fail. This answers a different
question: "does changing one variable move the outcome, and by how much against
run-to-run noise?" Two or more arms, N trials each, scored per planted defect
rather than by finding counts.

An arm varies one thing:

- ``contract`` — swap a file under ``reference/`` (in practice
  ``reference/prompt-contract.md``) for a variant.
- ``models`` — rewrite the ``model:`` frontmatter pin on named agents.

Both are applied by building a **shadow plugin root**: a tree of symlinks back
to this repo with only the overridden files materialized as real copies. The
checked-in prompts and agents are never mutated, so an interrupted run leaves
nothing to clean up and two arms can be built concurrently.

Scoring separates the two ways an arm can lose a finding, which a bare count
cannot tell apart:

- ``REPORTED`` — filed in a findings section at or above its floor tier.
- ``UNDER_TIERED`` — filed as a finding, but below its floor tier.
- ``DEMOTED`` — present in the report text, but not filed as a finding at all.
- ``MISSED`` — absent from the report entirely.

The DEMOTED/MISSED split is the reason this file exists. The calibration wording
in ``reference/prompt-contract.md`` §4 has produced demotions before — a real
missing-auth Critical rendered as prose instead of filed — and a harness that
only counts findings scores that identically to never having found it. Those are
opposite defects with opposite fixes, so an eval that conflates them can only
mislead.

Pure logic (shadow-tree construction, frontmatter rewriting, classification,
aggregation) is unit tested in ``tests/python/test_run_ab_eval.py``. Only the
``claude -p`` invocation, reused from ``run_gate_audit_fixtures``, needs a live
model. Protocol and worked experiments: ``tests/ab/README.md``.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath

from run_gate_audit_fixtures import (
    FIXTURES_DIR,
    REPO_ROOT,
    discover_fixtures,
    extract_section,
    parse_audit_report,
    run_claude_headless_json,
    setup_fixture_repo,
)

# Ordered worst-first; a defect's floor names the lowest tier that still counts
# as reporting it, and everything after that tier in this tuple is under-tiered.
TIERS: tuple[str, ...] = ("critical", "important", "track")

TIER_HEADINGS: Mapping[str, str] = {
    "critical": "Critical findings",
    "important": "Important findings",
    "track": "Track findings",
}

OUTCOMES: tuple[str, ...] = ("REPORTED", "UNDER_TIERED", "DEMOTED", "MISSED")

FRONTMATTER_RE = re.compile(r"\A---\n(.*?\n)---\n", re.DOTALL)
MODEL_LINE_RE = re.compile(r"^model:[ \t]*\S.*$", re.MULTILINE)


class ArmError(Exception):
    """An arm is misconfigured — raised before any model is invoked."""


@dataclasses.dataclass(frozen=True)
class PlantedDefect:
    """One known defect in a fixture's changeset, and how to recognize a report of it."""

    id: str
    floor: str
    locator: str
    signals: tuple[str, ...]

    @staticmethod
    def from_dict(data: Mapping[str, object]) -> PlantedDefect:
        floor = str(data["floor"]).lower()
        if floor not in TIERS:
            raise ArmError(f"planted defect {data.get('id')!r}: floor {floor!r} not in {TIERS}")
        signals = tuple(str(s) for s in data.get("signals", ()))
        if not signals:
            raise ArmError(f"planted defect {data.get('id')!r}: needs at least one signal")
        return PlantedDefect(
            id=str(data["id"]),
            floor=floor,
            locator=str(data["locator"]),
            signals=signals,
        )


@dataclasses.dataclass(frozen=True)
class Arm:
    """One configuration under test. `name` is the label; the rest is what varies."""

    name: str
    contract: Mapping[str, Path] = dataclasses.field(default_factory=dict)
    models: Mapping[str, str] = dataclasses.field(default_factory=dict)

    @staticmethod
    def from_dict(data: Mapping[str, object], config_dir: Path) -> Arm:
        name = str(data["name"])
        raw_contract = data.get("contract", {})
        if not isinstance(raw_contract, Mapping):
            raise ArmError(f"arm {name!r}: 'contract' must be an object of target -> variant path")
        contract = {
            str(target): _resolve_variant(str(variant), config_dir, name)
            for target, variant in raw_contract.items()
        }
        raw_models = data.get("models", {})
        if not isinstance(raw_models, Mapping):
            raise ArmError(f"arm {name!r}: 'models' must be an object of agent -> model")
        models = {str(agent): str(model) for agent, model in raw_models.items()}
        return Arm(name=name, contract=contract, models=models)

    @property
    def is_baseline(self) -> bool:
        return not self.contract and not self.models


def _resolve_variant(variant: str, config_dir: Path, arm_name: str) -> Path:
    """Resolve a variant path relative to the arms file, then to the repo root."""
    for candidate in (config_dir / variant, REPO_ROOT / variant):
        if candidate.is_file():
            return candidate.resolve()
    raise ArmError(f"arm {arm_name!r}: variant file {variant!r} not found")


def load_arms(path: Path) -> list[Arm]:
    data = json.loads(path.read_text())
    if not isinstance(data, list) or not data:
        raise ArmError(f"{path}: expected a non-empty JSON array of arms")
    arms = [Arm.from_dict(entry, path.parent) for entry in data]
    names = [arm.name for arm in arms]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ArmError(f"{path}: duplicate arm name(s) {duplicates}")
    return arms


def load_planted(fixture_dir: Path) -> list[PlantedDefect]:
    """Read a fixture's planted-defect ground truth.

    Absent or empty means the fixture asserts a clean result — the control case.
    `Expectation.from_dict` ignores this key, so the golden harness is unaffected.
    """
    data = json.loads((fixture_dir / "expected.json").read_text())
    return [PlantedDefect.from_dict(entry) for entry in data.get("planted", ())]


def rewrite_model_pin(text: str, model: str) -> str:
    """Return `text` with its YAML frontmatter `model:` value replaced by `model`.

    Only the frontmatter block is touched: a `model:` mentioned in the agent's
    prose body is documentation, not a pin. Missing frontmatter or a missing
    pin raises rather than silently no-ops — an arm that quietly failed to apply
    would be scored as a real result.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ArmError("agent file has no YAML frontmatter block")
    block = match.group(1)
    if not MODEL_LINE_RE.search(block):
        raise ArmError("agent frontmatter has no `model:` pin to rewrite")
    rewritten = MODEL_LINE_RE.sub(f"model: {model}", block, count=1)
    return text[: match.start(1)] + rewritten + text[match.end(1) :]


def build_shadow_root(
    dst: Path, overrides: Mapping[str, Path], source_root: Path = REPO_ROOT
) -> Path:
    """Materialize a plugin root at `dst` mirroring `source_root`, with `overrides` copied in.

    `overrides` maps a repo-relative POSIX path to the file that replaces it.
    Every entry not on the path to an override is symlinked straight back to
    `source_root`, so replacing one file never shadows its siblings and the
    shadow costs a handful of symlinks rather than a tree copy.

    Overrides replace only; naming a path that does not exist under
    `source_root` raises, so a typo fails loudly instead of adding a stray file
    the gate would never read.
    """
    rel_overrides = {PurePosixPath(target): variant for target, variant in overrides.items()}
    for target in rel_overrides:
        if not (source_root / target).is_file():
            raise ArmError(f"override target {str(target)!r} does not exist under {source_root}")

    # Every ancestor directory of an override must be a real directory, not a
    # symlink to the original — otherwise writing into it would write through.
    materialize = {parent for target in rel_overrides for parent in target.parents}

    dst.mkdir(parents=True, exist_ok=True)
    _mirror(source_root, dst, PurePosixPath("."), materialize, rel_overrides)
    return dst


def _mirror(
    src_dir: Path,
    dst_dir: Path,
    rel: PurePosixPath,
    materialize: set[PurePosixPath],
    overrides: Mapping[PurePosixPath, Path],
) -> None:
    dst_dir.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src_dir.iterdir()):
        entry_rel = rel / entry.name if rel != PurePosixPath(".") else PurePosixPath(entry.name)
        if entry_rel in overrides:
            shutil.copy2(overrides[entry_rel], dst_dir / entry.name)
        elif entry.is_dir() and entry_rel in materialize:
            _mirror(entry, dst_dir / entry.name, entry_rel, materialize, overrides)
        else:
            os.symlink(entry, dst_dir / entry.name)


def arm_overrides(arm: Arm, staging: Path, source_root: Path = REPO_ROOT) -> dict[str, Path]:
    """Resolve an arm's declarations into a concrete override map for `build_shadow_root`.

    Model pins are rewritten into `staging` first, since the override map takes
    files rather than transformations.
    """
    overrides: dict[str, Path] = dict(arm.contract)
    if arm.models:
        staging.mkdir(parents=True, exist_ok=True)
    for agent, model in sorted(arm.models.items()):
        target = f"agents/{agent}.md"
        source = source_root / target
        if not source.is_file():
            raise ArmError(f"arm {arm.name!r}: no such agent {agent!r} ({target})")
        rewritten = staging / f"{agent}.md"
        try:
            rewritten.write_text(rewrite_model_pin(source.read_text(), model))
        except ArmError as exc:
            raise ArmError(f"arm {arm.name!r}: {agent}: {exc}") from exc
        overrides[target] = rewritten
    return overrides


def _mentions(text: str, defect: PlantedDefect) -> bool:
    """True when `text` names the defect's locator alongside at least one signal.

    Both halves are required. The locator alone matches a Summary line that
    lists every file touched; a signal alone matches generic vocabulary
    ("authorization") that any report might use in passing.
    """
    lower = text.lower()
    if defect.locator.lower() not in lower:
        return False
    return any(signal.lower() in lower for signal in defect.signals)


def classify_defect(report_text: str, defect: PlantedDefect) -> str:
    """Score one planted defect against one report. Returns a member of OUTCOMES."""
    floor_index = TIERS.index(defect.floor)
    sections = {
        tier: extract_section(report_text, TIER_HEADINGS[tier]) or "" for tier in TIERS
    }
    at_or_above = "\n".join(sections[tier] for tier in TIERS[: floor_index + 1])
    below = "\n".join(sections[tier] for tier in TIERS[floor_index + 1 :])

    if _mentions(at_or_above, defect):
        return "REPORTED"
    if _mentions(below, defect):
        return "UNDER_TIERED"
    if _mentions(report_text, defect):
        return "DEMOTED"
    return "MISSED"


@dataclasses.dataclass(frozen=True)
class TrialResult:
    arm: str
    fixture: str
    trial: int
    verdict: str | None
    outcomes: Mapping[str, str]
    cost_usd: float | None = None


def score_trial(
    arm: str,
    fixture: str,
    trial: int,
    report_text: str,
    planted: Sequence[PlantedDefect],
    cost_usd: float | None = None,
) -> TrialResult:
    parsed = parse_audit_report(report_text)
    return TrialResult(
        arm=arm,
        fixture=fixture,
        trial=trial,
        verdict=parsed.verdict,
        outcomes={defect.id: classify_defect(report_text, defect) for defect in planted},
        cost_usd=cost_usd,
    )


def summarize(
    results: Iterable[TrialResult],
) -> dict[tuple[str, str, str], collections.Counter[str]]:
    """Tally outcomes per (fixture, defect id, arm) across trials."""
    tally: dict[tuple[str, str, str], collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for result in results:
        for defect_id, outcome in result.outcomes.items():
            tally[result.fixture, defect_id, result.arm][outcome] += 1
    return dict(tally)


def summarize_verdicts(
    results: Iterable[TrialResult],
) -> dict[tuple[str, str], collections.Counter[str]]:
    """Tally verdict tokens per (fixture, arm) across trials."""
    tally: dict[tuple[str, str], collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for result in results:
        tally[result.fixture, result.arm][result.verdict or "NO VERDICT"] += 1
    return dict(tally)


def render_report(results: Sequence[TrialResult], arms: Sequence[Arm], trials: int) -> str:
    """Render the comparison as text. Raw counts, never a verdict on the experiment."""
    arm_names = [arm.name for arm in arms]
    lines: list[str] = []

    lines.append(f"Arms: {', '.join(arm_names)}   trials/arm/fixture: {trials}")
    lines.append("")
    lines.append("Planted-defect outcomes (counts out of trials)")
    lines.append("")

    defect_tally = summarize(results)
    keys = sorted({(fixture, defect_id) for fixture, defect_id, _ in defect_tally})
    if not keys:
        lines.append("  (no planted defects in the selected fixtures)")
    for fixture, defect_id in keys:
        lines.append(f"  {fixture} :: {defect_id}")
        for name in arm_names:
            counter = defect_tally.get((fixture, defect_id, name))
            if counter is None:
                continue
            breakdown = "  ".join(
                f"{outcome}={counter[outcome]}" for outcome in OUTCOMES if counter[outcome]
            )
            lines.append(f"    {name:<24} {breakdown}")
        lines.append("")

    lines.append("Verdicts (counts out of trials)")
    lines.append("")
    verdict_tally = summarize_verdicts(results)
    for fixture in sorted({fixture for fixture, _ in verdict_tally}):
        lines.append(f"  {fixture}")
        for name in arm_names:
            counter = verdict_tally.get((fixture, name))
            if counter is None:
                continue
            breakdown = "  ".join(f"{token}={count}" for token, count in sorted(counter.items()))
            lines.append(f"    {name:<24} {breakdown}")
        lines.append("")

    costed = [r.cost_usd for r in results if r.cost_usd is not None]
    if costed:
        lines.append("Cost")
        lines.append("")
        for name in arm_names:
            arm_costs = [r.cost_usd for r in results if r.arm == name and r.cost_usd is not None]
            if arm_costs:
                lines.append(f"    {name:<24} ${sum(arm_costs):.2f} over {len(arm_costs)} run(s)")
        lines.append(f"    {'TOTAL':<24} ${sum(costed):.2f} over {len(costed)} run(s)")
        lines.append("")

    lines.append(
        "Counts, not conclusions. Every arm samples a stochastic system: read a gap\n"
        "as signal only when it is large against the trial count, and re-run before\n"
        "acting on a one-trial difference."
    )
    return "\n".join(lines)


def run_arm_on_fixture(
    arm: Arm,
    fixture_dir: Path,
    trials: int,
    planted: Sequence[PlantedDefect],
    artifacts_dir: Path | None,
    timeout_seconds: int,
) -> list[TrialResult]:
    results: list[TrialResult] = []
    for trial in range(1, trials + 1):
        with tempfile.TemporaryDirectory(prefix=f"ab-{arm.name}-{fixture_dir.name}-") as tmp:
            tmp_path = Path(tmp)
            overrides = arm_overrides(arm, tmp_path / "staging")
            shadow = build_shadow_root(tmp_path / "plugin-root", overrides)
            repo = setup_fixture_repo(fixture_dir, tmp_path / "repo", source_root=shadow)
            report_text, cost_usd = run_claude_headless_json(
                repo, timeout_seconds=timeout_seconds, plugin_root=shadow
            )
        if artifacts_dir:
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            name = f"{fixture_dir.name}.{arm.name}.trial{trial}.txt"
            (artifacts_dir / name).write_text(report_text)
        results.append(
            score_trial(
                arm.name, fixture_dir.name, trial, report_text, planted, cost_usd
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arms",
        type=Path,
        required=True,
        help="JSON array of arm definitions. See tests/ab/arms/ for worked experiments.",
    )
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        help="Fixture directory name to run (repeatable). Default: all fixtures.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="Trials per arm per fixture (default: 3). One trial cannot separate a real "
        "effect from sampling noise.",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        help="Directory to write every raw report to, one file per arm/fixture/trial.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Per-trial timeout in seconds (default: 900).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build each arm's shadow root and print what it changes, without invoking "
        "claude. Verifies an arm actually applies before spending a live run on it.",
    )
    args = parser.parse_args(argv)

    try:
        arms = load_arms(args.arms)
    except (ArmError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    fixture_dirs = discover_fixtures()
    if args.fixtures:
        wanted = set(args.fixtures)
        fixture_dirs = [f for f in fixture_dirs if f.name in wanted]
        missing = wanted - {f.name for f in fixture_dirs}
        if missing:
            print(f"error: no such fixture(s): {sorted(missing)}", file=sys.stderr)
            return 2
    if not fixture_dirs:
        print(f"error: no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2

    if args.trials < 1:
        print("error: --trials must be at least 1", file=sys.stderr)
        return 2

    try:
        planted_by_fixture = {f.name: load_planted(f) for f in fixture_dirs}
    except (ArmError, json.JSONDecodeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        return _dry_run(arms, fixture_dirs, planted_by_fixture)

    results: list[TrialResult] = []
    for arm in arms:
        for fixture_dir in fixture_dirs:
            print(f"running {arm.name} :: {fixture_dir.name} ({args.trials} trial(s))")
            try:
                results.extend(
                    run_arm_on_fixture(
                        arm,
                        fixture_dir,
                        args.trials,
                        planted_by_fixture[fixture_dir.name],
                        args.artifacts_dir,
                        args.timeout,
                    )
                )
            except ArmError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2

    report = render_report(results, arms, args.trials)
    print()
    print(report)
    if args.artifacts_dir:
        args.artifacts_dir.mkdir(parents=True, exist_ok=True)
        (args.artifacts_dir / "comparison.txt").write_text(report + "\n")
        (args.artifacts_dir / "results.json").write_text(
            json.dumps([dataclasses.asdict(r) for r in results], indent=2) + "\n"
        )
    return 0


def _dry_run(
    arms: Sequence[Arm],
    fixture_dirs: Sequence[Path],
    planted_by_fixture: Mapping[str, Sequence[PlantedDefect]],
) -> int:
    for fixture_dir in fixture_dirs:
        defects = planted_by_fixture[fixture_dir.name]
        summary = ", ".join(f"{d.id} (floor {d.floor})" for d in defects) or "none (control)"
        print(f"{fixture_dir.name}: planted = {summary}")
    print()
    for arm in arms:
        if arm.is_baseline:
            print(f"{arm.name}: baseline — no overrides")
            continue
        with tempfile.TemporaryDirectory(prefix=f"ab-dry-{arm.name}-") as tmp:
            tmp_path = Path(tmp)
            try:
                overrides = arm_overrides(arm, tmp_path / "staging")
                build_shadow_root(tmp_path / "plugin-root", overrides)
            except ArmError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            print(f"{arm.name}:")
            for target, variant in sorted(overrides.items()):
                identical = (REPO_ROOT / target).read_text() == variant.read_text()
                note = "  [WARNING: identical to baseline]" if identical else ""
                print(f"  {target} <- {variant}{note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
