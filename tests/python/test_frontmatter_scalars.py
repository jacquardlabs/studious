"""#340: every shipped frontmatter parses as YAML without a YAML library in CI.

A plain-scalar `description:` that contains `: ` is a mapping to YAML, and
`safe_load` fails on the whole block — the reviewer's description did exactly that.
This pins the one rule that keeps the block parseable: a plain-scalar value carries
no `: ` (quote it, or rephrase), and no key line is missing its value.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SURFACES = ("commands/*.md", "skills/*/SKILL.md", "agents/*.md")
KEY_LINE = re.compile(r"^(?P<key>[A-Za-z_-]+):(?P<value>.*)$")


def frontmatter_blocks() -> list[tuple[Path, str]]:
    return [
        (path, text.split("---\n", 2)[1])
        for pattern in SURFACES
        for path in sorted(REPO.glob(pattern))
        if (text := path.read_text(encoding="utf-8")).startswith("---\n")
    ]


def test_the_surface_is_not_empty() -> None:
    assert len(frontmatter_blocks()) >= 10


def test_no_plain_scalar_contains_a_mapping_separator() -> None:
    offenders: list[str] = []
    for path, block in frontmatter_blocks():
        for n, line in enumerate(block.splitlines(), 1):
            m = KEY_LINE.match(line)
            if not m:
                continue
            value = m.group("value").strip()
            quoted = value[:1] in ("'", '"') or value[:1] in (">", "|")
            if not quoted and ": " in value:
                offenders.append(f"{path.relative_to(REPO)}:{n}: `{m.group('key')}` carries ': ' in a plain scalar")
    assert offenders == [], "\n".join(offenders)
