#!/usr/bin/env python3
"""Assert Studious's gates never require jig.

The two plugins ship from one repo (issue #150). The reason that is safe — and the
reason PRODUCT.md's "not a methodology" non-goal survives co-location — is that the
gates stay executor-agnostic: `reference/worker-contract.md` is normative, and jig is
one executor that satisfies it, alongside Superpowers, a human, or anything else.

Co-location makes that promise easy to break by accident. This check is the guard.

Two rules:

1. **The gate surface never mentions jig at all.** Gate commands, every agent, the
   epic driver, the hooks, and the ledger are the machinery that judges work. A jig
   reference in any of them is a hard dependency in the making, even a benign-looking
   one.
2. **In prose an agent reads as instructions, a jig mention must be optional on its
   face.** The navigator, the worker contract, and the README may name jig as an
   available executor, but only inside a conditional — "if jig is installed", "when
   installed", "otherwise". A bare imperative ("run /build") would read as a
   requirement. This repo's own context docs are exempt: they describe where jig
   lives, which cannot be written conditionally.

Standard library only, to match the repo's other CI helpers.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

#: Rule 1. Anything matching these may never name jig.
GATE_SURFACE = (
    "commands/gate-*.md",
    "agents/*.md",
    "workflows/*.js",
    "hooks/*.sh",
    "bin/gate-ledger",
)

#: Rule 2. Files an agent reads as instructions, permitted to name jig only inside a
#: conditional — the flow has to still read correctly for a worker that isn't jig.
OPTIONAL_SURFACE = (
    "commands/work-on.md",
    "commands/work-through.md",
    "reference/worker-contract.md",
    "README.md",
)

#: This repo's own documentation, which describes the two-plugin arrangement rather
#: than instructing anyone to use it. Exempt from rule 2's guard requirement — you
#: cannot write "jig lives at plugins/jig/" conditionally — but still bound by rule 1,
#: since none of these is a gate. Note these are *this* repo's context docs; the
#: PRODUCT.md/DESIGN.md/CLAUDE.md that agents read at runtime live in the consuming
#: project and are never these files.
TOPOLOGY_DOCS = (
    "CLAUDE.md",
    "PRODUCT.md",
    "DESIGN.md",
    "CONTRIBUTING.md",
    "CHANGELOG.md",  # generated from commit subjects by semantic-release
)

#: Word-boundary match so "jigsaw" and the like don't trip the check.
JIG = re.compile(r"\bjig\b", re.IGNORECASE)

#: Any of these near a mention marks it optional rather than required. Deliberately
#: excludes a bare "or", which appears in enough ordinary prose to wave through an
#: unguarded mention on any wrapped line — the point is to catch a requirement
#: written as an imperative, so the markers have to actually mean "not mandatory".
GUARDS = re.compile(
    r"\b(if|when|whether|may|might|optional(?:ly)?|either|"
    r"otherwise|without|absent|installed|available|alongside)\b",
    re.IGNORECASE,
)

#: A mention is guarded by language on its own line or the line before it — enough
#: to cover a guard that lands on the far side of a prose wrap.
GUARD_LOOKBACK = 1


def gate_surface_violations() -> list[str]:
    problems = []
    for pattern in GATE_SURFACE:
        for path in sorted(REPO.glob(pattern)):
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if JIG.search(line):
                    rel = path.relative_to(REPO)
                    problems.append(
                        f"{rel}:{n}: the gate surface must not name jig — "
                        f"gates judge work, they never require one executor\n"
                        f"    {line.strip()}"
                    )
    return problems


def optional_surface_violations() -> list[str]:
    problems = []
    for name in OPTIONAL_SURFACE:
        path = REPO / name
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines, 1):
            if not JIG.search(line):
                continue
            window = lines[max(0, n - 1 - GUARD_LOOKBACK) : n]
            if not any(GUARDS.search(w) for w in window):
                problems.append(
                    f"{name}:{n}: names jig without marking it optional — "
                    f"add a conditional so the flow still reads correctly "
                    f"for a worker that isn't jig\n    {line.strip()}"
                )
    return problems


def unlisted_mentions() -> list[str]:
    """Catch a jig mention that appears somewhere neither rule covers."""
    covered = {REPO / n for n in OPTIONAL_SURFACE + TOPOLOGY_DOCS}
    for pattern in GATE_SURFACE:
        covered.update(REPO.glob(pattern))

    searched = ("commands", "agents", "skills", "reference", "workflows", "hooks", "templates")
    candidates = [p for d in searched for p in (REPO / d).rglob("*") if p.is_file()]
    candidates.extend(p for p in REPO.glob("*.md"))

    problems = []
    for path in sorted(set(candidates) - covered):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if JIG.search(line):
                rel = path.relative_to(REPO)
                problems.append(
                    f"{rel}:{n}: names jig outside the surfaces allowed to. Add the file "
                    f"to OPTIONAL_SURFACE in this script only if the mention is genuinely "
                    f"optional\n    {line.strip()}"
                )
    return problems


def main() -> int:
    problems = gate_surface_violations() + optional_surface_violations() + unlisted_mentions()
    if problems:
        print("Gate independence check FAILED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("Gate independence check passed: no Studious gate requires jig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
