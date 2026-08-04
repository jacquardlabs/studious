#!/usr/bin/env python3
"""Assert Studious's judge doors never require a particular producer.

The producer doors (`/shape`, `/build`, `/ship`) ship in this plugin alongside the judge
doors (#150). That makes one promise easy to break by accident, and it is the promise
PRODUCT.md's "the gates being a methodology" non-goal rests on: **a gate judges the work,
never who produced it.** `reference/worker-contract.md` is normative — a human,
Superpowers, or `/build` all satisfy it, and a judge must reach the same verdict either
way.

Two ways a judge could quietly acquire that dependency, both checked here:

1. **Invoking a producer door.** A judge command or specialist agent telling the reader to
   run `/build`, or routing a finding through `/shape`, only works for one kind of
   producer — and reaching past the door straight to the executable it wraps
   (`scripts/verify`, `scripts/design-lint`, ...) is the same dependency wearing a
   third hat (#246).
2. **Requiring a producer artifact.** A judge that reads `PLAN.md`'s checkpoint blocks or
   expects `docs/jig/evidence/` has the same dependency wearing a different hat — the
   evidence contract a judge may rely on is `reference/evidence-format.md`, which any
   executor can satisfy.

Everything outside the guarded surface — `/next`, `/retro`, the worker contract, the
README, the context docs — is free to name and route to the producer doors. That is the
product working as intended, not a violation.

**The surface is derived, never hardcoded.** `reference/personas.md`'s Doors table is the
authority: its `judge` rows name the command files guarded here, and its `producer` rows
name the invocations rule 1 forbids. Before the persona restructure this file carried a
literal `commands/gate-*.md` glob and a hardcoded build-skill tuple, so a renamed judge
door would have fallen off the guarded surface silently while CI stayed green.

**One file on the surface holds two roles.** `workflows/epic-driver.js` is a dispatcher
that also builds the prompts compiling verdicts. Its dispatch half must be able to route
work to `/build` exactly as `commands/next.md` does; its judge half must stay
producer-agnostic. Taking the whole file off the surface would drop the guarantee for
`auditFanIn` and `acceptanceFanIn`, which are the two functions that most need it — so
instead a file may mark a *region* as worker dispatch, exempt from rule 1 only, and never
containing verdict-compile machinery (#212). The markers are plain comments so the check
stays a line scanner and the exemption is visible where it applies rather than in this
file's config.

Standard library only, to match the repo's other CI helpers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHARTER = REPO / "reference" / "personas.md"

#: One row of the charter's Doors table: `/door` | persona | class | `commands/file.md` | …
DOOR_ROW = re.compile(
    r"^\|\s*`/(?P<door>[a-z][a-z-]*)`\s*\|[^|]*\|\s*(?P<cls>\w+)\s*\|\s*`(?P<path>[^`]+)`\s*\|",
    re.MULTILINE,
)

#: Guarded regardless of door: judgment machinery no single door owns outright.
STRUCTURAL_SURFACE = (
    "agents/*.md",
    "workflows/*.js",
    "hooks/*.sh",
    "bin/gate-ledger",
)

#: The producer doors' own executables (`scripts/<name>`). A judge that shells out to one
#: of these directly has the same producer dependency as a judge that names the door that
#: wraps it — the blind spot #246 closes: naming `/build` was already caught, but nothing
#: stopped a judge from reaching straight past the door to `scripts/verify`.
BUILD_EXECUTABLES = (
    "plan-lint",
    "design-lint",
    "verify",
    "status-flip",
    "build-report",
    "evidence-capture",
    "worktree-setup",
)

#: Artifacts only a producer run creates. A judge that reads one has the same dependency
#: as a judge that invokes the door. `docs/jig/evidence` is the store's retired committed
#: location — banned still, so prose reintroducing it fails the same way live paths do.
ARTIFACTS = re.compile(r"(?<![\w/-])(PLAN\.md|docs/jig/evidence|\.studious/build-evidence)")

#: Sentinel comments bounding a worker-dispatch region. Exempt from INVOCATION only.
REGION_OPEN = "gate-independence: begin worker-dispatch"
REGION_CLOSE = "gate-independence: end worker-dispatch"

#: Prompt builders that compile or scope a verdict. These judge work, so they may never
#: sit inside a worker-dispatch region — that would move the exemption onto the machinery
#: it exists to keep covered, and the check would still pass. Named here so the guard is a
#: list to maintain rather than an inference from brace matching.
GATE_COMPILERS = (
    "auditFanIn",
    "acceptanceFanIn",
    "premortemDispatchPrompt",
    "acceptancePremortemDispatchPrompt",
    "acceptancePremortemFallbackPrompt",
    "ledgerScopeCheckPrompt",
    "routingScopeCheckPrompt",
    "acceptanceScopeCheckPrompt",
    "criteriaConformancePrompt",
    "epicLedgerInstruction",
    "finaleClosurePrompt",
    "finaleSeamPrompt",
    "gatePrompt",
)
COMPILER_DEF = re.compile(r"\b(?:function\s+)?({})\s*\(".format("|".join(GATE_COMPILERS)))


def doors() -> list[dict]:
    """Every row of the charter's Doors table, in file order."""
    if not CHARTER.exists():
        raise SystemExit(f"charter not found: {CHARTER.relative_to(REPO).as_posix()}")
    rows = [m.groupdict() for m in DOOR_ROW.finditer(CHARTER.read_text(encoding="utf-8"))]
    if not rows:
        raise SystemExit(
            "reference/personas.md parsed to zero doors — the Doors table shape changed"
        )
    return rows


def doors_of_class(cls: str) -> list[dict]:
    return [d for d in doors() if d["cls"] == cls]


def judge_paths() -> list[str]:
    return [d["path"] for d in doors_of_class("judge")]


def producer_names() -> list[str]:
    return [d["door"] for d in doors_of_class("producer")]


def invocation_re() -> re.Pattern:
    """A slash-command invocation of a producer door, or a shell invocation of a producer
    executable — not a path segment. The lookarounds are what keep
    `templates/design-doc.md`, `docs/design/`, and "never run install/build/test" from
    reading as invocations — all three appear on the guarded surface legitimately today."""
    return re.compile(
        r"(?<![\w/-])/(?P<door>{})(?![\w/-])".format("|".join(producer_names()))
        + r"|(?<![\w/-])scripts/(?P<executable>{})(?![\w/-])".format(
            "|".join(BUILD_EXECUTABLES)
        )
    )


def surface_paths() -> list[Path]:
    """Every guarded file: the charter's judge doors plus the structural surface."""
    paths = [REPO / p for p in judge_paths()]
    for pattern in STRUCTURAL_SURFACE:
        paths.extend(sorted(REPO.glob(pattern)))
    return [p for p in paths if p.is_file()]


def scan(rel: str, text: str, invocation: re.Pattern | None = None) -> tuple[list[str], int]:
    """Check one guarded file. Returns its problems and how many invocations the
    worker-dispatch exemption actually absorbed.

    `invocation` defaults to the charter-derived pattern. It is a parameter at all so
    `main()` builds it once per run instead of once per file, and so a test can drive the
    scanner with a pattern of its own.
    """
    if invocation is None:
        invocation = invocation_re()
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
                f"{rel}:{n}: {match.group(1)} compiles a verdict and must stay covered "
                f"— it may not sit inside the worker-dispatch region opened at line "
                f"{open_at}\n    {line.strip()}"
            )

        if match := invocation.search(line):
            if open_at:
                exempted += 1
            elif door := match.group("door"):
                problems.append(
                    f"{rel}:{n}: a judge door must not invoke /{door} — it judges "
                    f"the work, never who produced it\n    {line.strip()}"
                )
            else:
                problems.append(
                    f"{rel}:{n}: a judge door must not shell out to "
                    f"scripts/{match.group('executable')} — it judges the work, never "
                    f"who produced it\n    {line.strip()}"
                )
        # Never exempt: a judge must not *require* a producer artifact anywhere, and a
        # dispatcher has no reason to name one.
        if match := ARTIFACTS.search(line):
            problems.append(
                f"{rel}:{n}: a judge door must not require {match.group(1)}, which only a "
                f"producer run creates. The executor-agnostic evidence contract "
                f"is reference/evidence-format.md\n    {line.strip()}"
            )

    if open_at:
        problems.append(
            f"{rel}:{open_at}: worker-dispatch region opened and never closed — an "
            f"unterminated region would exempt the rest of the file"
        )
    return problems, exempted


def violations(
    paths: list[Path] | None = None, invocation: re.Pattern | None = None
) -> list[str]:
    if paths is None:
        paths = surface_paths()
    if invocation is None:
        invocation = invocation_re()
    problems: list[str] = []
    for path in paths:
        rel = path.relative_to(REPO).as_posix()
        file_problems, _ = scan(rel, path.read_text(encoding="utf-8"), invocation)
        problems.extend(file_problems)
    return problems


def dead_regions(
    paths: list[Path] | None = None, invocation: re.Pattern | None = None
) -> list[str]:
    """A declared region that exempts nothing is scaffolding for a future mistake.
    Delete it rather than leaving an unused hole in the surface."""
    if paths is None:
        paths = surface_paths()
    if invocation is None:
        invocation = invocation_re()
    dead: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if REGION_OPEN not in text:
            continue
        _, exempted = scan(path.relative_to(REPO).as_posix(), text, invocation)
        if not exempted:
            dead.append(path.relative_to(REPO).as_posix())
    return dead


def main() -> int:
    # A judge door named in the charter but missing on disk is the failure mode the old
    # `len(matched) < 20` floor was standing in for — named directly now, so a rename that
    # forgets a file fails here instead of silently shrinking the surface.
    missing = [p for p in judge_paths() if not (REPO / p).is_file()]
    if missing:
        print("Gate independence check FAILED:")
        for path in missing:
            print(f"  - {path}: charter lists this judge door, but the file does not exist")
        return 1

    paths = surface_paths()
    invocation = invocation_re()

    if dead := dead_regions(paths, invocation):
        print("Gate independence check FAILED:")
        for path in dead:
            print(f"  - {path}: declares a worker-dispatch region that exempts nothing — remove it")
        return 1

    problems = violations(paths, invocation)
    if problems:
        print("Gate independence check FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(
        f"Gate independence check passed: none of {len(paths)} guarded files "
        f"({len(judge_paths())} judge doors, derived from reference/personas.md) "
        f"requires a producer."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
