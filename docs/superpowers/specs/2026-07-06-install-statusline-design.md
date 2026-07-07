# Design: `/install-statusline` — gate status in the Claude Code statusline

**Date:** 2026-07-06
**Status:** Approved

## Problem

Gate state (`audit`, `acceptance`) currently only surfaces via the PR-time hook and by
explicitly asking `/work-on` or reading `gate-ledger status`. There's no passive,
always-visible signal of where the current branch stands relative to its gates.

## Goal

An optional, standalone installer (`/install-statusline`) that wires a terse gate-status
segment into the user's statusline for the current project, without clobbering whatever
statusline command they already have configured.

## Constraints from the platform (verified, not assumed)

- `${CLAUDE_PLUGIN_ROOT}` does **not** expand inside `statusLine.command` — confirmed by
  the plugins-reference docs' variable-substitution list (hooks/MCP/LSP only, statusline
  absent) and independently by [anthropics/claude-code#64074](https://github.com/anthropics/claude-code/issues/64074),
  where another plugin author hit this exact wall building a statusline plugin and worked
  around it with a `SessionStart` hook that re-pins an absolute path every session.
- A plugin's `bin/` is documented as added to the **Bash tool's** PATH only. Nothing
  documents this extending to the statusline subprocess (which Claude Code spawns
  directly, not through the Bash tool) — treat it as unavailable.
- Consequently, whatever `command` we install must resolve its own absolute path at
  **render time**, not at install time — the plugin's cache path is versioned
  (`~/.claude/plugins/cache/<marketplace>/studious/<version>/bin`) and changes on every
  `/plugin update`.
- Plugin manifests cannot declare a primary `statusLine` at all (only
  `agent`/`subagentStatusLine`) — the only way to wire this up is a command that writes
  the user's own settings file.

## Approach

Project-local install, dynamic path discovery, no new hook (rejected alternatives:
global install, and a `SessionStart` re-pin hook — see PR discussion / brainstorming
transcript for tradeoffs).

### Components

**`bin/gate-ledger statusline`** (new subcommand)

Reuses `cmd_status`'s per-branch lookup logic (ledger dir, branch-mismatch detection,
pass-token table). Outputs a single terse line, or nothing:

- Ledger dir (`.studious/gates/`) doesn't exist at all → empty (studious never used here)
- No ledger file for the current branch, or branch mismatch → `audit— acceptance—`
- Per gate: `✓` (verdict is the pass token, sha matches HEAD), `⚠` (ran but stale, or
  returned a non-passing verdict), `—` (never ran)
- Example: `audit✓ acceptance—`

**`bin/studious-statusline`** (new executable)

1. Reads stdin JSON once.
2. If `.studious/statusline-prev-command` exists and is non-empty, runs its contents as a
   shell command with the same stdin, and passes its stdout through unchanged.
3. Calls `gate-ledger statusline` for the current branch (resolved via `cd` to
   `.workspace.current_dir` from the input JSON, falling back to the process cwd).
4. If step 3's output is non-empty, appends it to the last line of step 2's output with
   a ` | ` separator (or emits it alone if step 2 produced nothing).

**`bin/studious-statusline-install`** (new executable, `install`/`remove`)

Mechanical work lives here rather than inline in the command prompt, so it's unit
testable with the same bash-sandbox pattern as `gate-ledger` — `commands/install-statusline.md`
is a thin delegator that just invokes it by bare name (same PATH-injection precedent as
`gate-ledger` itself, commit `26cda7e`).

- Resolves the *effective* current `statusLine.command` by checking, in order:
  `.claude/settings.local.json` → `~/.claude/settings.json`. **Deliberately excludes**
  the shared, checked-in `.claude/settings.json` — capturing from it would let a repo
  author smuggle an arbitrary command into the persisted `.studious/statusline-prev-command`
  that later executes on every render (added post-review, `/gate-audit` finding). If a
  statusline is found only in the checked-in file, it's neither captured nor wrapped —
  install says so honestly rather than reporting "no previous statusLine found."
- If that command already contains `studious-statusline` (our own installed signature —
  the glob snippet always names it literally), report "already installed" and stop —
  idempotent re-run, never double-wraps.
- Otherwise, save the resolved command string to `.studious/statusline-prev-command`
  (create the file even if empty, so "no previous command" is distinguishable from "not
  yet installed").
- Write `.claude/settings.local.json`'s `statusLine.command` to a self-resolving snippet:
  glob `~/.claude/plugins/cache/*/studious/*/bin` — the wildcard covers both marketplace
  names (`jacquardlabs-marketplace` and `studious`, per the two install paths in
  README.md) — take the newest by version sort, and `exec` its `studious-statusline`. If
  no such path resolves, fall back to directly replaying
  `.studious/statusline-prev-command` inline, so a disabled/removed plugin degrades to
  the user's original statusline instead of going blank.
- `remove`: rewrite `.claude/settings.local.json`'s `statusLine` back to the saved
  previous command (or delete the key entirely if there wasn't one), then delete
  `.studious/statusline-prev-command`.

**`commands/install-statusline.md`** (new command, `/install-statusline`)

Prompt body just runs `studious-statusline-install` (or `studious-statusline-install
remove` when `$ARGUMENTS` is `remove`) and reports its output verbatim.

### Format

Symbols only, no `gates:` label — `audit✓ acceptance—`. Appended after any wrapped
command's output.

## Edge cases

| Case | Behavior |
|---|---|
| Plugin disabled/removed after install | Glob resolves to nothing → falls back to replaying the saved prev-command inline; no zombie/blank statusline |
| Studious never used in this project | `.studious/gates/` absent → segment silent |
| Gates never run on this branch | `audit— acceptance—` |
| `/install-statusline` run twice | Second run detects existing signature, no-ops with a message |
| No `jq`/`git` available | `gate-ledger statusline` degrades silently (empty), matching existing `cmd_status`/`cmd_record` behavior |

## Documentation updates

- **CLAUDE.md** (architecture invariants): the "recommend-only" bullet currently says the
  sole exception is `.studious/` state. `/install-statusline` writes to
  `.claude/settings.local.json` — Claude Code's own config, gitignored but outside
  `.studious/`. Call this out as a second, explicit exception.
- **README.md**: short mention of `/install-statusline` as an optional, per-project,
  non-invasive addition — probably near the gate-ledger/PR-hook paragraph.

## Testing

- Extend `tests/test_gate_ledger.sh`: `statusline` subcommand — pass/stale/never-run/
  branch-mismatch/no-ledger-dir/no-jq cases.
- New `tests/test_studious_statusline.sh`: `studious-statusline` compose-with-previous-command
  and fallback behavior, plus `studious-statusline-install` install/remove/idempotency
  cases (isolated via a sandboxed `$HOME` so tests never touch the real global settings).
- `shellcheck bin/studious-statusline bin/studious-statusline-install
  tests/test_studious_statusline.sh` alongside the existing `bin/gate-ledger` lint.

## Files touched

- `bin/gate-ledger` (new `statusline` subcommand)
- `bin/studious-statusline` (new file)
- `bin/studious-statusline-install` (new file)
- `commands/install-statusline.md` (new file)
- `tests/test_gate_ledger.sh` (extended)
- `tests/test_studious_statusline.sh` (new file)
- `.github/workflows/ci.yml` (wire new test file + shellcheck targets)
- `CLAUDE.md`, `README.md` (doc updates)

## What does not change

- `cmd_status`'s existing prose output (used by the PR-time hook) — untouched.
- No new hook, no `SessionStart` re-pinning.
- Global (`~/.claude/settings.json`) is never touched by the installer.
- `/work-on` phase is out of scope for this segment (gate ledger status only, per
  brainstorming decision).
