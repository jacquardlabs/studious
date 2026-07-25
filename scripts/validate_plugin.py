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
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
NAME = re.compile(r"^[a-z0-9-]+$")
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


def main() -> int:
    try:
        data = json.loads(PLUGIN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"plugin.json could not be read/parsed: {exc}")
        return 1
    errors = validate(data)
    if errors:
        print("Plugin manifest validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("Plugin manifest valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
