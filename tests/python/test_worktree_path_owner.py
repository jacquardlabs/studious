"""One owner for the `.studious/worktrees/<epic>/` layout (studious #166).

`__epic` for the integration checkout, one directory per in-flight story. That
shape used to be written out independently in three places — `bin/gate-ledger`'s
`epic-reconcile`, `workflows/epic-driver.js`, and `reference/epic-orchestration.md`'s
prose — so moving it meant three coordinated edits, and two consecutive audits
flagged it.

`bin/gate-ledger`'s `worktree_path()` is now the only definition, exposed to
everyone else through the `worktree-path` verb. The driver is the interesting
case: it runs on the Workflow substrate with no filesystem or exec access, so it
cannot call the verb. `reference/epic-orchestration.md` calls it once with `--json` and
hands the result over as `args.worktrees` — the layout crosses the args boundary
as data, the same way `args.contract` does.

The behavioral half here executes the driver's real, unmodified
`requireWorktree()` (extracted verbatim by balanced-brace scan, following
`test_contract_injection.py`'s precedent); the structural half asserts the
literal is gone from the places that used to carry a copy.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"
LEDGER = REPO_ROOT / "bin" / "gate-ledger"
WORK_THROUGH = REPO_ROOT / "reference" / "epic-orchestration.md"

LAYOUT_LITERAL = ".studious/worktrees"


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level ``function <name>(...) { ... }`` declaration verbatim."""
    marker = f"function {name}("
    start = source.index(marker)
    brace_open = source.index("{", start)
    depth = 0
    i = brace_open
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _strip_full_line_comments(source: str) -> str:
    """Drop whole-line ``//`` comments, keeping every line of executable code.

    Deliberately does not touch trailing comments: stripping from the first
    ``//`` on a line would also cut into any string holding a URL or a protocol
    prefix. Whole-line stripping is enough here because the only thing this file
    needs to see past is the block comment that *explains* the layout, and the
    driver carries no trailing comment mentioning it (nor any ``://`` at all).
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("//")
    )


# --- bin/gate-ledger owns the layout -----------------------------------------


def test_gate_ledger_defines_the_worktree_path_helper() -> None:
    source = LEDGER.read_text()
    assert "worktree_path() {" in source, (
        "bin/gate-ledger must define worktree_path(), the single owner of the "
        ".studious/worktrees/<epic>/{__epic,<story>} layout"
    )


def test_gate_ledger_exposes_the_worktree_path_verb() -> None:
    source = LEDGER.read_text()
    assert "worktree-path)" in source, (
        "bin/gate-ledger must dispatch a `worktree-path` verb — it is how every "
        "caller outside this script asks the owner for a path"
    )
    assert "worktree-path --slug S" in source, (
        "the usage line must document the worktree-path verb"
    )


def test_gate_ledger_composes_the_layout_in_exactly_one_place() -> None:
    """Only worktree_path() may spell the layout out; every other site calls it."""
    composing = [
        line
        for line in LEDGER.read_text().splitlines()
        if LAYOUT_LITERAL in line and not line.lstrip().startswith("#")
    ]
    assert len(composing) == 1, (
        "exactly one non-comment line in bin/gate-ledger may spell out "
        f"{LAYOUT_LITERAL!r} (worktree_path's own printf); found: {composing}"
    )


# --- workflows/epic-driver.js references the owner, never re-derives ----------


def test_driver_holds_no_worktree_layout_literal() -> None:
    code = _strip_full_line_comments(DRIVER.read_text())
    assert LAYOUT_LITERAL not in code, (
        "workflows/epic-driver.js must not compose a worktree path itself — it "
        "reads them from args.worktrees, which reference/epic-orchestration.md fills "
        "from `gate-ledger worktree-path --slug <slug> --json`"
    )


def test_driver_reads_both_worktree_kinds_from_args() -> None:
    code = _strip_full_line_comments(DRIVER.read_text())
    assert "const worktrees = input.worktrees" in code, (
        "the driver must take the layout from args.worktrees"
    )
    assert "const epicWorktree = requireWorktree(worktrees.epic" in code, (
        "the __epic integration worktree path must come from args.worktrees"
    )
    assert "function storyWorktree(story) { return requireWorktree(" in code, (
        "storyWorktree() must look its answer up in args.worktrees rather than "
        "building `${dir}/${story}`"
    )


def _run_require_worktree(call: str) -> dict:
    """Execute the driver's real requireWorktree() against one call expression."""
    fn = _extract_function(DRIVER.read_text(), "requireWorktree")
    harness = f"""
      {fn}
      try {{
        process.stdout.write(JSON.stringify({{ ok: true, value: {call} }}))
      }} catch (e) {{
        process.stdout.write(JSON.stringify({{ ok: false, message: e.message }}))
      }}
    """
    result = subprocess.run(
        ["node", "--input-type=module", "-e", harness],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_require_worktree_returns_a_supplied_path() -> None:
    out = _run_require_worktree("requireWorktree('/repo/.studious/worktrees/e/a', \"story 'a'\")")
    assert out["ok"], out
    assert out["value"] == "/repo/.studious/worktrees/e/a"


def test_require_worktree_throws_loudly_rather_than_deriving_a_fallback() -> None:
    """A missing entry is a wiring error in the args, not a runtime condition.

    Degrading here would dispatch a worker at a silently-wrong checkout, which is
    strictly worse than crashing — so this fails loud, not closed.
    """
    for call, what in (
        ("requireWorktree(undefined, 'the __epic integration worktree')", "undefined"),
        ("requireWorktree('', \"story 'a'\")", "empty string"),
        ("requireWorktree(null, \"story 'a'\")", "null"),
        ("requireWorktree(42, \"story 'a'\")", "non-string"),
    ):
        out = _run_require_worktree(call)
        assert not out["ok"], f"requireWorktree accepted {what}: {out}"
        assert "args.worktrees" in out["message"], (
            f"the {what} error must name args.worktrees so the fix is obvious: {out}"
        )
        assert "worktree-path" in out["message"], (
            f"the {what} error must name the verb that produces it: {out}"
        )


# --- reference/epic-orchestration.md asks the verb instead of typing the path --------


def test_work_through_resolves_every_worktree_through_the_verb() -> None:
    lines = WORK_THROUGH.read_text().splitlines()
    offenders = [
        line
        for line in lines
        if ("git worktree add" in line or "git worktree remove" in line)
        and LAYOUT_LITERAL in line
    ]
    assert not offenders, (
        "every `git worktree add`/`remove` in reference/epic-orchestration.md must take "
        f"its path from `gate-ledger worktree-path`, not spell {LAYOUT_LITERAL!r} "
        f"out: {offenders}"
    )


def test_work_through_hands_the_layout_to_the_driver() -> None:
    text = WORK_THROUGH.read_text()
    assert 'gate-ledger worktree-path --slug "<slug>" --json' in text, (
        "reference/epic-orchestration.md must resolve the whole layout once with the --json form — "
        "the driver has no exec access and cannot ask for paths itself"
    )
    assert '"worktrees"' in text, (
        "the driver args block must carry a `worktrees` field"
    )
