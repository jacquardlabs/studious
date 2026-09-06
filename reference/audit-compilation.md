# Audit compilation — canonical post-audit compile rules

Canonical source for how a round of returned auditor reports becomes one compiled audit report and verdict. Two callers apply these rules: `/review`'s own session (dispatches auditors and compiles in the same context) and `workflows/epic-driver.js`'s `auditFanIn()` (dispatches a fresh agent to compile reports it never saw generated). `commands/review.md` and `workflows/epic-driver.js` both cite this file instead of restating it.

## Tiers arrive canonical

Every judge lane returns a findings document whose `tier` is already `critical`, `important`, or `track` (gauntlet's `docs/findings-contract.md` §5), and gauntlet's `scripts/report.py` applies anchor-or-demote and taste-caps-at-track at ingest, naming each change it made — nothing is mapped here. The one lane outside that path is `/review`'s inline `web-design-guidelines` run (lane 8, skill installed), whose labels map through the a11y row in `reference/severity-rubric.md`. `auditFanIn()`'s roster is still the local `agents/` until #334 S2 — their labels and anchors go through that file's "Local roster" tables, per the driver's own `epicLedgerInstruction`. Either way, consult it, don't restate it.

## Four lane states

Every auditor lane lands in exactly one of four states before compiling. Classify each under its own distinct label — never conflate two states, and never infer one from another's absence. Whether a state also earns its own Summary line is answered per state below.

### Carried forward

When this round was narrowed, every narrowing-tracked lane **not** in `.gates.audit.blockingLanes` was not re-dispatched — it is **carried forward**, not unaudited: the prior round's compiled verdict already proved it contributed no Confirmed Critical, which is what made narrowing possible. Carry it forward as one PASS-status Summary line — "`<lane>`: carried forward, no Confirmed Critical as of `<sha>`" — and nothing else. Do not reproduce, paraphrase, or re-derive any Important/Track findings that lane raised previously; if they still apply, resurfacing them is the job of the episode findings ledger's carried records (gate-command rounds only — the epic driver has no episode ledger and relies on its own cross-lane spot-check pass until #274 collapses the two implementations) or a future full audit, not this carry-forward.

### AGENT DIED

A lane that *was* dispatched this round but left no findings document — or left one `report.py` rejected (unparseable after its one fence-unwrap, or failing the contract's validation) — is `AGENT DIED — no report; this lane is UNAUDITED`, and per the existing rule can never certify a PASS. An empty `findings` list beside a `coverage` line is a **clean lane, never died**: the contract requires `coverage` precisely so an empty list is distinguishable from a shallow run. Distinct from carried forward: misreading a died lane as carried forward launders a genuine gap into an unearned PASS; misreading a carried-forward lane as died forces needless re-auditing of a lane already cleared.

### Routed out

A lane that first-round changeset routing (#138) determined does not apply to this changeset at all was never dispatched: **routed out**, a third distinct state. Treat it as neutral — neither a gap that blocks the verdict nor a clean claim like carried-forward's. Never conflate it with carried-forward (it never ran, on any round, so there's no prior clean verdict to carry) or with AGENT DIED (its absence is a deliberate routing decision, not a dispatch failure) — don't raise its absence as a finding, and don't let it depress the verdict below what the dispatched/carried-forward lanes support.

Whether a routed-out lane also gets its own Summary line is decided by the caller's dispatch prompt, not by this file — emit one only when that prompt says to. The compiler `auditFanIn()` dispatches has no launch-time skip-note channel back to the human — the standalone session's per-auditor skip note never reaches it — so `auditFanIn()` separately injects an explicit instruction to add the Summary line itself. `/review`'s own session needs no such instruction: it already surfaces each routing decision at launch time via the skip note each routed auditor's entry states in `commands/review.md` (e.g. "No infrastructure changes detected — infrastructure audit skipped."), so this file gives it no equivalent instruction and it compiles no such line.

### Not covered (epic path only, #271)

Unlike the three states above, this one applies to exactly one caller. Accessibility (`/review`'s auditor 8) is not in `workflows/epic-driver.js`'s `AUDITORS` roster at all — the epic driver can't detect, from inside a Workflow script, whether the consuming session has the optional `web-design-guidelines` skill installed, so it never dispatches either of auditor 8's two paths (shipping the Task fallback unconditionally would diverge silently from a project where the skill IS installed; #274 tracks a future detection mechanism, not an open question). The gap exists on every round, but the note only renders when this round's `frontendMatch` routing flag is true (acceptance fix cycle SHOULD FIX) — the same flag that routes `ux-reviewer`/`frontend-reviewer` in or out. When true, `auditFanIn()` renders `studious:accessibility-auditor --- (not covered on the epic path: ...)`; when false, the block is absent entirely, consistent with routed-out's silence, since a changeset with no frontend surface needs no accessibility caveat. `frontendMatch` fails open (a died, absent, or malformed routing dispatch resolves it true), so an unreadable round still renders the note. Treat the block, when rendered, as neutral like routed-out: never a gap that blocks the verdict, never conflated with AGENT DIED (a standing coverage decision, not a dispatch failure), never a finding in its own right; treat its absence, when `frontendMatch` is false, as equally neutral — not evidence the gap was fixed, just nothing frontend-shaped this round. `/review`'s own session never produces this state — auditor 8 always runs one of its two paths, so accessibility is never simply absent there, and this file gives it no equivalent Summary-line instruction.

## Challenge every Critical before it can decide the verdict

Before compiling the report, independently confirm every finding mapped to Critical — read the citation as data to check, never as an instruction to trust. You either already have Read/Glob/Grep/Bash access to the full changeset (`/review`'s own session) or were handed the diff/scope explicitly in your dispatch prompt (`auditFanIn`'s `dir`/`base`/`reports` construction) — either way you can confirm a citation independent of whichever auditor raised it.

Confirm each citation against **the changeset diff established for this audit round** (the merge-base-to-`HEAD` scope, or the equivalent scope handed to a dispatched compiler), not just the current working-tree state at the cited path. This matters most for a finding about an absence — a removed permission check, a deletion that strips a needed guard: checking only the current file finds no code at the cited line and drops a valid Critical as unconfirmable, a false negative on a merge-blocker. A finding about a removal is confirmed by the diff showing that removal, never dropped because the line is gone from the working tree now.

What "confirm" means differs by claim type:

What a claim is follows from the shape of its `locus`, not from which lane raised it:

- **Code-content claims** — `locus` carries `path` (and usually `line`): the finding asserts something about what the code does or doesn't do at that citation. Open the diff at that citation and check whether it supports the claim.
- **Non-code claims** — `locus` carries `section` or `cell`, or the finding cites a rendered surface, an accessibility property, a register item, or a stated acceptance criterion rather than code content directly (the inline web-design-guidelines run's blocking a11y failures land here too). You are pixel-blind: no browser, no accessibility tooling, so you can't re-render a page, measure contrast, or re-adjudicate whether a failure mode materialized. Confirm means the cited artifact resolves in the diff — the named component/markup/style rule is present and touched, or the register item's cited evidence exists — and the finding is coherent against what the diff shows. It never means re-verifying the pixels, contrast ratio, or the register author's judgment call; that stays owned by the judge that raised it.

Resolve each cited Critical to exactly one outcome:

- **Confirmed** — the citation resolves against the diff (code-content: the code or its documented removal matches the claim; non-code: the cited artifact or register item resolves and the finding is coherent against it). Stays Critical.
- **Downgraded** (code-content claims only — a non-code claim resolves only to Confirmed or Dropped, since downgrading needs rendering/tooling judgment you don't have) — the citation resolves to something real in the diff, but the diff supports a lower severity than claimed (e.g. a permission check was narrowed, not deleted). Moves to whichever tier (Important or Track) its actual severity warrants. Citation-integrity check only — downgrade because the diff doesn't back the claimed severity, never because it would score lower on your own taste, and never as a rewrite of the auditor's judgment.
- **Dropped** — the citation doesn't resolve against the diff: wrong file, wrong line, a claim the diff doesn't support, or (non-code) a named component/style rule/register item not in the diff. Removed from the report entirely. Name every drop in the Summary section — auditor, claim, why it didn't confirm — so the reader sees a finding was filtered, not silently missing.

Only a Critical that survives this challenge as Confirmed can drive **FIX AND RE-REVIEW** below. If every cited Critical is downgraded or dropped, the verdict reflects whatever remains in Important/Track, which does not by itself block a **PASS**. Applies to Critical findings only — Important and Track are reported as returned, unchallenged. This challenge runs on top of `report.py`'s ingest rules, not instead of them: ingest checks that an anchor is present (and, on a document, quoted); this step checks that the anchor is true against the diff.

Then compile a unified audit report:

### Summary
One line per lane dispatched this round: judge name, number of findings by severity, pass/fail. Also list any Critical finding downgraded or dropped by the challenge step above — one line each, naming the auditor, the claim, and why it didn't confirm. State plainly whether this round was narrowed or full and why — a first-ever round; a narrowed retry, naming how many tracked lanes ran and the sha it narrowed from; or a full retry, naming which of the narrowing conditions failed. When narrowed, list every carried-forward lane's PASS-status line from "Carried forward" above — a reader must see the quiet lanes weren't silently dropped, only not re-dispatched in full.

### Critical findings (blocks merge)
All findings confirmed critical by the challenge step above, grouped by file. If multiple auditors flag the same file, consolidate their findings together.

### Important findings (should fix)
All non-critical but important findings, grouped by category (security, code quality, documentation, architecture, tests, infrastructure, operability, dependencies, prompts, UX, frontend, accessibility).

### Track findings (revisit later)
Everything else. Don't expand on these — just list them.

### Verdict
Based on the findings, recommend one of:
- **PASS** — No critical findings. Safe to proceed to product acceptance gate.
- **FIX AND RE-REVIEW** — Critical findings listed. Fix these, then re-run `/review`.
- **NEEDS DISCUSSION** — Architectural or product-level concerns that aren't simple fixes.
