"""Regression tests for the acceptance-retry-visibility story (issue #142, Finding 2).

No layer in this repo can detect that a prior `agent()` dispatch was abandoned/superseded
before a retry, so acceptance criterion 2 (a `work-log RETRY` entry) doesn't ship. Instead
(criterion 3), `reference/epic-orchestration.md`'s report reconstructs each phase's wall-clock
duration from `gate-ledger work-get`'s existing `history` array and renders it next to the
verdict.

The command file is prose, not code (same framing as `test_handback_skill.py`), except for
the `jq` filter that turns `history` into a duration chain — that piece is extracted
verbatim (never reimplemented, per `test_contract_injection.py`/`test_driver_crash_hardening.py`)
and run against fixtures via `jq`. This locks pre-mortem finding 2
(`docs/studious/premortems/2026-07-21-acceptance-retry-visibility-design.md`; malformed/missing
timestamps degrade to "no duration", never NaN or negative) plus the design doc's worked
example and #142 counterfactual, byte-for-byte.

Remaining pre-mortem findings have no arithmetic to run, so they're checked structurally:
finding 1 (degrade per-story, never abort the report), finding 3 (prose-level jq, no new
`gate-ledger` verb), finding 4 (fall back to the driver's trail text), finding 5 (full
history renders, not scoped to the run), finding 6 (rendered text never asserts health),
finding 7 (a compact parenthetical, not a table).

**Revision 2** (`gate-design-review` REVISE): suppressing duration for any phase right after
a `run-boundary` marker fixed the `HOLD` false positive but made a genuinely slow resumed
phase (#142's own 117-minute stall) render identical to a healthy 5-minute resume. Promotes
`(resumed)` from an Open Question to a requirement: every phase immediately after a
`run-boundary` marker gets an explicit tag, scoped to just that one phase.

**Revision 3** (`gate-acceptance` FIX AND RE-CHECK, Finding 1): the bare `(resumed)` tag
still read as benign lifecycle info rather than a signal to investigate — same false
negative, one level up. The tag's literal text (`RESUMED_TAG` below, copied verbatim so it
can't drift) now states plainly that no same-run duration was measured and a manual check
may be worth it — never a health verdict, never a minute count.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORK_THROUGH = REPO_ROOT / "reference" / "epic-orchestration.md"

# gate-acceptance FIX AND RE-CHECK, Finding 1: bare (resumed) read as benign, not a
# signal to investigate — states no-measurement + suggests a manual check, never a
# health verdict (criterion 4) or minute count (criterion 2). Single constant so
# wording can't drift between assertions.
RESUMED_TAG = "(resumed — no same-run duration; worth a gate-ledger work-get check)"

def _command_text() -> str:
    return WORK_THROUGH.read_text()


def _close_section() -> str:
    """Isolates the section this story edits so assertions can't match unrelated
    text (e.g. the finale section's own pre-existing "stalled")."""
    text = _command_text()
    start = text.index("## Close every invocation the same way")
    end = text.index("## Record keeping")
    return text[start:end]


def _reconcile_section() -> str:
    """Isolates the Reconcile step Revision 2 edits, same rationale as `_close_section`."""
    text = _command_text()
    start = text.index("### 1 · Reconcile")
    end = text.index("### 2 · Run the driver script")
    return text[start:end]


def _extract_jq_filter() -> str:
    """Extracts the jq filter verbatim from its fenced block — never
    reimplemented (same precedent as test_handback_skill.py, test_contract_injection.py)."""
    match = re.search(
        r"```bash\ngate-ledger work-get --slug \"<slug>--<story>\" \| jq -r '\n(.*?)\n'\n```",
        _command_text(),
        re.DOTALL,
    )
    assert match is not None, (
        "duration jq pipeline fenced block not found in reference/epic-orchestration.md — "
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
    """Out of scope: any change to gate-ledger's schema/verbs — this is
    prose-level jq over existing work-get, not a new verb."""
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
    """Pre-mortem finding 5: history is cumulative across runs by design, not
    a bug — locks that the prose says so explicitly."""
    text = _close_section()
    assert "Renders full history, not just this run's phases" in text


def test_degrade_per_story_instruction_present() -> None:
    """Pre-mortem finding 1: one malformed/unreadable work file must not abort
    the whole report; finding 4: fall back to the driver's own trail text."""
    text = _close_section()
    assert "Degrade per-story, never abort the whole report" in text
    assert "driver's own trail/reason text" in text


def test_finale_pseudo_entry_excluded_from_per_story_read() -> None:
    """The finale's stalled-gate entry (`<epic-slug>--finale: ...`) is a
    needsYou entry with no work file behind it — duration reconstruction
    must not assume every needsYou entry has one."""
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
    # Old placeholder must be gone, not just supplemented — a rendering
    # change, not an addition.
    assert "<story — verdict trail>" not in template


# --- the jq filter's actual behavior, run against constructed fixtures ---


def test_jq_pipeline_matches_design_doc_worked_example() -> None:
    """Design doc's own fixture; asserts byte-identical output, rounded not
    floored (14m46s -> 15m, 4m53s -> 5m)."""
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
    """Design doc's Success-metrics counterfactual: #142's own timeline
    yields the ~117-minute anomaly as a plain number, never labeled
    "stalled"/"retried"."""
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
    """Pre-mortem finding 2: missing `createdAt` renders the first phase with
    no duration, never NaN or negative."""
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
    """Finding 2 corollary: a malformed `at` degrades that entry (and any
    entry whose predecessor is malformed) to no duration, without aborting
    the rest."""
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
    """Clock skew (a later `at` earlier than its predecessor) degrades to no
    duration, never negative — the filter's explicit `$secs < 0` guard."""
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


# --- Revision 2: run-boundary marker + the `(resumed)` tag requirement ---
# (gate-design-review REVISE, criterion-4 false negative)


def test_run_boundary_marker_never_rendered_as_its_own_line() -> None:
    """The marker itself carries no phase transition worth a line — only the
    phase it precedes is affected."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-20T09:19:47Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert "run-boundary" not in out
    assert "DISPATCHED" not in out
    assert out == f"audit: PASS (13m) → acceptance: SHIP {RESUMED_TAG}"


def test_run_boundary_tags_a_fast_resumed_phase() -> None:
    """The `HOLD` finding's own scenario: a fast (5-minute) resumed phase must
    never render its idle-time delta (`(2877m)`) — it renders the resumed tag."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-20T09:19:47Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert f"acceptance: SHIP {RESUMED_TAG}" in out
    assert "2877" not in out
    assert "(5m)" not in out


def test_run_boundary_tags_a_slow_resumed_phase_the_same_way() -> None:
    """The regression this revision fixes: pre-Revision-2 bare rendering hid
    a slow resumed phase (#142's 117-minute stall) identically to a healthy
    one. Locks that slow and fast cases now carry the same tag — never bare,
    never a differentiating number (rejected on queueing-delay grounds in
    the design doc's Alternatives)."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-21T08:00:00Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-21T09:57:00Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == f"audit: PASS (13m) → acceptance: SHIP {RESUMED_TAG}"
    # Never fully bare — the pre-Revision-2 failure mode this test guards against.
    assert out.strip().endswith(f"acceptance: SHIP {RESUMED_TAG}")
    assert "acceptance: SHIP\n" not in out
    assert not out.rstrip().endswith("acceptance: SHIP")


def test_run_boundary_tag_is_scoped_to_the_immediately_following_phase_only() -> None:
    """A second phase after the marker has a real same-run predecessor and
    computes a normal duration — the tag doesn't leak past the one phase
    it's honest about."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
            {
                "step": "acceptance",
                "outcome": "FIX AND RE-CHECK",
                "at": "2026-07-20T09:19:47Z",
            },
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-20T09:30:00Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == (
        f"audit: PASS (13m) → acceptance: FIX AND RE-CHECK {RESUMED_TAG} → "
        "acceptance: SHIP (10m)"
    )


# --- Revision 3: the resumed tag's literal text states no-measurement + a check ---
# (gate-acceptance FIX AND RE-CHECK, Finding 1)


def test_resumed_tag_states_no_measurement_and_invites_a_manual_check() -> None:
    """gate-acceptance Finding 1: the tag's rendered text must state no
    same-run duration was measured and suggest a manual check, without a
    health verdict (criterion 4) or minute count (criterion 2)."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-20T09:19:47Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    tag = out[out.index("(resumed") :]
    assert "gate-ledger work-get" in tag
    assert "no same-run duration" in tag
    assert not re.search(r"\d", tag), f"a minute-count leaked into the tag: {tag!r}"
    for banned in ("slow", "stalled", "retried"):
        assert banned not in tag.lower(), f"a health verdict leaked into the tag: {tag!r}"


def test_resumed_tag_matches_the_hardcoded_regression_constant() -> None:
    """Catches `RESUMED_TAG` drifting from the actual rendered wording."""
    payload = {
        "createdAt": "2026-07-18T16:50:00Z",
        "history": [
            {"step": "audit", "outcome": "PASS", "at": "2026-07-18T17:03:11Z"},
            {"step": "run-boundary", "outcome": "DISPATCHED", "at": "2026-07-20T09:14:02Z"},
            {"step": "acceptance", "outcome": "SHIP", "at": "2026-07-20T09:19:47Z"},
        ],
    }
    out = _run_jq(_extract_jq_filter(), payload)
    assert out == f"audit: PASS (13m) → acceptance: SHIP {RESUMED_TAG}"


def test_reconcile_writes_run_boundary_marker_for_pre_existing_work_files() -> None:
    """Criterion 1: the run-boundary marker is written once per invocation,
    only for a story whose work file already existed — never for a new
    story, never twice, never when only merge is left."""
    text = _reconcile_section()
    assert 'gate-ledger work-log --slug "<slug>--<story>" --step "run-boundary"' in text
    assert '--outcome "DISPATCHED"' in text
    assert '"$last_step" != "run-boundary"' in text
    assert '"$next_phase" != "merge"' in text


def test_reconcile_binds_work_get_json_from_the_captured_reconcile_payload() -> None:
    """Regression (epic finale audit): issue #160 collapsed per-story
    `work-get` calls into one `epic-reconcile` call, but this section's prose
    was never updated — `$work_get_json` was referenced without being bound,
    so the run-boundary marker silently never wrote. Locks that
    `epic-reconcile`'s payload is captured and `$work_get_json` is actually
    derived from it (`.work` field) before the existing checks run."""
    text = _command_text()
    assert 'reconcile_json=$(gate-ledger epic-reconcile --slug "<slug>")' in text
    reconcile_text = _reconcile_section()
    assert (
        'work_get_json=$(echo "$reconcile_json" | jq -c '
        '\'.stories["<story>"].work // empty\')' in reconcile_text
    )


def test_run_boundary_reserved_step_name_documented_collision_free() -> None:
    text = _reconcile_section()
    assert "reserved" in text.lower()
    assert "design-review" in text and "audit" in text and "merge" in text


def test_resumed_tag_required_not_cosmetic_in_close_section() -> None:
    """The Open Question this design doc deferred was promoted to a
    requirement by gate-design-review's second round — locks that the prose
    states the tag is mandatory, not optional."""
    text = _close_section()
    assert "(resumed)" in text
    assert "never a bare render" in text or "never silently bare" in text


def test_resumed_tag_rationale_names_the_false_negative_it_fixes() -> None:
    """Locks that the prose explains *why* bare rendering was rejected, so a
    future edit can't quietly revert without re-breaking criterion 4."""
    text = _close_section()
    assert "5" in text and "117" in text
    assert "queueing-delay" in text or "queueing delay" in text


def test_report_template_documents_resumed_placeholder() -> None:
    text = _close_section()
    assert "(resumed)" in text
    assert "<Nm>" in text


# --- the rationale citation resolves (consumers-must-stay-in-sync style) ---


def test_rationale_citation_resolves() -> None:
    """Originally asserted a `docs/superpowers/specs/` doc existed; under the
    ratified rule (#219) a design doc is branch-local and dies at closeout, so
    a permanent file must cite the issue instead — this guard now checks that
    citation and, generalized rather than deleted, that every doc path in a
    tree this repo owns resolves. `docs/headless-contract.md` is excluded: it
    lives in viva's repo behind a published contract (CLAUDE.md boundary
    criterion (e)), so a checkout-local existence check doesn't apply."""
    text = WORK_THROUGH.read_text(encoding="utf-8")
    assert "issues/142" in text, "the retry-visibility rationale citation is gone"

    owned = re.findall(r"(?<![\w/-])(docs/(?:design|superpowers|studious)/[\w./-]+\.md)", text)
    missing = sorted({p for p in owned if not (REPO_ROOT / p).is_file()})
    assert not missing, f"reference/epic-orchestration.md cites paths that do not exist: {missing}"
