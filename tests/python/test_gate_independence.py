"""The promise-keeper's own tests (issue #150).

The build skills ship in this plugin now, so nothing structural stops a gate from
quietly growing a dependency on them. `scripts/check_gate_independence.py` is what
stops it; these tests are what stop the check from silently becoming a no-op.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import check_gate_independence as gi

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_gate_independence.py"


def run_script() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )


def test_repo_passes_today() -> None:
    result = run_script()
    assert result.returncode == 0, result.stdout + result.stderr


def test_gate_surface_is_not_empty() -> None:
    """A glob typo would make the whole check vacuously true."""
    matched = [p for pattern in gi.GATE_SURFACE for p in REPO.glob(pattern)]
    assert len(matched) > 20, f"gate surface matched only {len(matched)} files"


def test_catches_a_gate_invoking_a_build_skill(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "some-auditor.md").write_text("Run /build to fix this.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not invoke /build" in problems[0]


def test_catches_a_gate_requiring_a_build_artifact(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text("Read PLAN.md's checkpoint blocks.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "reference/evidence-format.md" in problems[0]


def test_every_build_skill_is_actually_guarded(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    for skill in gi.BUILD_SKILLS:
        (agents / f"{skill}-auditor.md").write_text(f"Then run /{skill}.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert len(gi.violations()) == len(gi.BUILD_SKILLS)


def test_catches_a_gate_shelling_out_to_a_build_executable(tmp_path: Path, monkeypatch) -> None:
    """#246: naming `/build` was already caught, but nothing stopped a gate from
    reaching past the skill straight to the executable it wraps."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "some-auditor.md").write_text(
        "Run `uv run --no-project python scripts/verify` to check the task.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not shell out to scripts/verify" in problems[0]


def test_every_build_executable_is_actually_guarded(tmp_path: Path, monkeypatch) -> None:
    agents = tmp_path / "agents"
    agents.mkdir()
    for executable in gi.BUILD_EXECUTABLES:
        (agents / f"{executable}-auditor.md").write_text(
            f"Then run scripts/{executable}.\n", encoding="utf-8"
        )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert len(gi.violations()) == len(gi.BUILD_EXECUTABLES)


def test_path_segments_are_not_invocations(tmp_path: Path, monkeypatch) -> None:
    """All three of these appear on the real gate surface today."""
    agents = tmp_path / "agents"
    agents.mkdir()
    (agents / "a.md").write_text(
        "Point at `templates/design-doc.md` as a scaffold.\n"
        "Reports land in docs/design/ for the cycle.\n"
        "Never run install/build/test — postinstall scripts execute code.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []


def test_routing_outside_the_gate_surface_is_allowed(tmp_path: Path, monkeypatch) -> None:
    """/next naming /build is the product working, not a violation."""
    commands = tmp_path / "commands"
    commands.mkdir()
    (commands / "work-on.md").write_text("Hand off to /build.\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("Then /build and /build.\n", encoding="utf-8")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []


# --- the worker-dispatch region (#212) ---------------------------------------
#
# `workflows/epic-driver.js` dispatches work *and* compiles gate verdicts. The
# region lets its dispatch half route to /build + /build without lifting the rule
# off `auditFanIn` and `acceptanceFanIn`. Everything below exists to make sure the
# hole stays exactly that size.


def _workflow(tmp_path: Path, body: str) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir(exist_ok=True)
    (workflows / "driver.js").write_text(body, encoding="utf-8")


def test_region_exempts_a_worker_dispatch_invocation(tmp_path: Path, monkeypatch) -> None:
    _workflow(
        tmp_path,
        f"// {gi.REGION_OPEN}\n"
        "const build = `The route that ships with this plugin is /build then /build.`\n"
        f"// {gi.REGION_CLOSE}\n",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []


def test_region_exempts_a_build_executable_too(tmp_path: Path, monkeypatch) -> None:
    """#246 extended the same INVOCATION regex the region already exempts from —
    confirm the hole grew to cover the new branch, not just the old one."""
    _workflow(
        tmp_path,
        f"// {gi.REGION_OPEN}\n"
        "const v = `Run scripts/verify to check the task.`\n"
        f"// {gi.REGION_CLOSE}\n",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.violations() == []
    assert gi.dead_regions() == []


def test_the_same_string_outside_the_region_still_fails(tmp_path: Path, monkeypatch) -> None:
    """The exemption is positional, not textual — identical text one line past the
    close marker is the violation it always was."""
    _workflow(
        tmp_path,
        f"// {gi.REGION_OPEN}\n// {gi.REGION_CLOSE}\n"
        "const build = `The route that ships with this plugin is /build then /build.`\n",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not invoke /build" in problems[0]


def test_a_gate_compiler_may_not_be_moved_inside_the_region(tmp_path: Path, monkeypatch) -> None:
    """#212's acceptance criterion. Moving the invocation into a compile prompt must
    fail — including by the route that would otherwise defeat the check entirely:
    dragging the region markers around the compiler so the invocation looks exempt."""
    _workflow(
        tmp_path,
        f"// {gi.REGION_OPEN}\n"
        "function auditFanIn(story, reports) {\n"
        "  return `Compile the verdict. First run /build to fix the findings.`\n"
        "}\n"
        f"// {gi.REGION_CLOSE}\n",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert any("auditFanIn compiles a gate verdict" in p for p in problems), problems


def test_every_gate_compiler_is_guarded_by_name(tmp_path: Path, monkeypatch) -> None:
    """Each name in GATE_COMPILERS is actually enforced, not just listed."""
    for compiler in gi.GATE_COMPILERS:
        _workflow(
            tmp_path,
            f"// {gi.REGION_OPEN}\nfunction {compiler}(a) {{ return a }}\n// {gi.REGION_CLOSE}\n",
        )
        monkeypatch.setattr(gi, "REPO", tmp_path)
        problems = gi.violations()
        assert any(f"{compiler} compiles a gate verdict" in p for p in problems), compiler


def test_the_region_never_exempts_a_build_artifact(tmp_path: Path, monkeypatch) -> None:
    """Rule 2 is not region-scoped. A dispatcher has no reason to require PLAN.md,
    and a gate must not require one anywhere."""
    _workflow(
        tmp_path,
        f"// {gi.REGION_OPEN}\nconst p = `Read PLAN.md first.`\n// {gi.REGION_CLOSE}\n",
    )
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert len(problems) == 1
    assert "must not require PLAN.md" in problems[0]


def test_an_unclosed_region_is_an_error_not_a_free_pass(tmp_path: Path, monkeypatch) -> None:
    """The dangerous failure: an unterminated marker would exempt the whole rest of
    the file, silently."""
    _workflow(tmp_path, f"// {gi.REGION_OPEN}\nconst build = `Run /build.`\n")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    problems = gi.violations()
    assert any("opened and never closed" in p for p in problems), problems


def test_nested_and_unopened_markers_are_errors(tmp_path: Path, monkeypatch) -> None:
    _workflow(tmp_path, f"// {gi.REGION_OPEN}\n// {gi.REGION_OPEN}\n// {gi.REGION_CLOSE}\n")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert any("already open" in p for p in gi.violations())

    _workflow(tmp_path, f"// {gi.REGION_CLOSE}\n")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert any("closed but never opened" in p for p in gi.violations())


def test_a_region_that_exempts_nothing_is_rejected(tmp_path: Path, monkeypatch) -> None:
    """An unused region is a hole waiting for something to fall into it."""
    _workflow(tmp_path, f"// {gi.REGION_OPEN}\nconst x = 1\n// {gi.REGION_CLOSE}\n")
    monkeypatch.setattr(gi, "REPO", tmp_path)
    assert gi.dead_regions() == ["workflows/driver.js"]


def test_the_real_driver_declares_exactly_one_live_region() -> None:
    """Against the shipped file, not a fixture: the exemption exists, is used, and
    hasn't multiplied."""
    text = (REPO / "workflows" / "epic-driver.js").read_text(encoding="utf-8")
    assert text.count(gi.REGION_OPEN) == 1
    assert text.count(gi.REGION_CLOSE) == 1

    _, exempted = gi.scan("workflows/epic-driver.js", text)
    assert exempted >= 1, "the driver's region exempts nothing — it should be removed"
    assert gi.dead_regions() == []
