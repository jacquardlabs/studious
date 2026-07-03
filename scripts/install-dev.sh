#!/usr/bin/env bash
# Install Studious for local development by symlinking commands, agents,
# skills, hooks, and bin into ~/.claude/. Safe to re-run — removes stale
# copies and refreshes symlinks. Pass --remove to uninstall the symlinks.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMMANDS_SRC="$REPO_DIR/commands"
AGENTS_SRC="$REPO_DIR/agents"
SKILLS_SRC="$REPO_DIR/skills"
HOOKS_SRC="$REPO_DIR/hooks"
BIN_SRC="$REPO_DIR/bin"
COMMANDS_DST="$HOME/.claude/commands"
AGENTS_DST="$HOME/.claude/agents"
SKILLS_DST="$HOME/.claude/skills"
HOOKS_DST="$HOME/.claude/hooks"
BIN_DST="$HOME/.claude/bin"

ACTION="install"
case "${1:-}" in
  "") ;;
  --remove) ACTION="remove" ;;
  *) echo "usage: $(basename "$0") [--remove]" >&2; exit 2 ;;
esac

link_files() {
  local src="$1"
  local dst="$2"
  local label="$3"
  local pattern="${4:-*.md}"

  mkdir -p "$dst"

  # Remove any plain files (non-symlinks) that exist in dst and match src
  for f in "$src"/$pattern; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    target="$dst/$name"
    if [[ -f "$target" && ! -L "$target" ]]; then
      echo "  removing stale copy: $label/$name"
      rm "$target"
    fi
  done

  # Create or refresh symlinks
  for f in "$src"/$pattern; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    target="$dst/$name"
    if [[ -L "$target" && "$(readlink "$target")" == "$f" ]]; then
      echo "  ok (already linked): $label/$name"
    else
      [[ -L "$target" ]] && rm "$target"
      ln -s "$f" "$target"
      echo "  linked: $label/$name"
    fi
  done
}

link_dirs() {
  local src="$1"
  local dst="$2"
  local label="$3"

  mkdir -p "$dst"

  for d in "$src"/*/; do
    [ -e "$d" ] || continue
    d="${d%/}"
    name="$(basename "$d")"
    target="$dst/$name"
    if [[ -d "$target" && ! -L "$target" ]]; then
      echo "  removing stale copy: $label/$name"
      rm -rf "$target"
    fi
    if [[ -L "$target" && "$(readlink "$target")" == "$d" ]]; then
      echo "  ok (already linked): $label/$name"
    else
      [[ -L "$target" ]] && rm "$target"
      ln -s "$d" "$target"
      echo "  linked: $label/$name"
    fi
  done
}

remove_files() {
  local src="$1"
  local dst="$2"
  local label="$3"
  local pattern="${4:-*.md}"

  [ -d "$dst" ] || return 0
  for f in "$src"/$pattern; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    target="$dst/$name"
    if [[ -L "$target" && "$(readlink "$target")" == "$f" ]]; then
      rm "$target"
      echo "  removed: $label/$name"
    fi
  done
}

remove_dirs() {
  local src="$1"
  local dst="$2"
  local label="$3"

  [ -d "$dst" ] || return 0
  for d in "$src"/*/; do
    [ -e "$d" ] || continue
    d="${d%/}"
    name="$(basename "$d")"
    target="$dst/$name"
    if [[ -L "$target" && "$(readlink "$target")" == "$d" ]]; then
      rm "$target"
      echo "  removed: $label/$name"
    fi
  done
}

if [[ "$ACTION" == "remove" ]]; then
  echo "Removing Studious dev symlinks for $REPO_DIR"
  echo ""
  echo "Commands:"
  remove_files "$COMMANDS_SRC" "$COMMANDS_DST" "commands"
  echo ""
  echo "Agents:"
  remove_files "$AGENTS_SRC" "$AGENTS_DST" "agents"
  echo ""
  echo "Skills:"
  remove_dirs "$SKILLS_SRC" "$SKILLS_DST" "skills"
  echo ""
  echo "Hooks:"
  remove_files "$HOOKS_SRC" "$HOOKS_DST" "hooks" "*"
  echo ""
  echo "Bin:"
  remove_files "$BIN_SRC" "$BIN_DST" "bin" "*"
  echo ""
  echo "Done."
  exit 0
fi

echo "Installing Studious from $REPO_DIR"
echo ""
echo "Commands:"
link_files "$COMMANDS_SRC" "$COMMANDS_DST" "commands"
echo ""
echo "Agents:"
link_files "$AGENTS_SRC" "$AGENTS_DST" "agents"
echo ""
echo "Skills:"
link_dirs "$SKILLS_SRC" "$SKILLS_DST" "skills"
echo ""
echo "Hooks:"
link_files "$HOOKS_SRC" "$HOOKS_DST" "hooks" "*"
echo ""
echo "Bin:"
link_files "$BIN_SRC" "$BIN_DST" "bin" "*"
echo ""
echo "Done. Restart Claude Code to pick up any new commands."
