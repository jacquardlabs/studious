#!/usr/bin/env bash
# Integration tests for bin/studious-statusline and bin/studious-statusline-install.
# Requires git + jq.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RENDER="$ROOT/bin/studious-statusline"
# shellcheck disable=SC2034
INSTALL="$ROOT/bin/studious-statusline-install"
LEDGER="$ROOT/bin/gate-ledger"
fails=0

check() { # description, expected, actual
  if [ "$2" = "$3" ]; then
    echo "ok   - $1"
  else
    echo "FAIL - $1"; echo "       expected: $2"; echo "       actual:   $3"; fails=$((fails + 1))
  fi
}
# shellcheck disable=SC2329
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

json_input() { # dir -> stdin JSON the way Claude Code would send it
  printf '{"cwd":"%s","workspace":{"current_dir":"%s"}}' "$1" "$1"
}

# ============================================================
# bin/studious-statusline (render wrapper)
# ============================================================

# --- no previous command, no gate ledger: empty output ---
d1=$(sandbox)
out=$(json_input "$d1" | "$RENDER")
check "render is empty with nothing to show" "" "$out"

# --- gate segment alone when there's no previous command ---
d2=$(sandbox)
( cd "$d2" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d2" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(json_input "$d2" | "$RENDER")
check "render shows the gate segment alone" "audit✓ acceptance✓" "$out"

# --- previous command output passes through unchanged when there's no gate data ---
d3=$(sandbox)
mkdir -p "$d3/.studious"
printf 'echo "[Opus] some-dir"' > "$d3/.studious/statusline-prev-command"
out=$(json_input "$d3" | "$RENDER")
check "render passes through the previous command with no gate segment" "[Opus] some-dir" "$out"

# --- previous command output and gate segment are composed with a separator ---
d4=$(sandbox)
mkdir -p "$d4/.studious"
printf 'echo "[Opus] some-dir"' > "$d4/.studious/statusline-prev-command"
( cd "$d4" && "$LEDGER" record --gate audit --verdict PASS )
( cd "$d4" && "$LEDGER" record --gate acceptance --verdict SHIP )
out=$(json_input "$d4" | "$RENDER")
check "render composes the previous command output with the gate segment" \
  "[Opus] some-dir | audit✓ acceptance✓" "$out"

# --- the previous command receives the same stdin JSON ---
d5=$(sandbox)
mkdir -p "$d5/.studious"
printf 'jq -r .cwd' > "$d5/.studious/statusline-prev-command"
out=$(json_input "$d5" | "$RENDER")
check "render's previous command sees the same stdin JSON" "$d5" "$out"

echo "----"
if [ "$fails" -eq 0 ]; then echo "all studious-statusline tests passed"; exit 0; else echo "$fails failure(s)"; exit 1; fi
