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
line below it already uses) plus a scoped `(cd "${dir}" && ...)` around the read itself,
since `gate-ledger`'s ledger-file lookup is *also* cwd-anchored, not just its branch
inference. It joins `SCOPE_PROBES` below and inherits all four generic checks; its own
error-signalling half (`ledgerAuditPrior` failing loudly instead of degrading to
`hasNarrowableVerdict:false`) gets dedicated executed-fixture tests further down, since
that half is a caller-side behavior no prompt-text assertion can observe.
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
    """`gate-ledger`'s ledger-*directory* lookup is also cwd-anchored (`repo_root()`
    walks up from cwd), not just its branch inference — `--branch` alone fixes one
    half of the bug. The read itself must run inside `(cd "${dir}" && ...)`.
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


def _run_ledger_audit_prior(agent_findings: dict | None, *, agent_throws: bool = False) -> dict:
    """Executes the real `ledgerAuditPrior` (plus the `ledgerScopeCheckPrompt` it
    calls, extracted verbatim like every other fixture in this file) under Node,
    with `agent` stubbed to return canned findings instead of really dispatching.
    Reports whether the returned promise rejected, and its message or resolved value.
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
{agent_body}
ledgerAuditPrior({json.dumps(PROBE_DIR)}, 'label', 'phase')
  .then(value => {{ console.log(JSON.stringify({{ threw: false, value }})) }})
  .catch(err => {{ console.log(JSON.stringify({{ threw: true, message: err.message }})) }})
"""
    return _run_node(script)


def test_ledger_audit_prior_throws_loudly_on_a_reported_read_error():
    """A read that honestly reports an error (wrong cwd, a failed cd, an unresolvable
    branch) must fail loudly, not fold into `hasNarrowableVerdict:false` and silently
    downgrade a narrowed retry to a full round (#261's core acceptance criterion).
    """
    result = _run_ledger_audit_prior({"hasNarrowableVerdict": False, "error": "cd failed: no such directory"})
    assert result["threw"], (
        f"ledgerAuditPrior swallowed a reported command error into a silent "
        f"hasNarrowableVerdict:false instead of failing loudly: {result}"
    )
    assert PROBE_DIR in result["message"], (
        "the thrown error should name the worktree whose read failed, for diagnosis: "
        f"{result}"
    )


def test_ledger_audit_prior_still_returns_null_for_a_genuinely_empty_ledger():
    """Regression: a well-formed, error-free `hasNarrowableVerdict:false` (the
    legitimate "nothing to narrow" case) must still degrade quietly to null — only a
    reported error is loud, not every non-narrowable verdict.
    """
    result = _run_ledger_audit_prior({"hasNarrowableVerdict": False})
    assert not result["threw"], f"a genuine non-narrowable verdict must not throw: {result}"
    assert result["value"] is None


def test_ledger_audit_prior_still_fails_closed_on_a_died_dispatch():
    """Regression: the dispatch itself dying (agent() throwing) is a different,
    already-established fail-closed-to-null case — untouched by this fix, and must
    stay that way (a died mechanical fact-check must never crash the story)."""
    result = _run_ledger_audit_prior(None, agent_throws=True)
    assert not result["threw"], f"a died dispatch must degrade quietly, not throw: {result}"
    assert result["value"] is None
