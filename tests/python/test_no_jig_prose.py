"""No shipped prompt still calls this plugin's build loop "jig" (issue #150).

jig was absorbed as skills of this plugin, so a user reading "jig's four skills"
or "if jig is installed" is being pointed at a product they cannot install —
the marketplace entry was deleted. The conditionals that *acted* on that name
are guarded separately (`tests/jig/test_gate_handoffs.py`); this guards the
prose, which regresses easily because old wording gets copied forward.

`docs/jig/` and `tests/jig/` survive as real directory names — the evidence
layout is pinned in `reference/evidence-format.md` and renaming it would break
the one contract a gate is allowed to rely on. So the rule is not "the string
never appears," it is "every appearance is part of one of those paths."
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# What a consuming project actually loads: prompts, not this repo's own tooling.
SHIPPED = (
    "README.md",
    "commands/*.md",
    "agents/*.md",
    "skills/*/SKILL.md",
    "reference/*.md",
    "templates/*.md",
    "hooks/*.sh",
    "bin/*",
)

# The two paths that keep the name legitimately.
ALLOWED_PATH = re.compile(r"(docs|tests)/jig\b")
ANY_JIG = re.compile(r"\bjig\b", re.IGNORECASE)


def shipped_files() -> list[Path]:
    return sorted({p for pattern in SHIPPED for p in REPO.glob(pattern) if p.is_file()})


def offenders() -> list[str]:
    found: list[str] = []
    for path in shipped_files():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # Blank out the legitimate paths, then look for anything left over.
            if ANY_JIG.search(ALLOWED_PATH.sub("", line)):
                found.append(f"{path.relative_to(REPO)}:{n}: {line.strip()[:90]}")
    return found


def test_no_shipped_prompt_names_jig() -> None:
    problems = offenders()
    assert problems == [], "shipped prompts still name jig:\n" + "\n".join(problems)


def test_the_surface_is_not_empty() -> None:
    """A glob typo would make the check vacuously true."""
    assert len(shipped_files()) > 40


def test_the_evidence_paths_are_still_allowed() -> None:
    """The rule must not tempt anyone into renaming docs/jig/evidence/."""
    assert ANY_JIG.search(ALLOWED_PATH.sub("", "reports land in docs/jig/evidence/")) is None
    assert ANY_JIG.search(ALLOWED_PATH.sub("", "see tests/jig/test_verify.py")) is None


def test_prose_uses_would_be_caught() -> None:
    for phrasing in (
        "Runs jig's build loop over a hand-written PLAN.md",
        "If jig is installed, its /build workflow picks up",
        "The four jig skills are the only dispatch targets",
        "no jig-specific flags invented",
    ):
        assert ANY_JIG.search(ALLOWED_PATH.sub("", phrasing)), phrasing
