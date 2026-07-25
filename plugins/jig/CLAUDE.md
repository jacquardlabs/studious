## Review workflow

### Context documents

- **PRODUCT.md** — product context, personas, principles, feature map. Read before any product decision.
- **DESIGN.md** — the interface design system: the product's user-facing surface(s) — web UI, CLI, TUI, API, or report — covering the semantic palette, vocabulary, formatting, and per-surface conventions. Read before changing anything users see. (CLAUDE.md owns *how the code is written*; DESIGN.md owns *the user-facing surface*.)

### Code conventions

Language conventions `code-auditor` enforces at `/gate-audit`. Document the rules and any deliberate deviations here — they override Studious's built-in idiom rubric.

Confirmed at M1 (repo & plugin scaffold, #30): `pyproject.toml`, `scripts/plan-lint`, `scripts/design-lint`, and `tests/*.py` are all Python — the recommendation below is now a detected fact, not a guess.

- **Python** — target 3.11+ (per the user's stated global preference for
  ML/general tooling compatibility). Use `uv` for all Python tooling. Type
  hints required on all code. Prefer comprehensions, generator expressions,
  and stdlib (`functools`, `itertools`, `collections`) over explicit loops.
- **Linter** — Ruff. `pyproject.toml`'s `[tool.ruff.lint]` selects `B`, `C4`,
  `PERF`, `PIE`, `RUF`, `SIM` (matches `reference/idioms/python.md`'s stated
  rule set); not yet wired into a CI job (tracked separately).
- **Tests** — standard-library `unittest`, run via
  `uv run --no-project python3 -m unittest discover -s tests -v` (see
  `tests/test_scaffold.py`); no pytest dependency for a repo this young.
- **Deliberate deviations** — none.

### Quality gates

| Gate | When | Command |
|------|------|---------|
| Should we build? | Before any engineering | `/gate-should-we-build [idea]` |
| Design review | After design doc, before implementation | `/gate-design-review` |
| Audit | After implementation, before acceptance | `/gate-audit` |
| Acceptance | After audit passes, before merge | `/gate-acceptance` |

### Periodic reviews

| Review | Cadence | Command |
|--------|---------|---------|
| Codebase health | Weekly or pre-milestone | `/deep-review codebase` |
| Interface health | Monthly or post-UI-sprint | `/deep-review interface` |
| Architecture | Quarterly or pre-major-feature | `/deep-review architecture` |
| Product health | Monthly | `/deep-review product` |
| Security health | Monthly | `/deep-review security` |
| README drift | After a release or feature batch | `/deep-review readme` |
| All reviews + summary | As needed | `/deep-review` |

### After each review

1. Fix any **Critical** findings before the next feature
2. File **Important** findings as tasks to address this cycle
3. Log **Track** findings (lowest tier — revisit next cycle); they compound if ignored
4. Update context docs if the review surfaced changes:
   - `/deep-review product` updates PRODUCT.md
   - `/deep-review interface` updates DESIGN.md
   - `/deep-review architecture` updates CLAUDE.md
   - `/deep-review readme` proposes a README.md diff
