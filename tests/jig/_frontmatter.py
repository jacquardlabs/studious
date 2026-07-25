"""Shared SKILL.md frontmatter-parsing helper.

`test_scaffold.py` (the five user-invoked skill stubs) and
`test_discipline_skill.py` (the model-invoked task-execution-discipline
skill) each need to pull the `--- ... ---` YAML block out of a SKILL.md
file. Previously each test module defined its own copy of the same regex;
this module is the one place it lives now.

Not itself a test module — nothing here is collected by
`unittest discover`.
"""
from __future__ import annotations

import re

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
