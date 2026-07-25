#!/usr/bin/env bash
# Release one of this repo's two plugins — studious at the root, jig under plugins/jig.
#
# Each plugin owns a semantic-release config and a tag prefix, so the two version lines
# stay independent inside one tree. This script is the gate in front of each: a plugin is
# only released when its own files changed since its own last tag, so a studious-only push
# never cuts a jig release and vice versa. semantic-release's commit-type analysis still
# decides *whether* and *how far* to bump; this only decides which line is eligible.
#
# Writes `plugin_released=true|false` to $GITHUB_OUTPUT when running under Actions.
# Deliberately NOT `released`: semantic-release writes a key by that name itself, and
# with two plugins sharing one job a collision resolves to whichever ran last — so the
# marketplace notification would key off the wrong plugin's outcome.
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
  echo "plugin_released=$1" >>"${GITHUB_OUTPUT:-/dev/null}"
}

# Ancestry-based, not lexical: the most recent tag on this line reachable from HEAD.
last_tag=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || true)

if [ -z "$last_tag" ]; then
  # Fail closed. semantic-release derives the current version from the last matching
  # tag, not from the manifest — so with no tag reachable it restarts the line at
  # 1.0.0, commits that to the manifest, and publishes it. On a plugin already
  # shipping 1.7.0 that is a silent version regression that reaches the marketplace.
  #
  # This branch is reachable exactly once per plugin: the push that first brings it
  # into the tree. Seeding the tag is a deliberate human step, and refusing here is
  # what reserves the window for it — release.yml runs on the merge push itself,
  # leaving no gap to hand-tag in.
  cat >&2 <<EOF
$name: no ${tag_prefix}* tag is reachable from HEAD, so semantic-release would
restart this plugin's version line at 1.0.0 rather than continue it. Refusing.

Seed the line at the version the manifest already carries, then re-run:

  git tag ${tag_prefix}\$(jq -r .version <path-to>/.claude-plugin/plugin.json) HEAD
  git push origin ${tag_prefix}<version>
  gh release create ${tag_prefix}<version> --notes "Seed the $name version line."
EOF
  emit false
  exit 0
else
  if [ -z "$(git diff --name-only "$last_tag..HEAD" -- "$@")" ]; then
    echo "$name: no changes under [$*] since $last_tag — skipping."
    emit false
    exit 0
  fi
  echo "$name: changes since $last_tag — evaluating a release."
fi

before=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || echo none)

# Capture the exit code rather than letting `set -e` take the script out. `version`
# tags, pushes, AND (upload_to_vcs_release) attaches the GitHub Release in one command,
# so it can fail *after* the tag is already pushed. Dying there would leave the step
# with no `plugin_released` output while the version line had in fact moved — the
# marketplace would never be told about a release that really happened.
rc=0
semantic-release -c "$config" version || rc=$?
after=$(git describe --tags --abbrev=0 --match "${tag_prefix}*" 2>/dev/null || echo none)

if [ "$before" = "$after" ]; then
  echo "$name: no release (still $after)."
  emit false
  exit "$rc"
fi

# The tag moved, so this is a release whatever else went wrong. Record that first.
echo "$name: released $after (was $before)."
emit true

if [ "$rc" -ne 0 ]; then
  echo "$name: semantic-release exited $rc after tagging $after — the tag is pushed but the release may be incomplete." >&2
  exit "$rc"
fi

semantic-release -c "$config" publish
