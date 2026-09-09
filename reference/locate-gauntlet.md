# Locate gauntlet — the one root-discovery protocol

`${CLAUDE_PLUGIN_ROOT}` resolves to studious's root, never gauntlet's. Every door that
dispatches a `gauntlet:<judge>` learns gauntlet's root once per session by this protocol
and no other — it is stated here and cited from the doors, never restated (#410):

1. Invoke the `gauntlet:where` skill if it is in this session's skill listing — its first
   line is gauntlet's absolute root.
2. Else invoke `gauntlet:review` with `--help` as its argument. Gauntlet's door reads a
   non-numeric argument as a document path, finds no such file, and stops before any
   dispatch; the loaded text carries the root in its `python3 "…/scripts/dispatch.py"`
   lines, already substituted by the `${CLAUDE_PLUGIN_ROOT}` expansion every plugin
   command gets on load (gauntlet#80, "Consumer transport for a co-installed plugin").
3. If neither is in the listing, gauntlet is not installed. Stop with one line —
   "gauntlet is not installed — `/plugin install gauntlet@jacquardlabs-marketplace`, then
   re-run" — never a guess.

Record the result as `GAUNTLET_ROOT` for the rest of the session. **Never Glob the plugin
cache** for it — a path guessed from a cache layout is the convention-boundary failure #150
recorded.
