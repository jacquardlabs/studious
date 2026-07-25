# jig

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A Claude Code plugin that owns the **build** step of feature development — the
slot where [studious](https://github.com/jacquardlabs/studious) currently says
"build it with your own workflow" and users reach for Superpowers. Five
user-invoked skills (`/design`, `/plan`, `/build`, `/finish`, `/coach`) and
a small set of deterministic scripts.

Workshop sense of the name: a fixture that holds the workpiece and guides the
tool so the cut lands precisely regardless of who holds the tool —
repeatability, accuracy, interchangeable operators. A jig for Claude Code —
holds the work and guides the tool so any model cuts precisely.

> [!NOTE]
> **Shipped.** All five skills (`/design`, `/plan`, `/build`, `/finish`,
> `/coach`) are implemented and registered in the jacquardlabs marketplace.
> Milestones M0–M6 are complete; current release is
> [v1.5.0](https://github.com/jacquardlabs/jig/releases/tag/v1.5.0). See the
> [CHANGELOG](CHANGELOG.md) for release history and
> [milestones](https://github.com/jacquardlabs/jig/milestones) for the
> M0–M6 breakdown.

## What this is — and isn't

A sibling plugin in the jacquardlabs marketplace, not a studious feature, not
a standalone platform:

- **Not merged into studious** — studious's identity is judgment (the *what*
  and *whether*); it explicitly steps back at build time. Bundling execution
  into it breaks that promise for users who pair studious with other build
  workflows, and couples stable gate logic to fast-churning harness
  scaffolding.
- **Not a platform** — the replacement surface for Superpowers is five
  skills, and the orchestration tier of the market is commoditizing as models
  improve. The durable value is process structure that lets cheaper/current
  models perform above their tier, not fleet machinery.
- **Sibling** — shares studious's context-document contract (`PRODUCT.md`,
  `DESIGN.md`, `CLAUDE.md`) so design docs arrive pre-shaped for the gates,
  while staying separately installable and versioned.

## Portfolio relationship

Composition via small contracts, not a suite:

| Tool | Role | Contract this plugin uses |
|---|---|---|
| [studious](https://github.com/jacquardlabs/studious) | judgment gates + health loop | three context docs; gate handoffs |
| [viva](https://github.com/jacquardlabs/viva) | human sectioned review | markdown sections; CLI + JSON round protocol |
| [cctx](https://github.com/jacquardlabs/cctx) | session forensics + CLAUDE.md harvest | Claude Code JSONL logs |
| **jig** | execution | `PLAN.md`; checkpoint blocks; evidence files |

## Install

Via the Jacquard Labs marketplace:

```
/plugin marketplace add jacquardlabs/marketplace
/plugin install jig@jacquardlabs-marketplace
```

Or directly:

```
/plugin marketplace add jacquardlabs/jig
/plugin install jig@jig
```

## Usage

This is the pipeline each skill implements, per the project's handoff
document:

```
/backlog-priorities or /gate-should-we-build     (studious, existing)
        ↓
/design      — batch interview → sectioned doc → viva
        ↓
/gate-design-review                              (studious, existing)
        ↓
/plan        — inventory → spine → checkpoint blocks → lint → viva
        ↓
/build       — for-loop: fresh executor per task, script verification,
               conditional inspector on load-bearing tasks
        ↓
/gate-audit → /gate-acceptance                   (studious, existing)
        ↓
/finish      — PR evidence table, cctx harvest, follow-ups, cleanup

Quick path (small fixes / most bugs): single task block → /build → /gate-audit
```

### Skills

| Skill | Milestone | Job |
|---|---|---|
| `/design` | M2 | Batch interview → forks → sectioned design doc → viva |
| `/plan` | M3 | Inventory → dependency spine → checkpoint blocks → lint → viva |
| `/build` | M4 | Fresh executor per task, script verification, conditional inspector on load-bearing tasks |
| `/finish` | M5 | PR evidence table, cctx harvest, follow-ups, cleanup |
| `/coach` | M6 | User-invoked orchestrator — reads pipeline state, recommends one next action, dispatches `/design`/`/plan`/`/build`/`/finish` on explicit confirmation |

## Design principles (non-negotiable)

1. Judgment in the model, mechanics in scripts.
2. Fresh context per unit of work.
3. Capabilities, not knowledge — every checkpoint is "run X → observe Y."
4. Closed verdict enums at every judgment point.
5. Recommend one action; the human decides. Propose; never apply.
6. Nothing signs off on itself.
7. Disposable scaffolding, durable decisions.
8. The loop never rewrites its own plan.
9. Shortcuts are first-class.
10. Standalone-capable — every degradation without a sibling installed is
    graceful, none is silent.
11. Anti-cleverness tripwire — sequential for-loop is the default; no named
    agent personas, no sprint ceremony, no resident coordinating roles.

## Status & roadmap

M0–M6 are complete. M0 (pre-work gate) ran a paper dogfood of `/design` and
`/plan` against a real dependency ([viva](https://github.com/jacquardlabs/viva)
issue #109) before any plugin code was written, surfacing blocking gaps —
full detail in `docs/jig/dogfood/FRICTION-REPORT.md` on branch
[`docs/m0-paper-dogfood`](https://github.com/jacquardlabs/jig/tree/docs/m0-paper-dogfood).
M1 shipped the plugin scaffold; M2–M6 shipped `/design`, `/plan`, `/build`,
`/finish`, and `/coach` in turn. Current release is
[v1.5.0](https://github.com/jacquardlabs/jig/releases/tag/v1.5.0) — see the
[CHANGELOG](CHANGELOG.md) for per-release detail and
[milestones](https://github.com/jacquardlabs/jig/milestones) for the M0–M6
breakdown. Known issues and follow-up work are tracked on the
[issue tracker](https://github.com/jacquardlabs/jig/issues).

## Contributing

> TODO: no CONTRIBUTING.md exists yet. Until one lands, file issues and open
> questions against [the tracker](https://github.com/jacquardlabs/jig/issues).

## License

MIT — see [LICENSE](LICENSE).
