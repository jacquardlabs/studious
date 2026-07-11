# CHANGELOG

<!-- version list -->

## v2.17.0 (2026-07-11)

### Bug Fixes

- De-number stale roster counts in test narrative; name infra and operability in gate-audit intro
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Drop stale lane count from premortem-scope assertion message
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

### Documentation

- Add operability-auditor design spec ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Add operability-auditor implementation plan; correct spec (no gate-audit SKILL.md, count lives in
  CLAUDE.md, epic-driver parity) ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Register operability lane in roster prose — README, PRODUCT, CONTRIBUTING, CLAUDE
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

### Features

- Add operability checklist — timeout/idempotency/shutdown lookup data
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Add operability-auditor agent — failure signal, resilience, runtime hygiene
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Dispatch operability-auditor on the epic path; fix stale lane count and premortem number in
  auditFanIn ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Operability-auditor — gate-audit lane for failure signal, resilience, and 12-factor runtime
  hygiene ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))

- Wire operability lane into /gate-audit as auditor 10; premortem renumbers to 11
  ([#123](https://github.com/jacquardlabs/studious/pull/123),
  [`63b99f4`](https://github.com/jacquardlabs/studious/commit/63b99f4568c062d3101ee95c24d7ba2ddb098bbf))


## v2.16.0 (2026-07-10)

### Bug Fixes

- Gate-audit verdict robustness — severity mapping, challenge step, god-file threshold
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Repoint test_severity_mapping.py's stale regex boundary
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Scope pre-mortem verification out of the audit gate's compiled verdict
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **epic-driver**: Namespace work-file slugs, split cycle vs downstream labels, fix duplicate-dep
  indegree ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **epic-driver**: Unify contract injection to one verbatim resolver
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **epic-driver**: Unify dispatch-prompt builders to a fields object
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **gate-ledger**: Json_update returns 0 on write failure
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **work-through**: Narrow fallback contract injection to audit/premortem
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

### Documentation

- Clarify challenge step confirms against the diff, not working tree
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Define per-claim-type confirm criteria for the challenge step
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for gate-audit verdict robustness
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for gate-doc-commit-ordering (M2, #99)
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for gate-ledger-json-writer story
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for premortem-hook-awareness
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for prompt-contract-dedup (M2 story, issue #92)
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for scheduler-fixes (namespaced work files, cycle labels)
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design doc for workflows/ JS lint + CI job
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design for audit-premortem-scope-fix story
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Design for contract-injection-unify story
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Pre-mortem register for gate-ledger-robustness epic
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Record pre-mortem register for contract-injection-unify
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- Record pre-mortem register for premortem-hook-awareness
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **gate-ledger**: Give pre-mortem CLEAR/REALIZED a canonical home
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

### Features

- **gate-ledger**: Make cmd_status aware of recorded pre-mortem verdicts
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

### Refactoring

- Dedup prompt-contract citations and command/agent output contracts
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))

- **gate-ledger**: Extract shared json_update writer
  ([#119](https://github.com/jacquardlabs/studious/pull/119),
  [`d0b0674`](https://github.com/jacquardlabs/studious/commit/d0b0674204d636f612354ababc8a73835256b1c3))


## v2.15.0 (2026-07-10)

### Bug Fixes

- Final-review findings — six-lane counts on user surfaces, CDK lookup accuracy, boundary symmetry
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Name security health in dashboard sources and init cadence table
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

### Documentation

- Add audit-coverage-seams design spec ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Add audit-coverage-seams implementation plan; sync spec counts to evidence
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Overhaul README around work-on/work-through, fix auditor-count drift
  ([#113](https://github.com/jacquardlabs/studious/pull/113),
  [`434a259`](https://github.com/jacquardlabs/studious/commit/434a2592b59e11704a8a4c2b957302e312c7f4a4))

### Features

- Add infra-auditor — IaC, blast-radius, pipeline, and container lane
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Add infra-checklist reference — lookup data for the infrastructure audit lane
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Add review-security-health — periodic whole-repo security posture lane
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Add security posture as /deep-review's sixth periodic lane
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Add test-auditor — changeset test-adequacy lane
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Close six audit-coverage seams — infra/IaC, CI pipeline, tests, periodic security, ops readiness,
  backend perf ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Fan out new auditors in epic driver; sync roster counts repo-wide
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Gate-time data-migrations dimension; assign backend perf to architecture-auditor
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Route test-auditor and infra-auditor through /gate-audit
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))

- Thread operational readiness through design contract, pre-mortem, and acceptance
  ([#114](https://github.com/jacquardlabs/studious/pull/114),
  [`7a13b7e`](https://github.com/jacquardlabs/studious/commit/7a13b7eb92e1b940bff74cea54a648dfe4be658e))


## v2.14.0 (2026-07-08)

### Bug Fixes

- Inject shared contract from commands instead of agent pull
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

- Resolve gate-acceptance scope before dispatching product-reviewer
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

- **agents**: Disambiguate diff-scoped vs periodic routing in descriptions
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

- **epic-driver**: Inject shared contract into driver audit/premortem dispatches
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

### Documentation

- Design for contract-injection story (inject shared contract into dispatches)
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

- Pre-mortem register for gate-runtime-correctness epic
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))

### Features

- Extend check_references and markdownlint to cover reference/**
  ([#108](https://github.com/jacquardlabs/studious/pull/108),
  [`af02218`](https://github.com/jacquardlabs/studious/commit/af0221802038a4278ef094a0ac8605742777b679))


## v2.13.1 (2026-07-08)

### Bug Fixes

- **epic-driver**: Normalize args boundary — parse string payload (#107)
  ([#109](https://github.com/jacquardlabs/studious/pull/109),
  [`6f9c09b`](https://github.com/jacquardlabs/studious/commit/6f9c09b26ed5402abe71a52987c89e55fe983d27))

### Documentation

- Commit plan/spec history for gate-ledger, backlog-priorities, premortem-register
  ([#106](https://github.com/jacquardlabs/studious/pull/106),
  [`0eb2069`](https://github.com/jacquardlabs/studious/commit/0eb2069777528be2af73c8beaf3c52ddbb2141d8))


## v2.13.0 (2026-07-08)

### Bug Fixes

- Anchor .studious state to the main working tree; add --reset-retry; validate --concurrency
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Harden epic-driver failure paths — dead-auditor labeling, merge mutex, cycle detection, merge
  sentinel, finale fix cycles, shell-safe interpolation
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Rename epic-story-set gates local to satisfy shellcheck
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

### Documentation

- Add /work-through epic orchestration spec and plan
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Delivery-discipline identity — one repo, entrypoints per scope
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Document /work-through in README, CONTRIBUTING, and gate vocabulary
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Record the substrate flip — spec amendment, PRODUCT.md exception, README modes
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

### Features

- Add /work-through — drive a whole epic through the gate flow
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add epic-driver Workflow script — scheduling in code, judgment in agents
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add epic-plan contract reference ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add epic-set and epic-get verbs to gate-ledger
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add epic-story-set and epic-list verbs to gate-ledger
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add run-the-milestone skill shim for /work-through
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Add worker contract — what dispatched workers receive and must return
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))

- Move /work-through's driver to the Workflow substrate with prompt fallback
  ([#105](https://github.com/jacquardlabs/studious/pull/105),
  [`92836f6`](https://github.com/jacquardlabs/studious/commit/92836f69ae1bbba758b999c622714146688c5e5e))


## v2.12.0 (2026-07-07)

### Bug Fixes

- Address gate-audit Important findings on studious-doctor
  ([#87](https://github.com/jacquardlabs/studious/pull/87),
  [`d5db2ab`](https://github.com/jacquardlabs/studious/commit/d5db2ab34c390eb6a0418ef44aa202a7becf1856))

- Exempt optional template sections from studious-doctor stub check
  ([#87](https://github.com/jacquardlabs/studious/pull/87),
  [`d5db2ab`](https://github.com/jacquardlabs/studious/commit/d5db2ab34c390eb6a0418ef44aa202a7becf1856))

### Documentation

- Document /studious-doctor in README ([#87](https://github.com/jacquardlabs/studious/pull/87),
  [`d5db2ab`](https://github.com/jacquardlabs/studious/commit/d5db2ab34c390eb6a0418ef44aa202a7becf1856))

### Features

- Add /studious-doctor read-only health check
  ([#87](https://github.com/jacquardlabs/studious/pull/87),
  [`d5db2ab`](https://github.com/jacquardlabs/studious/commit/d5db2ab34c390eb6a0418ef44aa202a7becf1856))

- Add check-studious-health skill shim for /studious-doctor
  ([#87](https://github.com/jacquardlabs/studious/pull/87),
  [`d5db2ab`](https://github.com/jacquardlabs/studious/commit/d5db2ab34c390eb6a0418ef44aa202a7becf1856))


## v2.11.1 (2026-07-06)

### Bug Fixes

- Invoke gate-ledger by bare name, not via ${CLAUDE_PLUGIN_ROOT}
  ([#85](https://github.com/jacquardlabs/studious/pull/85),
  [`26cda7e`](https://github.com/jacquardlabs/studious/commit/26cda7e98034946bf4c492c5b46421d17017522e))


## v2.11.0 (2026-07-06)

### Features

- Add /work-on — navigate the feature flow one piece at a time
  ([#84](https://github.com/jacquardlabs/studious/pull/84),
  [`9716a2c`](https://github.com/jacquardlabs/studious/commit/9716a2cc3f8949a765ffb43f1337ec83c18817df))


## v2.10.0 (2026-07-05)

### Bug Fixes

- Skip cross-branch registers found via fallback; register-integrity in rubric row
  ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))

### Features

- Add premortem-auditor agent ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))

- Generate pre-mortem register in gate-design-review
  ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))

- Pre-mortem register — record failure modes at design time, verify them at merge time
  ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))

- Verify product-lane pre-mortem items in gate-acceptance
  ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))

- Verify technical-lane pre-mortem items in gate-audit
  ([#82](https://github.com/jacquardlabs/studious/pull/82),
  [`8eec1f4`](https://github.com/jacquardlabs/studious/commit/8eec1f43aafd11c335de5b8371cc5f393ae573e8))


## v2.9.0 (2026-07-03)

### Features

- CI-mode gate-audit (dormant — manual trigger, docs in README)
  ([#75](https://github.com/jacquardlabs/studious/pull/75),
  [`74e187d`](https://github.com/jacquardlabs/studious/commit/74e187dd5219b8c7b03b306e8258d4351907e4ee))

- Run gate-audit non-interactively on pull_request
  ([#75](https://github.com/jacquardlabs/studious/pull/75),
  [`74e187d`](https://github.com/jacquardlabs/studious/commit/74e187dd5219b8c7b03b306e8258d4351907e4ee))

- Ship CI-mode gate-audit dormant, document setup in README
  ([#75](https://github.com/jacquardlabs/studious/pull/75),
  [`74e187d`](https://github.com/jacquardlabs/studious/commit/74e187dd5219b8c7b03b306e8258d4351907e4ee))


## v2.8.0 (2026-07-03)

### Features

- Define the design-doc contract gate-design-review expects
  ([#72](https://github.com/jacquardlabs/studious/pull/72),
  [`1a24476`](https://github.com/jacquardlabs/studious/commit/1a24476b71da74db3a334cc7da5e60aaa0e2738a))


## v2.7.0 (2026-07-03)

### Features

- Idiom feedback loop reads code-auditor's own recurring findings
  ([#70](https://github.com/jacquardlabs/studious/pull/70),
  [`bbd5dda`](https://github.com/jacquardlabs/studious/commit/bbd5dda33db76ed0681916af44ed898f04a06cd0))

- Propose idiom-file additions from recurring codebase-health findings
  ([#70](https://github.com/jacquardlabs/studious/pull/70),
  [`bbd5dda`](https://github.com/jacquardlabs/studious/commit/bbd5dda33db76ed0681916af44ed898f04a06cd0))


## v2.6.0 (2026-07-03)

### Features

- Persist deep-review metrics for trend tracking
  ([#69](https://github.com/jacquardlabs/studious/pull/69),
  [`1e5f5fe`](https://github.com/jacquardlabs/studious/commit/1e5f5fe60bf5da279fd0ae749548d992b606ec87))


## v2.5.1 (2026-07-03)

### Bug Fixes

- Commit install-dev.sh, cover skills/hooks/bin, fix empty-glob bug, add --remove
  ([#80](https://github.com/jacquardlabs/studious/pull/80),
  [`eb3defd`](https://github.com/jacquardlabs/studious/commit/eb3defd6c82d4d42ddb196792bf66d777b0ae057))

### Continuous Integration

- Pin dependencies, add push trigger, add macOS ledger runner
  ([#80](https://github.com/jacquardlabs/studious/pull/80),
  [`eb3defd`](https://github.com/jacquardlabs/studious/commit/eb3defd6c82d4d42ddb196792bf66d777b0ae057))


## v2.5.0 (2026-07-03)

### Bug Fixes

- Vendor a minimal accessibility rubric so gate-time a11y isn't a no-op
  ([#76](https://github.com/jacquardlabs/studious/pull/76),
  [`3674da0`](https://github.com/jacquardlabs/studious/commit/3674da05d49fa0e00037f52d9959986fa8057b39))

### Continuous Integration

- Pin dependencies, add push trigger, add macOS ledger runner
  ([#81](https://github.com/jacquardlabs/studious/pull/81),
  [`5ceda9f`](https://github.com/jacquardlabs/studious/commit/5ceda9f49f84270225ef81d2c55a48e13aaf2b47))

- Pin dependencies, add push trigger, add macOS ledger runner
  ([#71](https://github.com/jacquardlabs/studious/pull/71),
  [`ca35d5a`](https://github.com/jacquardlabs/studious/commit/ca35d5a1bd5e182800bff16188382e8d2ee0a2d6))

### Features

- Golden-fixture behavioral evals for gate-audit
  ([#81](https://github.com/jacquardlabs/studious/pull/81),
  [`5ceda9f`](https://github.com/jacquardlabs/studious/commit/5ceda9f49f84270225ef81d2c55a48e13aaf2b47))

### Refactoring

- Extract shared prompt contract and severity rubric into reference/
  ([#76](https://github.com/jacquardlabs/studious/pull/76),
  [`3674da0`](https://github.com/jacquardlabs/studious/commit/3674da05d49fa0e00037f52d9959986fa8057b39))


## v2.4.3 (2026-07-03)

### Bug Fixes

- Gate-reminder hook no longer evades whitespace-variant PR commands
  ([#79](https://github.com/jacquardlabs/studious/pull/79),
  [`c6ce58a`](https://github.com/jacquardlabs/studious/commit/c6ce58af214e05b050d1ab02a8f43e8219de4813))

- Harden gate-ledger CWD resolution, GC, collision detection, and write-side signal
  ([#67](https://github.com/jacquardlabs/studious/pull/67),
  [`db64a01`](https://github.com/jacquardlabs/studious/commit/db64a01f908a7ddd4b91ec334e23501741364533))

- Scan skills/ and recognize more skill-reference phrasings in check_references.py
  ([#73](https://github.com/jacquardlabs/studious/pull/73),
  [`6a78030`](https://github.com/jacquardlabs/studious/commit/6a78030350c0e3eb33de5a8f288908b374f4cbc4))

### Documentation

- Ship go/rust/ruby idiom rubrics to match code-auditor's claimed coverage
  ([#68](https://github.com/jacquardlabs/studious/pull/68),
  [`25af83a`](https://github.com/jacquardlabs/studious/commit/25af83a5e018777e77aff659baed3f81793a18bf))

### Refactoring

- Extract shared prompt contract and severity rubric into reference/
  ([#74](https://github.com/jacquardlabs/studious/pull/74),
  [`89f3673`](https://github.com/jacquardlabs/studious/commit/89f36736d749606c308350569dd28bedb25551de))


## v2.4.2 (2026-06-27)

### Bug Fixes

- Validate reference/ paths in check_references.py (#46)
  ([#53](https://github.com/jacquardlabs/studious/pull/53),
  [`39f31a7`](https://github.com/jacquardlabs/studious/commit/39f31a77c16ea12965838b27967cc67d113f081b))


## v2.4.1 (2026-06-27)

### Bug Fixes

- Resolve gate-ledger via ${CLAUDE_PLUGIN_ROOT} in gate commands
  ([#52](https://github.com/jacquardlabs/studious/pull/52),
  [`624fa5e`](https://github.com/jacquardlabs/studious/commit/624fa5ed22f15e0ca9b99dcfa4efb70a034a303b))


## v2.4.0 (2026-06-27)

### Documentation

- Add design spec for backlog-priorities overview mode
  ([#51](https://github.com/jacquardlabs/studious/pull/51),
  [`c1a5569`](https://github.com/jacquardlabs/studious/commit/c1a5569a413f558942c9b630177904b72a1e845a))

### Features

- Add overview mode to backlog-priorities agent
  ([#51](https://github.com/jacquardlabs/studious/pull/51),
  [`c1a5569`](https://github.com/jacquardlabs/studious/commit/c1a5569a413f558942c9b630177904b72a1e845a))

- Add overview mode to backlog-priorities command
  ([#51](https://github.com/jacquardlabs/studious/pull/51),
  [`c1a5569`](https://github.com/jacquardlabs/studious/commit/c1a5569a413f558942c9b630177904b72a1e845a))

- Backlog-priorities overview mode (no-arg → top-1 per area)
  ([#51](https://github.com/jacquardlabs/studious/pull/51),
  [`c1a5569`](https://github.com/jacquardlabs/studious/commit/c1a5569a413f558942c9b630177904b72a1e845a))


## v2.3.1 (2026-06-23)

### Bug Fixes

- Register all 5 deep-review agents (over-long descriptions) (#48)
  ([#50](https://github.com/jacquardlabs/studious/pull/50),
  [`514d12a`](https://github.com/jacquardlabs/studious/commit/514d12acf93929e907e57eba5dfb0739fa3cad59))

### Documentation

- Add CLAUDE.md for repo guidance ([#49](https://github.com/jacquardlabs/studious/pull/49),
  [`db2b8fb`](https://github.com/jacquardlabs/studious/commit/db2b8fbf677e3a2a37ac52c7ef0fb5eb300e0b74))


## v2.3.0 (2026-06-23)

### Bug Fixes

- Address gate-audit findings ([#47](https://github.com/jacquardlabs/studious/pull/47),
  [`af83b1b`](https://github.com/jacquardlabs/studious/commit/af83b1bba0be733cf3be1fc232dbe55c2d488f66))

### Features

- Standardize prompt contract across the 14 review/audit agents
  ([#47](https://github.com/jacquardlabs/studious/pull/47),
  [`af83b1b`](https://github.com/jacquardlabs/studious/commit/af83b1bba0be733cf3be1fc232dbe55c2d488f66))


## v2.2.0 (2026-06-23)

### Bug Fixes

- Clean up temp file and drive gate-ledger status off a gate→token table
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Make gate-ledger record degrade silently without jq/git
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Read gate-ledger verdicts via jq --arg so hyphenated gate names work
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Resolve plugin root once so gate-ledger tests pass under CI invocation
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Rewrite gate-ledger arg guard as explicit if (shellcheck SC2015)
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Surface a signal when the gate ledger can't be recorded
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

### Chores

- Add markdownlint config ratcheting current state
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Ignore local .studious gate ledger ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

### Continuous Integration

- Lint shell scripts with shellcheck ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

### Documentation

- Correct gh pr create in the README flow diagram
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Disclose the .gitignore write in the README
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Document the gate ledger, PR-hook reminder, and new directories
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

### Features

- Add @agent-/skill reference link-checker ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Add CI self-verification workflow ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Add gate-ledger record/status helper ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Add plugin manifest validator ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Make PR gate reminder specific via the gate ledger
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Record audit/acceptance verdicts to the gate ledger
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Report gate staleness as commit count, not raw SHAs
  ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))

- Self-verification harness + gate ledger ([#38](https://github.com/jacquardlabs/studious/pull/38),
  [`f2141df`](https://github.com/jacquardlabs/studious/commit/f2141df2f405d2c8682b81740662be000e25792a))


## v2.1.1 (2026-06-23)

### Bug Fixes

- Align init's CLAUDE.md tier vocabulary with review output
  ([#37](https://github.com/jacquardlabs/studious/pull/37),
  [`ab93158`](https://github.com/jacquardlabs/studious/commit/ab93158a4cf3fbeed5718d48c6b2aa31e646470b))


## v2.1.0 (2026-06-23)

### Documentation

- Dogfood Studious's own PRODUCT.md and DESIGN.md
  ([#36](https://github.com/jacquardlabs/studious/pull/36),
  [`64d0a44`](https://github.com/jacquardlabs/studious/commit/64d0a4481ea591a90fe31be54a7576bd663e3c27))

### Features

- Generalize DESIGN.md from visual-UI to interface-general
  ([#36](https://github.com/jacquardlabs/studious/pull/36),
  [`64d0a44`](https://github.com/jacquardlabs/studious/commit/64d0a4481ea591a90fe31be54a7576bd663e3c27))


## v2.0.0 (2026-06-20)

### Features

- Rename plugin from Jaqal to Studious ([#35](https://github.com/jacquardlabs/studious/pull/35),
  [`2e1809c`](https://github.com/jacquardlabs/studious/commit/2e1809c7f8731082f3a7ae35c86fc5092e9e232c))

### Breaking Changes

- The plugin installs as studious@... and the init command is /studious-init. Existing installs and
  /jaqal-init muscle memory break; reinstall under the new name.


## v1.5.0 (2026-06-20)

### Bug Fixes

- Align product-reviewer verdicts to the gates, specify doc discovery (I5, I6)
  ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))

- Audit cleanup batch (I7, I8, I9, minors) ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))

- Re-wire the PR gate hook as a plugin-level hooks.json (B1)
  ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))

- Reconcile /gate-audit severities, diff base, and a11y call (B2, I1, I2)
  ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))

### Features

- Enforce language idioms and conventions in code-auditor (I3, I4)
  ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))

- Remediate the behavioral audit — hook fix, idiom enforcement, gate-contract repairs
  ([#23](https://github.com/jacquardlabs/jaqal/pull/23),
  [`76c71cd`](https://github.com/jacquardlabs/jaqal/commit/76c71cd58cf2aa3cc67c55250daa44ee18f20060))


## v1.4.0 (2026-06-20)

### Features

- Add a PR-time gate reminder hook ([#22](https://github.com/jacquardlabs/jaqal/pull/22),
  [`36663d4`](https://github.com/jacquardlabs/jaqal/commit/36663d4c34ff6c58b7856b4ee06b953c13ea9055))


## v1.3.0 (2026-06-20)

### Continuous Integration

- Push-notify marketplace on release ([#16](https://github.com/jacquardlabs/jaqal/pull/16),
  [`93a47f2`](https://github.com/jacquardlabs/jaqal/commit/93a47f2fe36493f35e85760b514b71c73cbee991))

### Documentation

- Document the command/agent naming conventions
  ([#17](https://github.com/jacquardlabs/jaqal/pull/17),
  [`a379219`](https://github.com/jacquardlabs/jaqal/commit/a37921938d8e964253f33b6047b3dfc762309da4))

- Fix a11y audit claim, flag backlog GitHub-only, clarify init chaining
  ([#18](https://github.com/jacquardlabs/jaqal/pull/18),
  [`12f0360`](https://github.com/jacquardlabs/jaqal/commit/12f0360f763ab1d019004d7a0de6560582e39e0d))

### Features

- Add natural-language trigger skills for the three product gates
  ([#21](https://github.com/jacquardlabs/jaqal/pull/21),
  [`433e807`](https://github.com/jacquardlabs/jaqal/commit/433e80785330b7e09a5e2418e080212b2667d0d1))

### Refactoring

- Collapse duplicated review commands into thin agent wrappers
  ([#8](https://github.com/jacquardlabs/jaqal/pull/8),
  [`b5ca8c3`](https://github.com/jacquardlabs/jaqal/commit/b5ca8c3efec9624f50f7cf0b0448b0a25549da23))

- Collapse review commands into /deep-review [area] and finalize naming
  ([#17](https://github.com/jacquardlabs/jaqal/pull/17),
  [`a379219`](https://github.com/jacquardlabs/jaqal/commit/a37921938d8e964253f33b6047b3dfc762309da4))

- Collapse review duplication and remove vestigial fix layer
  ([#8](https://github.com/jacquardlabs/jaqal/pull/8),
  [`b5ca8c3`](https://github.com/jacquardlabs/jaqal/commit/b5ca8c3efec9624f50f7cf0b0448b0a25549da23))

- Collapse the 5 review commands into /deep-review [area]
  ([#17](https://github.com/jacquardlabs/jaqal/pull/17),
  [`a379219`](https://github.com/jacquardlabs/jaqal/commit/a37921938d8e964253f33b6047b3dfc762309da4))

- Pin agent models by stakes ([#19](https://github.com/jacquardlabs/jaqal/pull/19),
  [`6c4d630`](https://github.com/jacquardlabs/jaqal/commit/6c4d630db86eaab82247b81c9b5d41f91ab0db2e))

- Remove vestigial fix-orchestration layer ([#8](https://github.com/jacquardlabs/jaqal/pull/8),
  [`b5ca8c3`](https://github.com/jacquardlabs/jaqal/commit/b5ca8c3efec9624f50f7cf0b0448b0a25549da23))

- Rename /audit to /gate-audit and drop Gate N labels
  ([#20](https://github.com/jacquardlabs/jaqal/pull/20),
  [`0f2975b`](https://github.com/jacquardlabs/jaqal/commit/0f2975b457cbb56e297ad115aaf0d30c6ed2f3e9))

- Rename architect-reviewer agent to architecture-auditor
  ([#17](https://github.com/jacquardlabs/jaqal/pull/17),
  [`a379219`](https://github.com/jacquardlabs/jaqal/commit/a37921938d8e964253f33b6047b3dfc762309da4))


## v1.2.0 (2026-06-20)

### Features

- Include /review-readme in /deep-review and flag README drift in /audit
  ([#7](https://github.com/jacquardlabs/jaqal/pull/7),
  [`f0222e3`](https://github.com/jacquardlabs/jaqal/commit/f0222e34d3602b14337cb4c725b6f398fcbfca24))


## v1.1.0 (2026-06-20)

### Documentation

- Rewrite README in Bryan's voice ([#3](https://github.com/jacquardlabs/jaqal/pull/3),
  [`f2222d1`](https://github.com/jacquardlabs/jaqal/commit/f2222d1443bfe0b4cc667aabeb685f5687fded26))

### Features

- Add /review-readme drift review and README creation in /jaqal-init
  ([#6](https://github.com/jacquardlabs/jaqal/pull/6),
  [`653bdb6`](https://github.com/jacquardlabs/jaqal/commit/653bdb68316a8fd37fce5161cb047894469b76b9))


## v1.0.0 (2026-06-20)

- Initial Release
