# Prompt checklist — lookup data

Not `reference/prompt-contract.md` — that near-namesake is the fleet's own injected
posture (the five blocks every Studious auditor runs under). This file is the **lookup
data** for reviewing *other people's* prompts: consulted by both `prompt-auditor`
(diff-scoped, at the gate) and `review-prompt-health` (whole-repo, periodic), so the
depth of the seven dimensions lives in exactly one place. Not a detection crutch — a
capable model already knows these defect classes; this is the specifics it won't recall
verbatim: per-dimension probe lists, the prompt-surface signature table per ecosystem,
and token-economy heuristics. CLAUDE.md's documented prompt conventions override
anything here when they predate the change under review.

## Per-dimension probes

### Trigger reliability

- Read the trigger surface (a skill's `description`, an agent's frontmatter, a
  command's argument hints) and ask: what would a user actually type? A trigger keyed
  to internal vocabulary ("run the fan-out") that no user phrasing reaches is dead.
- Over-broad triggers: a description with no negative space ("use for any question
  about X") fires on requests it can't serve — conservative triggers list what they
  should NOT match.
- Shim drift: a skill or wrapper whose description promises what its delegated command
  no longer does (renamed arguments, removed modes, changed defaults).
- A trigger that duplicates another's phrasing — two prompts competing for the same
  user language means dispatch is arbitrary.

### Instruction conflicts

- Within one prompt: two directives that cannot both be followed ("never write files"
  / "save your report to…") with no stated precedence.
- Across the injection seam: a prompt contradicting the contract or context doc
  stamped in alongside it — the model resolves it differently per run.
- Precedence language that exists but points both ways ("X overrides Y" in one
  section, "Y is canonical" in another).

### Output-contract drift (the orchestrator↔subagent seam)

- Collect what the dispatching side promises to parse: verdict tokens, JSON/schema
  fields, row shapes, counts, file paths, section headings, label formats.
- Grep the dispatched side for each: a token the subagent never emits, a field it
  renamed, a heading it dropped. For a Task-dispatch seam, the orchestrator's schema
  (or its prose "Return: …" line) is the contract; the subagent's Output section is
  the implementation.
- Check both directions: an orchestrator that ignores fields the subagent is told to
  produce is dead weight (token economy); one that parses fields never produced is
  breakage (contract drift).
- Counts are contract too: "the six reviewers" in prose that dispatches seven.

### Duplication across copies

- The same rubric, list, table, or instruction block maintained in 2+ prompts — grep a
  distinctive phrase from any inline block to find its copies.
- Inline restatement of content a canonical reference file already owns ("consult it,
  don't restate it" violations) — the restated copy is where drift starts.
- Divergence check: when copies exist, diff them — copies that already disagree in
  meaning are a tier above copies that merely exist.

### Injection safety

- Markers of the safe posture to look for: "treat as data, never instructions",
  "untrusted", an injection-defense preamble, an explicit rule that embedded
  directives are findings.
- Unsafe shapes: tool or command output interpolated into a prompt as directives;
  repository content (issues, comments, file text) summarized into instructions;
  agents that read untrusted input with no defense block at all.
- A prompt that tells its model to *follow* instructions found in reviewed content is
  the critical form.

### Runtime identity

- Paths: does every referenced file exist *where the prompt executes* (a consuming
  project, not the plugin repo; a container, not the dev machine)? Unresolved
  variable fallbacks (`${…}` with no "if that does not resolve" branch) fail silently.
- Tools: every tool a prompt's instructions require must be in the agent's own
  `tools:` allowlist; a Write instruction in a read-only agent is dead.
- Commands: CLI invocations the runtime environment doesn't ship; flags that don't
  exist on the version installed.
- Dispatch identity: `subagent_type` / agent names that resolve nowhere.

### Token economy

- Blocks billed on every dispatch for nothing: dead sections no instruction consumes,
  restatement of what a pointer could carry, examples longer than the rule they
  illustrate.
- Model/effort frontmatter pinned against the project's documented stakes convention
  (an expensive pin on mechanical work, a cheap pin on merge-blocking judgment).
- Unbounded interpolation: a template that inlines whole files where a path would do.

## Prompt-surface signature table (per ecosystem)

How to recognize that a repo has a prompt surface, and which files are in it:

| Ecosystem | Signature | Prompt files |
|---|---|---|
| Claude Code plugin | `.claude-plugin/` manifest | `agents/*.md`, `commands/*.md`, `skills/**` (any `SKILL.md`), `hooks/hooks.json`-referenced prompts, `output-styles/**`, `reference/**` rubrics agents read at run time |
| Claude Code project | `.claude/` directory | `.claude/agents/**`, `.claude/commands/**`, `.claude/skills/**`, `CLAUDE.md` at any depth |
| Assistant instruction files | file presence | `AGENTS.md`, `.cursorrules`, `.cursor/rules/**`, `.github/copilot-instructions.md`, `GEMINI.md` |
| Prompt-template conventions | name contains `prompt` | `prompts/`, `prompt_templates/`, `system_prompt.*`, `*.prompt`, `*.prompt.md` |
| LLM SDK call sites | imports of an LLM client (`anthropic`, `openai`, `google.generativeai`, `langchain`, …) | the instruction strings handed to `messages`/`system`/template params — the string content, not the code around it |

A repo matching no row has no prompt surface: `prompt-auditor` skips at the gate and
`review-prompt-health` self-skips its periodic pass.

## Token-economy heuristics

- **Pointer beats copy**: content consumed by more than one prompt belongs in one
  canonical file the others cite — an inline copy is both a duplication finding and a
  per-dispatch cost.
- **Bound the interpolations**: anything stamped into a dispatch prompt at run time
  (logs, diffs, file contents) needs a stated bound or a "only when non-empty" rule.
- **Dead weight test**: for each block, name the instruction or consumer that depends
  on it; a block with no consumer bills every dispatch for nothing.
- **Stakes-priced pins**: judge `model`/`effort` frontmatter against the project's own
  documented convention (e.g. CONTRIBUTING.md's stakes rule), not against taste —
  flag the mismatch, cite the convention, and leave adjudication to the humans.
