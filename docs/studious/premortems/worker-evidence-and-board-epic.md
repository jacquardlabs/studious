# Epic pre-mortem — worker-evidence-and-board

Recorded at plan approval (2026-07-10). Cross-story failure modes only — each story's
own pre-mortem (if any) covers its local risks. Verified per item at the epic finale
by `@agent-premortem-auditor`: REALIZED / NOT REALIZED / CAN'T VERIFY.

## 1. Exhibit-format drift

`evidence-capture-hook` serializes to a shape read off winnow's
`docs/amendments/006-evidence-bundles.md` — itself still "Proposed — pending owner
adoption" in winnow's own roadmap, not a frozen spec. If that amendment changes before
either side adopts it, studious's hook format silently diverges from the one format it
was meant to interoperate with.

**Signal it's realized:** the story ships with no written schema doc in `reference/`
pinning the exact fields captured, or the schema doc doesn't cite the amendment's
"early footprint" section specifically (as opposed to the full Phase-2 workstream).

## 2. Dogfood-item-zero failure mode

Issue #97 names this explicitly: it's unverified whether PostToolUse hooks fire for
tool calls made *inside* a Task-dispatched worker agent, not just the interactive
session. If they don't, the harder and more valuable half of the evidence story — the
epic-driven, `/work-through`-dispatched case — is unreachable in v0.

**Signal it's realized:** `evidence-capture-hook` lands with no explicit statement of
which mode(s) it actually captures in, or claims dual-mode capture without a test that
exercises the dispatched-agent path specifically.

## 3. Stale acceptance-sketch language

Issue #98's body describes a "Control Room" swimlane/arc-and-pips visualization. The
issue's own later comment records the design direction changing to a "Flight Deck"
instrument-panel layout after comprehension testing. `board-ui`'s recorded criteria
point at the comment, not the body — but the body is still what a design-phase worker
reads first when it opens the issue.

**Signal it's realized:** `board-ui`'s design doc or build cites arc/swimlane/timeline
language from the issue body as if it were still the target, rather than gauges/CAS/
drawer language from the settled comment.

## 4. Shared gate-ledger choke point

`gates-cite-evidence` (#97) and `board-events-log` (#98) both extend the same
verdict-recording write sites in `bin/gate-ledger`. The DAG sequences them (board
group depends on the full evidence group landing first) specifically to avoid two
stories independently reshaping that region — but sequencing in time doesn't
guarantee `board-events-log`'s design accounts for the shape `gates-cite-evidence`
actually landed in.

**Signal it's realized:** `board-events-log`'s design doc doesn't reference the landed
`gates-cite-evidence` diff, or the two stories' changes to the same functions conflict
in a way audit has to catch instead of design anticipating.

## 5. Studious's first web surface

`DESIGN.md` currently states studious has a single surface (the plugin itself) and no
web UI; the web-only UX/frontend/a11y audit lanes auto-skip accordingly. Landing
`board-server` + `board-ui` makes that statement false going forward — a fact that
should surface explicitly, not be discovered as a surprise when a later `/gate-audit`
run stops auto-skipping those lanes on unrelated changesets.

**Signal it's realized:** the epic lands without any note (finale summary, follow-up
issue, or DESIGN.md flag) that a `DESIGN.md` re-extraction is now warranted; a
subsequent unrelated PR's `/gate-audit` run silently changes lane composition with no
one having predicted it here.
