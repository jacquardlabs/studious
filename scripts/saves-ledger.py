#!/usr/bin/env python3
"""Render a repo's saves ledger — findings a gate demonstrably caught (#146).

A **save** is a finding raised at one sha and closed at a later one, folded
from state `bin/gate-ledger` already wrote. No judgment calls, no prompt.

Sources, both local and gitignored:

- `.studious/epics/<epic>.events.jsonl` — per-epic findings ledger
  (`reference/events-format.md`): identity, severity, raised/resolved sha.
- `.studious/telemetry/<branch-slug>.jsonl` — gate-time outcome labels
  (`reference/telemetry-format.md`), optional enrichment: when an outcome
  line's `task_id` resolves to the same epic/story, a save whose fix-and-retry
  verdict was followed by a proceed verdict is marked `gate-confirmed`. That
  store is best-effort by its own contract, so a missing file must not empty
  the ledger — a save stands on the findings closure alone.

**The fold matches `gate-ledger epic-findings` exactly** — group by fingerprint,
sort by `at`, identity from the FIRST line, state from the LAST, resolved sha
from the last `closed` line. Two readers of one store must agree, and the
first-line rule stops a Critical being laundered down by a restatement.
Timestamps sort as plain strings (`at` is fixed-width `%Y-%m-%dT%H:%M:%SZ`) —
`datetime.fromisoformat` rejects the trailing `Z` below 3.11, a runtime break
under this directory's 3.9 floor that vermin can't see.

"What it prevented" is the finding's own `severity`/`lane`, never a generated
impact claim.

Read-only and stdout-only; `--json` emits the same records.

Exit codes: 0 always, including no `.studious/` at all. 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _gitutil import main_checkout_root as repo_root

#: Verdict tokens per `reference/gate-vocabulary.md`. A save is `gate-confirmed`
#: when a retry token at/after the raise is followed by a proceed token — the
#: gate saying, in its own vocabulary, that the work changed and then passed.
RETRY_VERDICTS = frozenset({"FIX AND RE-REVIEW", "REVISE"})
PROCEED_VERDICTS = frozenset({"PASS", "SHIP", "PROCEED TO PLAN", "BUILD", "BUILD SMALLER"})
#: Severity ladder, most serious first (`reference/severity-rubric.md`).
SEVERITY_ORDER = ("Critical", "Important", "Track")


@dataclass(frozen=True)
class Save:
    """One catch: finding -> verdict -> what changed -> what it prevented."""

    epic: str
    story: str
    fingerprint: str
    lane: str
    severity: str
    raised_at: str
    raised_sha: str
    resolved_sha: str
    gate: str
    retry_verdict: str
    proceed_verdict: str

    @property
    def gate_confirmed(self) -> bool:
        return bool(self.retry_verdict and self.proceed_verdict)


def read_records(path: Path) -> list[dict]:
    """Every well-formed JSON object in a `.jsonl` store, malformed lines skipped.

    Mirrors `epic-findings`'s `fromjson? // empty`: one corrupt append must not
    blind the reader to every other line.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: list[dict] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            out.append(record)
    return out


def epic_context_from_branch(branch: str) -> tuple[str, str] | None:
    """`epic/<epic>--<story>` -> (epic, story); `epic/<epic>` -> (epic, "").

    Same derivation as `bin/gate-ledger`'s `epic_context_from_branch()`,
    bridging an outcome line's raw `task_id` to the findings ledger's (epic,
    story) key. Both halves were pre-slugified, so the first `--` splits
    unambiguously. No `epic/` prefix -> no epic.
    """
    if not branch.startswith("epic/"):
        return None
    rest = branch[len("epic/") :]
    epic, sep, story = rest.partition("--")
    return (epic, story) if sep else (rest, "")


def fold_findings(records: list[dict]) -> list[dict]:
    """Group `finding` lines by fingerprint and fold each group into current state."""
    groups: dict[str, list[dict]] = {}
    for record in records:
        if record.get("kind") != "finding":
            continue
        fingerprint = record.get("finding")
        if isinstance(fingerprint, str) and fingerprint:
            groups.setdefault(fingerprint, []).append(record)

    folded: list[dict] = []
    for fingerprint, lines in sorted(groups.items()):
        ordered = sorted(lines, key=lambda r: str(r.get("at", "")))
        first, last = ordered[0], ordered[-1]
        closed = [r for r in ordered if r.get("status") == "closed"]
        folded.append(
            {
                "finding": fingerprint,
                "lane": str(first.get("lane", "")),
                "story": str(first.get("story", "")),
                "severity": str(first.get("severity", "")),
                "raisedAt": str(first.get("at", "")),
                "raisedSha": str(first.get("sha", "")),
                "status": str(last.get("status", "")),
                "resolvedSha": str(closed[-1].get("sha", "")) if closed else "",
            }
        )
    return folded


def verdicts_by_story(telemetry_dir: Path) -> dict[tuple[str, str], list[dict]]:
    """Outcome lines from every telemetry file, keyed by the (epic, story) they name."""
    index: dict[tuple[str, str], list[dict]] = {}
    if not telemetry_dir.is_dir():
        return index
    for path in sorted(telemetry_dir.glob("*.jsonl")):
        for record in read_records(path):
            if record.get("kind") != "outcome":
                continue
            context = epic_context_from_branch(str(record.get("task_id", "")))
            if context is not None:
                index.setdefault(context, []).append(record)
    return {key: sorted(lines, key=lambda r: str(r.get("at", ""))) for key, lines in index.items()}


def confirming_verdicts(outcomes: list[dict], raised_at: str) -> tuple[str, str, str]:
    """(gate, retry token, proceed token) for the first retry-then-proceed pair after `raised_at`.

    Matched per gate — a finding is answered by that gate's own retry/proceed
    pair — and the winner across gates is whichever proceed line lands
    EARLIEST, never the alphabetically first gate (`acceptance` sorts before
    `audit`, which would credit the wrong door on a story retried at both). No
    pair, or no telemetry, leaves the save unconfirmed rather than dropped.
    """
    candidates: list[tuple[str, str, str, str]] = []  # (proceed at, gate, retry, proceed)
    for gate in sorted({str(r.get("gate", "")) for r in outcomes}):
        retry = ""
        for record in outcomes:
            if str(record.get("gate", "")) != gate or str(record.get("at", "")) < raised_at:
                continue
            verdict = str(record.get("verdict", ""))
            if not retry and verdict in RETRY_VERDICTS:
                retry = verdict
            elif retry and verdict in PROCEED_VERDICTS:
                candidates.append((str(record.get("at", "")), gate, retry, verdict))
                break
    if not candidates:
        return ("", "", "")
    _, gate, retry, proceed = min(candidates)
    return (gate, retry, proceed)


def collect_saves(studious: Path) -> list[Save]:
    """Every finding that closed at a different sha than it was raised at."""
    epics_dir = studious / "epics"
    if not epics_dir.is_dir():
        return []
    outcomes = verdicts_by_story(studious / "telemetry")

    saves: list[Save] = []
    for path in sorted(epics_dir.glob("*.events.jsonl")):
        epic = path.name[: -len(".events.jsonl")]
        for finding in fold_findings(read_records(path)):
            resolved = finding["resolvedSha"]
            if finding["status"] != "closed" or not resolved or resolved == finding["raisedSha"]:
                continue
            story = finding["story"]
            gate, retry, proceed = confirming_verdicts(
                outcomes.get((epic, story), []), finding["raisedAt"]
            )
            saves.append(
                Save(
                    epic=epic,
                    story=story,
                    fingerprint=finding["finding"],
                    lane=finding["lane"],
                    severity=finding["severity"],
                    raised_at=finding["raisedAt"],
                    raised_sha=finding["raisedSha"],
                    resolved_sha=resolved,
                    gate=gate,
                    retry_verdict=retry,
                    proceed_verdict=proceed,
                )
            )

    def rank(save: Save) -> tuple[int, str, str, str]:
        severity = (
            SEVERITY_ORDER.index(save.severity)
            if save.severity in SEVERITY_ORDER
            else len(SEVERITY_ORDER)
        )
        return (severity, save.epic, save.story, save.fingerprint)

    return sorted(saves, key=rank)


def render(saves: list[Save]) -> str:
    """The highlight ledger, one stanza per save, most serious first."""
    epics = sorted({save.epic for save in saves})
    confirmed = sum(1 for save in saves if save.gate_confirmed)
    header = (
        f"saves ledger — {len(saves)} save(s) across {len(epics)} epic(s), {confirmed} gate-confirmed"
    )
    if not saves:
        return header + "\n  no finding has closed at a later sha yet"

    lines = [header]
    for save in saves:
        story = save.story or "(epic)"
        lines.append("")
        lines.append(f"  {save.epic}/{story}  {save.severity} · {save.lane}")
        lines.append(f"    finding    {save.fingerprint}")
        lines.append(f"    changed    {save.raised_sha} → {save.resolved_sha}")
        if save.gate_confirmed:
            lines.append(
                f"    verdict    {save.gate} {save.retry_verdict} → {save.proceed_verdict} (gate-confirmed)"
            )
        else:
            lines.append("    verdict    (no gate-time label joined)")
        lines.append(f"    prevented  a {save.severity} in the {save.lane} lane, before merge")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render the saves ledger — findings that demonstrably changed the work."
    )
    parser.add_argument(
        "--repo", default=".", help="repository to read (default: the main working tree containing cwd)"
    )
    parser.add_argument("--studious", default=None, help="override the .studious/ store path")
    parser.add_argument("--json", action="store_true", help="emit the save records as JSON")
    args = parser.parse_args(argv)

    studious = (
        Path(args.studious) if args.studious else repo_root(Path(args.repo).resolve()) / ".studious"
    )
    saves = collect_saves(studious)
    if args.json:
        payload = [dict(asdict(save), gate_confirmed=save.gate_confirmed) for save in saves]
        print(json.dumps(payload, indent=2))
    else:
        print(render(saves))
    return 0


if __name__ == "__main__":
    sys.exit(main())
