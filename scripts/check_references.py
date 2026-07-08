#!/usr/bin/env python3
"""Verify every @agent-*, internal-skill, and reference/ path in commands/, agents/, skills/, and reference/ resolves.

Run from CI to catch broken cross-references (e.g. an agent rename that orphans a
command's @agent-* reference). Standard library only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("commands", "agents", "skills", "reference")
AGENT_RE = re.compile(r"@agent-([a-z0-9-]+)")
# Recognized phrasings for a skill reference, e.g. "the `<name>` skill" (also
# matches the possessive "the `<name>` skill's ..."), "invoke `<name>`"/"invoke
# the `<name>`", and "skill `<name>`". Commands (`` `/gate-x` ``) and agents
# (`@agent-x`) use their own distinct prefixes, so a bare backtick-wrapped
# lowercase-dash token after "invoke" or "skill" is unambiguously a skill name.
SKILL_RES = (
    re.compile(r"the `([a-z0-9-]+)` skill"),
    re.compile(r"invoke (?:the )?`([a-z0-9-]+)`"),
    re.compile(r"skill `([a-z0-9-]+)`"),
)
# Curated rubric paths agents cite, e.g. `reference/security-checklist.md` or the
# template `reference/idioms/<language>.md`. Angle-bracket placeholders are allowed.
REFERENCE_RE = re.compile(r"reference/[A-Za-z0-9_./<>-]+\.md")
# Skills referenced by name but legitimately shipped elsewhere, not in this repo.
EXTERNAL_SKILLS = {"web-design-guidelines"}


def find_broken(root: Path) -> list[str]:
    errors: list[str] = []
    for sub in SCAN_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            rel = md.relative_to(root)
            for name in sorted(set(AGENT_RE.findall(text))):
                if not (root / "agents" / f"{name}.md").is_file():
                    errors.append(
                        f"@agent-{name} referenced in {rel} but agents/{name}.md missing"
                    )
            skill_names = {name for regex in SKILL_RES for name in regex.findall(text)}
            for name in sorted(skill_names):
                if name in EXTERNAL_SKILLS:
                    continue
                if not (root / "skills" / name).is_dir():
                    errors.append(
                        f"skill `{name}` referenced in {rel} but skills/{name}/ missing"
                    )
            for ref in sorted(set(REFERENCE_RE.findall(text))):
                if "<" in ref:
                    # Template path (e.g. reference/idioms/<language>.md): the literal
                    # file can't exist, so validate the deepest placeholder-free dir.
                    parts: list[str] = []
                    for part in ref.split("/"):
                        if "<" in part:
                            break
                        parts.append(part)
                    if not root.joinpath(*parts).is_dir():
                        errors.append(
                            f"{ref} referenced in {rel} but {'/'.join(parts)}/ missing"
                        )
                elif not (root / ref).is_file():
                    errors.append(f"{ref} referenced in {rel} but {ref} missing")
    return errors


def main() -> int:
    errors = find_broken(REPO)
    if errors:
        print("Reference check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Reference check passed: all @agent-*, skill, and reference/ paths resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
