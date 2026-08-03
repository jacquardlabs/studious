#!/usr/bin/env python3
"""Validate .claude-plugin/plugin.json against Studious's required manifest shape.

Standard library only. Cross-check against the official Claude Code plugin manifest
schema if one is published; until then this local check stands.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / ".claude-plugin" / "plugin.json"
HOOKS = REPO / "hooks" / "hooks.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
NAME = re.compile(r"^[a-z0-9-]+$")
PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s]+)")
REQUIRED = ("name", "description", "version", "author", "repository", "license", "keywords")


def validate(data: dict) -> list[str]:
    errors: list[str] = [f"missing required field: {key}" for key in REQUIRED if key not in data]

    name = data.get("name")
    if "name" in data and not isinstance(name, str):
        errors.append("name must be a string")
    elif isinstance(name, str) and not NAME.match(name):
        errors.append(f"name '{name}' must match ^[a-z0-9-]+$")

    version = data.get("version")
    if "version" in data and not isinstance(version, str):
        errors.append("version must be a string")
    elif isinstance(version, str) and not SEMVER.match(version):
        errors.append(f"version '{version}' is not semver (X.Y.Z)")

    author = data.get("author")
    if isinstance(author, dict):
        if "name" not in author:
            errors.append("author.name is required")
    elif "author" in data:
        errors.append("author must be an object with a name")

    if "keywords" in data and not isinstance(data.get("keywords"), list):
        errors.append("keywords must be an array")

    return errors


def validate_hooks(data: object, repo: Path) -> list[str]:
    """Basic-shape check for hooks/hooks.json — not a full schema validation.

    Asserts only what a syntax or path error would silently break: the top-level
    ``hooks`` object of event -> matcher entries, each entry carrying a ``hooks``
    array of command hooks, and every command's ``${CLAUDE_PLUGIN_ROOT}/...``
    reference resolving to a file that ships in this repo. Matcher strings, hook
    types beyond ``command``, and Claude Code's own schema are not checked here.
    """
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hooks.json: top level must be an object"]
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return ["hooks.json: 'hooks' must be an object of event name -> entry array"]
    for event, entries in hooks.items():
        if not isinstance(entries, list):
            errors.append(f"hooks.json: {event} must be an array of matcher entries")
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                errors.append(f"hooks.json: each {event} entry must carry a 'hooks' array")
                continue
            for hook in entry["hooks"]:
                command = hook.get("command") if isinstance(hook, dict) else None
                if not isinstance(command, str) or not command.strip():
                    errors.append(f"hooks.json: a {event} hook has no command string")
                    continue
                refs = PLUGIN_ROOT_REF.findall(command)
                if not refs:
                    errors.append(
                        f"hooks.json: {event} command references no"
                        f" ${{CLAUDE_PLUGIN_ROOT}} file: {command}"
                    )
                errors.extend(
                    f"hooks.json: {event} command references missing file: {ref}"
                    for ref in refs
                    if not (repo / ref).is_file()
                )
    return errors


def main() -> int:
    try:
        data = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plugin.json could not be read/parsed: {exc}")
        return 1
    errors = validate(data)
    if HOOKS.exists():
        try:
            hooks_data = json.loads(HOOKS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"hooks.json could not be read/parsed: {exc}")
        else:
            errors.extend(validate_hooks(hooks_data, REPO))
    if errors:
        print("Plugin manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Plugin manifest valid.")
    if HOOKS.exists():
        print("hooks/hooks.json parses and its hook commands resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
