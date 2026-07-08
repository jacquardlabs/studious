# Epic pre-mortem — gate-runtime-correctness

**Epic goal:** Every Studious gate and review resolves its shared contract, scope, and
routing correctly at runtime in a real consuming project — no reliance on the CI
symlink, no unscoped agent dispatch, no misrouted auto-delegation.

**Source:** milestone M1 · **Stories:** contract-injection (#88), acceptance-scope
(#89), agent-descriptions (#90), reference-tooling (#101).

These are the cross-story failure modes recorded at plan time. The epic finale's
`premortem-auditor` checks each against the integrated diff and reports
REALIZED / NOT REALIZED / CAN'T VERIFY.

## Failure modes

1. **Shared-file merge seam on `agents/*.md`.** contract-injection (#88) rewrites the
   bodies of the 13 contract agents; agent-descriptions (#90) rewrites the frontmatter
   `description:` of an overlapping set. Merged out of order or concurrently, one
   clobbers the other or conflicts.
   *Mitigation:* DAG edge agent-descriptions → contract-injection; #88 merges first;
   #90 builds on the post-#88 tree.

2. **Injection-pattern divergence.** contract-injection establishes a command-side
   context-assembly convention; acceptance-scope (#89) must adopt the same idiom, not
   invent a second way to compute-and-pass scope.
   *Mitigation:* DAG edge acceptance-scope → contract-injection; the finale audit
   checks that gate-audit, deep-review, and gate-acceptance share one injection shape.

3. **CI symlink still masks the gap.** `scripts/run_gate_audit_fixtures.py` symlinks
   `reference/` into the fixture repo, so a #88 fix validated *with* that symlink would
   pass while real consuming projects still fail.
   *Mitigation:* #88's acceptance criterion mandates validation with no `reference/`
   symlink present.

4. **Ratchet churn (#101).** Adding `reference/**` to markdownlint triggers a one-time
   violation sweep; if that sweep edits files another story also touches, integration
   seam.
   *Mitigation:* reference-tooling has no dependents and lands early as its own commit;
   #88 moves content into `reference/` afterward.

5. **Trimmed-gate blind spot.** Three stories run without design-review; a dropped
   contract block or a subtle prompt regression could slip past a thin per-story pass.
   *Mitigation:* audit is never trimmed; the epic finale re-audits the full integrated
   diff against the merge-base.

6. **Auto-delegation over-narrowing (#90).** Tightening agent descriptions to
   disambiguate routing could over-constrain and silently stop a legitimate invocation.
   *Mitigation:* acceptance verifies both routing directions — periodic vs gate-invoked.
