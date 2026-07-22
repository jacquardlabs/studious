"""Regression tests for the audit-doc-split story (issue #159).

Before this story, `workflows/epic-driver.js`'s `auditFanIn()` pointed its dispatched
compiling agent at the entire 189-line `commands/gate-audit.md` to reach the ~48 lines
of post-audit compile rules it actually needed — paying for dispatch mechanics
(shared-contract assembly, diff precompute, evidence-log resolution, re-audit-scope
narrowing, the 13 numbered auditor role descriptions) it never uses. This story
relocates those compile rules verbatim into `reference/audit-compilation.md`, points
both `commands/gate-audit.md`'s own session and `auditFanIn()` at that one file, and
folds "routed out" in as a third named lane state alongside carry-forward and AGENT
DIED — a vocabulary unification, not a judgment change.

These are static/textual checks, following this repo's own precedent
(`test_gate_audit_md_and_epic_driver_agree_on_the_ten_lane_roster`,
`test_both_dispatch_surfaces_cite_the_identical_blocking_lanes_flag` in
`test_delta_scoped_reaudit.py`) for exactly this kind of two-surface-drift risk.
"""

from __future__ import annotations

from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT

GATE_AUDIT_MD = REPO_ROOT / "commands" / "gate-audit.md"
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
AUDIT_COMPILATION = REPO_ROOT / "reference" / "audit-compilation.md"

# A line lifted verbatim from the moved section — distinctive enough that a second,
# independent occurrence anywhere in the live prompt surfaces means the compilation
# rules were copied rather than relocated.
DISTINCTIVE_MOVED_LINE = "map each one's labels into the report's three tiers"

# The prompt/rubric-carrying directories a duplicate copy could hide in.
# `check_references.py` only scans the first four of these — never `workflows/`, the
# one place a second inline copy of this story's moved text would actually live (see
# `docs/studious/premortems/2026-07-21-audit-doc-split-design.md` item 4).
PROMPT_SURFACE_DIRS = ("commands", "agents", "skills", "reference", "workflows")


def _count_occurrences(root: Path, phrase: str, dirs: tuple[str, ...]) -> dict[str, int]:
    """Count files under each of ``dirs`` (relative to ``root``) containing ``phrase``."""
    hits: dict[str, int] = {}
    for sub in dirs:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if phrase in text:
                hits[str(path.relative_to(root))] = text.count(phrase)
    return hits


def test_reference_file_exists() -> None:
    """Acceptance criterion 1: reference/audit-compilation.md exists."""
    assert AUDIT_COMPILATION.is_file()


def test_reference_file_contains_the_extracted_rules() -> None:
    """Acceptance criterion 1: the severity-tier pointer, all three lane-state rules,
    the critical-challenge process, and the verdict tiers all landed in the new file."""
    text = AUDIT_COMPILATION.read_text()
    assert "reference/severity-rubric.md" in text, "severity-tier pointer is missing"
    for lane_state in ("Carried forward", "AGENT DIED", "Routed out"):
        assert lane_state in text, f"{lane_state!r} lane-state rule is missing"
    assert "Confirmed" in text and "Downgraded" in text and "Dropped" in text, (
        "critical-challenge process outcomes are missing"
    )
    for token in ("PASS", "FIX AND RE-AUDIT", "NEEDS DISCUSSION"):
        assert token in text, f"verdict tier {token!r} is missing"


def test_gate_audit_md_points_to_the_new_file_and_does_not_restate_it() -> None:
    """Acceptance criterion 2: gate-audit.md's own section is a pointer, not a copy."""
    text = GATE_AUDIT_MD.read_text()
    start = text.index("## After all auditors return")
    end = text.index("## Record the verdict")
    section = text[start:end]
    assert "reference/audit-compilation.md" in section
    # The pointer names the file; it must not restate the substantive rule text that
    # only belongs in the new file now (premortem item 5).
    for restated in (
        DISTINCTIVE_MOVED_LINE,
        "AGENT DIED — no report; this lane is UNAUDITED",
        "pixel-blind",
        "citation-integrity check only",
    ):
        assert restated not in section, (
            f"gate-audit.md's pointer restates {restated!r} instead of only citing "
            "reference/audit-compilation.md"
        )


def test_epic_driver_points_to_the_new_file_not_gate_audit_md() -> None:
    """Acceptance criterion 3: auditFanIn's opening sentence cites the new file."""
    text = DRIVER.read_text()
    anchor = "You are compiling Studious's audit gate verdict."
    i = text.index(anchor)
    opening = text[i : i + 400]
    assert "reference/audit-compilation.md" in opening
    assert "Read commands/gate-audit.md" not in opening, (
        "auditFanIn still points its compiling agent at commands/gate-audit.md "
        "instead of reference/audit-compilation.md"
    )


def test_both_dispatch_surfaces_cite_the_identical_compilation_file_path() -> None:
    """Acceptance criterion 3: the same literal path, cited by both surfaces."""
    assert "reference/audit-compilation.md" in GATE_AUDIT_MD.read_text()
    assert "reference/audit-compilation.md" in DRIVER.read_text()


def test_no_second_copy_of_the_moved_compilation_rules_exists() -> None:
    """Acceptance criterion 3, the static check: a distinctive line from the moved
    section appears exactly once across every prompt/rubric-carrying directory —
    `reference/audit-compilation.md` itself. Any second hit (including inside
    `workflows/epic-driver.js`, which `check_references.py` never scans) means a
    second copy exists somewhere it shouldn't."""
    hits = _count_occurrences(REPO_ROOT, DISTINCTIVE_MOVED_LINE, PROMPT_SURFACE_DIRS)
    assert hits == {"reference/audit-compilation.md": 1}, (
        f"expected the moved line to appear exactly once, in reference/audit-compilation.md "
        f"only; found: {hits}"
    )


def test_the_duplicate_copy_detector_actually_detects_a_duplicate(tmp_path: Path) -> None:
    """Premortem mitigation (item 4): prove the counting helper above is not a test
    that 'passes trivially' — a deliberately-injected second copy must make it fail."""
    (tmp_path / "reference").mkdir()
    (tmp_path / "workflows").mkdir()
    (tmp_path / "reference" / "audit-compilation.md").write_text(
        f"...{DISTINCTIVE_MOVED_LINE}...", encoding="utf-8"
    )
    (tmp_path / "workflows" / "epic-driver.js").write_text(
        f"// a second, drifted copy: {DISTINCTIVE_MOVED_LINE}", encoding="utf-8"
    )
    hits = _count_occurrences(tmp_path, DISTINCTIVE_MOVED_LINE, PROMPT_SURFACE_DIRS)
    assert hits == {
        "reference/audit-compilation.md": 1,
        "workflows/epic-driver.js": 1,
    }
    assert hits != {"reference/audit-compilation.md": 1}


def test_routed_out_is_named_as_a_third_lane_state_alongside_the_other_two() -> None:
    """The acceptance criteria name carry-forward/routed-out/AGENT-DIED together as
    one set — confirm all three are named as distinct states in the new file, not
    just two of the three (the pre-story gate-audit.md text named only two)."""
    text = AUDIT_COMPILATION.read_text()
    carried_idx = text.index("Carried forward")
    died_idx = text.index("AGENT DIED")
    routed_idx = text.index("Routed out")
    # All three appear, in the order the acceptance criteria list them.
    assert carried_idx < died_idx < routed_idx
