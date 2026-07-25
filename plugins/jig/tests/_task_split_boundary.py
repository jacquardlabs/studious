"""Derives, from each of jig's three independently-encoded task-splitting
surfaces, a function computing where a `### Task N` block ends -- so a
test can check the three actually agree, instead of trusting they do by
inspection (story plan-lint-build-boundary-integration-test, issue #66,
epic pre-dogfood-hardening).

The three surfaces:

1. `scripts/plan-lint`'s own `split_tasks()` -- code, executed for real via
   `load_plan_lint_module`; see `surface_1_plan_lint_ends`.
2. `skills/build/SKILL.md` Step 1.4's boundary prose -- read-only: this
   module extracts the *documented rule* out of the prose text (the
   backtick-quoted heading marker it names, e.g. "### ", and whether the
   coarser-heading-exclusion sentence is still present), never executes
   or dispatches the skill; see `derive_build_step_1_4_boundary_regex` and
   `surface_2_build_ends`.
3. `skills/plan/SKILL.md` Step 6's `--split-on` pattern -- read-only: this
   module extracts the literal regex string from the documented
   invocation and applies it exactly as viva's own flag does (heading
   title text, any depth), never executes `/plan` or viva; see
   `derive_plan_step_6_split_on_pattern` and `surface_3_plan_ends`.

Not a test module -- nothing here is collected by `unittest discover`,
matching the `_vocabulary.py` / `_load_bearing.py` "shared, not itself
collected" convention already established in this repo.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
PLAN_LINT_SCRIPT = REPO_ROOT / "scripts" / "plan-lint"

# ---------------------------------------------------------------------------
# Surface 1: scripts/plan-lint, executed for real (it's code, not prose).
# ---------------------------------------------------------------------------


def load_plan_lint_module(script_path: Path = PLAN_LINT_SCRIPT) -> ModuleType:
    """Import `scripts/plan-lint` as an in-process module so this test can
    call its actual `split_tasks()` (and read its `TASK_HEADING_RE`)
    directly -- the acceptance criteria names `split_tasks()` itself as the
    surface under test, not just its stdout (the existing
    `test_plan_lint.py` subprocess convention). The script has no `.py`
    suffix -- a hyphenated executable, not a package -- so
    `importlib.util`'s file-location loader is what makes a direct import
    possible at all.
    """
    # The script has no `.py` suffix, so `spec_from_file_location` can't
    # infer a loader from the extension alone -- name one explicitly
    # (a plain source file, exactly what it is).
    loader = importlib.machinery.SourceFileLoader("plan_lint_script", str(script_path))
    spec = importlib.util.spec_from_file_location("plan_lint_script", script_path, loader=loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {script_path} as a module")
    module = importlib.util.module_from_spec(spec)
    # `scripts/plan-lint` decorates classes with `@dataclass`, which looks
    # its own defining module up via `sys.modules` at class-creation time
    # -- register it first, matching what a normal `import` does under the
    # hood, or that lookup returns `None` and `@dataclass` breaks.
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


def task_starts(plan_lint_module: ModuleType, text: str) -> dict[str, int]:
    """{task_number: start_offset}, from plan-lint's own `TASK_HEADING_RE`
    -- the one thing all three surfaces already agree on verbatim (a task
    starts at its own `### Task N` heading). Only where a block *ends* is
    the disputed question this module exists to check."""
    return {m.group(1): m.start() for m in plan_lint_module.TASK_HEADING_RE.finditer(text)}


def surface_1_plan_lint_ends(plan_lint_module: ModuleType, text: str) -> dict[str, int]:
    """End offset per task number, from plan-lint's own `split_tasks()`."""
    starts = task_starts(plan_lint_module, text)
    tasks = plan_lint_module.split_tasks(text)
    return {num: starts[num] + len(block) for num, block in tasks}


def _next_boundary_after(start: int, boundary_starts: list[int], text_len: int) -> int:
    return next((b for b in boundary_starts if b > start), text_len)


# ---------------------------------------------------------------------------
# Surface 2: skills/build/SKILL.md Step 1.4's boundary prose (read-only --
# parsed for its documented rule, never executed/dispatched).
# ---------------------------------------------------------------------------

_STEP_1_4_NEXT_HEADING_RE = re.compile(r"the next\s*`(#{1,6})[ \t]*`\s*heading")
_STEP_1_4_COARSER_EXAMPLE_RE = re.compile(r"a closing\s*`(#{1,6})[ \t]+([^`]+)`")
_STEP_1_4_COARSER_EXCLUSION_RE = re.compile(r"Explicitly exclude any trailing content at a\s+coarser heading level")


def derive_build_step_1_4_task_heading_level(build_skill_md_text: str) -> int:
    """The task heading's own level (3), read from Step 1.4's own "stop
    accumulating a task's content at the next `### ` heading" phrase -- the
    backtick-quoted marker's hash count, not a hand-copied "3"."""
    match = _STEP_1_4_NEXT_HEADING_RE.search(build_skill_md_text)
    if match is None:
        raise AssertionError(
            "skills/build/SKILL.md Step 1.4 no longer names its own task-heading "
            "marker in the documented phrase this derivation reads"
        )
    return len(match.group(1))


def derive_build_step_1_4_coarser_example_level(build_skill_md_text: str) -> int:
    """The level of the concrete coarser-heading example Step 1.4 itself
    gives ("a closing `## Not-here follow-ups` section") -- read here only
    for a sanity check that the doc's own example is coherent with its own
    stated task-heading level; not consumed by
    `derive_build_step_1_4_boundary_regex` itself, which needs only the
    task level and the exclusion sentence's presence."""
    match = _STEP_1_4_COARSER_EXAMPLE_RE.search(build_skill_md_text)
    if match is None:
        raise AssertionError(
            "skills/build/SKILL.md Step 1.4 no longer names a concrete "
            "coarser-heading example this derivation reads"
        )
    return len(match.group(1))


def derive_build_step_1_4_boundary_regex(build_skill_md_text: str) -> re.Pattern[str]:
    """Parse Step 1.4's own boundary prose into an executable boundary
    regex, instead of hand-copying `scripts/plan-lint`'s `#{1,3}` pattern a
    second time.

    Two facts, both read from the text, decide the result:

    - the task heading's own level (see
      `derive_build_step_1_4_task_heading_level`);
    - whether the prose still carries its own coarser-heading-exclusion
      sentence ("Explicitly exclude any trailing content at a coarser
      heading level"). Present: any heading from level 1 up to and
      including the task level ends a block (markdown's own coarsest
      level, 1, is the structural floor -- nothing in either doc needs to
      spell that out again). Absent: this derivation falls back to the
      *naive* "next task heading only" rule the sentence exists to rule
      out -- exactly the M0 dogfood bug Step 1.4 itself names -- so a
      regression that drops the sentence is caught as a real behavior
      change, not silently kept "correct" by a hardcoded floor.
    """
    task_heading_level = derive_build_step_1_4_task_heading_level(build_skill_md_text)
    if _STEP_1_4_COARSER_EXCLUSION_RE.search(build_skill_md_text) is None:
        return re.compile(rf"^(#{{{task_heading_level}}})[ \t]", re.MULTILINE)
    return re.compile(rf"^(#{{1,{task_heading_level}}})[ \t]", re.MULTILINE)


def surface_2_build_ends(text: str, boundary_regex: re.Pattern[str], starts: dict[str, int]) -> dict[str, int]:
    """End offset per task number, from Step 1.4's derived boundary regex."""
    boundary_starts = sorted(h.start() for h in boundary_regex.finditer(text))
    return {num: _next_boundary_after(start, boundary_starts, len(text)) for num, start in starts.items()}


# ---------------------------------------------------------------------------
# Surface 3: skills/plan/SKILL.md Step 6's --split-on pattern (read-only --
# the literal regex string extracted from the documented invocation, never
# executed via /plan or viva itself).
# ---------------------------------------------------------------------------

_STEP_6_SPLIT_ON_RE = re.compile(r"--split-on\s+'([^']+)'")
_ANY_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.*)$", re.MULTILINE)


def derive_plan_step_6_split_on_pattern(plan_skill_md_text: str) -> re.Pattern[str]:
    """The literal `--split-on` regex Step 6 documents passing to viva,
    compiled from the exact quoted string in the doc -- so any character
    changed in that documented flag value (a dropped alternative, a
    changed anchor, ...) changes what this returns."""
    match = _STEP_6_SPLIT_ON_RE.search(plan_skill_md_text)
    if match is None:
        raise AssertionError(
            "skills/plan/SKILL.md Step 6 no longer names an explicit --split-on "
            "pattern in the documented invocation this derivation reads"
        )
    return re.compile(match.group(1))


def surface_3_plan_ends(text: str, split_on_pattern: re.Pattern[str], starts: dict[str, int]) -> dict[str, int]:
    """End offset per task number, from Step 6's `--split-on` pattern
    applied exactly as documented: matching by heading *title* text, at
    any heading depth -- not a heading-level rule at all."""
    boundary_starts = sorted(
        m.start() for m in _ANY_HEADING_RE.finditer(text) if split_on_pattern.match(m.group(2).strip())
    )
    return {num: _next_boundary_after(start, boundary_starts, len(text)) for num, start in starts.items()}
