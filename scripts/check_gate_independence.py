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
   producer.
2. **Requiring a build artifact.** A gate that reads `PLAN.md`'s checkpoint blocks or
   expects `docs/jig/evidence/` has the same dependency wearing a different hat — the
   evidence contract a gate may rely on is `reference/evidence-format.md`, which any
   executor can satisfy.

Everything outside the gate surface — `/work-on`, `/work-through`, the worker
contract, the README, the context docs — is free to name and route to the build
skills. That is the product working as intended, not a violation.

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

#: A slash-command invocation, not a path segment. The lookarounds are what keep
#: `templates/design-doc.md`, `docs/design/`, and "never run install/build/test" from
#: reading as invocations — all three appear on the gate surface legitimately today.
INVOCATION = re.compile(rf"(?<![\w/-])/({'|'.join(BUILD_SKILLS)})(?![\w/-])")

#: Artifacts only a build-skill run produces. A gate that reads one has the same
#: dependency as a gate that invokes the skill.
ARTIFACTS = re.compile(r"(?<![\w/-])(PLAN\.md|docs/jig/evidence)")


def violations() -> list[str]:
    problems: list[str] = []
    for pattern in GATE_SURFACE:
        for path in sorted(REPO.glob(pattern)):
            rel = path.relative_to(REPO)
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if match := INVOCATION.search(line):
                    problems.append(
                        f"{rel}:{n}: a gate must not invoke /{match.group(1)} — it judges "
                        f"the work, never who produced it\n    {line.strip()}"
                    )
                if match := ARTIFACTS.search(line):
                    problems.append(
                        f"{rel}:{n}: a gate must not require {match.group(1)}, which only a "
                        f"build-skill run produces. The executor-agnostic evidence contract "
                        f"is reference/evidence-format.md\n    {line.strip()}"
                    )
    return problems


def main() -> int:
    matched = [p for pattern in GATE_SURFACE for p in REPO.glob(pattern)]
    if len(matched) < 20:
        print(f"Gate surface matched only {len(matched)} files — check the globs.")
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
