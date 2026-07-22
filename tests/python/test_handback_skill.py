"""Structural regression tests for the handback-skill story (issue #97).

`commands/handback.md` and `skills/handback/SKILL.md` are prose, not executable code
— there is no script backing the manifest assembly for a live model to run, so
`bin/gate-ledger evidence-list` (locked by `tests/test_gate_ledger.sh`) is the only
mechanical surface. These tests instead lock the prompt's structural commitments
that the design doc's pre-mortem register
(`docs/studious/premortems/2026-07-10-handback-skill-design.md`) named as concrete
audit-time detection hints:

- item 1: the branch-slug/anchoring reuse (`evidence-list`, never a re-derived slug).
- item 2: only the pinned fields land in the manifest; a missing digest renders a
  placeholder, never a raw-output fallback (the schema has no raw-output field to
  fall back to in the first place, but the command must not invent one).
- item 3: an explicit regeneration notice, since overwrite-on-rerun is the design's
  chosen policy (not a preserve/merge rule).
- item 4: the no-log message must distinguish "never armed" from "armed but empty."
- item 5: a provenance banner separating worker-authored output from gate verdicts.
- item 7: no split naming — `/handback` everywhere, never `work-handback`.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDBACK_COMMAND = REPO_ROOT / "commands" / "handback.md"
HANDBACK_SKILL = REPO_ROOT / "skills" / "handback" / "SKILL.md"
GATE_LEDGER = REPO_ROOT / "bin" / "gate-ledger"
GATE_VOCABULARY = REPO_ROOT / "reference" / "gate-vocabulary.md"
EVIDENCE_FORMAT = REPO_ROOT / "reference" / "evidence-format.md"


def _command_text() -> str:
    return HANDBACK_COMMAND.read_text()


def _skill_text() -> str:
    return HANDBACK_SKILL.read_text()


# --- files exist, frontmatter is well-formed ---


def test_command_file_exists() -> None:
    assert HANDBACK_COMMAND.is_file(), "commands/handback.md is missing"


def test_skill_dir_exists() -> None:
    assert HANDBACK_SKILL.is_file(), "skills/handback/SKILL.md is missing"


def test_command_frontmatter_has_required_fields() -> None:
    text = _command_text()
    assert text.startswith("---\n"), "handback.md must open with YAML frontmatter"
    frontmatter = text.split("---", 2)[1]
    assert "description:" in frontmatter
    assert "argument-hint:" in frontmatter
    assert "allowed-tools:" in frontmatter
    # Write is required: this command commits a file, unlike a pure-report command.
    assert "Write" in frontmatter, "handback.md must declare the Write tool"


def test_skill_frontmatter_has_name_and_description() -> None:
    text = _skill_text()
    assert text.startswith("---\n")
    frontmatter = text.split("---", 2)[1]
    assert "name: handback" in frontmatter
    assert "description:" in frontmatter


def test_skill_description_has_conservative_negative_scope() -> None:
    """CONTRIBUTING.md: skill descriptions list what they should NOT match."""
    text = _skill_text()
    assert "Do NOT use for" in text


# --- naming: no split spelling (pre-mortem item 7) ---


def test_no_work_handback_spelling_in_command() -> None:
    assert "work-handback" not in _command_text()


def test_no_work_handback_spelling_in_skill() -> None:
    assert "work-handback" not in _skill_text()


def test_skill_delegates_to_the_bare_command_name() -> None:
    assert "/handback" in _skill_text()


# --- reuse over re-derivation: evidence-list, not a hand-rolled reader (item 1, 6) ---


def test_command_reads_via_evidence_list_verb() -> None:
    text = _command_text()
    assert "gate-ledger evidence-list" in text


def test_command_forbids_reading_the_raw_jsonl_directly() -> None:
    text = _command_text()
    assert "Never read" in text and ".studious/evidence/*.jsonl" in text


def test_command_derives_slug_the_same_way_gate_ledger_does() -> None:
    """The slug derivation shown must be the same rule bin/gate-ledger's own
    branch_slug() performs (every '/' -> '-', nothing else), not a
    re-implementation that could diverge on an edge case."""
    text = _command_text()
    assert "tr '/' '-'" in text
    assert "branch_slug()" in text
    # bin/gate-ledger's own implementation, sanity-checked for the doc's claim:
    # both replace every '/' with '-' and nothing else.
    ledger_src = GATE_LEDGER.read_text()
    match = re.search(r'branch_slug\(\).*?\n', ledger_src)
    assert match is not None, "branch_slug() definition not found in bin/gate-ledger"
    assert "//" in match.group(0) and "/-" in match.group(0), (
        "branch_slug() no longer looks like a global '/' -> '-' substitution — "
        "commands/handback.md's tr-based restatement needs to be re-checked against it"
    )


# --- manifest content boundary: pinned fields only, digest placeholder (item 2) ---


def test_manifest_columns_match_the_pinned_evidence_fields() -> None:
    text = _command_text()
    for field in ("capturedAt", "command", "predicate.result", "origin", "outputDigest"):
        assert field in text, f"manifest column source field {field!r} not named"


def test_manifest_never_falls_back_to_raw_output() -> None:
    text = _command_text()
    assert "raw stdout/stderr" in text
    assert "never fall back" in text.lower() or "never fall back" in text


def test_missing_digest_renders_a_placeholder_not_blank() -> None:
    text = _command_text()
    assert "_(no digest captured)_" in text


def test_manifest_jq_pipeline_is_present_and_escapes_pipes() -> None:
    """The jq transform embedded in the command is the one hand-verified against
    a live evidence log while building this story (pipe-escaped commands,
    digest placeholder) — lock its presence so a future edit can't silently
    drop the escaping and reintroduce a broken table row."""
    text = _command_text()
    assert 'gsub("\\\\|"; "\\\\|")' in text or "gsub(\"\\\\|\"" in text
    assert "no digest captured" in text


# --- single-read manifest assembly: one evidence-list call, four derivations reuse it ---
# (perf-audit-followups epic, issue #161: four re-reads of an append-only, ever-growing
# evidence log collapsed to one captured value; see commands/handback.md step 4)


def _step_four_text() -> str:
    text = _command_text()
    return text[text.index("## 4."): text.index("## 5.")]


def test_step_four_invokes_evidence_list_exactly_once() -> None:
    step_four = _step_four_text()
    assert step_four.count('gate-ledger evidence-list --branch "$branch"') == 1, (
        "step 4 must capture the evidence log with a single gate-ledger evidence-list "
        "call, not re-invoke it once per derivation"
    )


def test_step_four_captures_evidence_log_into_a_variable() -> None:
    step_four = _step_four_text()
    assert 'evidence_log=$(gate-ledger evidence-list --branch "$branch")' in step_four


def test_all_four_derivations_reuse_the_captured_evidence_log() -> None:
    """Manifest rows, total, passed, and failed counts must all read from
    $evidence_log rather than re-invoking gate-ledger evidence-list."""
    step_four = _step_four_text()
    assert step_four.count('printf \'%s\\n\' "$evidence_log"') == 4, (
        "expected exactly four derivations (manifest rows, total, passed, failed) "
        "to read from the single captured $evidence_log"
    )


# --- no-log messaging distinguishes armed-empty from never-armed (item 4) ---


def test_no_log_messages_distinguish_armed_from_unarmed() -> None:
    text = _command_text()
    assert "No work file is armed for" in text
    assert "No evidence log found for" in text
    # The two messages must actually differ in wording, not just casing/whitespace.
    unarmed = text[text.index("No work file is armed for"):][:200]
    armed_empty = text[text.index("No evidence log found for"):][:200]
    assert unarmed != armed_empty


def test_no_log_path_writes_and_commits_nothing() -> None:
    text = _command_text()
    section = text[text.index("## 3."): text.index("## 4.")]
    assert "write nothing, commit nothing" in section.lower()


# --- provenance banner (item 5) ---


def test_output_file_carries_a_provenance_banner() -> None:
    text = _command_text()
    assert "not a Studious gate verdict" in text


# --- regeneration notice (item 3) ---


def test_regeneration_is_explicitly_noted_not_silent() -> None:
    text = _command_text()
    assert "regenerat" in text.lower()
    assert "git history" in text.lower() or "git log --" in text


# --- not a gate: no verdict vocabulary added ---


def test_handback_adds_no_gate_vocabulary_entry() -> None:
    vocab = GATE_VOCABULARY.read_text()
    assert "handback" not in vocab.lower()


def test_command_states_it_is_not_a_gate() -> None:
    text = _command_text()
    assert "not a gate" in text.lower()


# --- evidence-format.md documents the new read verb (consumers-must-stay-in-sync) ---


def test_evidence_format_documents_evidence_list() -> None:
    text = EVIDENCE_FORMAT.read_text()
    assert "evidence-list" in text
    assert "commands/handback.md" in text


# --- gate-ledger: the verb this command depends on actually exists ---


def test_gate_ledger_wires_evidence_list_verb() -> None:
    src = GATE_LEDGER.read_text()
    assert re.search(r"evidence-list\)\s+shift;\s+cmd_evidence_list", src)
    assert "cmd_evidence_list()" in src
