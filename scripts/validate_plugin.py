#!/usr/bin/env python3
"""Validate every .claude-plugin/plugin.json in the repo against Studious's manifest shape.

This repo ships two plugins from one tree: `studious` at the root and `jig` under
`plugins/jig/`. Both manifests are validated, so a manifest defect in either one fails
CI the same way.

Standard library only. Cross-check against the official Claude Code plugin manifest
schema if one is published; until then this local check stands.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
NAME = re.compile(r"^[a-z0-9-]+$")
REQUIRED = ("name", "description", "version", "author", "repository", "license", "keywords")


def manifests() -> list[Path]:
    """Every plugin manifest this repo ships, root first then plugins/*/ in name order."""
    found = [REPO / ".claude-plugin" / "plugin.json"]
    found.extend(sorted((REPO / "plugins").glob("*/.claude-plugin/plugin.json")))
    return [p for p in found if p.is_file()]


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED:
        if key not in data:
            errors.append(f"missing required field: {key}")

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

    errors.extend(validate_dependencies(data.get("dependencies")))

    return errors


def validate_dependencies(deps: object) -> list[str]:
    """A `dependencies` entry is a bare plugin name or {name, version?, marketplace?}."""
    if deps is None:
        return []
    if not isinstance(deps, list):
        return ["dependencies must be an array"]

    errors: list[str] = []
    for i, dep in enumerate(deps):
        if isinstance(dep, str):
            if not NAME.match(dep):
                errors.append(f"dependencies[{i}] '{dep}' must match ^[a-z0-9-]+$")
        elif isinstance(dep, dict):
            name = dep.get("name")
            if not isinstance(name, str) or not NAME.match(name):
                errors.append(f"dependencies[{i}].name must be a plugin name matching ^[a-z0-9-]+$")
        else:
            errors.append(f"dependencies[{i}] must be a string or an object with a name")
    return errors


def main() -> int:
    found = manifests()
    if not found:
        print("No plugin manifests found.")
        return 1

    failed = False
    for path in found:
        rel = path.relative_to(REPO)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"{rel} could not be read/parsed: {exc}")
            failed = True
            continue
        errors = validate(data)
        if errors:
            print(f"{rel} validation FAILED:")
            for e in errors:
                print(f"  - {e}")
            failed = True
        else:
            print(f"{rel} valid ({data.get('name')} v{data.get('version')}).")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
