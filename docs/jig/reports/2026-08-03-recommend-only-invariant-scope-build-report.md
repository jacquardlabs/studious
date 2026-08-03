# Build report — recommend-only-invariant-scope (issue #257)

Branch: `fix/recommend-only-invariant-scope`. This story rescoped CLAUDE.md's "recommend-only" invariant (false as written — false on `/studious-init`, `/finish`, `/build`, `/handback`) into three self-documenting bullets, corrected `CONTRIBUTING.md`'s restated copy and `reference/decision-journal-format.md`'s false commit-scope claim, and (same branch, explicit user request) qualified every actionable `/design`/`/plan`/`/build`/`/finish` dispatch instruction with the `studious:` prefix a bare form collides on.

## cctx footer

cctx not installed in this environment — session-cost footer and harvest offer skipped. Install with `pipx install cctx-cli` to enable for future `/finish` runs.

## Follow-ups

0 issues drafted, 0 filed. `PLAN.md`'s 3 Not-here follow-ups were reviewed: item 1 (carry the Success-metrics check forward) was folded into the durable pre-mortem register during `/gate-audit` and into this PR's body directly, not filed as an issue; item 2 (post the PRODUCT.md:193-194 finding as a comment on existing issue #255) is the human's own action, not something this flow files; item 3 (the ~9-file site sweep, un-parking #247) is already tracked by existing issues #255 and #247. 0 NOTES stubs found.

## Proposed decision patch (not applied)

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -182,6 +182,10 @@
 - **Commands are actions:** an action prefix + target — `gate-`, `review-`/`deep-review`, `extract-`, `backlog-`, `work-on`.
 - **Agents are a 1:1 reviewer or a role:** periodic project-scoped reviewers share their command's `review-*` name; changeset specialists are `<domain>-auditor` (rule/technical checks) or `<domain>-reviewer` (human-judgment checks).
 - **Skills are named for the intent they detect**, not the command they call. Keep `description` triggers conservative — list what they should NOT match so a gate never fires unwanted.
+- **Qualify a skill's own name with `studious:` in any text that tells a human to dispatch or re-invoke it** — `/studious:design`, never bare `/design`. Claude Code built-ins can collide with a bare skill name (`/design` does, confirmed live — it routes to an unrelated built-in, not this plugin's skill), and the qualified form works whether or not a given name currently collides, so it costs nothing to use everywhere. Applies to `/design`, `/plan`, `/build`, `/finish`, `/coach` today; check any newly-shipped skill name against Claude Code's current built-in command list before assuming it's safe bare (#257 found this missed in five different files on the first pass, including the one line a skill speaks aloud to a user).
 - **Pin `model` and `effort` by stakes**, per the split in `CONTRIBUTING.md` — `model` moves the per-token rate, `effort` moves the turn count, and they are set independently. `opus` for high-stakes reasoning and human judgment; `sonnet`/`haiku` for recommend-only work with no merge gate behind it. **`inherit` is a known defect, not a cheap tier** ([#136](https://github.com/jacquardlabs/studious/issues/136)): it resolves to the session model, so the same branch can be judged by two different models on two different days. Don't add new `inherit` agents, and don't drop a merge-blocking agent's tier without an A/B (`tests/ab/README.md`).
```

## Gate history

- `should-we-build`: BUILD
- `design-review`: REVISE → REVISE → REVISE → PROCEED TO PLAN (4 rounds — each caught a genuinely new gap: a missing carve-out, a false "gates never commit" claim, `/work-through`'s git plumbing, then a `.gitignore`-self-heal citation and a name-vs-predicate gap)
- `build`: BUILT (4/4 tasks PASS, 3 load-bearing Inspector CLEAR, 1 leaf task correctly skipped; one real mid-build defect caught and fixed — `Done means` items were mis-tiered `script` against non-executable markdown files, which `verify` executes as literal shell commands)
- `audit`: PASS (2 rounds — round 1 found 1 Confirmed Critical, a false citation baked into the invariant's own replacement text, plus several convergent Important findings about the new bullets' own example lists being incomplete; round 2 confirmed all fixed, 0 Critical)
- `acceptance`: SHIP (2 rounds — round 1 found 1 BLOCKER (missed prefix sites in the skill's own handoff text) + 3 SHOULD FIX; round 2 found one more BLOCKER (the one line the coach speaks aloud to the user) plus 2 MINOR; all fixed and verified)

