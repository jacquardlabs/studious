#!/usr/bin/env bash
# Integration tests for bin/gate-ledger. Requires git + jq.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LEDGER="$ROOT/bin/gate-ledger"
fails=0

check() { # description, expected, actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1"; echo "       expected: $2"; echo "       actual:   $3"; fails=$((fails + 1))
  fi
}
contains() { # description, needle, haystack
  case "$3" in
    *"$2"*) echo "ok   - $1" ;;
    *) echo "FAIL - $1"; echo "       expected substring: $2"; echo "       in: $3"; fails=$((fails + 1)) ;;
  esac
}

sandbox() { # create a throwaway git repo, echo its path
  local d; d=$(mktemp -d)
  git -C "$d" init -q
  git -C "$d" config user.email t@t.t
  git -C "$d" config user.name t
  git -C "$d" commit -q --allow-empty -m init
  git -C "$d" checkout -q -b feat/foo
  printf '%s' "$d"
}

# --- record writes the expected shape ---
d=$(sandbox)
( cd "$d" && "$LEDGER" record --gate audit --verdict PASS )
f="$d/.studious/gates/feat-foo.json"
check "record creates branch-slug ledger file" "yes" "$([ -f "$f" ] && echo yes || echo no)"
check "record stores verdict token" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "record stores branch name" "feat/foo" "$(jq -r '.branch' "$f")"
check "record stores HEAD sha" "$(git -C "$d" rev-parse --short HEAD)" "$(jq -r '.gates.audit.sha' "$f")"

# --- record self-heals .gitignore ---
contains "record adds .studious/ to .gitignore" ".studious/" "$(cat "$d/.gitignore")"
check "ledger is gitignored (not in status)" "" "$(cd "$d" && git status --porcelain .studious 2>/dev/null)"

# --- second record upserts (latest wins, second gate added) ---
( cd "$d" && "$LEDGER" record --gate acceptance --verdict SHIP )
check "upsert keeps audit" "PASS" "$(jq -r '.gates.audit.verdict' "$f")"
check "upsert adds acceptance" "SHIP" "$(jq -r '.gates.acceptance.verdict' "$f")"

# --- status: both passing at HEAD ---
out=$(cd "$d" && "$LEDGER" status)
contains "status reports clean pass" "proceed" "$out"

# --- status: missing gate ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" record --gate audit --verdict PASS )
out=$(cd "$d2" && "$LEDGER" status)
contains "status names the missing gate" "acceptance never ran" "$out"

# --- status: non-passing verdict ---
d3=$(sandbox)
( cd "$d3" && "$LEDGER" record --gate audit --verdict "FIX AND RE-AUDIT" )
( cd "$d3" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(cd "$d3" && "$LEDGER" status)
contains "status surfaces non-passing audit" "FIX AND RE-AUDIT" "$out"

# --- status: stale sha ---
d4=$(sandbox)
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && "$LEDGER" record --gate acceptance --verdict SHIP )
( cd "$d4" && git commit -q --allow-empty -m more )
out=$(cd "$d4" && "$LEDGER" status)
contains "status flags stale gate" "re-run" "$out"

# --- status: no ledger -> empty (hook uses default) ---
d5=$(sandbox)
out=$(cd "$d5" && "$LEDGER" status)
check "status empty when no ledger" "" "$out"

# --- hook surfaces the ledger reason and always asks ---
HOOK="$ROOT/hooks/gate-reminder.sh"
d6=$(sandbox)
( cd "$d6" && "$LEDGER" record --gate audit --verdict PASS )
hook_out=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh pr create"}}')
contains "hook decision is ask" '"permissionDecision": "ask"' "$hook_out"
contains "hook reason names missing acceptance" "acceptance never ran" "$hook_out"

# --- hook stays silent for non-PR commands ---
hook_noop=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"ls -la"}}')
check "hook ignores non-PR commands" "" "$hook_noop"

# --- hook matches spacing variants that would evade a literal-string grep ---
hook_spacing=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"gh  pr   create"}}')
contains "hook matches gh pr create with irregular spacing" '"permissionDecision": "ask"' "$hook_spacing"

# --- hook still matches when the phrase is embedded in a longer command ---
hook_embedded=$(cd "$d6" && CLAUDE_PLUGIN_ROOT="$ROOT" \
  bash "$HOOK" <<<'{"tool_input":{"command":"git log --grep=\"gh pr create\""}}')
contains "hook matches gh pr create embedded in a longer command" '"permissionDecision": "ask"' "$hook_embedded"

# --- command prompts invoke the ledger via ${CLAUDE_PLUGIN_ROOT}, not a bare name ---
# Plugins don't add bin/ to PATH, so a bare `gate-ledger ...` in a command prompt
# is "command not found" at runtime. Every invocation must resolve the script path.
bare=$(grep -rnE '^[[:space:]]*gate-ledger ' "$ROOT/commands" 2>/dev/null || true)
check "no command invokes gate-ledger without \${CLAUDE_PLUGIN_ROOT}" "" "$bare"

# --- record from a subdirectory still anchors the ledger at the repo root (#55) ---
d7=$(sandbox)
mkdir -p "$d7/sub/dir"
( cd "$d7/sub/dir" && "$LEDGER" record --gate audit --verdict PASS )
check "record from a subdirectory writes the ledger at the repo root" "yes" \
  "$([ -f "$d7/.studious/gates/feat-foo.json" ] && echo yes || echo no)"
check "record from a subdirectory does not write under the subdirectory" "no" \
  "$([ -f "$d7/sub/dir/.studious/gates/feat-foo.json" ] && echo yes || echo no)"
out=$(cd "$d7" && "$LEDGER" status)
contains "status run from repo root sees a ledger written from a subdirectory" "acceptance never ran" "$out"

# --- record stamps schemaVersion, and preserves it on upsert (#55) ---
f7="$d7/.studious/gates/feat-foo.json"
check "record sets schemaVersion on the new file" "1" "$(jq -r '.schemaVersion' "$f7")"
( cd "$d7/sub/dir" && "$LEDGER" record --gate acceptance --verdict SHIP )
check "record preserves schemaVersion on upsert" "1" "$(jq -r '.schemaVersion' "$f7")"

# --- status treats a branch-slug collision as no record, not a stale/wrong verdict (#41) ---
d9=$(sandbox)
( cd "$d9" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d9" && "$LEDGER" record --gate acceptance --verdict SHIP )
f9="$d9/.studious/gates/feat-foo.json"
# Simulate the collision: feat/foo and feat-foo both slug to feat-foo.json. Rewrite
# the stored .branch to a different branch than the one we're actually on.
tmp9=$(mktemp)
jq '.branch = "feat-foo"' "$f9" > "$tmp9" && mv "$tmp9" "$f9"
out=$(cd "$d9" && "$LEDGER" status)
contains "branch-slug collision reports audit as never ran" "audit never ran on this branch" "$out"
contains "branch-slug collision reports acceptance as never ran" "acceptance never ran on this branch" "$out"

# --- gc prunes ledgers for branches that no longer exist, keeps live ones (#42) ---
d10=$(sandbox)
( cd "$d10" && "$LEDGER" record --gate audit --verdict PASS )
stale10="$d10/.studious/gates/ghost-branch.json"
printf '{"schemaVersion":1,"branch":"ghost/branch","gates":{}}' > "$stale10"
out=$(cd "$d10" && "$LEDGER" gc)
contains "gc reports the removed stale ledger" "removed stale ledger: ghost-branch.json (branch ghost/branch no longer exists)" "$out"
check "gc deletes the stale ledger file" "no" "$([ -f "$stale10" ] && echo yes || echo no)"
check "gc keeps the ledger for a live branch" "yes" \
  "$([ -f "$d10/.studious/gates/feat-foo.json" ] && echo yes || echo no)"

# --- record signals on stderr (but still returns 0) when jq is unavailable (#43) ---
d11=$(sandbox)
fakebin=$(mktemp -d)
for tool in bash git date mktemp grep mv mkdir rm cat; do
  src=$(command -v "$tool" 2>/dev/null) || continue
  ln -sf "$src" "$fakebin/$tool"
done
stderr11=$(cd "$d11" && PATH="$fakebin" "$LEDGER" record --gate audit --verdict PASS 2>&1 1>/dev/null)
contains "record signals on stderr when jq is unavailable" "gate-ledger: record skipped (jq and git required)" "$stderr11"
check "record does not create a ledger file when jq is unavailable" "no" \
  "$([ -f "$d11/.studious/gates/feat-foo.json" ] && echo yes || echo no)"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all gate-ledger tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
