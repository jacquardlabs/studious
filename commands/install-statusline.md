---
description: Install an optional statusline segment showing gate status (audit/acceptance) for this project
argument-hint: "[remove] (omit to install)"
allowed-tools: Bash
---

# Install statusline gate segment

Wire (or remove) a terse gate-status segment — `audit✓ acceptance—` — into this
project's Claude Code statusline. Optional and project-scoped: it writes only to
`.claude/settings.local.json` (gitignored, personal), never to your global
`~/.claude/settings.json` or a shared, checked-in `.claude/settings.json`. If you
already have a statusline command configured, it's preserved — the gate segment
is appended after it, nothing is replaced.

Run:

```bash
studious-statusline-install
```

Or, to remove it and restore whatever statusline command was configured before
(when `$ARGUMENTS` is `remove`):

```bash
studious-statusline-install remove
```

Report the tool's own output to the user verbatim — it already states what
happened (installed fresh, installed but found a shared statusLine it wouldn't
wrap, wrapped an existing local command, already installed, restored, or
nothing to remove).

If `studious-statusline-install` is not found (the plugin's `bin/` isn't on
`PATH` in this environment), tell the user the install couldn't run — do not
silently skip.
