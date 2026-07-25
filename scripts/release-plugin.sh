#!/usr/bin/env bash
# Release one of this repo's two plugins — studious at the root, jig under plugins/jig.
#
# Each plugin owns a semantic-release config and a tag prefix, so the two version lines
# stay independent inside one tree. This script is the gate in front of each: a plugin is
# only released when its own files changed since its own last tag, so a studious-only push
# never cuts a jig release and vice versa. semantic-release's commit-type analysis still
# decides *whether* and *how far* to bump; this only decides which line is eligible.
#
# Writes `released=true|false` to $GITHUB_OUTPUT when running under Actions.
#
# Usage: release-plugin.sh <name> <config> <tag-prefix> <pathspec>...
set -euo pipefail

if [ "$#" -lt 4 ]; then
  echo "usage: $0 <name> <config> <tag-prefix> <pathspec>..." >&2
  exit 2
fi

name=$1
config=$2
tag_prefix=$3
shift 3

emit() {
  echo "released=$1" >>"${GITHUB_OUTPUT:-/dev/null}"
}

# Ancestry-based, not lexical: the most recent tag on this line reachable from HEAD.
last_tag=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || true)

if [ -z "$last_tag" ]; then
  # No line yet. Seeding it by hand (git tag "${tag_prefix}<current version>") before the
  # first run is what keeps semantic-release from restarting the version at 1.0.0.
  echo "$name: no ${tag_prefix}* tag yet — treating every commit as in scope."
else
  if [ -z "$(git diff --name-only "$last_tag..HEAD" -- "$@")" ]; then
    echo "$name: no changes under [$*] since $last_tag — skipping."
    emit false
    exit 0
  fi
  echo "$name: changes since $last_tag — evaluating a release."
fi

before=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || echo none)
semantic-release -c "$config" version
after=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || echo none)

if [ "$before" = "$after" ]; then
  echo "$name: no release (still $after)."
  emit false
  exit 0
fi

echo "$name: released $after (was $before)."
semantic-release -c "$config" publish
emit true
