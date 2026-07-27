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
