#!/usr/bin/env python3
"""Assert Studious's gates never require its own build skills.

The build-execution skills (`/design`, `/plan`, `/build`, `/finish`, `/coach`) ship in
this plugin alongside the gates (#150). That makes one promise easy to break by
accident, and it is the promise PRODUCT.md's "the gates being a methodology" non-goal
rests on: **a gate judges the work, never who produced it.**
`reference/worker-contract.md` is normative — a human, Superpowers, or `/build` all
satisfy it, and a gate must reach the same verdict either way.

Two ways a gate could quietly acquire that dependency, both checked here:

1. **Invoking a build skill.** A gate command or auditor telling the reader to run
   `/build`, or routing a finding through `/plan`, only works for one kind of
   producer — and reaching past the skill straight to the executable it wraps
   (`scripts/verify`, `scripts/design-lint`, ...) is the same dependency wearing a
   third hat (#246): a gate that shells out to a build skill's own script has bound
   itself to that skill's implementation as surely as one that names the skill.
2. **Requiring a build artifact.** A gate that reads `PLAN.md`'s checkpoint blocks or
   expects `docs/jig/evidence/` has the same dependency wearing a different hat — the
   evidence contract a gate may rely on is `reference/evidence-format.md`, which any
   executor can satisfy.

Everything outside the gate surface — `/work-on`, `/work-through`, the worker
contract, the README, the context docs — is free to name and route to the build
skills. That is the product working as intended, not a violation.

**One file on the surface holds two roles.** `workflows/epic-driver.js` is a
dispatcher that also builds the prompts compiling gate verdicts. Its dispatch half
must be able to route work to `/plan` + `/build` exactly as `commands/work-on.md`
does; its gate half must stay producer-agnostic. Taking the whole file off the
surface would drop the guarantee for `auditFanIn` and `acceptanceFanIn`, which are
the two functions that most need it — so instead a file may mark a *region* as
worker dispatch, exempt from rule 1 only, and never containing gate-compile
machinery (#212). The markers are plain comments so the check stays a line scanner
and the exemption is visible where it applies rather than in this file's config.

Standard library only, to match the repo's other CI helpers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: The machinery that judges work. None of it may require a particular producer.
GATE_SURFACE = (
    "commands/gate-*.md",
    "agents/*.md",
    "workflows/*.js",
    "hooks/*.sh",
    "bin/gate-ledger",
)

BUILD_SKILLS = ("design", "plan", "build", "finish", "coach")

#: The build skills' own executables (`scripts/<name>`). A gate that shells out to one
#: of these directly has the same producer dependency as a gate that names the skill
#: that wraps it — the blind spot #246 closes: naming `/build` was already caught, but
#: nothing stopped a gate from reaching straight past the skill to `scripts/verify`.
BUILD_EXECUTABLES = (
    "plan-lint",
    "design-lint",
    "verify",
    "status-flip",
    "build-report",
    "evidence-capture",
    "worktree-setup",
)

#: A slash-command invocation, or a shell invocation of a build skill's own
#: executable — not a path segment. The lookarounds are what keep
#: `templates/design-doc.md`, `docs/design/`, and "never run install/build/test" from
#: reading as invocations — all three appear on the gate surface legitimately today.
INVOCATION = re.compile(
    rf"(?<![\w/-])/(?P<skill>{'|'.join(BUILD_SKILLS)})(?![\w/-])"
    rf"|(?<![\w/-])scripts/(?P<executable>{'|'.join(BUILD_EXECUTABLES)})(?![\w/-])"
)

#: Artifacts only a build-skill run produces. A gate that reads one has the same
#: dependency as a gate that invokes the skill.
ARTIFACTS = re.compile(r"(?<![\w/-])(PLAN\.md|docs/jig/evidence)")

#: Sentinel comments bounding a worker-dispatch region. Exempt from INVOCATION only.
REGION_OPEN = "gate-independence: begin worker-dispatch"
REGION_CLOSE = "gate-independence: end worker-dispatch"

#: Prompt builders that compile or scope a gate verdict. These judge work, so they may
#: never sit inside a worker-dispatch region — that would move the exemption onto the
#: machinery it exists to keep covered, and the check would still pass. Named here so
#: the guard is a list to maintain rather than an inference from brace matching.
GATE_COMPILERS = (
    "auditFanIn",
    "acceptanceFanIn",
    "premortemDispatchPrompt",
    "acceptancePremortemDispatchPrompt",
    "acceptancePremortemFallbackPrompt",
    "ledgerScopeCheckPrompt",
    "routingScopeCheckPrompt",
    "acceptanceScopeCheckPrompt",
    "gatePrompt",
)
COMPILER_DEF = re.compile(rf"\b(?:function\s+)?({'|'.join(GATE_COMPILERS)})\s*\(")


def scan(rel: str, text: str) -> tuple[list[str], int]:
    """Check one gate-surface file. Returns its problems and how many invocations
    the worker-dispatch exemption actually absorbed."""
    problems: list[str] = []
    open_at = 0  # line number of the unclosed region marker, 0 when outside one
    exempted = 0

    for n, line in enumerate(text.splitlines(), 1):
        if REGION_OPEN in line:
            if open_at:
                problems.append(
                    f"{rel}:{n}: worker-dispatch region opened while one is already open "
                    f"(line {open_at}) — regions never nest"
                )
            open_at = n
            continue
        if REGION_CLOSE in line:
            if not open_at:
                problems.append(f"{rel}:{n}: worker-dispatch region closed but never opened")
            open_at = 0
            continue

        if open_at and (match := COMPILER_DEF.search(line)):
            problems.append(
                f"{rel}:{n}: {match.group(1)} compiles a gate verdict and must stay covered "
                f"— it may not sit inside the worker-dispatch region opened at line "
                f"{open_at}\n    {line.strip()}"
            )

        if match := INVOCATION.search(line):
            if open_at:
                exempted += 1
            elif skill := match.group("skill"):
                problems.append(
                    f"{rel}:{n}: a gate must not invoke /{skill} — it judges "
                    f"the work, never who produced it\n    {line.strip()}"
                )
            else:
                problems.append(
                    f"{rel}:{n}: a gate must not shell out to scripts/{match.group('executable')} "
                    f"— it judges the work, never who produced it\n    {line.strip()}"
                )
        # Never exempt: a gate must not *require* a build artifact anywhere, and a
        # dispatcher has no reason to name one.
        if match := ARTIFACTS.search(line):
            problems.append(
                f"{rel}:{n}: a gate must not require {match.group(1)}, which only a "
                f"build-skill run produces. The executor-agnostic evidence contract "
                f"is reference/evidence-format.md\n    {line.strip()}"
            )

    if open_at:
        problems.append(
            f"{rel}:{open_at}: worker-dispatch region opened and never closed — an "
            f"unterminated region would exempt the rest of the file"
        )
    return problems, exempted


def violations() -> list[str]:
    problems: list[str] = []
    for pattern in GATE_SURFACE:
        for path in sorted(REPO.glob(pattern)):
            rel = path.relative_to(REPO).as_posix()
            file_problems, _ = scan(rel, path.read_text(encoding="utf-8"))
            problems.extend(file_problems)
    return problems


def dead_regions() -> list[str]:
    """A declared region that exempts nothing is scaffolding for a future mistake.
    Delete it rather than leaving an unused hole in the surface."""
    dead: list[str] = []
    for pattern in GATE_SURFACE:
        for path in sorted(REPO.glob(pattern)):
            text = path.read_text(encoding="utf-8")
            if REGION_OPEN not in text:
                continue
            _, exempted = scan(path.relative_to(REPO).as_posix(), text)
            if not exempted:
                dead.append(path.relative_to(REPO).as_posix())
    return dead


def main() -> int:
    matched = [p for pattern in GATE_SURFACE for p in REPO.glob(pattern)]
    if len(matched) < 20:
        print(f"Gate surface matched only {len(matched)} files — check the globs.")
        return 1

    if dead := dead_regions():
        print("Gate independence check FAILED:")
        for path in dead:
            print(f"  - {path}: declares a worker-dispatch region that exempts nothing — remove it")
        return 1

    problems = violations()
    if problems:
        print("Gate independence check FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"Gate independence check passed: none of {len(matched)} gate files requires a build skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
