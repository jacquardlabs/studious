"""Regression tests for issue #243: the driver's two mechanical scope probes
dictated their git commands in prose ("From ${dir}: ... git merge-base ...") instead of
anchoring each one with `git -C "${dir}"`.

Both probes are dispatched at `model: 'haiku', effort: 'low'` and both run with the
agent's own working directory, not `dir`. When that directory is a checkout sitting at
the default branch, `git diff --name-only <merge-base> HEAD` prints nothing and the probe
returns a well-formed, empty result:

* `acceptanceScopeCheckPrompt` → empty `files` → `acceptanceRound`'s `emptyChangeset`
  path skips product-review and gates the pre-mortem fallback on `files.length > 0`,
  capping every acceptance round at HOLD.
* `routingScopeCheckPrompt` → empty changed-file list → every `*Match` flag resolves
  false → `resolveAuditRoster` routes every specialist auditor **out**, silently
  narrowing the fan-out at both story and finale altitude.

`resolveRoutingMatchFlags` fails open only on a *died or unparseable* dispatch (`null` →
"route everything in"). A confidently-empty list is well-formed JSON, so it sails past
that guard — which is why the fix has to be in the prompt, not the caller.

Following this repo's established precedent (`test_contract_injection.py`,
`test_audit_first_round_routing.py`): the pure prompt builders are extracted verbatim from
`workflows/epic-driver.js` and executed standalone in a plain Node process.

Extended for issue #261: `ledgerScopeCheckPrompt` has the exact same cwd-dependent shape
("From ${dir}, run: gate-ledger gate-get") but for a `gate-ledger` invocation rather than a
`git` one — `gate-ledger` has no `-C` flag of its own, so anchoring it takes an explicit
`--branch` (computed via `git -C "${dir}"`, the same technique the merge-base check one
line below it already uses) plus a scoped `(cd "${dir}" && ...)` around the read itself.
That `cd` does NOT anchor the ledger *file* to this worktree specifically — bin/gate-
ledger's `repo_root()` resolves via `git rev-parse --git-common-dir`, which every linked
worktree of one repo shares, so they already point at the identical `.studious/gates`
regardless of which one cwd sits in. What the `cd` actually guards is cwd landing
outside this repo entirely, where `repo_root()` fails and `ledger_dir()` silently
degrades to a cwd-relative path instead of erroring (corrected 2026-07-28,
gate-acceptance round 2 non-blocking finding 3 — a prior round of this docstring stated
the ledger-file rationale incorrectly). It joins `SCOPE_PROBES` below and inherits all
four generic checks; its own error-signalling half (`ledgerAuditPrior` failing loudly
instead of degrading to `hasNarrowableVerdict:false`) gets dedicated executed-fixture
tests further down, since that half is a caller-side behavior no prompt-text assertion
can observe.
"""

from __future__ import annotations

import json
import re

import pytest
from test_driver_crash_hardening import (
    DRIVER,
    _extract_function,
    _run_node,
)
from test_epic_driver_decomposition import _extract_async_function

# A dir that is not the ambient checkout, so a prompt that leaks cwd-dependence is visible.
PROBE_DIR = "/tmp/probe-worktree"
PROBE_BASE = "main"
PROBE_SLUG = "some-epic--some-story"

# Every git invocation must carry its own -C. Anchored on the subcommand rather than on
# `git` alone, so prose about a "git command" is not mistaken for one.
_GIT_SUBCOMMANDS = (
    "diff|merge-base|rev-parse|log|show|status|worktree|branch|checkout|apply|commit|add|stash"
)
_UNANCHORED_GIT = re.compile(rf"\bgit\s+(?!-C\b)(?={_GIT_SUBCOMMANDS})\b")

# The cwd-dependent phrasing the fix replaced. Prose that tells an agent where to stand
# instead of pinning each command is the defect, even if a -C appears elsewhere.
_CWD_DIRECTIVE = re.compile(r"From\s+/tmp/probe-worktree[:,]")


def _build_prompt(fn_name: str, args: list[str]) -> str:
    source = DRIVER.read_text()
    fn = _extract_function(source, fn_name)
    script = f"""
{fn}
process.stdout.write(JSON.stringify({{ prompt: {fn_name}({", ".join(args)}) }}))
"""
    return _run_node(script)["prompt"]


SCOPE_PROBES = [
    ("acceptanceScopeCheckPrompt", [json.dumps(PROBE_DIR), json.dumps(PROBE_BASE), json.dumps(PROBE_SLUG)]),
    ("routingScopeCheckPrompt", [json.dumps(PROBE_DIR), json.dumps(PROBE_BASE)]),
    ("ledgerScopeCheckPrompt", [json.dumps(PROBE_DIR)]),
]


@pytest.mark.parametrize("fn_name,args", SCOPE_PROBES, ids=[p[0] for p in SCOPE_PROBES])
def test_every_git_command_in_a_scope_probe_is_anchored_to_its_worktree(fn_name, args):
    prompt = _build_prompt(fn_name, args)
    unanchored = _UNANCHORED_GIT.findall(prompt)
    assert not unanchored, (
        f"{fn_name} builds {len(unanchored)} git invocation(s) without `-C \"{PROBE_DIR}\"`. "
        "A haiku/low agent runs these in its own cwd, and an empty result is well-formed "
        "enough to pass every downstream guard (#243)."
    )


@pytest.mark.parametrize("fn_name,args", SCOPE_PROBES, ids=[p[0] for p in SCOPE_PROBES])
def test_a_scope_probe_pins_each_command_rather_than_naming_a_directory_to_stand_in(fn_name, args):
    prompt = _build_prompt(fn_name, args)
    assert not _CWD_DIRECTIVE.search(prompt), (
        f"{fn_name} still tells the agent to work *from* {PROBE_DIR} rather than pinning "
        "each command with -C. That phrasing is what #243 was: the agent is free to ignore it."
    )


@pytest.mark.parametrize("fn_name,args", SCOPE_PROBES, ids=[p[0] for p in SCOPE_PROBES])
def test_a_scope_probe_forbids_reporting_an_empty_result_it_did_not_observe(fn_name, args):
    """The prompt must say an empty result is only reportable when genuinely observed.

    Both callers read empty as a substantive fact — "this branch changed nothing" — so a
    probe that errored and shrugged is indistinguishable from a clean one.
    """
    prompt = _build_prompt(fn_name, args)
    assert "errored" in prompt and "empty" in prompt, (
        f"{fn_name} does not tell the agent to distinguish a genuinely empty result from a "
        "failed command. Downstream both read as 'nothing changed' (#243)."
    )


def test_the_probes_still_anchor_to_the_directory_they_were_handed():
    """Guards the fix itself: -C must interpolate `dir`, not a hardcoded or wrong value."""
    for fn_name, args in SCOPE_PROBES:
        prompt = _build_prompt(fn_name, args)
        assert f'git -C "{PROBE_DIR}"' in prompt, (
            f"{fn_name} carries a -C that does not interpolate the dir it was passed."
        )


# ---------- #261: ledgerScopeCheckPrompt's own anchor, gate-ledger has no -C ----------


def test_ledger_scope_check_never_calls_gate_get_without_an_explicit_branch():
    """`gate-ledger gate-get` with no `--branch` resolves the branch via cwd
    (`git rev-parse --abbrev-ref HEAD`) — exactly the cwd-dependence #243 fixed for
    git commands. `--branch` must be computed via the anchored `git -C` lookup and
    passed explicitly, never left to gate-ledger's own cwd inference.
    """
    prompt = _build_prompt("ledgerScopeCheckPrompt", [json.dumps(PROBE_DIR)])
    assert "gate-ledger gate-get --branch" in prompt, (
        "ledgerScopeCheckPrompt calls `gate-ledger gate-get` without an explicit "
        "--branch — its branch would be resolved from the agent's own cwd, not the "
        f"worktree it was handed ({PROBE_DIR})."
    )


def test_ledger_scope_check_scopes_the_gate_get_read_with_a_cd():
    """The read itself must run inside `(cd "${dir}" && ...)` — not because
    `gate-ledger`'s ledger-*directory* lookup is itself worktree-specific
    (`repo_root()` resolves via `git rev-parse --git-common-dir`, shared by every
    linked worktree of one repo, so `--branch` alone already fixes the branch half of
    the bug regardless of cwd), but because `repo_root()` still requires cwd to be
    inside *some* worktree of this repo at all. The `cd` guards a dispatched shell
    landing in an unrelated repo or none, where `repo_root()` fails outright and
    `ledger_dir()` silently degrades to a cwd-relative path instead of erroring.
    """
    prompt = _build_prompt("ledgerScopeCheckPrompt", [json.dumps(PROBE_DIR)])
    assert f'(cd "{PROBE_DIR}" && gate-ledger gate-get' in prompt, (
        f"ledgerScopeCheckPrompt does not scope its gate-get read to {PROBE_DIR} with "
        "a cd — gate-ledger has no -C of its own, so this is the only way to anchor "
        "its ledger-file lookup, as distinct from its branch lookup."
    )


def test_ledger_scope_check_forbids_the_error_key_on_a_successful_empty_read():
    """`ledgerAuditPrior` treats a truthy `.error` as a fail-loud signal (below), and
    that key is free text a haiku/low agent supplies — the prompt must tell it not to
    add "error" as commentary on an otherwise normal outcome (a genuinely empty
    ledger, an absent `.gates.audit`, a non-matching verdict, a failed merge-base
    check), or an over-helpful agent turns every legitimate non-narrowable verdict
    into a parked story. "Never trust prompt compliance alone" cuts both ways here:
    this assertion can't prove an agent won't do it, only that the prompt says not to.
    """
    prompt = _build_prompt("ledgerScopeCheckPrompt", [json.dumps(PROBE_DIR)])
    assert "ONLY when a command actually failed" in prompt, (
        "ledgerScopeCheckPrompt does not tell the agent to withhold the \"error\" key "
        "on a successful-but-empty read — an over-helpful agent could attach it as "
        "commentary and turn every legitimate hasNarrowableVerdict:false into a "
        "fail-loud park (#261)."
    )


# ---------- #261: ledgerAuditPrior fails loudly on a reported read error ----------

# This story's own branch, matching the shape storyBranch() computes
# (`epic/${slug}--${story}`) — used as `expectedBranch` in every fixture below unless a
# test deliberately supplies a different one to simulate a mismatch.
EXPECTED_STORY_BRANCH = "epic/some-epic--some-story"


def _run_ledger_audit_prior(
    agent_findings: dict | None,
    *,
    agent_throws: bool = False,
    expected_branch: str = EXPECTED_STORY_BRANCH,
) -> dict:
    """Executes the real `ledgerAuditPrior` (plus the `ledgerScopeCheckPrompt` it
    calls, extracted verbatim like every other fixture in this file) under Node,
    with `agent` stubbed to return canned findings instead of really dispatching, and
    `log` stubbed to capture its lines (the driver harness always supplies a real
    `log`; see `test_driver_crash_hardening.py`'s own `function log() {}` stub — this
    one records instead of discarding, so the degrade-to-null path's "fail loudly via
    log()" half is actually observable, not just asserted by code inspection).
    Reports whether the returned promise rejected, its message or resolved value, and
    every line `log()` was called with.
    """
    source = DRIVER.read_text()
    ledger_scope_fn = _extract_function(source, "ledgerScopeCheckPrompt")
    ledger_prior_fn = _extract_async_function(source, "ledgerAuditPrior")
    if agent_throws:
        agent_body = "async function agent() { throw new Error('dispatch died') }"
    else:
        findings_json = json.dumps(json.dumps(agent_findings)) if agent_findings is not None else "undefined"
        agent_body = f"async function agent() {{ return {{ findings: {findings_json} }} }}"
    script = f"""
{ledger_scope_fn}
{ledger_prior_fn}
const GATES = {{ audit: {{ retry: 'FIX AND RE-AUDIT' }} }}
const REPORT = {{ type: 'object', properties: {{ findings: {{ type: 'string' }} }}, required: ['findings'] }}
const LOGS = []
function log(line) {{ LOGS.push(line) }}
{agent_body}
ledgerAuditPrior({json.dumps(PROBE_DIR)}, {json.dumps(expected_branch)}, 'label', 'phase')
  .then(value => {{ console.log(JSON.stringify({{ threw: false, value, logs: LOGS }})) }})
  .catch(err => {{ console.log(JSON.stringify({{ threw: true, message: err.message, parkGate: err.parkGate || null, logs: LOGS }})) }})
"""
    return _run_node(script)


def test_ledger_audit_prior_throws_loudly_on_a_broken_worktree():
    """A read that honestly reports the worktree itself as unusable (`errorKind`
    `"worktree-broken"` — a failed cd, or the worktree not resolving at all) must
    fail loudly, not fold into `hasNarrowableVerdict:false` and silently downgrade a
    narrowed retry to a full round (#261's core acceptance criterion). This is the
    one `errorKind` where a park is honest: the real audit dispatch, which also runs
    inside this same worktree, could not have run there either.
    """
    result = _run_ledger_audit_prior(
        {"hasNarrowableVerdict": False, "error": "cd failed: no such directory", "errorKind": "worktree-broken"}
    )
    assert result["threw"], (
        f"ledgerAuditPrior swallowed a reported worktree-broken error into a silent "
        f"hasNarrowableVerdict:false instead of failing loudly: {result}"
    )
    assert PROBE_DIR in result["message"], (
        "the thrown error should name the worktree whose read failed, for diagnosis: "
        f"{result}"
    )
    assert result["parkGate"] == "ledger-scope-check", (
        "a throw from this mechanical pre-check must park under its own gate name, "
        "not 'audit' — the audit dispatch this throw pre-empts never ran "
        f"(fix-and-recheck finding 3): {result}"
    )


@pytest.mark.parametrize(
    "error_text,error_kind",
    [
        ("gate-ledger: command not found", "check-unavailable"),
        ("branch lookup printed the literal string HEAD", "check-unavailable"),
        ("branch lookup exited non-zero for an unrelated reason", "check-unavailable"),
        ("some future error this prompt has no name for yet", "a-kind-the-driver-does-not-recognize"),
        ("an old agent that predates the errorKind field", None),
    ],
    ids=["gate-ledger-off-path", "detached-head", "unresolvable-branch", "unrecognized-kind", "missing-kind"],
)
def test_ledger_audit_prior_degrades_loudly_instead_of_parking_on_non_worktree_errors(error_text, error_kind):
    """Every reported error OTHER than `"worktree-broken"` is this narrowing check's
    own limitation, not proof the story is unworkable (fix-and-recheck findings 1 and
    2): gate-ledger missing from PATH, a detached HEAD mid-rebase, an otherwise-
    unresolvable branch, an `errorKind` this driver doesn't recognize, and a report
    that omits `errorKind` entirely (an agent that hasn't adopted it) all take the
    same path — log it and degrade to null, a full unnarrowed round, never a park.
    Loud is not the same as fatal: a `log()` call still fires, satisfying "fail
    loudly" without treating "this check couldn't tell" as "nothing here can run".
    """
    findings = {"hasNarrowableVerdict": False, "error": error_text}
    if error_kind is not None:
        findings["errorKind"] = error_kind
    result = _run_ledger_audit_prior(findings)
    assert not result["threw"], (
        f"a non-worktree-broken error must degrade to null, not throw and park: {result}"
    )
    assert result["value"] is None
    assert result["logs"], (
        f"a reported error that degrades instead of throwing must still log loudly, "
        f"never disappear silently: {result}"
    )
    assert any(PROBE_DIR in line and error_text in line for line in result["logs"]), (
        f"the log line should name both the worktree and what was reported, for "
        f"diagnosis: {result}"
    )


def test_ledger_audit_prior_never_throws_on_a_narrowable_verdict_even_with_a_stray_error_key():
    """The BLOCKER fix-and-recheck reproduced: a fully valid `hasNarrowableVerdict:true`
    report carrying a stray `error` key (an over-helpful agent's commentary on an
    otherwise-successful read) must return the narrowed verdict, not throw and
    permanently park the story. `hasNarrowableVerdict` is checked before `error`
    is ever looked at. `resolvedBranch` is included here matching this story's own
    branch — an orthogonal precondition the round-3 fix below requires before any
    narrowing is trusted at all — so this fixture isolates the one thing it actually
    tests: the stray-error-key behavior, not branch confirmation.
    """
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": True,
            "sha": "abc1234",
            "blockingLanes": ["security"],
            "error": "just a note, everything succeeded",
            "resolvedBranch": EXPECTED_STORY_BRANCH,
        }
    )
    assert not result["threw"], (
        f"a valid narrowable verdict was discarded over a stray 'error' key instead of "
        f"winning outright: {result}"
    )
    assert result["value"] == {
        "verdict": "FIX AND RE-AUDIT",
        "sha": "abc1234",
        "blockingLanes": ["security"],
    }, result


def test_ledger_audit_prior_still_returns_null_for_a_genuinely_empty_ledger():
    """Regression: a well-formed, error-free `hasNarrowableVerdict:false` (the
    legitimate "nothing to narrow" case) must still degrade quietly to null — only a
    reported error is loud, not every non-narrowable verdict.
    """
    result = _run_ledger_audit_prior({"hasNarrowableVerdict": False})
    assert not result["threw"], f"a genuine non-narrowable verdict must not throw: {result}"
    assert result["value"] is None
    assert not result["logs"], f"a genuinely empty, error-free read must not log anything: {result}"


def test_ledger_audit_prior_still_fails_closed_on_a_died_dispatch():
    """Regression: the dispatch itself dying (agent() throwing) is a different,
    already-established fail-closed-to-null case — untouched by this fix, and must
    stay that way (a died mechanical fact-check must never crash the story)."""
    result = _run_ledger_audit_prior(None, agent_throws=True)
    assert not result["threw"], f"a died dispatch must degrade quietly, not throw: {result}"
    assert result["value"] is None


# ---------- gate-acceptance round 2 (fix-and-recheck SHOULD FIX 1 & 2): resolvedBranch ----------


def test_ledger_scope_check_requires_resolved_branch_in_every_returned_outcome():
    """`resolvedBranch` — the literal output of the FIRST, unambiguous `git -C`
    rev-parse command — must ride along on every one of the prompt's five returned
    JSON shapes (both `hasNarrowableVerdict:false` error outcomes, both plain
    `hasNarrowableVerdict:false` outcomes, and the `hasNarrowableVerdict:true` one), or
    `ledgerAuditPrior`'s mismatch check below has nothing to compare against on
    exactly the outcome where a #261-pattern wrong-cwd read is otherwise invisible: a
    well-formed, error-free `hasNarrowableVerdict:false`.
    """
    prompt = _build_prompt("ledgerScopeCheckPrompt", [json.dumps(PROBE_DIR)])
    missing = re.findall(r'\{"hasNarrowableVerdict":(?:true|false)(?!,"resolvedBranch")', prompt)
    assert not missing, (
        f"ledgerScopeCheckPrompt has {len(missing)} returned JSON shape(s) that don't "
        "carry \"resolvedBranch\" immediately after \"hasNarrowableVerdict\" — an agent "
        "following this prompt could omit it on some outcomes, leaving "
        "ledgerAuditPrior's mismatch check blind on exactly those."
    )
    narrowable_count = prompt.count('"hasNarrowableVerdict"')
    assert narrowable_count == 5, (
        "this assertion assumes the prompt still returns exactly 5 distinct JSON "
        f"shapes; it now returns {narrowable_count} — update the count above if that "
        "changed deliberately."
    )


def test_ledger_audit_call_site_passes_the_expected_story_branch():
    """The whole mechanical mismatch-detection mechanism is inert unless the driver's
    own call site hands `ledgerAuditPrior` this story's branch to compare against —
    guards against the function being fixed in isolation while its one caller is
    never updated to pass the new argument.
    """
    source = DRIVER.read_text()
    assert "ledgerAuditPrior(storyWorktree(story), storyBranch(story)," in source, (
        "runGate's ledgerAuditPrior call no longer passes storyBranch(story) as the "
        "expected branch — the mismatch check in ledgerAuditPrior always sees an "
        "unrelated or undefined value and can never fire."
    )


def test_ledger_audit_prior_degrades_loudly_on_a_resolved_branch_mismatch_with_no_error_key():
    """The AC's own literal failure mode: an agent that disregards the `-C`/`cd`
    anchoring still runs a real rev-parse and a real gate-get, just against the
    AMBIENT checkout — and can report a perfectly well-formed, error-free
    `hasNarrowableVerdict:false` with no hint anything went wrong. Only comparing the
    now-mandatory `resolvedBranch` against this story's own branch catches it; must
    degrade loudly (log fires, value null), never silently.
    """
    result = _run_ledger_audit_prior(
        {"hasNarrowableVerdict": False, "resolvedBranch": "epic/other-epic--other-story"}
    )
    assert not result["threw"], f"a resolved-branch mismatch must degrade, not park: {result}"
    assert result["value"] is None
    assert result["logs"], (
        f"a resolved-branch mismatch must still fail loudly via log(), never "
        f"disappear as a silent hasNarrowableVerdict:false: {result}"
    )
    assert any(
        PROBE_DIR in line and "epic/other-epic--other-story" in line and EXPECTED_STORY_BRANCH in line
        for line in result["logs"]
    ), f"the log line should name the worktree, the wrong branch, and the expected one: {result}"


def test_ledger_audit_prior_discards_a_narrowable_verdict_on_a_resolved_branch_mismatch():
    """A `hasNarrowableVerdict:true` report is not exempt from the mismatch check —
    checked BEFORE hasNarrowableVerdict is ever trusted, since applying a narrowed
    verdict read from the WRONG branch would fold some other story's `blockingLanes`
    into this one's re-audit, actively harmful rather than merely a wasted round.
    """
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": True,
            "sha": "abc1234",
            "blockingLanes": ["security"],
            "resolvedBranch": "epic/other-epic--other-story",
        }
    )
    assert not result["threw"], f"a mismatch must degrade, not throw: {result}"
    assert result["value"] is None, (
        f"a narrowed verdict read from the wrong branch must never be trusted, even "
        f"though hasNarrowableVerdict was true: {result}"
    )
    assert result["logs"], "a discarded mismatch must still log loudly"


def test_ledger_audit_prior_trusts_a_matching_resolved_branch():
    """Regression: when `resolvedBranch` matches this story's own branch, the
    pre-existing hasNarrowableVerdict handling proceeds exactly as before — the new
    check must not false-positive on the ordinary, correctly-anchored case."""
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": True,
            "sha": "abc1234",
            "blockingLanes": ["security"],
            "resolvedBranch": EXPECTED_STORY_BRANCH,
        }
    )
    assert not result["threw"], result
    assert result["value"] == {
        "verdict": "FIX AND RE-AUDIT",
        "sha": "abc1234",
        "blockingLanes": ["security"],
    }, result
    assert not result["logs"], "a matching resolvedBranch is not a mismatch and must not log"


def test_ledger_audit_prior_never_trusts_a_narrowable_verdict_with_no_resolved_branch():
    """Gate-acceptance round 3 (fix-and-recheck SHOULD FIX): the mismatch check above
    is truthy-gated (`resolvedBranch && ...`), so an omitted or empty `resolvedBranch`
    used to skip it entirely and reach hasNarrowableVerdict:true with zero cwd
    confirmation at all — the same #261-pattern risk as a known mismatch, just silent
    instead of caught. A narrowed verdict must now require a confirmed resolvedBranch
    (this story's own branch, or the detached-HEAD case) before it is ever trusted."""
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": True,
            "sha": "abc1234",
            "blockingLanes": ["security"],
        }
    )
    assert not result["threw"], f"an unconfirmed narrowing must degrade, not throw: {result}"
    assert result["value"] is None, (
        f"hasNarrowableVerdict:true with no resolvedBranch must never be trusted: {result}"
    )
    assert result["logs"], "an unconfirmed narrowing must still log loudly"


def test_ledger_audit_prior_treats_detached_head_as_not_a_mismatch():
    """`resolvedBranch: "HEAD"` (a detached checkout) is a distinct, already-named
    check-unavailable case, not a mismatch — the mismatch check must not fire on it
    and must leave the existing errorKind handling to degrade it as before."""
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": False,
            "resolvedBranch": "HEAD",
            "error": "branch lookup printed the literal string HEAD",
            "errorKind": "check-unavailable",
        }
    )
    assert not result["threw"], result
    assert result["value"] is None
    assert result["logs"], "the pre-existing check-unavailable degrade must still log"


def test_ledger_audit_prior_overrides_a_misattributed_worktree_broken_when_branch_matches():
    """Fix-and-recheck SHOULD FIX 2: a resolvedBranch that matches this story's own
    branch already proves `dir` resolves as a worktree — so a self-reported
    `errorKind:"worktree-broken"` alongside it is a misattributed guess (the agent
    saw an ambiguous shell error and could not tell whether the `cd` or `gate-ledger`
    itself failed). This must be overridden down to check-unavailable and degrade
    loudly, not throw and permanently park a healthy story.
    """
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": False,
            "resolvedBranch": EXPECTED_STORY_BRANCH,
            "error": "gate-ledger: command not found",
            "errorKind": "worktree-broken",
        }
    )
    assert not result["threw"], (
        f"a resolvedBranch match proves dir resolves as a worktree — a self-reported "
        f"worktree-broken here is a misattribution that must be overridden, not "
        f"trusted into a permanent park: {result}"
    )
    assert result["value"] is None
    assert result["logs"], "the overridden check-unavailable degrade must still log loudly"


def test_ledger_audit_prior_still_throws_worktree_broken_when_resolved_branch_is_empty():
    """Regression: the one case that still throws is a genuinely empty
    `resolvedBranch` (the FIRST, unambiguous rev-parse itself failing) alongside a
    self-reported `worktree-broken` — unambiguous, so the model's own classification
    is trustworthy here and the override in the test above does not apply."""
    result = _run_ledger_audit_prior(
        {
            "hasNarrowableVerdict": False,
            "resolvedBranch": "",
            "error": "cd failed: no such directory",
            "errorKind": "worktree-broken",
        }
    )
    assert result["threw"], result
    assert result["parkGate"] == "ledger-scope-check", result
