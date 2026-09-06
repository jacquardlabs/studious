"""Regression tests for the scheduler-fixes story (issue #104).

`workflows/epic-driver.js` isn't importable (see the harness-shape comment in
`eslint.config.mjs`), so — per `test_contract_injection.py`'s precedent — these tests
extract the driver's real functions verbatim and run them via a `node -e` subprocess.

1. **Work-file collisions** — every `work-set`/`work-log`/`work-get` call site (never
   `epic-story-set`, already scoped by its own `--epic` arg) must key on `workSlug(story)`,
   the epic-qualified slug also printed in `parkedThisRun`/`landedThisRun`, so
   `/next "<printed slug>"` resolves the right work file. `workSlug`'s round trip through
   `bin/gate-ledger`'s `slugify()` is already covered by `tests/test_gate_ledger.sh`.
2. **Misleading cycle labels** — `unresolvedStories()` distinguishes true cycle members
   from stories merely downstream of a cycle, naming the blocking member(s).
3. **False cycle flags from duplicate deps** — a duplicate dependency entry must not
   inflate a story's indegree past its distinct dependency count.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from test_driver_crash_hardening import _extract_function, _run_node

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

# Gate-ledger verbs whose --slug must carry the epic-qualified slug. epic-story-set
# is excluded: it takes its own --epic argument (design doc's "Out of scope").
# Perf item 10 added acceptanceFanIn's own work-log call site, bumping this from 6.
WORK_VERB_SLUG_CALL_COUNT = 7
EPIC_STORY_SET_BARE_SLUG_COUNT = 4
# History: 6 -> 7 (#270 fix-and-recheck adds a parkedThisRun push for the
# VERIFY MISMATCH branch) -> 6 (#270 round 6 consolidates that branch through the
# shared park() helper) -> 9 (#268/#144/#297 canary story adds two heldThisRun
# pushes plus the `canary:` report field — held entries need the same
# /next-resolvable identity as parked ones) -> 11 (#304 review fixes add a
# heldThisRun push for a ceiling-refused resume-at-merge story, and a
# parkedThisRun push for an UNKNOWN DEP story).
DISPLAY_WORK_SLUG_COUNT = 11


def _work_slug_probe(epic_slug: str, story: str) -> str:
    source = DRIVER.read_text()
    fn = _extract_function(source, "workSlug")
    script = f"""
const slug = {json.dumps(epic_slug)}
{fn}
console.log(JSON.stringify({{ result: workSlug({json.dumps(story)}) }}))
"""
    return _run_node(script)["result"]


def _unresolved_probe(stories: dict) -> dict:
    """Run the driver's real `unresolvedStories()` against a fixture DAG.

    `stories` maps slug -> list of dep slugs; only `.deps` is read.
    """
    source = DRIVER.read_text()
    fn = _extract_function(source, "unresolvedStories")
    stories_js = json.dumps({slug: {"deps": deps} for slug, deps in stories.items()})
    script = f"""
const stories = {stories_js}
{fn}
const result = unresolvedStories()
const cycleDepsOf = {{}}
for (const s of result.downstream) cycleDepsOf[s] = result.cycleDepsOf(s)
console.log(JSON.stringify({{ cycle: result.cycle, downstream: result.downstream, cycleDepsOf }}))
"""
    return _run_node(script)


# ---------- 1. work-file collisions: qualified slug at every call site ----------


def test_work_verb_call_sites_use_the_qualified_slug() -> None:
    """Every work-set/work-log/work-get call site interpolates workSlug(story).

    Asserted as a property over the call sites present, not a hardcoded total —
    pinning at 7 broke the moment #237 added a legitimate eighth site. `>=` still
    guards against the check going vacuous if the interpolation is renamed.
    """
    source = DRIVER.read_text()
    qualified = source.count('--slug "${workSlug(story)}"')
    assert qualified >= WORK_VERB_SLUG_CALL_COUNT, (
        f"only {qualified} work-verb call sites use the qualified slug; expected at "
        f"least {WORK_VERB_SLUG_CALL_COUNT} — did an interpolation get renamed?"
    )
    # The real property: no work-verb call site keys on the *bare* story slug.
    # `workSlug(story)` and `workSlugVal` (a param already holding the qualified
    # slug, in acceptanceScopeCheckPrompt) both resolve to `<epic>--<story>`; only
    # `${story}` doesn't, and that's the collision this guard prevents.
    for verb in ("work-set", "work-get", "work-log"):
        for match in re.finditer(rf"{verb} --slug \"(\$\{{[^}}]+\}})\"", source):
            assert match.group(1) != "${story}", (
                f"{verb} keys a work file to the bare story slug — two epics with a "
                f"story of the same name would share one work file"
            )
            assert "workSlug" in match.group(1), (
                f"{verb} keys a work file to {match.group(1)}, which is not a known "
                f"epic-qualified slug expression"
            )


def test_epic_story_set_keeps_the_bare_slug() -> None:
    """epic-story-set is already scoped by --epic; it must NOT be qualified too."""
    source = DRIVER.read_text()
    count = source.count('epic-story-set --epic "${slug}" --slug "${story}"')
    assert count == EPIC_STORY_SET_BARE_SLUG_COUNT, (
        f"expected {EPIC_STORY_SET_BARE_SLUG_COUNT} epic-story-set call sites with "
        f"the bare story slug, found {count} — did epic-story-set get qualified too?"
    )


def test_reported_story_identifiers_match_the_work_file_key() -> None:
    """Every parkedThisRun/landedThisRun entry names the story with workSlug().

    The identifier printed in the "Needs you" queue must be the exact on-disk
    work-file key, or `/next "<the printed slug>"` can't resolve the feature.
    """
    source = DRIVER.read_text()
    count = source.count("story: workSlug(")
    assert count == DISPLAY_WORK_SLUG_COUNT, (
        f"expected {DISPLAY_WORK_SLUG_COUNT} parkedThisRun/landedThisRun entries "
        f"keyed by workSlug(...), found {count}"
    )
    assert "parkedThisRun.push({ story," not in source, (
        "a park entry still reports the bare story slug"
    )
    assert "landedThisRun.push({ story," not in source, (
        "a landed entry still reports the bare story slug"
    )


def test_work_slug_joins_epic_and_story() -> None:
    """workSlug() mirrors storyBranch()'s epic/<slug>--<story> separator."""
    assert _work_slug_probe("gate-ledger-robustness", "scheduler-fixes") == (
        "gate-ledger-robustness--scheduler-fixes"
    )


# ---------- 2 & 3. unresolvedStories(): cycle vs. downstream, duplicate deps ----------


def test_true_cycle_members_are_labeled_cycle() -> None:
    """A direct two-story cycle is reported as `cycle`, not `downstream`."""
    result = _unresolved_probe({"a": ["b"], "b": ["a"]})
    assert set(result["cycle"]) == {"a", "b"}
    assert result["downstream"] == []


def test_self_dependency_is_a_degenerate_cycle() -> None:
    """A story depending on itself is a one-node cycle, not silently ignored."""
    result = _unresolved_probe({"g": ["g"]})
    assert result["cycle"] == ["g"]
    assert result["downstream"] == []


def test_downstream_of_cycle_gets_a_distinct_accurate_reason() -> None:
    """A story stuck behind a cycle is `downstream`, never mislabeled `cycle`.

    Covers both a direct dependent of a cycle member and one several hops out.
    cycleDepsOf() must name the true cycle member transitively, not the
    intermediate downstream story.
    """
    result = _unresolved_probe({
        "a": ["b"], "b": ["a"],   # the cycle
        "c": ["a"],               # directly downstream
        "d": ["c"],                # transitively downstream (two hops from the cycle)
    })
    assert set(result["cycle"]) == {"a", "b"}
    assert set(result["downstream"]) == {"c", "d"}
    assert result["cycleDepsOf"]["c"] == ["a"]
    assert result["cycleDepsOf"]["d"] == ["a"]


def test_duplicate_dep_does_not_inflate_indegree_into_a_false_cycle() -> None:
    """A duplicate dep entry on an otherwise-resolvable story flags nothing.

    Regression: indegree was incremented once per listed dep (including
    duplicates) but decremented only once per distinct dep that settles, so a
    duplicate left indegree stuck above zero and the story falsely cycled.
    """
    result = _unresolved_probe({"e": [], "f": ["e", "e"]})
    assert result["cycle"] == []
    assert result["downstream"] == []


def test_unknown_dep_is_ignored_not_a_false_cycle() -> None:
    """A dep naming a story that isn't in the plan resolves the story fine."""
    result = _unresolved_probe({"h": ["does-not-exist"]})
    assert result["cycle"] == []
    assert result["downstream"] == []


def test_duplicate_dep_alongside_a_real_cycle_is_still_correctly_split() -> None:
    """Combines both bugs in one plan: the duplicate must not mask or fake a cycle."""
    result = _unresolved_probe({
        "a": ["b", "b"],  # duplicate dep, but a real cycle partner
        "b": ["a"],
        "c": ["e", "e"],  # duplicate dep, no cycle at all
        "e": [],
    })
    assert set(result["cycle"]) == {"a", "b"}
    assert result["downstream"] == []
    assert "c" not in result["cycle"] and "c" not in result["downstream"]
    assert "e" not in result["cycle"] and "e" not in result["downstream"]
