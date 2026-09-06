"""Every input to a CI job is pinned to an immutable identity (issue #201).

`release.yml` ran `pip install python-semantic-release` unpinned, and its actions used
mutable `@v4`/`@v5` tags, inside the one job holding `RELEASE_TOKEN` (contents:write
plus cross-repo dispatch to jacquardlabs/marketplace) — flagged Important in the
2026-07-17 `/retro`. Asserted repo-wide, not just for that file, so a new workflow or
job inherits the check.

Text-based, not YAML-parsed: the `python-checks` CI job has no PyYAML, and a trailing
`# v1.2.3` comment is invisible to a YAML parser anyway.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

#: The privileged job's dependency set: exact versions plus hashes for the full closure.
RELEASE_REQUIREMENTS = WORKFLOW_DIR / "release-requirements.txt"

#: Its source: the one version a human bumps; the .txt closure is machine-derived from
#: it, so the two can disagree if the .txt isn't regenerated.
RELEASE_REQUIREMENTS_IN = WORKFLOW_DIR / "release-requirements.in"

#: `owner/repo@ref` with an optional `# comment`. Local (`./path`) and container
#: (`docker://`) uses carry no SHA and are excluded by the leading-segment class.
USES_RE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*(?P<action>[\w.-]+/[\w.-]+(?:/[\w./-]+)?)@(?P<ref>\S+)"
    r"(?:\s*#\s*(?P<comment>.*?))?\s*$"
)

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

#: A `--hash=` bearing requirement line: `name==version \` opening a hash block.
PINNED_REQUIREMENT_RE = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)==(?P<version>[^\s\\;]+)")


def workflow_files() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))


def action_uses() -> list[tuple[Path, int, str, str, str | None]]:
    """Every remote `uses:` in `.github/workflows/`, as (file, lineno, action, ref, comment)."""
    return [
        (path, lineno, m["action"], m["ref"], m["comment"])
        for path in workflow_files()
        for lineno, line in enumerate(path.read_text().splitlines(), start=1)
        if (m := USES_RE.match(line))
    ]


def requirement_blocks() -> list[tuple[str, str, list[str]]]:
    """`release-requirements.txt` as (name, version, hashes) triples."""
    blocks: list[tuple[str, str, list[str]]] = []
    for line in RELEASE_REQUIREMENTS.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if hash_match := re.search(r"--hash=(sha256:[0-9a-f]{64})", stripped):
            if blocks:
                blocks[-1][2].append(hash_match[1])
            continue
        if m := PINNED_REQUIREMENT_RE.match(stripped):
            blocks.append((m["name"].lower().replace("_", "-"), m["version"], []))
    return blocks


def test_workflow_dir_is_not_empty() -> None:
    """Guards every assertion below: a bad glob would make them all vacuously pass."""
    assert workflow_files(), f"no workflows found under {WORKFLOW_DIR}"
    assert action_uses(), "no `uses:` lines found — the parse regex has drifted"


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    """A mutable tag is a standing invitation to whoever can move it."""
    floating = [
        f"{path.name}:{lineno} {action}@{ref}"
        for path, lineno, action, ref, _ in action_uses()
        if not SHA_RE.match(ref)
    ]
    assert not floating, (
        "actions must pin a 40-character commit SHA, not a mutable tag:\n  "
        + "\n  ".join(floating)
    )


def test_every_action_pin_names_its_version_in_a_comment() -> None:
    """A bare SHA is unreviewable; the comment is what makes the pin auditable."""
    uncommented = [
        f"{path.name}:{lineno} {action}@{ref}"
        for path, lineno, action, ref, comment in action_uses()
        if comment is None or not re.match(r"^v\d", comment.strip())
    ]
    assert not uncommented, (
        "each action pin needs a trailing `# vX.Y.Z` comment naming the release:\n  "
        + "\n  ".join(uncommented)
    )


def test_release_job_installs_python_semantic_release_with_hash_verification() -> None:
    """The unpinned install this issue was opened for (release.yml:27) must not return."""
    release = (WORKFLOW_DIR / "release.yml").read_text()
    unpinned = re.search(
        r"pip install\s+(?![^\n]*(?:--require-hashes|-r\s))[^\n]*python-semantic-release",
        release,
    )
    assert not unpinned, (
        "release.yml installs python-semantic-release without hash verification: "
        f"{unpinned.group(0) if unpinned else ''}"
    )
    assert "--require-hashes" in release, (
        "release.yml must install with --require-hashes so a compromised registry "
        "cannot substitute a package"
    )
    assert RELEASE_REQUIREMENTS.name in release, (
        f"release.yml must install from {RELEASE_REQUIREMENTS.name}"
    )


def test_release_requirements_pin_the_full_closure_with_hashes() -> None:
    """`--require-hashes` is only as strong as the weakest line in the file it reads."""
    assert RELEASE_REQUIREMENTS.is_file(), f"{RELEASE_REQUIREMENTS} is missing"
    blocks = requirement_blocks()
    assert len(blocks) > 1, (
        "expected python-semantic-release and its transitive dependencies, "
        f"found {len(blocks)}"
    )
    unhashed = [f"{name}=={version}" for name, version, hashes in blocks if not hashes]
    assert not unhashed, (
        "every pinned requirement needs at least one --hash; pip rejects the whole "
        "file otherwise:\n  " + "\n  ".join(unhashed)
    )
    pinned = {name: version for name, version, _ in blocks}
    assert "python-semantic-release" in pinned, (
        f"python-semantic-release is not pinned in {RELEASE_REQUIREMENTS.name}"
    )


def test_the_compiled_closure_matches_its_source_pin() -> None:
    """Bumping `.in` without regenerating `.txt` leaves a green build on the old
    version: the stale hashes still satisfy `--require-hashes`, so nothing else
    catches it."""
    declared = {
        m["name"].lower().replace("_", "-"): m["version"]
        for line in RELEASE_REQUIREMENTS_IN.read_text().splitlines()
        if not (stripped := line.strip()).startswith("#")
        and (m := PINNED_REQUIREMENT_RE.match(stripped))
    }
    assert declared, f"{RELEASE_REQUIREMENTS_IN.name} pins nothing"
    compiled = {name: version for name, version, _ in requirement_blocks()}
    stale = [
        f"{name}: .in wants {want}, .txt has {compiled.get(name, '<absent>')}"
        for name, want in declared.items()
        if compiled.get(name) != want
    ]
    assert not stale, (
        f"{RELEASE_REQUIREMENTS.name} was not regenerated after "
        f"{RELEASE_REQUIREMENTS_IN.name} changed:\n  " + "\n  ".join(stale)
    )


def test_release_requirements_record_how_to_regenerate_themselves() -> None:
    """A lockfile nobody can rebuild is a pin that silently rots (ci.yml's convention)."""
    header = RELEASE_REQUIREMENTS.read_text()
    assert "uv pip compile" in header, (
        f"{RELEASE_REQUIREMENTS.name} must carry the command that regenerates it"
    )
    assert "--generate-hashes" in header, (
        f"{RELEASE_REQUIREMENTS.name}'s regeneration command must include "
        "--generate-hashes, or a rebuild drops the hashes"
    )
    assert RELEASE_REQUIREMENTS_IN.name in header, (
        f"{RELEASE_REQUIREMENTS.name}'s regeneration command must name "
        f"{RELEASE_REQUIREMENTS_IN.name} as its input, or the two files have no "
        "recorded relationship"
    )
