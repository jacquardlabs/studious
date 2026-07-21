"""Regression tests for the scheduler-fixes story (issue #104).

`workflows/epic-driver.js` is not a conventionally importable module — see the
harness-shape comment at the top of `eslint.config.mjs` — so, following the
precedent `test_contract_injection.py` established, these tests extract the
driver's real, unmodified pure functions verbatim (balanced-brace scan, never
reimplemented) and execute them in a plain `node -e` subprocess. That proves
something about the actual shipped source, not a paraphrase of it.

Three defects, three test groups:

1. **Work-file collisions** — every `work-set`/`work-log`/`work-get` call site
   (never `epic-story-set`, already scoped by its own `--epic` argument) keys
   an epic-dispatched story to `workSlug(story)`, an epic-qualified slug — and
   the same qualified string is what gets printed back to the user in
   `parkedThisRun`/`landedThisRun`, so `/work-on "<the printed slug>"`
   resolves the exact on-disk work file. `workSlug`'s own round trip through
   `bin/gate-ledger`'s `slugify()` (which collapses the "--" separator to a
   single "-", same collision-acceptance precedent as `branch_slug()`
   collapsing '/') is exercised end-to-end by the existing gate-ledger suite's
   work-set/work-get slug tests (`tests/test_gate_ledger.sh`); nothing new is
   owed there since this story introduces no change to `bin/gate-ledger`.
2. **Misleading cycle labels** — `unresolvedStories()` reports true cycle
   members and stories merely downstream of a cycle as two distinct outcomes,
   naming the actual cycle member(s) a downstream story is blocked behind.
3. **False cycle flags from duplicate deps** — a duplicate dependency entry
   never inflates a story's indegree past its distinct dependency count, so an
   acyclic plan with a duplicate dep is never mistaken for a cycle.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER = REPO_ROOT / "workflows" / "epic-driver.js"

# The four gate-ledger verbs whose --slug argument must carry the epic-qualified
# slug. epic-story-set is deliberately excluded: it takes its own --epic argument
# and is out of scope for this story (see the design doc's "Out of scope").
# Perf item 10 added acceptanceFanIn's own work-log call site, bumping this from 6.
WORK_VERB_SLUG_CALL_COUNT = 7
EPIC_STORY_SET_BARE_SLUG_COUNT = 4
DISPLAY_WORK_SLUG_COUNT = 6


def _extract_function(source: str, name: str) -> str:
    """Extract a top-level ``function <name>(...) { ... }`` declaration verbatim.

    Balanced-brace scan from the function's own opening brace. Every ``${...}``
    interpolation inside the driver's template literals is individually balanced
    (a bare identifier, never a literal ``{``/``}``), so counting braces
    character-by-character finds the true closing brace correctly. Mirrors
    `test_contract_injection.py`'s helper of the same name and behavior.
    """
    marker = f"function {name}("
    start = source.index(marker)
    brace_open = source.index("{", start)
    depth = 0
    i = brace_open
    while True:
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    return source[start : i + 1]


def _run_node(script: str) -> dict:
    proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, f"node probe crashed: {proc.stderr}"
    return json.loads(proc.stdout)


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

    `stories` maps slug -> list of dep slugs; every story implicitly has an
    empty gate profile (irrelevant here — only `.deps` is read).
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
    """Every work-set/work-log/work-get call site interpolates workSlug(story)."""
    source = DRIVER.read_text()
    count = source.count('--slug "${workSlug(story)}"')
    assert count == WORK_VERB_SLUG_CALL_COUNT, (
        f"expected {WORK_VERB_SLUG_CALL_COUNT} work-verb call sites using the "
        f"qualified slug, found {count}"
    )
    # No bare-slug work-verb call site should remain.
    for verb in ("work-set", "work-get", "work-log"):
        assert f'{verb} --slug "${{story}}"' not in source, (
            f"{verb} still keys a work file to the bare story slug"
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

    Non-regression per the design doc: the identifier printed in the "Needs
    you" queue must be the exact on-disk work-file key, or `/work-on "<the
    printed slug>"` cannot resolve the feature it names.
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

    Covers both a story directly depending on a cycle member and one several
    hops further out — `unresolvedStories()`'s own comment on why a two-pass
    Kahn's over the induced subgraph would mislabel exactly this shape.
    cycleDepsOf() must still name the true cycle member transitively, not the
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

    Regression for the bug: indegree was incremented once per listed dep
    (including duplicates) but only ever decremented once per distinct
    dependency that settles, so a duplicate dep entry left indegree stuck
    above zero forever and the story was wrongly reported as cycling.
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
