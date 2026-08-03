#!/usr/bin/env python3
"""Verify every @agent-*, internal-skill, and reference/ path in commands/, agents/, skills/, and reference/ resolves.

Run from CI to catch broken cross-references (e.g. an agent rename that orphans a
command's @agent-* reference). Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / ".claude-plugin" / "plugin.json"
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
#: Directories holding files that outlive any branch. A file here may not cite a
#: *specific* design doc, because design docs are branch-local and deleted at
#: closeout (#219) — the citation is dangling the moment the branch merges. The
#: bare directory (`docs/design/`, `docs/design/<slug>.md` as a template) is fine
#: and common: that is the producer's output path, not a reference to one doc.
DURABLE_DIRS = ("scripts", "skills", "commands", "agents", "reference", "bin", "workflows", "tests")
#: A concrete filename under a disposable doc tree, as opposed to the bare
#: directory or the `<slug>` placeholder form, both of which are legitimate.
DISPOSABLE_CITATION = re.compile(r"docs/design/(?!<)([A-Za-z0-9_-]+\.md)")


def find_disposable_citations(root: Path) -> list[str]:
    """Durable files citing a design doc that cannot survive its branch (#233).

    Thirty-three of these accumulated before anyone noticed, every one reading as
    load-bearing rationale ("per the build-scripts design doc") that a reader
    following it would find missing — unable to tell whether the claim was ever
    true. `check_references.py` did not catch them because it validates only
    `@agent-*`, skill names, and `reference/*.md`, and scans only three
    directories.
    """
    errors: list[str] = []
    for sub in DURABLE_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix in {".png", ".jpg", ".gif"}:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rel = path.relative_to(root)
            errors.extend(
                f"{rel} cites docs/design/{name}, a branch-local design doc that is "
                f"deleted at closeout — attribute the claim to the issue, the "
                f"pre-mortem register, or state it inline (#233)"
                for name in sorted(set(DISPOSABLE_CITATION.findall(text)))
            )
    return errors


def _declared_dependencies() -> set[str]:
    """Plugins this one declares a dependency on. Their skills are legitimately
    referenced by name and legitimately absent from `skills/` — derived from the
    manifest rather than restated here, so declaring a dependency is the single
    action that makes its skill citable."""
    try:
        return set(json.loads(MANIFEST.read_text(encoding="utf-8")).get("dependencies", []))
    except (OSError, json.JSONDecodeError):
        return set()  # validate_plugin.py owns manifest validity; don't double-report


# Skills referenced by name but legitimately shipped elsewhere, not in this repo.
# `web-design-guidelines` ships with Claude Code itself; the rest come from the
# manifest's declared dependencies (`viva`, which /shape, /build, and the doctor's
# tooling check all name).
EXTERNAL_SKILLS = {"web-design-guidelines"} | _declared_dependencies()


def find_broken(root: Path) -> list[str]:
    errors: list[str] = []
    for sub in SCAN_DIRS:
        base = root / sub
        if not base.is_dir():
            continue
        for md in sorted(base.rglob("*.md")):
            text = md.read_text(encoding="utf-8")
            rel = md.relative_to(root)
            errors.extend(
                f"@agent-{name} referenced in {rel} but agents/{name}.md missing"
                for name in sorted(set(AGENT_RE.findall(text)))
                if not (root / "agents" / f"{name}.md").is_file()
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
    errors = find_broken(REPO) + find_disposable_citations(REPO)
    if errors:
        print("Reference check FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(
        "Reference check passed: all @agent-*, skill, and reference/ paths resolve, "
        "and no durable file cites a disposable design doc."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
