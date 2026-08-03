#!/usr/bin/env python3
"""Render a repo's saves ledger — the catches a gate demonstrably made (#146).

A **save** is a finding that changed the work: it was raised at one sha and
closed at a later one. Nothing here is a judgment call and no prompt is
consulted; every field is folded out of state `bin/gate-ledger` already wrote.

Two read-only sources, both local and gitignored:

- `.studious/epics/<epic>.events.jsonl` — the per-epic findings ledger
  (`finding` / `attestation` lines, `reference/events-format.md`). This is the
  core: it carries the finding's identity, its severity, the sha it was raised
  at, and the sha it was resolved at.
- `.studious/telemetry/<branch-slug>.jsonl` — the gate-time outcome labels
  (`reference/telemetry-format.md`). Enrichment only: when an outcome line's
  `task_id` resolves to the same epic/story, a save that sat across a
  fix-and-retry verdict followed by a proceed verdict is marked
  `gate-confirmed` and names both tokens.

The telemetry half is deliberately optional. That store is best-effort by its
own contract and a missing file changes no verdict anywhere, so requiring it
would render an empty ledger in the common case. A save stands on the findings
closure; the verdict pair is the confirmation when it is there.

**The fold matches `gate-ledger epic-findings` exactly** — group by fingerprint,
sort each group by `at`, take identity (lane, story, severity, raised sha) from
the FIRST line and state from the LAST, and the resolved sha from the last line
whose status is `closed`. Two readers of one store that disagree are a defect,
and the first-line rule is what stops a Critical being laundered down by a
restatement. Timestamps sort as plain strings: `at` is fixed-width
`%Y-%m-%dT%H:%M:%SZ`, which orders lexicographically, and `datetime.
fromisoformat` rejects the trailing `Z` below 3.11 — under this directory's 3.9
floor that would be a runtime break vermin cannot see.

"What it prevented" is the finding's own `severity` and `lane`, never a
generated impact claim: the issue's constraint is no new judgment calls.

Read-only and stdout-only. It writes nothing, anywhere — rendering is the
persistence. `--json` emits the same records for a downstream corpus.

Exit codes: 0 always, including a repo with no `.studious/` at all (an empty
ledger is a true answer). 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

#: Verdict tokens per `reference/gate-vocabulary.md`. A save is `gate-confirmed`
#: when a fix-and-retry token was recorded at or after the finding was raised and
#: a proceed token followed it — the gate saying, in its own vocabulary, that the
#: work changed and then passed.
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


def git_output(start: Path, *args: str) -> str:
    """One `git -C <start> ...` invocation's stdout, empty on any failure."""
    try:
        out = subprocess.run(
            ["git", "-C", str(start), *args], capture_output=True, text=True, check=False
        )
    except OSError:
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def repo_root(start: Path) -> Path:
    """The MAIN working tree containing `start`, or `start` itself outside a repo.

    Mirrors `bin/gate-ledger`'s own `repo_root()`, which is the store's owner:
    it resolves `--git-common-dir`, not `--show-toplevel`, so an agent running in
    a linked worktree reads the one `.studious/` every store is anchored to. A
    `--show-toplevel` here would render `0 save(s)` from inside a story worktree —
    silently, in exactly the run that produces the most saves.
    """
    common = git_output(start, "rev-parse", "--git-common-dir")
    if not common:
        return start
    resolved = (start / common).resolve() if not Path(common).is_absolute() else Path(common)
    if resolved.name == ".git":
        return resolved.parent
    toplevel = git_output(start, "rev-parse", "--show-toplevel")
    return Path(toplevel) if toplevel else start


def read_records(path: Path) -> list[dict]:
    """Every well-formed JSON object in a `.jsonl` store, malformed lines skipped.

    Mirrors `epic-findings`' `fromjson? // empty`: one corrupt append must not
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

    The same derivation `bin/gate-ledger`'s `epic_context_from_branch()` does,
    and the bridge between the two stores: an outcome line's `task_id` is the raw
    branch name, so it resolves to the (epic, story) the findings ledger is keyed
    by. Both halves were slugified before concatenation, so the first `--` splits
    unambiguously. A branch with no `epic/` prefix belongs to no epic.
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

    A pair is matched per gate — a finding raised mid-episode is answered by that
    gate's own retry token and the proceed token that closes it — and the winner
    across gates is the pair whose proceed line lands EARLIEST, never the
    alphabetically first gate (`acceptance` sorts before `audit`, and picking by
    name would credit the wrong door on a story that retried at both). No pair,
    or no telemetry at all, leaves the save unconfirmed rather than dropping it.
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
