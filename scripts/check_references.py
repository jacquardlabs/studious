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
# A namespaced token (`@agent-gauntlet:security-auditor`) names another plugin's agent.
AGENT_RE = re.compile(r"@agent-((?:[a-z0-9-]+:)?[a-z0-9-]+)")
# Recognized skill-reference phrasings: "the `<name>` skill" (incl. possessive
# "skill's"), "invoke [the] `<name>`", "skill `<name>`". Commands and agents use
# their own prefixes, so a bare backtick token after "invoke"/"skill" is unambiguous.
SKILL_RES = (
    re.compile(r"the `([a-z0-9-]+)` skill"),
    re.compile(r"invoke (?:the )?`([a-z0-9-]+)`"),
    re.compile(r"skill `([a-z0-9-]+)`"),
)
# Curated rubric paths doors cite, e.g. `reference/severity-rubric.md`. Angle-bracket
# placeholders are allowed.
REFERENCE_RE = re.compile(r"reference/[A-Za-z0-9_./<>-]+\.md")
#: Directories holding files that outlive any branch. Design docs are branch-local
#: and deleted at closeout (#219), so a file here citing a *specific* one dangles
#: once merged. The bare directory or `<slug>` template form is fine — that's an
#: output path, not a reference to one doc.
DURABLE_DIRS = ("scripts", "skills", "commands", "agents", "reference", "bin", "workflows", "tests")
#: A concrete filename under a disposable doc tree, as opposed to the bare
#: directory or the `<slug>` placeholder form, both of which are legitimate.
DISPOSABLE_CITATION = re.compile(r"docs/design/(?!<)([A-Za-z0-9_-]+\.md)")


def find_disposable_citations(root: Path) -> list[str]:
    """Durable files citing a design doc that cannot survive its branch (#233).

    33 of these accumulated undetected, each reading as load-bearing rationale
    a later reader can't verify since the cited doc is gone by then.
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
                f"deleted at closeout — attribute the claim to the issue, a "
                f"`git show <sha>:<path>` citation, or state it inline (#233)"
                for name in sorted(set(DISPOSABLE_CITATION.findall(text)))
            )
    return errors


def _declared_dependencies() -> set[str]:
    """Plugins this one depends on — their skills are citable by name though
    absent from `skills/`. Derived from the manifest, not restated here."""
    try:
        return set(json.loads(MANIFEST.read_text(encoding="utf-8")).get("dependencies", []))
    except (OSError, json.JSONDecodeError):
        return set()  # validate_plugin.py owns manifest validity; don't double-report


# Plugins whose skills and agents are citable here though they ship elsewhere: the
# manifest's declared dependencies (`viva`, which /shape, /build, and the doctor's
# tooling check all name; `gauntlet`, whose posture judges /health dispatches). An
# agent token namespaced `<plugin>:<name>` resolves in that plugin, not in `agents/`.
EXTERNAL_PLUGINS = _declared_dependencies()
# `web-design-guidelines` ships with Claude Code itself.
EXTERNAL_SKILLS = {"web-design-guidelines"} | EXTERNAL_PLUGINS


def _agent_error(root: Path, token: str) -> str:
    """Why `@agent-<token>` fails to resolve, or "" when it does."""
    namespace, _, name = token.rpartition(":")
    if namespace:
        return "" if namespace in EXTERNAL_PLUGINS else f"{namespace} is not a declared dependency"
    return "" if (root / "agents" / f"{name}.md").is_file() else f"agents/{name}.md missing"


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
                f"@agent-{name} referenced in {rel} but {why}"
                for name in sorted(set(AGENT_RE.findall(text)))
                if (why := _agent_error(root, name))
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
                    # Template path (a `<placeholder>` segment): the literal file
                    # can't exist, so validate the deepest placeholder-free dir.
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
