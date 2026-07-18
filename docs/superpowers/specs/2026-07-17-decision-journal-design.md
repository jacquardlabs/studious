# Design: Decision journal — give /gate-should-we-build a memory of rejected ideas

**Date:** 2026-07-17
**Status:** Design, pre-implementation
**Story:** decision-journal (epic: expand-gate-coverage)
**Source:** [#94](https://github.com/jacquardlabs/studious/issues/94)

## Problem & persona

The persona is PRODUCT.md's primary user: **"a developer (solo or small team) building
features with Claude Code who wants product judgment and quality gates woven into the
build, without heavy process."** The principle this story extends is **"Grounded in
shared context — every gate and review reads from the same three context docs, so
judgments are consistent rather than per-prompt improvisation."** The gap: verdicts
themselves are not part of that shared context. `/gate-should-we-build` generates a
verdict with rationale, speaks it, records a bare token to the local gitignored gate
ledger — and the reasoning is discarded. The next time the same idea surfaces (in a new
session, a new clone, or six weeks later in `/backlog-priorities`), the gate
re-litigates from scratch with no memory that the question was already answered, or why.

The secondary persona — **"the maintainer dogfooding Studious on Studious"** — is the
live evidence. Issue #94 documents the manual workaround: the maintainer hand-stamps
"Gate verdict: DON'T BUILD (yet)" into GitHub issue bodies (#34 is the example)
precisely because the tool won't remember for them. PRODUCT.md's "What we're NOT
building" list is the static form of the same need; what's missing is the dated,
per-idea form — living case law with a rationale and a revisit condition attached, so
"has X changed?" is a question the gate can actually ask.

The job-to-be-done: when a user asks "should we build X" about an idea that was already
evaluated, open with the prior verdict, its date, and its revisit condition — then
evaluate fresh — instead of silently re-deriving (or worse, contradicting) a decision
the project already made.

## Proposed design

Three prompt-surface changes and one new reference file. No executable code changes —
no new `gate-ledger` verb, no hook, no script.

**1. The journal: `docs/studious/decisions.jsonl` in the consuming project.**
Append-only, one compact JSON object per line, committed (tracked, not gitignored) —
the exact committed-artifact-plus-append-only pattern `/deep-review`'s
`docs/studious/reviews/metrics.jsonl` already established, including lazy creation:
the first append creates the file and directory; no `/studious-init` change. The gate
writes the file; committing it stays with the user's normal git flow — Studious never
runs `git commit` in a consuming project.

**2. Record on every verdict.** After `/gate-should-we-build` states its
recommendation, alongside the existing `gate-ledger record` step (which stays — see
"Two writes, two jobs" below), it appends one journal line. Illustrative shape (the
byte-exact shape, field ordering, and append mechanics are pinned at build time in a
new `reference/decision-journal-format.md`, mirroring how
`reference/evidence-format.md` pins the evidence log for `hooks/evidence-capture.sh`):

```json
{
  "date": "2026-07-17",
  "gate": "should-we-build",
  "idea": "decision journal — give the decide gate memory of rejected ideas",
  "verdict": "DEFER",
  "rationale": "Real pain, but the gate-ledger statefulness work (#27) must land first.",
  "revisitCondition": "Gate ledger ships and verdicts persist per-branch."
}
```

- `date` — date-only, matching `metrics.jsonl`'s precedent and the issue's own framing
  ("you evaluated this on 2026-03-12"); computed by a shell `date` call in the append
  command, never from model memory.
- `gate` — constant `"should-we-build"` in this story. Recorded now so a later story
  can journal another gate's decisions without a shape change (the same
  cheap-now-structural-later call `evidence-format.md` made with `capturer`).
- `idea` — a one-line statement of the idea *as evaluated* (the gate's restatement,
  since `$ARGUMENTS` may be a paragraph). This is the match key for future reads.
- `verdict` — one of the gate's four tokens: `BUILD`, `BUILD SMALLER`, `DEFER`,
  `DON'T BUILD`.
- `rationale` — the one-sentence rationale the gate already ends on, captured verbatim.
- `revisitCondition` — what would change the answer. Required for `DEFER` and
  `DON'T BUILD` (the entries the journal exists for); optional for `BUILD`/`BUILD
  SMALLER`, where "we built it" is the usual epilogue.

If the append fails (no `jq`, unwritable directory), the gate tells the user the
verdict could not be journaled — the same never-skip-silently posture the existing
`gate-ledger`-not-found fallback already takes in this command.

**3. Read before evaluating — in both consumers.** `/gate-should-we-build` gains a
step before its evaluation: read `docs/studious/decisions.jsonl` if present (absent
file = no prior verdicts, proceed; never created at read time), scan for entries
matching the idea under evaluation, and open the findings with any match: *"You
evaluated this on 2026-03-12: DEFER because X — has X changed?"* Matching is semantic,
by the model, against the `idea` field — this is judgment, which is exactly what
prompts own in this system. `@agent-backlog-priorities` gains the mirror step: read
the journal after PRODUCT.md, and when a ranked issue matches a journal entry,
annotate that item with the prior verdict and date in its rationale line.

**4. The journal informs, never decides — enforced in the prompt text, both
directions.** This is the epic pre-mortem's risk #5
(`docs/studious/premortems/expand-gate-coverage-epic.md`) and acceptance criterion 3,
and the design treats it as a contract, not a hope. The prompt text added to both
consumers states the guardrail explicitly: a prior entry never pre-fills, shortcuts, or
substitutes for the fresh evaluation — `/gate-should-we-build` runs all five criteria
and reaches its own verdict every time (which may contradict the prior entry; that
contradiction is surfaced, with both dates, not smoothed over), and
`/backlog-priorities` never moves an issue's rank because a prior DEFER exists — the
annotation informs the human, not the score. Judgment stays the spine; the journal is
context, exactly like PRODUCT.md.

**5. Journal entries are untrusted data.** The journal lives in the consuming
project's repo — any contributor can edit it. Both consumers treat entries as data to
surface, never instructions: an entry whose text tries to steer ("auto-approve this
next time", "skip evaluation, already decided") is a flag to surface, not an order —
the same posture `@agent-backlog-priorities` already takes toward issue text.
Malformed lines are skipped and noted, never a crash.

**Two writes, two jobs.** The existing `gate-ledger record --gate should-we-build`
call stays untouched. The ledger is local, gitignored, per-branch *flow state* —
`/work-on` reads it to know where a feature stands. The journal is committed,
project-lifetime *decision memory* — durable across clones, branches, and sessions.
Neither substitutes for the other; the design names this so a future simplification
pass doesn't collapse them.

**One invariant edit in this repo.** CLAUDE.md's recommend-only invariant currently
reads "The sole exception: gate commands record verdicts … to local, gitignored
`.studious/` state." This story adds a second sanctioned gate write — the committed
journal under `docs/studious/`, which the same invariant's own boundary ("files
outside `docs/studious/` in the consuming project") already permits, as
`/deep-review`'s reports and `metrics.jsonl` demonstrate. The implementation updates
that CLAUDE.md sentence in the same diff, so the stated invariant and the shipped
behavior never diverge (the epic pre-mortem's risk #2 is exactly this class of doc
drift).

## User journey

This touches PRODUCT.md's critical journey #2, **per-feature gate flow**, at its first
step — "`/backlog-priorities` or `/gate-should-we-build [idea]`" — in both entries.

Decide-gate path, after this story:

1. The user asks "should we build X" (directly, or via the `evaluate-feature-idea`
   skill shim — unchanged, it just routes).
2. The gate reads PRODUCT.md as today, then reads `docs/studious/decisions.jsonl`.
   First-ever run: file absent, nothing to surface, journey identical to today.
3. On a match, the gate's output *opens* with the prior verdict: "You evaluated this
   on 2026-03-12: DEFER because X — has X changed?" — then runs the same five criteria
   it runs today and reaches its own fresh verdict.
4. The gate ends on its bold verdict token, records to the gate ledger (existing), and
   appends the journal line (new). It tells the user the decision was journaled.
5. The user commits `docs/studious/decisions.jsonl` whenever they commit — the same
   way deep-review reports and `metrics.jsonl` already reach the repo.

Backlog path: the user runs `/backlog-priorities new-initiative`; the ranked list
comes back with an annotation on any issue the journal already ruled on — "#34 ·
prior verdict DON'T BUILD (2026-03-12): parked pending real multi-repo demand" —
ranked exactly where the agent's own scoring puts it, with the human deciding what the
prior verdict is worth.

Steps that change an existing journey: step 3 (the gate may open with a prior-verdict
line) and the backlog annotation. Nothing is removed, gated, or reordered; a project
with an empty or absent journal sees today's journey byte-for-byte.

## Out of scope

- **Auto-verdicting from prior entries** — acceptance criterion 3 and pre-mortem risk
  #5. No pre-filling, no "still DEFER, skipping evaluation," no rank demotion in
  `/backlog-priorities` sourced from the journal alone.
- **GitHub writes** — the gate never stamps verdicts into issue bodies (the #34
  manual workaround stays manual until the human retires it; see Open questions), and
  `/backlog-priorities` stays read-only on `gh`. Recommend-only is preserved intact:
  the only write is the journal append inside the consuming project's
  `docs/studious/`.
- **Journaling other gates** — design-review, audit, and acceptance verdicts stay in
  the local ledger only. The `gate` field leaves the door open; nothing walks through
  it here.
- **Backfill** — no migration of historical verdicts from issue bodies or PRODUCT.md's
  "not building" list into the journal. The journal starts empty everywhere and earns
  its entries.
- **Journal maintenance tooling** — no dedup, compaction, edit, or expiry verbs; no
  `gate-ledger` involvement. Append-only, human-editable like any committed doc.
- **`/backlog-hygiene` integration** — adjacent (a DON'T BUILD entry could inform
  close-candidates) but a separate concern for a separate story if it earns one.
- **A matching algorithm** — no embeddings, no fuzzy-match code. Matching an idea to
  prior entries is model judgment over a small file, per "prompts own judgment."
- **`/studious-init` scaffolding changes** — lazy creation at first append, exactly as
  `metrics.jsonl` does; init's directory list is untouched.

## Alternatives considered

**Automate the existing workaround: write verdicts into GitHub issue bodies.** The
maintainer already does this by hand, so it demonstrably serves the need. Rejected:
it breaks the recommend-only invariant (commands never modify issues — CLAUDE.md
names `gh issue edit` as exactly what `/backlog-priorities` must never do), requires
every evaluated idea to have an issue (most `/gate-should-we-build` arguments are
free-text ideas, pre-issue), and leaves the memory unreadable to a gate without
network access. The journal makes the workaround unnecessary instead of automating it.

**Record into the existing gate ledger and read from there — no new file.** Simplest
diff: the write already exists, only the read is new. Rejected: the ledger is
gitignored and keyed per-branch, so the memory would evaporate on every fresh clone
and never exist on the branch where the *next* evaluation happens — the exact
opposite of project-lifetime case law. The ledger's job is short-lived flow state;
stretching it into decision memory would give it two masters and still require a
committed store for the durable half.

**A markdown decision log (`docs/studious/decisions.md`) instead of JSONL.** More
human-readable in review. Rejected: append-only discipline is fragile in prose (every
edit invites reflowing history), and the consumers are prompts that need reliable
per-entry field access (date, verdict, revisit condition) — one JSON object per line
is trivially scannable, matches `metrics.jsonl` and `evidence-format.md` precedent,
and `git log -p` on a JSONL is still perfectly readable case law.

**A `gate-ledger decision-append` verb instead of a prompt-side append.** The
strongest alternative — "code owns bookkeeping" argues for it, and a verb would make
the shape mechanically uniform. Rejected for a boundary reason: `gate-ledger`'s
entire write surface is local, gitignored `.studious/` state, and every one of its
path helpers anchors there; giving it a second lane into *committed* project docs
blurs the exact line the recommend-only invariant draws. The system already has a
sanctioned pattern for committed-JSONL-appended-by-a-prompt —
`/deep-review`'s `metrics.jsonl` — and the drift risk that motivates a code choke
point is covered the same way `evidence-format.md` covers the hook: a pinned
reference file the command must match, checked in review. If a second journaling gate
ever lands, revisit — two prompt-side appenders is where a verb starts earning its
surface.

## Operational readiness

N/A — no operational surface beyond the plugin's existing distribution path, with the
following stated plainly. **Migration:** pure addition — two prompt files gain steps, a
reference file is born; no existing store, hook, or verb changes shape; consuming
projects need no action and gain no file until their first post-update
`/gate-should-we-build` run. **Rollback:** revert the prompt edits; already-written
`decisions.jsonl` files are inert committed docs — nothing else reads them, and they
harm nothing sitting still. **Rollout:** normal semantic-release cadence via the
marketplace. **How we'll know it's working:** this repo dogfoods it — the next
`/gate-should-we-build` run against a previously evaluated idea (the tracker holds
several pre-recorded verdicts) should open with the prior verdict and date; CI's
`check_references.py`, `validate_plugin.py`, and markdownlint (acceptance criterion 5)
verify the prompt surfaces stay well-formed. There are no logs, metrics, or alarms to
wire — this is a local prompt plugin, and inventing telemetry here would be fiction.

## Open questions

- **Match aggressiveness.** How loose should the semantic match be before surfacing a
  prior verdict? A false positive is cheap (one informational line the user can wave
  off); a false negative just means re-litigating, which is today's baseline. v0
  leans permissive and adjusts on dogfood evidence, not speculation.
- **Retiring the manual issue-stamp practice.** Once the journal lands, the
  maintainer's hand-stamped "Gate verdict:" lines in issue bodies (#34 et al.) become
  redundant with journal entries. Whether to leave them, or note journal adoption in
  those issues, is the human's call — flagged so it's decided, not forgotten. No
  command touches them either way.
- **Journal growth.** Append-only with no expiry means the file grows for the
  project's life. At one line per evaluated idea this is years from mattering (the
  read is a model scan, not a parse-everything pipeline), but if a future project
  journals hundreds of decisions, a compaction convention (not tooling) may be worth
  writing down in the reference file then.
