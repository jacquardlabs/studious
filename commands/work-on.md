---
description: Navigate the feature flow one piece at a time — run the next step without needing to know the full workflow
argument-hint: "[idea, issue number, or in-flight feature] (omit to do the next piece)"
allowed-tools: Read, Glob, Grep, Bash, Task
---

# Work on a feature

Walk one feature through the per-feature gate flow, one piece per invocation. This command owns *which step comes next* — the what and the whether — never the how. It runs Studious's own gates directly and, at the two steps Studious doesn't own (writing the design doc, building), hands over context and steps back.

**One invocation, one piece. Never auto-advance.** When the piece finishes — pass, fail, or handoff — stop and hand control back with the closing block below, even when the result is a clean pass and the next step is obvious. The user advances the flow; you never do.

Read PRODUCT.md at the project root first.

## The flow being navigated

| # | Piece | Owner | The piece is done when |
|---|-------|-------|------------------------|
| 1 | decide | `/gate-should-we-build` | verdict recorded (**BUILD** / **BUILD SMALLER** continue the flow) |
| 2 | design | handoff — Studious steps back | a design doc exists satisfying `reference/design-doc-contract.md` |
| 3 | design-review | `/gate-design-review` | **PROCEED TO PLAN** |
| 4 | build | handoff — Studious steps back | implementation commits exist on the feature branch |
| 5 | audit | `/gate-audit` | **PASS** at HEAD |
| 6 | acceptance | `/gate-acceptance` | **SHIP** at HEAD |

After piece 6 the flow is `done`: recap the verdict trail and remind the user the PR is theirs to open (`gh pr create` — the PR-time hook reads the same ledger). Never create the PR yourself.

For the gate pieces, run that slash command's workflow now, with the flow's context as its input — each gate owns its own logic and records its own verdict; don't restate or reimplement it here.

## Resolve the feature

Flow position lives in a per-feature work file, `.studious/work/<slug>.json`, read and written only through the ledger tool (see Record keeping). See what's in flight with:

```bash
gate-ledger work-list
```

- **`$ARGUMENTS` is empty — "do the next piece."** If a work file's branch matches the current branch, that's the feature. Otherwise, if exactly one work file is active (phase not `done`/`stopped`), use it. If several are active, list them and ask which — don't guess. If none exist, say there's no feature in flight and invite `/work-on [idea or issue]`.
- **`$ARGUMENTS` names in-flight work** (matches a slug, branch, or title) — resume that feature.
- **Anything else starts a new feature** — a raw idea or an issue reference. For an issue, fetch its title and body with `gh issue view` and use them as the gate input. Derive a short slug from the title, then create the work file at phase `decide`:

```bash
gate-ledger work-set --slug "<slug>" --title "<title>" --source "<issue #N or: idea>" --phase decide
```

## Find the next piece — evidence first

The work file's `phase` names the next piece, but verify it against evidence before running anything, and correct the file when they disagree — evidence wins:

- **Gate verdicts** — read via the ledger tool, never the raw file: `gate-ledger gate-get` prints the current branch's recorded verdicts as JSON (`.gates.<gate>.verdict` / `.gates.<gate>.sha`); empty output means nothing recorded yet. For audit and acceptance a passing verdict counts only at the current HEAD sha; commits since mean that gate is due again.
- **Design doc** — the `designDoc` path in the work file, else discover a candidate the way `/gate-design-review` does. When found, record it: `work-set --design-doc "<path>"`.
- **Pre-mortem register** — `docs/studious/premortems/<doc-slug>.md`, where `<doc-slug>` is the recorded `designDoc`'s filename without its extension — `/gate-design-review` names the register after the design doc, not the feature slug, so don't reuse this flow's `<slug>` here. A register found at that path with a `Branch:` header matching the current branch is evidence design-review already returned **PROCEED TO PLAN**.
- **Build progress** — implementation commits since the design-review sha. If the phase says `build` and there are none, the build piece isn't done: say so rather than advancing (re-offering the handoff is fine).

## Run exactly one piece

Verdict tokens named below are canonical in `reference/gate-vocabulary.md` — if a gate's
actual output ever looks inconsistent with the mapping here, that file (and the gate command
itself) wins.

### 1 · decide

Run `/gate-should-we-build` with the feature as its argument, then set the next phase by verdict:

- **BUILD** → phase `design`
- **BUILD SMALLER** → phase `design`, and update the work file title to the scoped-down version so every later piece inherits the smaller scope
- **DEFER** / **DON'T BUILD** → phase `stopped`; surface the gate's reasoning and end the flow (the user can explicitly restart it later)

```bash
gate-ledger work-log --slug "<slug>" --step decide --outcome "<verdict>" --phase "<next phase>"
```

### 2 · design — handoff

Studious doesn't author design docs (`reference/design-doc-contract.md` — authoring stays with the user's how-layer). Set the user up, then stop:

- Hand over the decide verdict, the (possibly scoped-down) title, and the contract's six required sections; point at `templates/design-doc.md` as the scaffold.
- If Superpowers is installed, note that its brainstorming and planning workflow produces a doc satisfying the contract; otherwise any hand-written spec does.
- Do not draft the doc yourself. It may well get written right here in the session — that work belongs to the user and their workflow, not to this command.

Log the handoff: `work-log --step design --outcome HANDED-OFF` (phase stays `design`; the evidence check advances the flow once the doc exists).

### 3 · design-review

Run `/gate-design-review` against the recorded doc, then:

- **PROCEED TO PLAN** → phase `build`
- **REVISE** → phase stays `design-review`; the next piece is addressing the listed changes, after which this gate re-runs
- **RETHINK** → phase `design`; back to the doc with the gate's reasoning

Log with `work-log --step design-review --outcome "<verdict>" --phase "<phase>"`.

### 4 · build — handoff

Studious steps back here (README: build with your own workflow). Hand over the working context, then stop:

- The design doc path, the pre-mortem register path (its items are what `/gate-audit` and `/gate-acceptance` verify at the end), the scoped title, and the source issue if any.
- Once a feature branch exists, record it — the gate ledger is per-branch, so later pieces need it: `work-set --branch "<branch>"`.
- If Superpowers is installed, its plan/execute workflow picks up from the design doc; otherwise the user builds however they like.

Log `work-log --step build --outcome HANDED-OFF`. Phase stays `build`; the evidence check advances it when implementation commits exist.

### 5 · audit

Run `/gate-audit`, then:

- **PASS** → phase `acceptance`
- **FIX AND RE-AUDIT** → phase stays `audit`; the next piece is fixing the critical findings, then re-audit
- **NEEDS DISCUSSION** → phase stays `audit`; surface the concerns — the user decides how to resolve them

Log with `work-log --step audit --outcome "<verdict>" --phase "<phase>"`.

### 6 · acceptance

Run `/gate-acceptance`, then:

- **SHIP** → phase `done` — recap the trail and hand the PR to the user
- **FIX AND RE-CHECK** → phase stays `acceptance`
- **HOLD** → phase stays `acceptance`; surface the product concerns

Log with `work-log --step acceptance --outcome "<verdict>" --phase "<phase>"`.

## Skips

Gates are optional by judgment — but that judgment is the user's. Skip a piece only when the user explicitly says to; log it (`work-log --step <piece> --outcome SKIPPED --phase <next>`) and move on. Never skip on your own initiative, and never treat a fix-and-retry verdict as skippable.

## Close every invocation the same way

After the piece finishes, end with exactly this shape and nothing after it:

```text
Flow: <slug> — piece <k>/6 (<name>): <outcome>.
Next piece: <name> — <one clause on what it involves>.
Run /work-on when you're ready, or just say "next".
```

When the flow reaches `done` or `stopped`, the last two lines become the wrap-up instead: `done` points at `gh pr create`; `stopped` states the verdict that ended it.

Then stop. Do not start the next piece, do part of it "to save time," or ask whether to continue — the whole point is that the user advances the flow with one word, whenever they're ready.

## Record keeping

All flow state goes through `gate-ledger` — `work-set`, `work-log`, `work-get`, `work-list` for this flow's own state, and `gate-get` to read gate verdicts — never hand-edit the JSON or read either store's files directly. The files are local and gitignored; they never enter the repo. If `gate-ledger` is not found (the plugin's `bin/` isn't on `PATH` in this environment), tell the user flow position can't be recorded — do not skip silently — and navigate from evidence alone for this session.
