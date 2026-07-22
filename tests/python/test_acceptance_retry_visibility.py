"""Regression tests for the acceptance-retry-visibility story (issue #142, Finding 2).

The design doc (`docs/superpowers/specs/2026-07-21-acceptance-retry-visibility-design.md`)
determined that no layer this repo controls (`workflows/epic-driver.js`, `bin/gate-ledger`,
the dispatched-agent prompts) has an accessible signal that a prior `agent()` dispatch was
abandoned/superseded before a retry began — so acceptance criterion 2 (a `work-log RETRY`
entry) does not ship. Instead, per criterion 3, `commands/work-through.md`'s report gained
a staleness-heuristic mitigation: reconstruct each reported story's per-phase wall-clock
duration from `gate-ledger work-get`'s own `history` array (data already recorded today,
no new instrumentation) and render it next to that phase's verdict.

`commands/work-through.md` is prose, not executable code, so there is no runtime harness
for the render loop itself (mirrors `tests/python/test_handback_skill.py`'s framing for the
same reason). The one piece of real logic this story adds — the `jq` filter that turns a
work file's `history` array into a duration chain — *is* executable, so these tests extract
it from the prose verbatim (never reimplemented, the same discipline
`test_contract_injection.py`/`test_driver_crash_hardening.py` use for `epic-driver.js`) and
run it against constructed fixtures via `jq` directly. That locks the design doc's own
pre-mortem register (`docs/studious/premortems/2026-07-21-acceptance-retry-visibility-design.md`)
finding 2 (a missing/malformed `createdAt` or `at` must degrade to "no duration shown", never
a literal NaN or a negative number) as an executable regression, plus the design's own
worked example and its issue #142 counterfactual, byte-for-byte.

The remaining findings have no code to execute against — a prose instruction, not an
arithmetic result — so they're checked structurally instead, the same way
`test_handback_skill.py` checks its command's prose commitments: finding 1 (degrade
per-story, never abort the whole report), finding 3 (prose-level `jq`, not a new
`gate-ledger` verb, while this story is the arithmetic's only consumer), finding 4 (fall
back to the driver's own trail when a story's history can't be read), finding 5 (full
history renders, intentionally, not scoped to this run), finding 6 (the rendered text never
asserts health), and finding 7 (a compact parenthetical, not a separate table).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "commands" / "work-through.md"
DESIGN_DOC = (
    REPO_ROOT / "docs" / "superpowers" / "specs" / "2026-07-21-acceptance-retry-visibility-design.md"
)

def _command_text() -> str:
    return WORK_THROUGH.read_text()


def _close_section() -> str:
    """The `## Close every invocation the same way` section this story edits,
    isolated from the rest of the file so assertions about its prose can't be
    satisfied by unrelated text elsewhere (e.g. the finale section's own,
    pre-existing use of the word "stalled")."""
    text = _command_text()
    start = text.index("## Close every invocation the same way")
    end = text.index("## Record keeping")
    return text[start:end]


def _extract_jq_filter() -> str:
    """Extract the jq filter embedded in the fenced ```bash block, verbatim —
    never reimplemented, per this repo's own precedent
    (test_handback_skill.py, test_contract_injection.py) for locking prose-
    embedded logic against silent drift."""
    match = re.search(
        r"```bash\ngate-ledger work-get --slug \"<slug>--<story>\" \| jq -r '\n(.*?)\n'\n```",
        _command_text(),
        re.DOTALL,
    )
    assert match is not None, (
        "duration jq pipeline fenced block not found in commands/work-through.md — "
        "did its shape change?"
    )
    return match.group(1)


def _run_jq(filter_text: str, payload: dict) -> str:
    result = subprocess.run(
        ["jq", "-r", filter_text],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"jq exited {result.returncode} on well-formed input; stderr: {result.stderr}"
    )
    return result.stdout.strip()


# --- the fenced block exists and is where the prose says it is ---


def test_jq_pipeline_fenced_block_present() -> None:
    assert _extract_jq_filter(), "jq filter extraction returned empty text"


def test_jq_pipeline_reads_work_get_not_a_new_verb() -> None:
    """Out of scope: 'Any change to bin/gate-ledger's schema, verbs, or dispatch
    table' — the design's working default (open question) is prose-level jq
    over the existing work-get verb, not a new gate-ledger read verb."""
    text = _close_section()
    assert "gate-ledger work-get" in text
    assert "work-durations" not in text


# --- criterion 4: never misreports a healthy long-running gate ---


def test_never_asserts_health_language_present() -> None:
    text = _close_section()
    assert "Never asserts health" in text
    assert '"slow," "stalled," or "retried"' in text or (
        "slow" in text.lower() and "stalled" in text.lower() and "retried" in text.lower()
    )


def test_full_history_intentional_note_present() -> None:
    """Pre-mortem finding 5: history is cumulative across runs, not scoped to
    this run — the design doc's stated intent, not a bug. Locks that the
    command prose says so explicitly rather than leaving it ambiguous."""
    text = _close_section()
    assert "Renders full history, not just this run's phases" in text


def test_degrade_per_story_instruction_present() -> None:
    """Pre-mortem finding 1: one malformed/unreadable work file must not abort
    the whole report; finding 4: fall back to the driver's own trail text."""
    text = _close_section()
    assert "Degrade per-story, never abort the whole report" in text
    assert "driver's own trail/reason text" in text


def test_finale_pseudo_entry_excluded_from_per_story_read() -> None:
    """The epic finale's stalled-gate entry (`<epic-slug>--finale: ...`) is a
    needsYou entry with no `<slug>--story>` work file behind it — the
    duration-reconstruction step must not assume every needsYou entry has one."""
    text = _close_section()
    assert "finale" in text.lower()
    assert "does not and falls through the degrade rule" in text


# --- report template actually carries the duration chain ---


def test_report_template_carries_duration_placeholder() -> None:
    text = _close_section()
    template_match = re.search(r"```text\n(.*?)\n```", text, re.DOTALL)
    assert template_match is not None, "closing report template fence not found"
    template = template_match.group(1)
    assert "(<Nm>)" in template
    assert "Needs you:" in template
    assert "Landed this run:" in template
    # The old, pre-duration placeholder must actually be gone, not just
    # supplemented — this was a real rendering change, not an addition.
    assert "<story — verdict trail>" not in template


# --- the jq filter's actual behavior, run against constructed fixtures ---


def test_jq_pipeline_matches_design_doc_worked_example() -> None:
    """Reproduces the design doc's own real, already-recorded fixture
    (13m20s / 14m46s / 8m26s / 4m53s) and asserts the rendered chain is
    byte-identical to the design doc's rendering example (13m / 15m / 8m / 5m
    — rounded, not floored: 14m46s rounds up to 15m, 4m53s rounds up to 5m)."""
    payload = {
        "createdAt": "2026-07-11T13:32:09Z",
        "history": [
            {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-07-11T13:45:29Z"},
            {"step": "build", "outcome": "DONE", "at": "2026-07-11T14:00:15Z"},
            {"step": "audit", "outcome": "PASS", "at": "2026-07-11T14:08:41Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-11T14:13:34Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == (
        "design-review: PROCEED TO PLAN (13m) → "
        "build: DONE (15m) → audit: PASS (8m) → acceptance: SHIP (5m)"
    )


def test_jq_pipeline_reproduces_issue_142s_117_minute_incident() -> None:
    """The counterfactual check from the design doc's Success metrics section:
    applying the computation to issue #142's own reported timeline yields the
    ~117-minute anomaly the reporter surfaced by hand, unattributed — a plain
    number, never labeled "stalled" or "retried" by the filter itself."""
    payload = {
        "createdAt": "2026-07-20T15:00:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-20T15:25:43Z"},
            {"step": "acceptance", "outcome": "FIX AND RE-CHECK", "at": "2026-07-20T17:22:50Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == "audit: PASS (26m) → acceptance: FIX AND RE-CHECK (117m)"
    assert "stalled" not in out.lower()
    assert "retried" not in out.lower()


def test_jq_pipeline_missing_created_at_shows_no_duration_not_nan() -> None:
    """Pre-mortem finding 2: a work file missing `createdAt` (pre-existing on
    disk, hand-edited, or otherwise) must render the first phase with no
    duration at all, never a NaN or a negative number."""
    payload = {
        "history": [
            {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-07-11T13:45:29Z"},
            {"step": "build", "outcome": "DONE", "at": "2026-07-11T14:00:15Z"},
        ]
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == "design-review: PROCEED TO PLAN → build: DONE (15m)"
    assert "nan" not in out.lower()
    assert not re.search(r"\(-\d", out), f"a negative duration leaked into: {out!r}"


def test_jq_pipeline_malformed_at_degrades_without_crashing() -> None:
    """Pre-mortem finding 2's corollary: a malformed `at` on one entry must not
    abort the computation for the rest of the story's history — it (and any
    later entry whose predecessor is the malformed one) shows no duration."""
    payload = {
        "createdAt": "2026-07-11T13:32:09Z",
        "history": [
            {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "not-a-timestamp"},
            {"step": "build", "outcome": "DONE", "at": "2026-07-11T14:00:15Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == "design-review: PROCEED TO PLAN → build: DONE"
    assert "nan" not in out.lower()


def test_jq_pipeline_never_emits_a_negative_duration_on_clock_skew() -> None:
    """A later entry's `at` earlier than its predecessor (clock skew, a
    hand-edited file) must degrade to no duration, never a negative number —
    the filter's own explicit `$secs < 0` guard."""
    payload = {
        "createdAt": "2026-07-11T14:00:00Z",
        "history": [
            {"step": "design-review", "outcome": "PROCEED TO PLAN", "at": "2026-07-11T13:45:29Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == "design-review: PROCEED TO PLAN"
    assert not re.search(r"\(-\d", out), f"a negative duration leaked into: {out!r}"


def test_jq_pipeline_empty_history_degrades_to_empty_not_an_error() -> None:
    payload = {"createdAt": "2026-07-11T13:32:09Z", "history": []}
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == ""


# --- the cited design doc actually exists (consumers-must-stay-in-sync style) ---


def test_cited_design_doc_exists() -> None:
    assert DESIGN_DOC.is_file(), (
        f"commands/work-through.md cites {DESIGN_DOC.relative_to(REPO_ROOT)}, "
        "which does not exist"
    )
