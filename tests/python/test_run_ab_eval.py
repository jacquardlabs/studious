import json
from pathlib import Path

import pytest
from run_ab_eval import (
    Arm,
    ArmError,
    PlantedDefect,
    arm_overrides,
    build_shadow_root,
    classify_defect,
    load_arms,
    load_planted,
    render_report,
    rewrite_model_pin,
    score_trial,
    summarize,
    summarize_verdicts,
)

AGENT = """\
---
name: doc-auditor
description: Documentation coverage analyzer.
tools: Read, Grep
model: inherit
effort: low
---

# Doc auditor

Pick a `model:` for a new agent by stakes — this line is prose, not a pin.
"""

REPORT_REPORTED = """\
### Summary
security-auditor: 1 critical, fail

### Critical findings (blocks merge)
- `app/admin.py:14` (security) — `is_admin` is computed and logged but never
  gates the delete; any caller can remove any account.

### Important findings (should fix)
None.

### Verdict
**FIX AND RE-REVIEW** — Critical findings listed.
"""

REPORT_UNDER_TIERED = """\
### Critical findings (blocks merge)
None.

### Important findings (should fix)
- `app/admin.py:14` (security) — `is_admin` is computed but not enforced.

### Verdict
**PASS** — No critical findings.
"""

REPORT_DEMOTED = """\
### Critical findings (blocks merge)
None.

### Important findings (should fix)
None.

### Residual
Verified clean. Noted but not filed: `app/admin.py` computes `is_admin` without
using it; could not confirm reachability, so this is left as an observation.

### Verdict
**PASS** — No critical findings.
"""

REPORT_MISSED = """\
### Critical findings (blocks merge)
None.

### Important findings (should fix)
- `app/dates.py` (code quality) — naming nit.

### Verdict
**PASS** — No critical findings.
"""

AUTHZ = PlantedDefect(
    id="authz-bypass",
    floor="critical",
    locator="app/admin.py",
    signals=("is_admin", "authorization"),
)


# --- classification -------------------------------------------------------


def test_classify_reported_at_floor_tier() -> None:
    assert classify_defect(REPORT_REPORTED, AUTHZ) == "REPORTED"


def test_classify_under_tiered_when_filed_below_floor() -> None:
    assert classify_defect(REPORT_UNDER_TIERED, AUTHZ) == "UNDER_TIERED"


def test_classify_demoted_when_present_but_not_filed() -> None:
    # The suppression case this harness exists to separate from MISSED: the
    # auditor saw it and wrote it into prose instead of filing it.
    assert classify_defect(REPORT_DEMOTED, AUTHZ) == "DEMOTED"


def test_classify_missed_when_absent() -> None:
    assert classify_defect(REPORT_MISSED, AUTHZ) == "MISSED"


def test_classify_locator_without_signal_is_not_a_report() -> None:
    # A Summary line naming every file touched must not score as a finding.
    text = "### Summary\ncode-auditor reviewed `app/admin.py`, 0 findings, pass\n"
    assert classify_defect(text, AUTHZ) == "MISSED"


def test_classify_signal_without_locator_is_not_a_report() -> None:
    text = "### Critical findings (blocks merge)\n- `app/billing.py` — authorization gap.\n"
    assert classify_defect(text, AUTHZ) == "MISSED"


def test_classify_important_floor_reported_at_critical() -> None:
    defect = PlantedDefect(
        id="missing-regression-test",
        floor="important",
        locator="app/pricing.py",
        signals=("regression test",),
    )
    text = (
        "### Critical findings (blocks merge)\n"
        "- `app/pricing.py` — bug fix ships with no regression test.\n"
    )
    assert classify_defect(text, defect) == "REPORTED"


# --- model pin rewriting --------------------------------------------------


def test_rewrite_model_pin_replaces_frontmatter_value() -> None:
    rewritten = rewrite_model_pin(AGENT, "haiku")
    assert "model: haiku\n" in rewritten
    assert "model: inherit" not in rewritten.split("---")[1]


def test_rewrite_model_pin_leaves_body_prose_alone() -> None:
    rewritten = rewrite_model_pin(AGENT, "haiku")
    assert "Pick a `model:` for a new agent by stakes" in rewritten


def test_rewrite_model_pin_preserves_other_frontmatter() -> None:
    rewritten = rewrite_model_pin(AGENT, "haiku")
    assert "effort: low" in rewritten
    assert "name: doc-auditor" in rewritten


def test_rewrite_model_pin_without_frontmatter_raises() -> None:
    with pytest.raises(ArmError, match="frontmatter"):
        rewrite_model_pin("# Just a heading\n", "haiku")


def test_rewrite_model_pin_without_pin_raises() -> None:
    # A silent no-op here would score an unapplied arm as a real result.
    with pytest.raises(ArmError, match="no `model:` pin"):
        rewrite_model_pin("---\nname: x\n---\n\nbody\n", "haiku")


# --- shadow root ----------------------------------------------------------


@pytest.fixture
def source_root(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    (root / "reference").mkdir(parents=True)
    (root / "agents").mkdir()
    (root / "reference" / "prompt-contract.md").write_text("baseline contract\n")
    (root / "reference" / "security-checklist.md").write_text("checklist\n")
    (root / "agents" / "doc-auditor.md").write_text(AGENT)
    (root / "CLAUDE.md").write_text("root doc\n")
    return root


def test_shadow_root_materializes_the_override(tmp_path: Path, source_root: Path) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("variant contract\n")
    shadow = build_shadow_root(
        tmp_path / "shadow", {"reference/prompt-contract.md": variant}, source_root
    )
    target = shadow / "reference" / "prompt-contract.md"
    assert not target.is_symlink()
    assert target.read_text() == "variant contract\n"


def test_shadow_root_symlinks_the_overrides_siblings(tmp_path: Path, source_root: Path) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("variant contract\n")
    shadow = build_shadow_root(
        tmp_path / "shadow", {"reference/prompt-contract.md": variant}, source_root
    )
    sibling = shadow / "reference" / "security-checklist.md"
    assert sibling.is_symlink()
    assert sibling.read_text() == "checklist\n"


def test_shadow_root_symlinks_untouched_top_level_entries(
    tmp_path: Path, source_root: Path
) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("variant contract\n")
    shadow = build_shadow_root(
        tmp_path / "shadow", {"reference/prompt-contract.md": variant}, source_root
    )
    assert (shadow / "agents").is_symlink()
    assert (shadow / "CLAUDE.md").is_symlink()


def test_shadow_root_never_writes_through_to_source(tmp_path: Path, source_root: Path) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("variant contract\n")
    build_shadow_root(
        tmp_path / "shadow", {"reference/prompt-contract.md": variant}, source_root
    )
    original = (source_root / "reference" / "prompt-contract.md").read_text()
    assert original == "baseline contract\n"


def test_shadow_root_rejects_a_nonexistent_target(tmp_path: Path, source_root: Path) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("x\n")
    with pytest.raises(ArmError, match="does not exist"):
        build_shadow_root(tmp_path / "shadow", {"reference/nope.md": variant}, source_root)


def test_arm_overrides_rewrites_the_named_agent(tmp_path: Path, source_root: Path) -> None:
    arm = Arm(name="doc-haiku", models={"doc-auditor": "haiku"})
    overrides = arm_overrides(arm, tmp_path / "staging", source_root)
    assert "model: haiku" in overrides["agents/doc-auditor.md"].read_text()


def test_arm_overrides_rejects_an_unknown_agent(tmp_path: Path, source_root: Path) -> None:
    arm = Arm(name="typo", models={"doc-auditer": "haiku"})
    with pytest.raises(ArmError, match="no such agent"):
        arm_overrides(arm, tmp_path / "staging", source_root)


# --- arms config ----------------------------------------------------------


def test_load_arms_reads_baseline_and_variant(tmp_path: Path) -> None:
    variant = tmp_path / "variant.md"
    variant.write_text("v\n")
    config = tmp_path / "arms.json"
    config.write_text(
        json.dumps(
            [
                {"name": "baseline"},
                {"name": "variant", "contract": {"reference/prompt-contract.md": "variant.md"}},
            ]
        )
    )
    arms = load_arms(config)
    assert [a.name for a in arms] == ["baseline", "variant"]
    assert arms[0].is_baseline
    assert not arms[1].is_baseline


def test_load_arms_rejects_duplicate_names(tmp_path: Path) -> None:
    config = tmp_path / "arms.json"
    config.write_text(json.dumps([{"name": "a"}, {"name": "a"}]))
    with pytest.raises(ArmError, match="duplicate arm name"):
        load_arms(config)


def test_load_arms_rejects_a_missing_variant_file(tmp_path: Path) -> None:
    config = tmp_path / "arms.json"
    config.write_text(
        json.dumps([{"name": "v", "contract": {"reference/prompt-contract.md": "gone.md"}}])
    )
    with pytest.raises(ArmError, match="not found"):
        load_arms(config)


def test_load_arms_rejects_an_empty_array(tmp_path: Path) -> None:
    config = tmp_path / "arms.json"
    config.write_text("[]")
    with pytest.raises(ArmError, match="non-empty"):
        load_arms(config)


# --- ground truth ---------------------------------------------------------


def test_planted_defect_rejects_an_unknown_floor() -> None:
    with pytest.raises(ArmError, match="floor"):
        PlantedDefect.from_dict(
            {"id": "x", "floor": "blocker", "locator": "a.py", "signals": ["s"]}
        )


def test_planted_defect_requires_a_signal() -> None:
    with pytest.raises(ArmError, match="signal"):
        PlantedDefect.from_dict({"id": "x", "floor": "critical", "locator": "a.py"})


def test_load_planted_treats_a_missing_key_as_a_control_fixture(tmp_path: Path) -> None:
    fixture = tmp_path / "clean"
    fixture.mkdir()
    (fixture / "expected.json").write_text(json.dumps({"verdict_any_of": ["PASS"]}))
    assert load_planted(fixture) == []


def test_every_checked_in_fixture_declares_usable_ground_truth() -> None:
    # Guards the two files against drifting apart: a fixture whose expected.json
    # promises findings but plants nothing cannot be scored by an arm, and reads
    # as a well-behaved flat metric rather than a broken one.
    from run_gate_audit_fixtures import discover_fixtures

    for fixture in discover_fixtures():
        expected = json.loads((fixture / "expected.json").read_text())
        planted = load_planted(fixture)
        if expected.get("min_critical_findings", 0) > 0:
            assert any(d.floor == "critical" for d in planted), (
                f"{fixture.name}: expects a critical finding but plants no critical defect"
            )
        if expected.get("min_important_findings", 0) > 0:
            assert planted, (
                f"{fixture.name}: expects an important finding but plants no defect"
            )


# --- aggregation ----------------------------------------------------------


def test_summarize_tallies_outcomes_per_arm() -> None:
    results = [
        score_trial("baseline", "trap", 1, REPORT_REPORTED, [AUTHZ]),
        score_trial("baseline", "trap", 2, REPORT_DEMOTED, [AUTHZ]),
        score_trial("variant", "trap", 1, REPORT_REPORTED, [AUTHZ]),
        score_trial("variant", "trap", 2, REPORT_REPORTED, [AUTHZ]),
    ]
    tally = summarize(results)
    assert tally["trap", "authz-bypass", "baseline"]["REPORTED"] == 1
    assert tally["trap", "authz-bypass", "baseline"]["DEMOTED"] == 1
    assert tally["trap", "authz-bypass", "variant"]["REPORTED"] == 2


def test_summarize_verdicts_tallies_tokens_per_arm() -> None:
    results = [
        score_trial("baseline", "trap", 1, REPORT_REPORTED, [AUTHZ]),
        score_trial("baseline", "trap", 2, REPORT_DEMOTED, [AUTHZ]),
    ]
    tally = summarize_verdicts(results)
    assert tally["trap", "baseline"]["FIX AND RE-REVIEW"] == 1
    assert tally["trap", "baseline"]["PASS"] == 1


def test_render_report_shows_both_arms_and_the_noise_caveat() -> None:
    arms = [Arm(name="baseline"), Arm(name="variant")]
    results = [
        score_trial("baseline", "trap", 1, REPORT_DEMOTED, [AUTHZ]),
        score_trial("variant", "trap", 1, REPORT_REPORTED, [AUTHZ]),
    ]
    rendered = render_report(results, arms, trials=1)
    assert "DEMOTED=1" in rendered
    assert "REPORTED=1" in rendered
    assert "Counts, not conclusions" in rendered
