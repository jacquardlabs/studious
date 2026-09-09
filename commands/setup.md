---
description: Set Studious up in this project — creates PRODUCT.md and DESIGN.md (extracting both from the codebase), scaffolds the report directories, and wires CLAUDE.md. Run once per project; re-run a single extraction later with `extract-product` or `extract-design`.
argument-hint: "[extract-product | extract-design] (omit for full first-time setup)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write, Edit, WebFetch
---

# Set up Studious here

Set up the full flow in this project: PRODUCT.md, DESIGN.md, and the CLAUDE.md wiring.

**With an argument, run only that extraction and stop:** `extract-product` follows
`reference/product-context-extraction.md`; `extract-design` follows
`reference/design-system-extraction.md`. Both are the same procedures Steps 2 and 3 run
inline during first-time setup, exposed separately to refresh one doc later without
re-running everything.

Everything this command writes, it names first. Propose, then write — never a silent
scaffold.

## Step 1 — Check current state

Before creating anything, check what already exists:
- Does PRODUCT.md exist? Is it populated or empty?
- Does DESIGN.md exist? Is it populated or empty?
- Does README.md exist?
- Does CLAUDE.md exist?
- Do any `docs/` review directories exist?

Report what you found and what you'll create vs skip.

## Step 2 — Create PRODUCT.md (if needed)

If PRODUCT.md doesn't exist, create it by copying the template that ships with the plugin. Copy it verbatim rather than inlining a second copy here — `templates/PRODUCT.md` is the single source of truth:

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/PRODUCT.md" PRODUCT.md
```

(`${CLAUDE_PLUGIN_ROOT}` is substituted to the plugin's install path before you read this. If the copy fails because it didn't resolve, locate `templates/PRODUCT.md` inside the plugin install with Glob and copy its contents — do not re-inline a template here.)

Then populate it inline — follow `reference/product-context-extraction.md` in full now; don't hand this back as a separate step. (`/setup extract-product` re-runs it alone later.)

## Step 3 — Create DESIGN.md (if needed)

If DESIGN.md doesn't exist, create it by copying the template that ships with the plugin (`templates/DESIGN.md`, the single source of truth — copy it verbatim rather than inlining a second copy here). DESIGN.md documents the product's *interface* conventions — the user-facing surface, whatever it is (web UI, CLI, TUI, REST API, HTML/email report) — not just visual design. It is distinct from CLAUDE.md, which documents how the code is written internally.

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/DESIGN.md" DESIGN.md
```

(Same fallback as Step 2: if `${CLAUDE_PLUGIN_ROOT}` didn't resolve and the copy fails, locate `templates/DESIGN.md` inside the plugin install with Glob and copy its contents — do not re-inline a template here.)

Then populate it inline — follow `reference/design-system-extraction.md` in full now; don't hand this back as a separate step. It detects which surfaces the product has and extracts conventions per surface — a non-visual product (CLI, API, plugin) gets a real interface doc, a pure library an honest minimal one. (`/setup extract-design` re-runs it alone later.)

## Step 4 — Create README.md (if needed)

If README.md already exists, skip this step — leave it alone and tell the user to run `/health readme` to check it for drift. Never overwrite an existing README.

If README.md doesn't exist, generate one now. PRODUCT.md exists at this point, so draw from it directly:

- **Source the content** from PRODUCT.md (what the product does, who it's for), the codebase (install/run commands, real file paths, config, `.env.example`), and the package manifest (name, scripts, license).
- **Match the project's voice.** Follow CLAUDE.md's writing-style guidance if present. Lead with what the product does and why. Keep it lean and direct.
- **No template decoration.** No emoji headers, no decorative badges, no marketing fluff. Standard Markdown, real headers, code blocks with language labels.
- **Only claim what's true.** Every command, path, and filename must match the codebase. Don't invent placeholders or aspirational features.

Cover, at minimum: what it is, install, a runnable usage example, and license. Write the file, then flag it for the user's review — the same way PRODUCT.md needs a human pass.

## Step 5 — Scaffold review directories

Create these directories if they don't exist:
- `docs/studious/health-reviews/`
- `docs/studious/interface-reviews/`
- `docs/studious/architecture-reviews/`
- `docs/studious/product-reviews/`
- `docs/studious/security-reviews/`
- `docs/studious/readme-reviews/`
- `docs/studious/prompt-reviews/`
- `docs/studious/outcome-reviews/`
- `docs/studious/retros/`

Add a `.gitkeep` to each empty directory so they're tracked in git.

## Step 5b — Propose the .gitignore entries

Studious keeps process residue out of the repo by convention; that only works if the
project's `.gitignore` carries it. Read the `.gitignore` (create one if absent) and check
for these entries:

```gitignore
# Studious local state — gate ledger, work files, build evidence (never committed)
.studious/

# Disposable build scaffolding — lives on the branch, dies at closeout
# (the durable record is the PR body's evidence table and the pre-mortem register)
/PLAN.md
docs/design/
```

Propose the exact missing lines as a diff, state what each keeps out of review, and add
them on the user's word in this same invocation — never silently, and never touching any
other line of their `.gitignore`. `.studious/` matters most: `/build`'s evidence store is
`.studious/build-evidence/` under the main checkout, and left unignored it shows up as
noise in every `git status`. (`bin/gate-ledger` self-heals that one entry when it first
creates ledger state, so a skipped proposal only degrades to that, later, missing the
other two.)

A project that deliberately tracks its design docs or `PLAN.md` can decline those lines —
`/ship`'s closeout handles the tracked case with a `git rm` commit instead. Note the
choice; don't relitigate it.

## Step 6 — Update CLAUDE.md

If CLAUDE.md exists, append the review workflow section (if not already present). If it doesn't exist, create it with just this section. Check for existing content first — don't duplicate.

Add this section:

```markdown
## Review workflow

### Context documents

- **PRODUCT.md** — product context, personas, principles, feature map. Read before any product decision.
- **DESIGN.md** — the interface design system: the product's user-facing surface(s) — web UI, CLI, TUI, API, or report — covering the semantic palette, vocabulary, formatting, and per-surface conventions. Read before changing anything users see. (CLAUDE.md owns *how the code is written*; DESIGN.md owns *the user-facing surface*.)

### Code conventions

Language conventions `code-auditor` enforces at `/review`. Document the rules and any deliberate deviations here — they override Studious's built-in idiom rubric.

- **<language>** — <conventions, e.g. "Python 3.11+. Prefer comprehensions, generator expressions, and stdlib (functools, itertools, collections) over explicit loops. Type hints required.">
- **Linter** — <the idiom linter and its rule selection, e.g. "Ruff with C4,SIM,PERF,B,RUF,PIE; run `ruff check` before pushing.">
- **Deliberate deviations** — <conventions you intentionally break and why, e.g. "explicit loops in hot paths.">

### Quality gates

| Gate | When | Command |
|------|------|---------|
| Should we build? | Before any engineering | `/bet [idea]` |
| Design review | After design doc, before implementation | `/review` |
| Audit | After implementation, before acceptance | `/review` |
| Acceptance | After audit passes, before merge | `/review --delivery` |

### Periodic reviews

| Review | Cadence | Command |
|--------|---------|---------|
| Codebase health | Weekly or pre-milestone | `/health codebase` |
| Interface health | Monthly or post-UI-sprint | `/health interface` |
| Architecture | Quarterly or pre-major-feature | `/health architecture` |
| Product health | Monthly | `/health product` |
| Security health | Monthly | `/health security` |
| Docs drift | After a release or feature batch | `/health readme` |
| All inspections + summary | As needed | `/health` |
| Backlog hygiene | After a review cycle | `/health backlog` |
| Retrospective | After each epic or milestone closes | `/retro` |
| Outcome review (post-ship) | Quarterly or after a milestone closes | `/retro outcomes` |

### After each review

1. Fix any **Critical** findings before the next feature
2. File **Important** findings as tasks to address this cycle
3. Log **Track** findings (lowest tier — revisit next cycle); they compound if ignored
4. Update context docs if the review surfaced changes:
   - `/health product` updates PRODUCT.md
   - `/health interface` updates DESIGN.md
   - `/health architecture` updates CLAUDE.md
   - `/health readme` proposes a README.md diff
```

When writing the **Code conventions** block, detect the project's primary language(s) from the codebase and pre-fill sensible defaults plus the matching idiom linter — Ruff for Python, ESLint/Biome for JS/TS, golangci-lint for Go, Clippy for Rust, RuboCop for Ruby — then flag it for the user to refine.

## Step 6b — Propose the exorcist ward

[exorcist](https://github.com/jacquardlabs/exorcist)'s ward is a standing simplification
stance — smallest change that satisfies the request, search before writing, no abstraction
below two call sites, fix where a value enters — imported into CLAUDE.md as one `@` line.
Every `/build` executor and every dispatched worker reads CLAUDE.md
(`reference/worker-contract.md`, "Project conventions"), so the ward governs production
from the first task with no further wiring, and `code-auditor` defers to CLAUDE.md
conventions at `/review`, so the judge holds the same rules.

Check whether exorcist is installed the way `/studious:doctor` checks for viva: look for
`exorcist:ward` in this session's registered skill listing — never a file path.

- **Not installed:** one line — "exorcist not installed — ward skipped; install with
  `/plugin install exorcist@jacquardlabs-marketplace`, then run `/exorcist:ward`." — and
  move to Step 7. Never an error, never a Critical: the ward is optional.
- **Installed, CLAUDE.md already imports `@.claude/ward.md`:** note "ward already present"
  and move on.
- **Installed, not yet imported:** propose it — name the two writes (`.claude/ward.md`
  copied from the plugin; a `## Ward` section with `@.claude/ward.md` appended to
  CLAUDE.md) and the one-line why above — and run `/exorcist:ward` on the user's word in
  this same invocation, the same propose-then-write posture as Step 5b. Declined: note the
  choice; don't relitigate it.

## Step 7 — Summary

Report what was created, what was populated, and what the user should review:
- PRODUCT.md — auto-populated sections and sections that need human input
- DESIGN.md — auto-populated sections and inconsistencies found
- README.md — created from scratch, or skipped because one already exists
- CLAUDE.md — sections added
- Review directories created
- Ward — installed, already present, declined, or exorcist not installed

Note that the plugin's PR-time gate reminder is already active (it ships with Studious as a `PreToolUse` hook — no per-project wiring needed) and fires a non-blocking confirmation when you run `gh pr create`. When `/review` and `/review --delivery` have recorded verdicts to the branch's ledger, the reminder names the specific gates that never ran, ran on a stale commit, or didn't pass.

Suggest the user review PRODUCT.md first (product principles and "not building" sections need human judgment), then DESIGN.md (anti-patterns section needs human input), then README.md if one was generated.
