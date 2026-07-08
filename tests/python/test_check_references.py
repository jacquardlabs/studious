from pathlib import Path

from check_references import find_broken


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_resolves_clean(tmp_path: Path) -> None:
    _write(tmp_path / "agents" / "security-auditor.md", "x")
    _write(tmp_path / "commands" / "gate.md", "Use @agent-security-auditor here")
    assert find_broken(tmp_path) == []


def test_flags_dangling_agent(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "Use @agent-ghost here")
    errors = find_broken(tmp_path)
    assert len(errors) == 1
    assert "agents/ghost.md missing" in errors[0]


def test_allows_external_skill(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "invoke the `web-design-guidelines` skill")
    assert find_broken(tmp_path) == []


def test_flags_missing_internal_skill(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "invoke the `ghost-skill` skill")
    errors = find_broken(tmp_path)
    assert any("skills/ghost-skill/ missing" in e for e in errors)


def test_passes_when_internal_skill_exists(tmp_path: Path) -> None:
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)
    _write(tmp_path / "commands" / "gate.md", "invoke the `real-skill` skill")
    assert find_broken(tmp_path) == []


def test_resolves_existing_reference_file(tmp_path: Path) -> None:
    _write(tmp_path / "reference" / "security-checklist.md", "x")
    _write(
        tmp_path / "agents" / "security-auditor.md",
        "consult `reference/security-checklist.md`",
    )
    assert find_broken(tmp_path) == []


def test_flags_missing_reference_file(tmp_path: Path) -> None:
    _write(tmp_path / "agents" / "security-auditor.md", "see `reference/ghost.md`")
    errors = find_broken(tmp_path)
    assert any("reference/ghost.md" in e for e in errors)


def test_resolves_reference_placeholder_path_via_directory(tmp_path: Path) -> None:
    # code-auditor cites a template path with a <language> placeholder; the literal
    # file can't exist, so the containing directory is what gets validated.
    _write(tmp_path / "reference" / "idioms" / "python.md", "x")
    _write(
        tmp_path / "agents" / "code-auditor.md",
        "apply `reference/idioms/<language>.md`",
    )
    assert find_broken(tmp_path) == []


def test_flags_reference_placeholder_with_missing_directory(tmp_path: Path) -> None:
    _write(
        tmp_path / "agents" / "code-auditor.md",
        "apply `reference/ghosts/<language>.md`",
    )
    errors = find_broken(tmp_path)
    assert any("reference/ghosts" in e for e in errors)


def test_resolves_skill_reference_inside_skill_md(tmp_path: Path) -> None:
    (tmp_path / "skills" / "real-skill").mkdir(parents=True)
    _write(
        tmp_path / "skills" / "shim" / "SKILL.md",
        "Invoke the `/gate-x` command, which delegates to the `real-skill` skill.",
    )
    assert find_broken(tmp_path) == []


def test_flags_broken_skill_reference_inside_skill_md(tmp_path: Path) -> None:
    _write(
        tmp_path / "skills" / "shim" / "SKILL.md",
        "This routes to the `ghost-skill` skill.",
    )
    errors = find_broken(tmp_path)
    assert any("skills/ghost-skill/ missing" in e for e in errors)


def test_recognizes_invoke_backtick_phrasing(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "invoke `ghost-skill` before continuing")
    errors = find_broken(tmp_path)
    assert any("skills/ghost-skill/ missing" in e for e in errors)


def test_recognizes_skill_name_backtick_phrasing(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "gate.md", "delegates to skill `ghost-skill`")
    errors = find_broken(tmp_path)
    assert any("skills/ghost-skill/ missing" in e for e in errors)


def test_scans_reference_dir_for_dangling_agent(tmp_path: Path) -> None:
    # A reference/ doc that cites a renamed (now-missing) agent must fail the check.
    _write(
        tmp_path / "reference" / "design-doc-contract.md",
        "dispatched to @agent-product-reviewer for the acceptance read",
    )
    errors = find_broken(tmp_path)
    assert any("agents/product-reviewer.md missing" in e for e in errors)


def test_scans_reference_dir_for_moved_sibling(tmp_path: Path) -> None:
    # A reference/ doc that cites a moved/renamed sibling reference file must fail.
    _write(
        tmp_path / "reference" / "worker-contract.md",
        "the build-side analogue of `reference/design-doc-contract.md`",
    )
    errors = find_broken(tmp_path)
    assert any("reference/design-doc-contract.md" in e for e in errors)


def test_reference_dir_siblings_resolve(tmp_path: Path) -> None:
    _write(tmp_path / "reference" / "design-doc-contract.md", "x")
    _write(tmp_path / "agents" / "product-reviewer.md", "x")
    _write(
        tmp_path / "reference" / "worker-contract.md",
        "analogue of `reference/design-doc-contract.md`; @agent-product-reviewer judges",
    )
    assert find_broken(tmp_path) == []
