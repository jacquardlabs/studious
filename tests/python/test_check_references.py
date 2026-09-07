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
    # code-auditor's <language> placeholder can't exist literally, so the
    # containing directory is validated instead.
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
    """`viva` ships in its own plugin, so `skills/viva/` never exists here. The
    exemption derives from the manifest's `dependencies` list rather than a
    hardcoded name, so adding or dropping a dependency is what makes a
    citation valid or broken."""
    import check_gate_independence  # noqa: F401  (proves scripts/ is importable)
    from check_references import EXTERNAL_SKILLS, _declared_dependencies

    declared = _declared_dependencies()
    assert declared, ".claude-plugin/plugin.json declares no dependencies to derive from"
    assert declared <= EXTERNAL_SKILLS
    assert "web-design-guidelines" in EXTERNAL_SKILLS


def test_a_declared_dependencys_agent_is_not_a_broken_reference(tmp_path: Path) -> None:
    """#334: judge lanes dispatch `gauntlet:<judge>`, which ships in gauntlet's
    plugin, so `agents/<judge>.md` never exists here. Same manifest-derived
    exemption as the skill case — the namespace must be a declared dependency."""
    from check_references import EXTERNAL_PLUGINS

    assert "gauntlet" in EXTERNAL_PLUGINS
    _write(
        tmp_path / "commands" / "review.md",
        "dispatch `gauntlet:security-auditor` (@agent-gauntlet:security-auditor); "
        "never @agent-nonexistent",
    )
    errors = find_broken(tmp_path)
    assert len(errors) == 1
    assert "agents/nonexistent.md missing" in errors[0]


def test_an_undeclared_plugins_agent_is_still_broken(tmp_path: Path) -> None:
    _write(tmp_path / "commands" / "review.md", "dispatch @agent-not-a-dependency:security-auditor")
    errors = find_broken(tmp_path)
    assert len(errors) == 1
    assert "not-a-dependency is not a declared dependency" in errors[0]


def test_every_namespaced_judge_health_dispatches_is_a_declared_dependency() -> None:
    """`/health` dispatches `gauntlet:<judge>` subagents that ship in another plugin.
    A `subagent_type` prefix the manifest does not declare is a lane that fails at
    dispatch on a fresh install, and `check_references.py` cannot see it (its regexes
    match the `@agent-` form only). Derived from the area table and the manifest, so
    the assertion moves with both."""
    import re

    from check_references import REPO, _declared_dependencies

    table_cells = re.findall(r"\| `([a-z0-9-]+):([a-z0-9-]+)` \|", (REPO / "commands" / "health.md").read_text(encoding="utf-8"))
    assert table_cells, "commands/health.md's area table names no namespaced judge"
    allowed = {"studious"} | _declared_dependencies()
    undeclared = sorted({prefix for prefix, _ in table_cells} - allowed)
    assert not undeclared, f"/health dispatches {undeclared} but plugin.json does not declare them"


def test_an_undeclared_external_skill_is_still_broken(tmp_path: Path) -> None:
    """The exemption is scoped to declared dependencies — a typo or an undeclared
    plugin's skill must still fail."""
    _write(tmp_path / "commands" / "x.md", "the `not-a-dependency` skill handles it")
    errors = find_broken(tmp_path)
    assert any("skills/not-a-dependency/ missing" in e for e in errors)


# The guard forbids a literal `docs/design/<file>.md` in any durable file, including
# this one — so fixtures assemble the path at runtime to avoid tripping it while still
# testing the exact string, keeping the invariant absolute with no self-exemption list
# (#233).
_DIR = "docs/design/"


def _cite(name: str) -> str:
    return _DIR + name


def test_a_durable_file_may_not_cite_a_specific_design_doc(tmp_path: Path) -> None:
    """#233: 33 citations pointed at design docs deleted at closeout (#219) —
    each read as load-bearing rationale that resolved to nothing."""
    from check_references import find_disposable_citations

    _write(tmp_path / "scripts" / "verify", f"per {_cite('build-scripts.md')}, step 2")
    errors = find_disposable_citations(tmp_path)
    assert len(errors) == 1
    assert "build-scripts.md" in errors[0]
    assert "#233" in errors[0]


def test_the_design_doc_directory_itself_is_not_a_citation(tmp_path: Path) -> None:
    """The bare directory and `<slug>` placeholder are the producer's output
    path, named legitimately by /shape, /build, /next, and gate-design-review —
    only a concrete filename can dangle."""
    from check_references import find_disposable_citations

    _write(tmp_path / "skills" / "shape" / "SKILL.md", f"Written to `{_DIR}<slug>.md`")
    _write(tmp_path / "commands" / "next.md", f"discover a candidate under {_DIR}")
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
