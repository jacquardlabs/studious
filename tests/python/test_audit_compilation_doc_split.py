"""Regression tests for the audit-doc-split story (issue #159): moves the ~48
lines of post-audit compile rules out of the 189-line
`commands/review.md` into `reference/audit-compilation.md`, points the door at that file, and names "routed out" as a third lane state alongside
carry-forward and AGENT DIED (vocabulary unification, not a judgment change).

Static/textual checks, per this repo's precedent in `test_delta_scoped_reaudit.py`
for two-surface-drift risk.
"""

from __future__ import annotations

from pathlib import Path

from run_gate_audit_fixtures import REPO_ROOT

GATE_AUDIT_MD = REPO_ROOT / "commands" / "review.md"
AUDIT_COMPILATION = REPO_ROOT / "reference" / "audit-compilation.md"

# A line lifted verbatim from the moved section; a second occurrence anywhere means
# the rules were copied rather than relocated.
# (Was the severity-mapping sentence until #334 S1 retired label mapping.)
DISTINCTIVE_MOVED_LINE = "Every auditor lane lands in exactly one of three states before compiling"

PROMPT_SURFACE_DIRS = ("commands", "agents", "skills", "reference")


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
    """Acceptance criterion 1."""
    assert AUDIT_COMPILATION.is_file()


def test_reference_file_contains_the_extracted_rules() -> None:
    """Acceptance criterion 1: all extracted rules landed in the new file."""
    text = AUDIT_COMPILATION.read_text()
    assert "reference/severity-rubric.md" in text, "severity-tier pointer is missing"
    for lane_state in ("Carried forward", "AGENT DIED", "Routed out"):
        assert lane_state in text, f"{lane_state!r} lane-state rule is missing"
    assert "Confirmed" in text and "Downgraded" in text and "Dropped" in text, (
        "critical-challenge process outcomes are missing"
    )
    # FIX AND RE-REVIEW replaced FIX AND RE-AUDIT as the retry token (#289 Task 3);
    # reference/gate-vocabulary.md is canonical.
    for token in ("PASS", "FIX AND RE-REVIEW", "NEEDS DISCUSSION"):
        assert token in text, f"verdict tier {token!r} is missing"


def test_gate_audit_md_points_to_the_new_file_and_does_not_restate_it() -> None:
    """Acceptance criterion 2: commands/review.md's section is a pointer, not a copy."""
    text = GATE_AUDIT_MD.read_text()
    start = text.index("## Compile")
    end = text.index("\n## Shared — record findings")
    section = text[start:end]
    assert "reference/audit-compilation.md" in section
    # Must not restate rule text that now belongs only in the new file (premortem item 5).
    for restated in (
        DISTINCTIVE_MOVED_LINE,
        "AGENT DIED — no report; this lane is UNAUDITED",
        "pixel-blind",
        "citation-integrity check only",
    ):
        assert restated not in section, (
            f"commands/review.md's pointer restates {restated!r} instead of only citing "
            "reference/audit-compilation.md"
        )


def test_no_second_copy_of_the_moved_compilation_rules_exists() -> None:
    """Acceptance criterion 3: the distinctive moved line appears exactly once,
    in reference/audit-compilation.md — any other hit means a second copy exists."""
    hits = _count_occurrences(REPO_ROOT, DISTINCTIVE_MOVED_LINE, PROMPT_SURFACE_DIRS)
    assert hits == {"reference/audit-compilation.md": 1}, (
        f"expected the moved line to appear exactly once, in reference/audit-compilation.md "
        f"only; found: {hits}"
    )


def test_the_duplicate_copy_detector_actually_detects_a_duplicate(tmp_path: Path) -> None:
    """Premortem item 4: proves the counting helper isn't a test that passes trivially
    — an injected second copy must make it fail."""
    (tmp_path / "reference").mkdir()
    (tmp_path / "commands").mkdir()
    (tmp_path / "reference" / "audit-compilation.md").write_text(
        f"...{DISTINCTIVE_MOVED_LINE}...", encoding="utf-8"
    )
    (tmp_path / "commands" / "review.md").write_text(
        f"// a second, drifted copy: {DISTINCTIVE_MOVED_LINE}", encoding="utf-8"
    )
    hits = _count_occurrences(tmp_path, DISTINCTIVE_MOVED_LINE, PROMPT_SURFACE_DIRS)
    assert hits == {
        "reference/audit-compilation.md": 1,
        "commands/review.md": 1,
    }
    assert hits != {"reference/audit-compilation.md": 1}


def test_routed_out_is_named_as_a_third_lane_state_alongside_the_other_two() -> None:
    """All three lane states are named distinctly (pre-story text named only two)."""
    text = AUDIT_COMPILATION.read_text()
    carried_idx = text.index("Carried forward")
    died_idx = text.index("AGENT DIED")
    routed_idx = text.index("Routed out")
    # In the order the acceptance criteria list them.
    assert carried_idx < died_idx < routed_idx
