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


def test_a_declared_dependencys_skill_is_not_a_broken_reference() -> None:
    """`viva` ships in its own plugin, so `skills/viva/` will never exist here — but
    `/design`, `/plan`, and `/studious-doctor`'s tooling check all name it, and the
    manifest declares the dependency. Deriving the exemption from `dependencies`
    rather than hardcoding it means declaring a dependency is the one action that
    makes its skill citable, and dropping one immediately makes citations broken
    again."""
    import check_gate_independence  # noqa: F401  (proves scripts/ is importable)
    from check_references import EXTERNAL_SKILLS, _declared_dependencies

    declared = _declared_dependencies()
    assert declared, ".claude-plugin/plugin.json declares no dependencies to derive from"
    assert declared <= EXTERNAL_SKILLS
    assert "web-design-guidelines" in EXTERNAL_SKILLS


def test_an_undeclared_external_skill_is_still_broken(tmp_path: Path) -> None:
    """The exemption is scoped to declared dependencies — a typo or an undeclared
    plugin's skill must still fail."""
    _write(tmp_path / "commands" / "x.md", "the `not-a-dependency` skill handles it")
    errors = find_broken(tmp_path)
    assert any("skills/not-a-dependency/ missing" in e for e in errors)


# The guard forbids a literal `docs/design/<file>.md` in any durable file — and this
# file is one. The fixtures below therefore assemble the path at runtime: the regex
# needs the filename immediately after the slash, so a concatenation never matches in
# source while still producing the exact string under test. That keeps the invariant
# absolute, with no self-exemption list to go stale (#233).
_DIR = "docs/design/"


def _cite(name: str) -> str:
    return _DIR + name


def test_a_durable_file_may_not_cite_a_specific_design_doc(tmp_path: Path) -> None:
    """#233: 33 citations accumulated pointing at design docs that are deleted at
    closeout by the rule ratified in #219. Each read as load-bearing rationale, so a
    reader following one found nothing and could not tell whether the claim was ever
    true."""
    from check_references import find_disposable_citations

    _write(tmp_path / "scripts" / "verify", f"per {_cite('build-scripts.md')}, step 2")
    errors = find_disposable_citations(tmp_path)
    assert len(errors) == 1
    assert "build-scripts.md" in errors[0]
    assert "#233" in errors[0]


def test_the_design_doc_directory_itself_is_not_a_citation(tmp_path: Path) -> None:
    """The bare directory and the `<slug>` placeholder are the producer's output
    path, named legitimately by /design, /plan, /coach, and gate-design-review. Only
    a concrete filename is a pointer that can dangle."""
    from check_references import find_disposable_citations

    _write(tmp_path / "skills" / "design" / "SKILL.md", f"Written to `{_DIR}<slug>.md`")
    _write(tmp_path / "commands" / "work-on.md", f"discover a candidate under {_DIR}")
    assert find_disposable_citations(tmp_path) == []


def test_the_guard_covers_the_directories_the_old_check_missed() -> None:
    """`find_broken` scans only commands/agents/skills/reference, which is why none
    of the 33 were caught: most were in scripts/ and tests/."""
    from check_references import DURABLE_DIRS

    for missed in ("scripts", "tests", "bin", "workflows"):
        assert missed in DURABLE_DIRS


def test_the_guard_reads_non_markdown_files(tmp_path: Path) -> None:
    """Most of the 33 were in Python and in extensionless script files, not .md —
    the old check only ever globbed `*.md`."""
    from check_references import find_disposable_citations

    _write(tmp_path / "scripts" / "_gitutil.py", f"# per {_cite('build-scripts.md')}")
    _write(tmp_path / "tests" / "jig" / "test_x.py", f"# {_cite('plan-lint.md')} says")
    assert len(find_disposable_citations(tmp_path)) == 2
