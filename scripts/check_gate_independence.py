#!/usr/bin/env python3
"""Assert Studious's judge doors never require a particular producer.

A gate judges the work, never who produced it — the invariant PRODUCT.md's "the gates
being a methodology" non-goal rests on. `reference/worker-contract.md` is normative: a
human, Superpowers, or `/build` must all satisfy a judge equally.

Two ways a judge could quietly acquire a producer dependency:

1. **Invoking a producer door** (`/build`, `/shape`) or the executable it wraps
   (`scripts/verify`, `scripts/design-lint`, ...) — reaching past the door is the same
   dependency (#246).
2. **Requiring a producer artifact** (`PLAN.md`, `docs/jig/evidence/`) instead of the
   executor-agnostic `reference/evidence-format.md`.

Everything outside the guarded surface (`/next`, `/retro`, the worker contract, README,
context docs) is free to route to producer doors — that's the product working as
intended.

The surface is derived from `reference/personas.md`'s Doors table, never hardcoded:
`judge` rows name the guarded command files, `producer` rows name the forbidden
invocations. (Before the persona restructure this file hardcoded a `commands/gate-*.md`
glob and a build-skill tuple, so a renamed judge door could fall off the surface
silently.)

Standard library only, to match the repo's other CI helpers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CHARTER = REPO / "reference" / "personas.md"

#: One row of the charter's Doors table: `/door` | persona | class | `commands/file.md` | absorbed
DOOR_ROW = re.compile(
    r"^\|\s*`/(?P<door>[a-z][a-z-]*)`\s*\|(?P<persona>[^|]*)\|\s*(?P<cls>\w+)\s*\|"
    r"\s*`(?P<path>[^`]+)`\s*\|(?P<absorbed>[^|]*)\|",
    re.MULTILINE,
)

#: Guarded regardless of door: judgment machinery no single door owns outright.
STRUCTURAL_SURFACE = (
    "agents/*.md",
    "hooks/*.sh",
    "bin/gate-ledger",
)

#: The producer doors' own executables (`scripts/<name>`, or `studious <name>` through
#: the one entrypoint) — shelling out to one directly is the same dependency as naming
#: the door that wraps it (#246).
BUILD_EXECUTABLES = (
    "plan-lint",
    "plan-drift",
    "design-lint",
    "verify",
    "status-flip",
    "build-report",
    "evidence-capture",
    "evidence-freshness",
    "worktree-setup",
)

#: Artifacts only a producer run creates; reading one is the same dependency as invoking
#: the door. `docs/jig/evidence` is the retired committed location — still banned, so
#: prose reintroducing it fails the same way live paths do.
ARTIFACTS = re.compile(r"(?<![\w/-])(PLAN\.md|docs/jig/evidence|\.studious/build-evidence)")


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
    """A slash-command invocation of a producer door, or a shell invocation of its
    executable — not a path segment. The lookarounds keep `templates/design-doc.md`,
    `docs/design/`, and "never run install/build/test" from misreading as invocations."""
    return re.compile(
        r"(?<![\w/-])/(?P<door>{})(?![\w/-])".format("|".join(producer_names()))
        + r"|(?<![\w/-])(?:scripts/|(?:\S*/)?studious[\"']?\s+)(?P<executable>{})(?![\w/-])".format(
            "|".join(BUILD_EXECUTABLES)
        )
    )


def surface_paths() -> list[Path]:
    """Every guarded file: the charter's judge doors plus the structural surface."""
    paths = [REPO / p for p in judge_paths()]
    for pattern in STRUCTURAL_SURFACE:
        paths.extend(sorted(REPO.glob(pattern)))
    return [p for p in paths if p.is_file()]


def scan(rel: str, text: str, invocation: re.Pattern | None = None) -> list[str]:
    """Check one guarded file and return its problems.

    `invocation` is a parameter so `main()` builds it once per run, not once per file,
    and a test can drive the scanner with a pattern of its own.
    """
    if invocation is None:
        invocation = invocation_re()
    problems: list[str] = []

    for n, line in enumerate(text.splitlines(), 1):
        if match := invocation.search(line):
            if door := match.group("door"):
                problems.append(
                    f"{rel}:{n}: a judge door must not invoke /{door} — it judges "
                    f"the work, never who produced it\n    {line.strip()}"
                )
            else:
                problems.append(
                    f"{rel}:{n}: a judge door must not shell out to "
                    f"studious {match.group('executable')} — it judges the work, never "
                    f"who produced it\n    {line.strip()}"
                )
        if match := ARTIFACTS.search(line):
            problems.append(
                f"{rel}:{n}: a judge door must not require {match.group(1)}, which only a "
                f"producer run creates. The executor-agnostic evidence contract "
                f"is reference/evidence-format.md\n    {line.strip()}"
            )

    return problems


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
        problems.extend(scan(rel, path.read_text(encoding="utf-8"), invocation))
    return problems


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
    problems = violations(paths, invocation_re())
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
