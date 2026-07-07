# /work-through Epic Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One new command, `/work-through`, that drives an entire milestone/epic through the existing gate flow using dispatched agents — plan-for-approval first, then autonomous DAG execution that escalates only judgment verdicts.

**Architecture:** Prompt-orchestrated command on top of the existing gates and work-file machinery. `bin/gate-ledger` grows four `epic-*` verbs for a new `.studious/epics/<slug>.json` store; stories reuse the unchanged `.studious/work/` files. The command is a scheduler in the main session (subagents can't nest), dispatching flat one-phase-one-story agents into per-story git worktrees, merging gated stories into an `epic/<slug>` integration branch.

**Tech Stack:** Bash + jq (`bin/gate-ledger`), Markdown prompt files, bash integration tests, markdownlint/check_references/validate_plugin CI.

**Spec:** `docs/superpowers/specs/2026-07-07-work-through-epic-orchestration-design.md`

## Global Constraints

- GitHub is read-only: never create/modify issues, never open PRs — `gh pr create` stays the user's.
- All new state lives in gitignored `.studious/` and is touched only through `gate-ledger` verbs.
- Verdict tokens come verbatim from `reference/gate-vocabulary.md` — never invent or respell one.
- Commands invoke `gate-ledger` by bare name — an existing test fails the suite if any `commands/*.md` uses `${CLAUDE_PLUGIN_ROOT}/bin/gate-ledger`.
- Retry cap: 2 fix cycles per gate per story. Default concurrency: 3.
- Branch naming: integration branch `epic/<slug>`; story branches `epic/<slug>--<story>` (a nested `epic/<slug>/<story>` name is impossible — git can't create a ref under an existing branch ref). Worktrees: `.studious/worktrees/<epic-slug>/<story-slug>`, epic checkout at `.studious/worktrees/<epic-slug>/__epic`.
- Never edit `version` in `.claude-plugin/plugin.json` — semantic-release owns it.
- Conventional commit messages (`feat:`, `test:`, `docs:`) — semantic-release derives releases from them.
- Before editing any file under `skills/`, invoke the `superpowers:writing-skills` skill (project rule).
- Don't fix pre-existing lint failures in files outside this change's scope.
- All work happens on branch `feat/work-through`, never on `main`.

---

### Task 1: Feature branch + commit spec and plan

**Files:**
- Commit (already on disk): `docs/superpowers/specs/2026-07-07-work-through-epic-orchestration-design.md`, `docs/superpowers/plans/2026-07-07-work-through-epic-orchestration.md`

**Interfaces:**
- Produces: branch `feat/work-through` that every later task commits to.

- [ ] **Step 1: Create the branch**

```bash
cd /Users/bryan/Projects/studious
git checkout -b feat/work-through
```

- [ ] **Step 2: Commit the design docs**

```bash
git add docs/superpowers/specs/2026-07-07-work-through-epic-orchestration-design.md \
        docs/superpowers/plans/2026-07-07-work-through-epic-orchestration.md
git commit -m "docs: add /work-through epic orchestration spec and plan"
```

(Leave the other untracked files under `docs/superpowers/` alone — they belong to other work.)

---

### Task 2: `gate-ledger` — `epic-set` and `epic-get`

**Files:**
- Modify: `bin/gate-ledger` (new `epic_dir`/`epic_file_init` helpers after `work_dir` at line 40; new `cmd_epic_set`/`cmd_epic_get` after `cmd_work_get`; dispatch + usage at lines 326–336)
- Test: `tests/test_gate_ledger.sh` (append before the final `echo "----"` block)

**Interfaces:**
- Consumes: existing helpers `have`, `slugify`, `ensure_gitignore`, `now_iso` in `bin/gate-ledger`.
- Produces: `gate-ledger epic-set --slug S [--title T] [--source SRC] [--goal G] [--branch B] [--premortem P] [--concurrency N] [--status ST]` (upsert; file init shape `{"schemaVersion":1,"slug":S,"status":"planning","stories":{}}`) and `gate-ledger epic-get --slug S` (prints the JSON, empty when absent). Epic file path: `.studious/epics/<slug>.json`. `epic_file_init(slug)` helper reused by Task 3.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gate_ledger.sh`, immediately before the final `echo "----"` line (the `$fakebin` directory is defined earlier in the file by the d11 block — reuse it):

```bash
# --- epic-set creates a slugged epic file with fields and defaults ---
d15=$(sandbox)
( cd "$d15" && "$LEDGER" epic-set --slug "Checkout Revamp!!" --title "Checkout revamp" \
    --source "milestone 4" --goal "Users can pay without leaving the cart" \
    --branch epic/checkout-revamp --concurrency 3 --status approved )
ef15="$d15/.studious/epics/checkout-revamp.json"
check "epic-set slugs the filename" "yes" "$([ -f "$ef15" ] && echo yes || echo no)"
check "epic-set stores title" "Checkout revamp" "$(jq -r '.title' "$ef15")"
check "epic-set stores goal" "Users can pay without leaving the cart" "$(jq -r '.goal' "$ef15")"
check "epic-set stores branch" "epic/checkout-revamp" "$(jq -r '.branch' "$ef15")"
check "epic-set stores concurrency as a number" "3" "$(jq '.concurrency' "$ef15")"
check "epic-set stores status" "approved" "$(jq -r '.status' "$ef15")"
check "epic-set initializes empty stories" "{}" "$(jq -c '.stories' "$ef15")"
check "epic-set stamps schemaVersion" "1" "$(jq -r '.schemaVersion' "$ef15")"
check "epic-set stamps createdAt" "yes" "$([ "$(jq -r '.createdAt' "$ef15")" != "null" ] && echo yes || echo no)"
contains "epic-set self-heals .gitignore" ".studious/" "$(cat "$d15/.gitignore")"

# --- epic-set upserts: later fields land, earlier fields survive ---
( cd "$d15" && "$LEDGER" epic-set --slug checkout-revamp --status running )
check "epic-set upsert moves status" "running" "$(jq -r '.status' "$ef15")"
check "epic-set upsert keeps title" "Checkout revamp" "$(jq -r '.title' "$ef15")"

# --- epic-get prints the epic file; empty when absent ---
out=$(cd "$d15" && "$LEDGER" epic-get --slug checkout-revamp)
contains "epic-get prints the epic file" '"slug": "checkout-revamp"' "$out"
check "epic-get empty when no epic exists" "" "$(cd "$d15" && "$LEDGER" epic-get --slug nope)"

# --- epic-set signals on stderr (but still returns 0) when jq is unavailable ---
d16=$(sandbox)
stderr16=$(cd "$d16" && PATH="$fakebin" "$LEDGER" epic-set --slug x 2>&1 1>/dev/null)
contains "epic-set signals on stderr when jq is unavailable" "gate-ledger: epic-set skipped (jq and git required)" "$stderr16"
check "epic-set does not create an epic file when jq is unavailable" "no" \
  "$([ -f "$d16/.studious/epics/x.json" ] && echo yes || echo no)"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bash tests/test_gate_ledger.sh`
Expected: FAILs on the new epic-set/epic-get checks (usage error → no file created), all pre-existing checks still `ok`.

- [ ] **Step 3: Implement `epic_dir`, `epic_file_init`, `cmd_epic_set`, `cmd_epic_get`**

In `bin/gate-ledger`, after `work_dir()` (line 40), add:

```bash
epic_dir() {
  # Same root-anchoring as ledger_dir, different store.
  local root
  if root=$(git rev-parse --show-toplevel 2>/dev/null); then
    printf '%s/.studious/epics' "$root"
  else
    printf '.studious/epics'
  fi
}
```

After `cmd_work_get` (before `cmd_work_list`), add:

```bash
epic_file_init() { # slug → ensures the epic file exists, echoes its path
  local slug="$1"
  local dir; dir=$(epic_dir)
  mkdir -p "$dir"
  local file; file="$dir/$slug.json"
  [ -f "$file" ] || printf '{"schemaVersion":1,"slug":"%s","status":"planning","stories":{}}' "$slug" > "$file"
  printf '%s' "$file"
}

cmd_epic_set() {
  local slug="" title="" src="" goal="" branch="" premortem="" concurrency="" status=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --slug)        slug="$2"; shift 2 ;;
      --title)       title="$2"; shift 2 ;;
      --source)      src="$2"; shift 2 ;;
      --goal)        goal="$2"; shift 2 ;;
      --branch)      branch="$2"; shift 2 ;;
      --premortem)   premortem="$2"; shift 2 ;;
      --concurrency) concurrency="$2"; shift 2 ;;
      --status)      status="$2"; shift 2 ;;
      *) echo "gate-ledger: unknown arg '$1'" >&2; return 2 ;;
    esac
  done
  if [ -z "$slug" ]; then
    echo "gate-ledger: --slug required" >&2
    return 2
  fi
  if ! have jq || ! have git; then
    echo "gate-ledger: epic-set skipped (jq and git required)" >&2
    return 0
  fi

  slug=$(slugify "$slug")
  if [ -z "$slug" ]; then
    echo "gate-ledger: --slug reduced to nothing after slugify" >&2
    return 2
  fi

  ensure_gitignore
  local file; file=$(epic_file_init "$slug")
  local dir; dir=$(epic_dir)
  local tmp; tmp=$(mktemp "$dir/.tmp.XXXXXX")
  trap 'rm -f "$tmp"' RETURN
  jq --arg title "$title" --arg src "$src" --arg goal "$goal" --arg branch "$branch" \
     --arg pm "$premortem" --arg conc "$concurrency" --arg status "$status" --arg t "$(now_iso)" \
     '.schemaVersion = (.schemaVersion // 1)
      | .createdAt = (.createdAt // $t)
      | .updatedAt = $t
      | (if $title  != "" then .title       = $title  else . end)
      | (if $src    != "" then .source      = $src    else . end)
      | (if $goal   != "" then .goal        = $goal   else . end)
      | (if $branch != "" then .branch      = $branch else . end)
      | (if $pm     != "" then .premortem   = $pm     else . end)
      | (if $conc   != "" then .concurrency = ($conc | tonumber) else . end)
      | (if $status != "" then .status      = $status else . end)' \
     "$file" > "$tmp" && mv "$tmp" "$file"
}

cmd_epic_get() {
  local slug=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --slug) slug="$2"; shift 2 ;;
      *) echo "gate-ledger: unknown arg '$1'" >&2; return 2 ;;
    esac
  done
  if [ -z "$slug" ]; then
    echo "gate-ledger: --slug required" >&2
    return 2
  fi
  slug=$(slugify "$slug")
  local file; file="$(epic_dir)/$slug.json"
  [ -f "$file" ] || return 0
  cat "$file"
}
```

In the dispatch `case` at the bottom, add before the `*)` line:

```bash
  epic-set)  shift; cmd_epic_set "$@" ;;
  epic-get)  shift; cmd_epic_get "$@" ;;
```

Extend the usage string's brace list with: `| epic-set --slug S [--title T] [--source SRC] [--goal G] [--branch B] [--premortem P] [--concurrency N] [--status ST] | epic-get --slug S`.

Also update the header comment block (lines 2–10) to name the third store: `.studious/epics/<epic-slug>.json  — per-epic plan and story DAG for /work-through (written via epic-set / epic-story-set; read via epic-get / epic-list).`

- [ ] **Step 4: Run tests to verify they pass**

Run: `bash tests/test_gate_ledger.sh`
Expected: `all gate-ledger tests passed`

- [ ] **Step 5: Shellcheck**

Run: `shellcheck bin/gate-ledger tests/test_gate_ledger.sh`
Expected: no output (clean).

- [ ] **Step 6: Commit**

```bash
git add bin/gate-ledger tests/test_gate_ledger.sh
git commit -m "feat: add epic-set and epic-get verbs to gate-ledger"
```

---

### Task 3: `gate-ledger` — `epic-story-set` and `epic-list`

**Files:**
- Modify: `bin/gate-ledger` (new `cmd_epic_story_set` after `cmd_epic_get`; `cmd_epic_list` after it; dispatch + usage)
- Test: `tests/test_gate_ledger.sh` (append after Task 2's tests, before the final `echo "----"` block)

**Interfaces:**
- Consumes: `epic_dir`, `epic_file_init` from Task 2; `slugify`, `have`, `now_iso`.
- Produces: `gate-ledger epic-story-set --epic E --slug S [--title T] [--source SRC] [--criteria C] [--deps "a,b"] [--gates "audit,acceptance"] [--status ST] [--reason R] [--worktree P] [--bump-retry GATE]` (upsert into `.stories[S]`; errors rc=2 with "no epic file" if the epic doesn't exist; new stories default `{status:"pending", deps:[], retries:{}}`; `--deps`/`--gates` split on commas with whitespace trimmed; `--bump-retry G` increments `.retries[G]`). `gate-ledger epic-list` prints one TSV row per epic: slug, status, landed/total, branch, title.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_gate_ledger.sh` after Task 2's tests (still using `$d15`/`$ef15`):

```bash
# --- epic-story-set requires an existing epic file ---
err=$(cd "$d15" && "$LEDGER" epic-story-set --epic missing-epic --slug s1 2>&1 1>/dev/null; echo "rc=$?")
contains "epic-story-set errors on unknown epic" "no epic file" "$err"
contains "epic-story-set exits 2 on unknown epic" "rc=2" "$err"

# --- epic-story-set adds a story with defaults ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --title "Cart API" \
    --source "issue #12" --criteria "POST /cart returns 201 with a cart id" \
    --gates "design,design-review,build,audit,acceptance" )
check "story lands under its slug" "Cart API" "$(jq -r '.stories["cart-api"].title' "$ef15")"
check "story stores criteria" "POST /cart returns 201 with a cart id" "$(jq -r '.stories["cart-api"].criteria' "$ef15")"
check "story status defaults to pending" "pending" "$(jq -r '.stories["cart-api"].status' "$ef15")"
check "story deps default to empty array" "[]" "$(jq -c '.stories["cart-api"].deps' "$ef15")"
check "story retries default to empty object" "{}" "$(jq -c '.stories["cart-api"].retries' "$ef15")"
check "story gates split to an array" "5" "$(jq '.stories["cart-api"].gates | length' "$ef15")"

# --- deps split on commas, trimming whitespace ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug checkout-ui --title "Checkout UI" \
    --deps "cart-api, payment-svc" )
check "deps split to a trimmed array" '["cart-api","payment-svc"]' "$(jq -c '.stories["checkout-ui"].deps' "$ef15")"

# --- story upsert: status/reason land, earlier fields survive ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api \
    --status parked --reason "audit: NEEDS DISCUSSION - auth model unclear" )
check "story upsert moves status" "parked" "$(jq -r '.stories["cart-api"].status' "$ef15")"
check "story upsert stores reason" "audit: NEEDS DISCUSSION - auth model unclear" "$(jq -r '.stories["cart-api"].reason' "$ef15")"
check "story upsert keeps title" "Cart API" "$(jq -r '.stories["cart-api"].title' "$ef15")"

# --- bump-retry increments a per-gate counter ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --bump-retry audit )
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug cart-api --bump-retry audit )
check "bump-retry increments the gate counter" "2" "$(jq '.stories["cart-api"].retries.audit' "$ef15")"

# --- epic-list summarizes landed/total per epic ---
( cd "$d15" && "$LEDGER" epic-story-set --epic checkout-revamp --slug checkout-ui --status landed )
out=$(cd "$d15" && "$LEDGER" epic-list)
contains "epic-list reports slug, status, and landed count" "$(printf 'checkout-revamp\trunning\t1/2')" "$out"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `bash tests/test_gate_ledger.sh`
Expected: FAILs on every new epic-story-set/epic-list check; Task 2's checks still `ok`.

- [ ] **Step 3: Implement `cmd_epic_story_set` and `cmd_epic_list`**

In `bin/gate-ledger`, after `cmd_epic_get`, add:

```bash
cmd_epic_story_set() {
  local epic="" slug="" title="" src="" criteria="" deps="" gates="" status="" reason="" worktree="" bump=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --epic)       epic="$2"; shift 2 ;;
      --slug)       slug="$2"; shift 2 ;;
      --title)      title="$2"; shift 2 ;;
      --source)     src="$2"; shift 2 ;;
      --criteria)   criteria="$2"; shift 2 ;;
      --deps)       deps="$2"; shift 2 ;;
      --gates)      gates="$2"; shift 2 ;;
      --status)     status="$2"; shift 2 ;;
      --reason)     reason="$2"; shift 2 ;;
      --worktree)   worktree="$2"; shift 2 ;;
      --bump-retry) bump="$2"; shift 2 ;;
      *) echo "gate-ledger: unknown arg '$1'" >&2; return 2 ;;
    esac
  done
  if [ -z "$epic" ] || [ -z "$slug" ]; then
    echo "gate-ledger: --epic and --slug required" >&2
    return 2
  fi
  if ! have jq || ! have git; then
    echo "gate-ledger: epic-story-set skipped (jq and git required)" >&2
    return 0
  fi

  epic=$(slugify "$epic")
  slug=$(slugify "$slug")
  if [ -z "$epic" ] || [ -z "$slug" ]; then
    echo "gate-ledger: --epic or --slug reduced to nothing after slugify" >&2
    return 2
  fi

  local file; file="$(epic_dir)/$epic.json"
  if [ ! -f "$file" ]; then
    echo "gate-ledger: no epic file for '$epic' (run epic-set first)" >&2
    return 2
  fi

  local dir; dir=$(epic_dir)
  local tmp; tmp=$(mktemp "$dir/.tmp.XXXXXX")
  trap 'rm -f "$tmp"' RETURN
  jq --arg s "$slug" --arg title "$title" --arg src "$src" --arg criteria "$criteria" \
     --arg deps "$deps" --arg gates "$gates" --arg status "$status" --arg reason "$reason" \
     --arg wt "$worktree" --arg bump "$bump" --arg t "$(now_iso)" \
     '.updatedAt = $t
      | .stories[$s] = ((.stories[$s] // {status: "pending", deps: [], retries: {}})
        | (if $title    != "" then .title    = $title    else . end)
        | (if $src      != "" then .source   = $src      else . end)
        | (if $criteria != "" then .criteria = $criteria else . end)
        | (if $deps     != "" then .deps     = ($deps  | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(. != ""))) else . end)
        | (if $gates    != "" then .gates    = ($gates | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(. != ""))) else . end)
        | (if $status   != "" then .status   = $status   else . end)
        | (if $reason   != "" then .reason   = $reason   else . end)
        | (if $wt       != "" then .worktree = $wt       else . end)
        | (if $bump     != "" then .retries[$bump] = ((.retries[$bump] // 0) + 1) else . end))' \
     "$file" > "$tmp" && mv "$tmp" "$file"
}

cmd_epic_list() {
  if ! have jq; then return 0; fi
  local dir; dir=$(epic_dir)
  local f
  for f in "$dir"/*.json; do
    [ -e "$f" ] || continue
    jq -r '[(.slug // "?"), (.status // "?"),
            (([.stories[] | select(.status == "landed")] | length | tostring) + "/" + (.stories | length | tostring)),
            (.branch // "-"), (.title // "-")] | @tsv' "$f" 2>/dev/null
  done
}
```

Dispatch entries (before `*)`):

```bash
  epic-story-set) shift; cmd_epic_story_set "$@" ;;
  epic-list)      shift; cmd_epic_list "$@" ;;
```

Extend the usage string with: `| epic-story-set --epic E --slug S [--title T] [--source SRC] [--criteria C] [--deps D] [--gates G] [--status ST] [--reason R] [--worktree P] [--bump-retry GATE] | epic-list`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `bash tests/test_gate_ledger.sh`
Expected: `all gate-ledger tests passed`

- [ ] **Step 5: Shellcheck**

Run: `shellcheck bin/gate-ledger tests/test_gate_ledger.sh`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add bin/gate-ledger tests/test_gate_ledger.sh
git commit -m "feat: add epic-story-set and epic-list verbs to gate-ledger"
```

---

### Task 4: `reference/epic-plan-contract.md`

**Files:**
- Create: `reference/epic-plan-contract.md`

**Interfaces:**
- Consumes: `reference/design-doc-contract.md` (tone/shape model), `agents/premortem-auditor.md` (referenced verifier).
- Produces: the contract `commands/work-through.md` (Task 5) cites for what an approvable plan contains.

- [ ] **Step 1: Write the file**

Create `reference/epic-plan-contract.md` with exactly this content:

```markdown
# Epic-plan contract — lookup data

`/work-through`'s plan piece proposes a decomposition; the user approves it. This file
names what an approvable plan must contain — the analogue of
`reference/design-doc-contract.md` one level up. A plan missing a required element isn't
a style nit: the driver schedules from this data, so a gap here becomes an unscheduled
or unjudgeable story later.

## Required elements

| Element | Why the driver needs it |
|---------|-------------------------|
| Epic goal statement | One sentence. The epic-finale `/gate-acceptance` judges the integrated result against it, not against any single story. |
| Stories | Each: a short slug, a title, and its source issue(s). Splitting or merging GitHub issues is proposed here, never applied to GitHub. |
| Acceptance criteria per story | What the story's `/gate-acceptance` run must be able to verify — concrete and observable. "Works" is not a criterion. |
| Dependency edges | The DAG the scheduler runs. Only real sequencing dependencies: an edge claims the downstream story cannot be designed or built until the upstream one lands. |
| Gate profile per story | Which of design → design-review → build → audit → acceptance run for this story. Default is all five. Audit is never trimmed. Trimming is proposed by the planner, decided by the user at approval. |
| Epic pre-mortem | Cross-story failure modes — integration seams, shared-schema drift, sequencing risk — written to `docs/studious/premortems/<epic-slug>-epic.md` and verified at the epic finale by `agents/premortem-auditor.md`. |
| Concurrency cap | How many stories may run at once. Default 3. |

## Approval

Approval is explicit — the user says so after seeing the full plan. Silence, a partial
comment, or "looks interesting" is not approval. What the user approves is what gets
recorded: if they trim, reorder, or drop stories, record the edited version. Approving
the plan is the batched should-we-build for every story in it — no per-story decide
gate runs later. A story added mid-flight gets its own scoped decide pass and explicit
approval of its DAG placement before it joins the schedule.
```

- [ ] **Step 2: Lint and reference-check**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py`
Expected: both exit 0.

- [ ] **Step 3: Commit**

```bash
git add reference/epic-plan-contract.md
git commit -m "feat: add epic-plan contract reference"
```

---

### Task 5: `commands/work-through.md`

**Files:**
- Create: `commands/work-through.md`

**Interfaces:**
- Consumes: `gate-ledger` verbs from Tasks 2–3 (exact flags as specified there), `reference/epic-plan-contract.md` (Task 4), `reference/gate-vocabulary.md`, `reference/design-doc-contract.md`, the four gate commands, `agents/premortem-auditor.md`.
- Produces: the `/work-through` command. Task 6's skill shim delegates to it by name.

- [ ] **Step 1: Write the command file**

Create `commands/work-through.md` with exactly this content:

````markdown
---
description: Drive a whole milestone or epic through the gate flow with dispatched agents — plan once for approval, then run everything runnable, stopping only for judgment calls
argument-hint: "[milestone, epic issue, or label] (omit to keep driving the epic in flight)"
allowed-tools: Read, Glob, Grep, Bash, Task, Write
---

# Work through an epic

Drive a whole milestone through the same gate flow `/work-on` walks one piece at a
time. This command owns scheduling — which stories run, in what order, and when a
verdict escalates to the user — never the gates' judgments and never the how of
building. Two modes, resolved by state rather than flags: no epic in flight → the plan
piece; an approved epic → the driver.

**The posture — non-negotiable:**

- **Gates are unbypassable.** Run the gate commands' workflows verbatim; never soften,
  reinterpret, or skip a verdict. Tokens are canonical in `reference/gate-vocabulary.md`.
- **Lanes stay separate.** Gate agents never build; worker agents never gate; the two
  never share context. A gate judges the diff and the doc, never a worker's transcript.
- **GitHub is read-only.** Never create or edit issues; never open PRs — after the
  finale the branch is the user's (`gh pr create`).
- **Judgment verdicts always stop the story** and wait for the user. Autonomy never
  absorbs a RETHINK, NEEDS DISCUSSION, or HOLD.
- **Nothing runs before the user approves the plan.**

Read PRODUCT.md at the project root first. If `gate-ledger` is not on `PATH`, stop —
this flow cannot run without recorded state. Say so and point at `/work-on` for the
supervised, evidence-first flow instead.

## Resolve the epic

`gate-ledger epic-list` shows epics in flight (slug, status, landed/total, branch, title).

- **`$ARGUMENTS` is empty** — if exactly one epic has status `approved`, `running`, or
  `ready`, drive it. If several, list them and ask which — don't guess. If none, invite
  `/work-through [milestone, epic issue, or label]`.
- **`$ARGUMENTS` matches an epic in flight** (slug or title) — drive that one.
- **Anything else starts a new epic.** Resolve it read-only with `gh`:
  - a milestone name or number → `gh issue list --milestone "<M>" --state open --json number,title,body,labels`
  - an issue reference → `gh issue view <N> --json number,title,body` (for an epic
    issue, follow its checklist and linked issues too)
  - a label → `gh issue list --label "<L>" --state open --json number,title,body,labels`

  Then run the plan piece.

## Plan piece — runs once, ends at approval

1. Read PRODUCT.md, DESIGN.md, and CLAUDE.md.
2. Propose a decomposition satisfying `reference/epic-plan-contract.md`: stories with
   slugs, source issues, acceptance criteria, dependency edges, a gate profile each, an
   epic goal statement, a concurrency cap, and an epic pre-mortem. Present the whole
   plan — the user can only approve what they can see.
3. Stop and iterate. The user trims, reorders, re-scopes, drops. Nothing is recorded
   and nothing runs until they explicitly approve.
4. On approval, record exactly what was approved. Derive `<slug>` from the epic title:

   ```bash
   gate-ledger epic-set --slug "<slug>" --title "<title>" --source "<milestone M | issue #N | label L>" \
     --goal "<goal statement>" --branch "epic/<slug>" --concurrency <cap> --status approved
   gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --title "<story title>" \
     --source "issue #N" --criteria "<criteria>" --deps "<dep-a,dep-b>" --gates "<profile>"
   ```

   (one `epic-story-set` per story), then:

   - Write the epic pre-mortem register to `docs/studious/premortems/<slug>-epic.md`
     and record it: `gate-ledger epic-set --slug "<slug>" --premortem "<path>"`.
   - Create the integration branch and its dedicated worktree — never touch the user's
     checkout:

     ```bash
     git branch "epic/<slug>"
     git worktree add ".studious/worktrees/<slug>/__epic" "epic/<slug>"
     ```

5. Close with the report block below. Driving starts on the next invocation — approval
   and execution never share one.

## Driver — every later invocation

If the epic's status is still `approved`, mark the run started:
`gate-ledger epic-set --slug "<slug>" --status running`. Then loop steps 1–4 until
nothing is runnable without the user.

### 1 · Reconcile — evidence first

For every story, recorded state must match evidence; evidence wins, and the files get
corrected when they disagree:

- Phase: `gate-ledger work-get --slug "<story>"`.
- Verdicts: `gate-ledger gate-get --branch "epic/<slug>--<story>"` — a passing verdict
  counts only at that branch's HEAD sha.
- Design doc: the work file's `designDoc` path exists on disk.
- Landed: the story's merge is actually on the epic branch
  (`git -C .studious/worktrees/<slug>/__epic log --oneline`); a story marked `landed`
  without its merge isn't landed.

### 2 · Schedule

Runnable = status `pending` or `running` ∧ every dep `landed` ∧ concurrent stories ≤
the epic's `concurrency`. `parked` and `dropped` stories never schedule; their
dependents wait.

### 3 · Dispatch — one agent, one phase, one story

On a story's first dispatch, create its work file, branch, and worktree:

```bash
gate-ledger work-set --slug "<story>" --title "<story title>" --source "epic:<slug>" \
  --branch "epic/<slug>--<story>" --phase design
git branch "epic/<slug>--<story>" "epic/<slug>"
git worktree add ".studious/worktrees/<slug>/<story>" "epic/<slug>--<story>"
```

Dispatch independent stories' phases in parallel — one message, multiple Task calls.
Each dispatched agent gets its story's context (title, criteria, design doc path,
worktree path) and nothing about other stories. Per phase:

- **design** — a worker agent authors a design doc in the story worktree satisfying
  `reference/design-doc-contract.md`, grounded in PRODUCT.md and the story's acceptance
  criteria. Record it: `gate-ledger work-set --slug "<story>" --design-doc "<path>"`.
- **design-review / audit / acceptance** — run that gate command's workflow as the
  agent, against the story worktree; the gate records its own verdict to the story
  branch's ledger, as always.
- **build** — a worker agent implements the design doc in the story worktree, following
  CLAUDE.md conventions, committing to the story branch. If Superpowers is installed
  the worker uses its plan/execute workflow; otherwise it builds directly.

### 4 · Advance on the verdict

The three-outcome shape in `reference/gate-vocabulary.md` drives every transition; log
each with `gate-ledger work-log --slug "<story>" --step <gate> --outcome "<verdict>"`:

- **Proceed** (`PROCEED TO PLAN`, `PASS`, `SHIP`) → the story's next profiled phase, no
  pause. A `SHIP` at story HEAD → merge: in the `__epic` worktree,
  `git merge --no-ff "epic/<slug>--<story>"`. On conflict, one merge-fixer agent
  attempt in that worktree; still conflicted → `git merge --abort`, park the story with
  reason `merge-conflict`. Merged →
  `gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --status landed` and
  `git worktree remove ".studious/worktrees/<slug>/<story>"` (keep the branch).
- **Fix and retry** (`REVISE`, `FIX AND RE-AUDIT`, `FIX AND RE-CHECK`) → first bump:
  `gate-ledger epic-story-set --epic "<slug>" --slug "<story>" --bump-retry <gate>`.
  If the counter now exceeds 2, park with reason `<gate>: retry cap`. Otherwise
  dispatch a fixer agent with the gate's findings (the fixer never re-runs the gate),
  then re-run the gate with a fresh agent.
- **Judgment** (`RETHINK`, `NEEDS DISCUSSION`, `HOLD`) → park immediately, no retry, no
  workaround: `epic-story-set --status parked --reason "<gate>: <verdict> — <one-line
  gate reasoning>"`. These verdicts exist to reach the user.

## Epic finale

When every story is `landed` or `dropped`, in the `__epic` worktree:

1. `/gate-audit` across the full epic diff (against the merge-base with the default
   branch) — the cross-story integration pass no per-story audit saw.
2. `/gate-acceptance` against the epic goal statement, not any single story.
3. `@agent-premortem-auditor` over the epic pre-mortem register.

Verdicts record to the epic branch's ledger — the PR-time hook reads the same file.
Mechanical failures get the same bounded fix cycle (2, then stop and surface). All
pass → `gate-ledger epic-set --slug "<slug>" --status ready`: recap every story's
verdict trail and remind the user the PR is theirs (`gh pr create` from the epic
branch).

## Skips and amendments

Gate profiles fixed at plan time are the only built-in skip mechanism. Mid-flight,
skip a gate only on the user's explicit say-so — log it
(`work-log --step <gate> --outcome SKIPPED`) and never on your own initiative.

Amendments go through the driver, never hand-edited state: dropping a story →
`epic-story-set --status dropped` (then re-evaluate dependents — a dependent of a
dropped story needs the user to confirm it still makes sense); adding a story → a
scoped plan piece for just that story (a `/gate-should-we-build` pass plus explicit
approval of its DAG placement) before it joins the schedule.

## Close every invocation the same way

End with exactly this shape and nothing after it:

```text
Epic: <slug> — <landed>/<total> landed, <parked> parked, <n> runnable next.
Needs you:
  - <story>: <gate> returned <verdict> — <one clause: what's needed>
Landed this run: <story — verdict trail>
Run /work-through when you're ready, or resolve the queue first.
```

Omit `Needs you:` when nothing is parked. When the epic reaches `ready`, the last line
becomes the `gh pr create` handoff; `stopped` states what ended it. A parked story is
always also a valid `/work-on` feature — say so when the queue is non-empty, so the
user knows they can take any story over by hand.

## Record keeping

All state goes through `gate-ledger` — `epic-set`, `epic-get`, `epic-list`,
`epic-story-set` for the epic; `work-set`, `work-log`, `work-get` for stories;
`gate-get` for verdicts. Never hand-edit or directly read the JSON files. Worktrees
live under `.studious/worktrees/<slug>/` — gitignored, one per running story plus
`__epic`, removed as stories land; `git worktree list` is the recovery tool when state
and disk disagree.
````

- [ ] **Step 2: Lint and reference-check**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py`
Expected: both exit 0. Also confirm the bare-name rule holds:

Run: `bash tests/test_gate_ledger.sh`
Expected: `all gate-ledger tests passed` (includes the no-`${CLAUDE_PLUGIN_ROOT}`-in-commands check).

- [ ] **Step 3: Commit**

```bash
git add commands/work-through.md
git commit -m "feat: add /work-through — drive a whole epic through the gate flow"
```

---

### Task 6: Skill shim `skills/run-the-milestone/SKILL.md`

**Files:**
- Create: `skills/run-the-milestone/SKILL.md`

**Interfaces:**
- Consumes: `/work-through` (Task 5) by name; `skills/continue-feature-work/SKILL.md` as the shape model.
- Produces: the natural-language trigger for epic runs.

- [ ] **Step 1: Invoke the writing-skills meta-skill**

Invoke `superpowers:writing-skills` before editing anything under `skills/` (project rule). Apply its guidance to the content below — if it conflicts, the meta-skill wins and this plan's text is the starting draft.

- [ ] **Step 2: Write the skill file**

Create `skills/run-the-milestone/SKILL.md` with this content:

```markdown
---
name: run-the-milestone
description: Use when the user asks Studious to drive an entire milestone or epic autonomously — "knock out this milestone", "run the whole epic", "work through milestone 4", "drive these issues to done as a batch". This routes to /work-through, which proposes a story plan for approval and then runs the gate flow across parallel story agents, stopping only for judgment calls. Do NOT use for a single feature or its next step (that's /work-on via continue-feature-work), for picking what to work on (that's /backlog-priorities), for evaluating one idea (that's the should-we-build gate), or for running a single gate.
---

# Run the milestone

The user wants a whole milestone or epic driven through the gate flow, not one piece
of one feature. Route that to the orchestrator.

Invoke the `/work-through` command — with the milestone, epic issue, or label the user
named, or with no argument to keep driving the epic already in flight. Do not
reimplement its logic here: the command owns plan approval, scheduling, dispatch, and
escalation.

Two things never move out of that command's control: nothing runs before the user
approves the plan, and judgment verdicts (RETHINK, NEEDS DISCUSSION, HOLD) park for
the user rather than retry. When an invocation finishes, surface its closing report
block and wait.
```

- [ ] **Step 3: Lint and reference-check**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py`
Expected: both exit 0.

- [ ] **Step 4: Commit**

```bash
git add skills/run-the-milestone/SKILL.md
git commit -m "feat: add run-the-milestone skill shim for /work-through"
```

---

### Task 7: Documentation — README, CONTRIBUTING, gate-vocabulary consumers

**Files:**
- Modify: `README.md` (insert a `###` section between "Or have Studious navigate" and "## CI mode (optional)")
- Modify: `CONTRIBUTING.md` (Structure conventions ~line 46, bin/ description line 32, Naming conventions line 52)
- Modify: `reference/gate-vocabulary.md` (consumers list, lines 27–34)

**Interfaces:**
- Consumes: names and behavior fixed in Tasks 2–6.
- Produces: user-facing and contributor-facing documentation for `/work-through`.

- [ ] **Step 1: Add the README section**

Insert after the "Or have Studious navigate" paragraph (currently ends line 75), before "## CI mode (optional)":

```markdown
### Or run a whole milestone

`/work-through [milestone, epic issue, or label]` scales the flow up a level. The first
run reads the milestone's issues (read-only) and proposes a story plan — dependency
order, acceptance criteria per story, which gates each story needs, an epic-level
pre-mortem — then stops for your approval; nothing runs before it. Every run after
that drives: agents design, build, and gate stories in parallel worktrees (3 at once
by default), stories that pass their gates merge into an `epic/<name>` integration
branch, and fix-it verdicts get at most 2 repair cycles with a fresh auditor each
time. Judgment verdicts — RETHINK, NEEDS DISCUSSION, HOLD — never retry: that story
parks for you while independent stories keep moving. When everything lands, the whole
epic diff gets a final audit plus an acceptance check against the epic's goal, and the
branch is yours (`gh pr create` — same ledger, same PR-time hook). Any parked story is
a normal `/work-on` feature, so you can always take one over by hand. Fair warning: an
epic run spends tokens like the 5–10 supervised flows it replaces.
```

- [ ] **Step 2: Update CONTRIBUTING.md**

Three edits:

1. Line 32, extend the `bin/` description to:
   `bin/          — Executables used by commands (e.g. gate-ledger for gate verdicts, /work-on's per-feature state, and /work-through's per-epic state)`
2. After the recommend-only bullet (line 46), add:

   ```markdown
   - **Workers never gate; gates never build.** `/work-through` dispatches worker agents (design docs, implementation, fixes) and gate agents (the existing gate commands) as separate agents with no shared context. A worker must never record a verdict; a gate agent must never write code. The `.studious/` exception above extends to `/work-through`: it records epic and story flow state to the same local, gitignored stores.
   ```

3. Line 52, extend the commands-are-actions bullet's list: change `` `work-on` (flow navigation, one piece at a time) `` to `` `work-` (flow navigation: `work-on` one piece at a time, `work-through` a whole epic) ``.

- [ ] **Step 3: Update gate-vocabulary consumers**

In `reference/gate-vocabulary.md`, add to the consumers bullet list (after the `commands/work-on.md` bullet):

```markdown
- `commands/work-through.md`'s driver — advances on proceed tokens, bounds retries on
  fix-and-retry tokens, and parks the story on stop/rethink tokens.
```

Also add `skills/run-the-milestone` to the skill-shim bullet's parenthetical list.

- [ ] **Step 4: Lint and reference-check**

Run: `npx -y markdownlint-cli2 && uv run --no-project python scripts/check_references.py`
Expected: both exit 0.

- [ ] **Step 5: Commit**

```bash
git add README.md CONTRIBUTING.md reference/gate-vocabulary.md
git commit -m "docs: document /work-through in README, CONTRIBUTING, and gate vocabulary"
```

---

### Task 8: Full validation sweep

**Files:**
- None created; runs the complete CI-equivalent suite.

**Interfaces:**
- Consumes: everything above.
- Produces: a branch ready for the user to open a PR from.

- [ ] **Step 1: Run the full local check suite**

```bash
npx -y markdownlint-cli2
uv run --no-project python scripts/check_references.py
uv run --no-project python scripts/validate_plugin.py
uv run --no-project --with pytest pytest tests/python -v
bash tests/test_gate_ledger.sh
shellcheck bin/gate-ledger hooks/gate-reminder.sh tests/test_gate_ledger.sh
```

Expected: every command exits 0; pytest all green; `all gate-ledger tests passed`.

- [ ] **Step 2: Verify the branch contains only intended commits**

```bash
git log --oneline main..HEAD
```

Expected: exactly the commits from Tasks 1–7, nothing else.

- [ ] **Step 3: Hand off**

Do not open a PR — report the branch state to the user; the PR is theirs.

---

## Post-plan notes for the executor

- The heavy artifact is `commands/work-through.md` — its content is fully specified in
  Task 5; do not improvise structure or invent verdict tokens.
- If markdownlint flags line-length or style in the authored markdown, fix the new
  files to comply; never loosen `.markdownlint-cli2.jsonc`.
- Manual end-to-end validation (a 2–3 story toy milestone in a sandbox repo) is called
  for by the spec before release but is out of scope for this plan's automated tasks —
  flag it in the handoff message.
