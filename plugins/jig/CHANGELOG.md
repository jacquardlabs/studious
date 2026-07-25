# CHANGELOG

<!-- version list -->

## v1.7.0 (2026-07-21)

### Documentation

- Add 2026-07-17 deep-review reports and metrics baseline
  ([#96](https://github.com/jacquardlabs/jig/pull/96),
  [`c4fe7b9`](https://github.com/jacquardlabs/jig/commit/c4fe7b9c0bbb4e1773eb2daf65c7cc97381f2c75))

- Re-run context-doc extraction now that M1-M6 have shipped
  ([#86](https://github.com/jacquardlabs/jig/pull/86),
  [`b2e6551`](https://github.com/jacquardlabs/jig/commit/b2e6551425bae8da010e4cb908b80fe6c0f76fcd))

- Update README to reflect shipped M1-M6 state ([#85](https://github.com/jacquardlabs/jig/pull/85),
  [`174a7f6`](https://github.com/jacquardlabs/jig/commit/174a7f6270e49e02b8ff8d9071dacb0b4a997bb3))

### Features

- Report /build's session verdict back to studious's gate-ledger
  ([#97](https://github.com/jacquardlabs/jig/pull/97),
  [`64c4803`](https://github.com/jacquardlabs/jig/commit/64c4803be0c2ce6e529e49630d5324ba122e0029))


## v1.6.0 (2026-07-18)

### Documentation

- Trim changelog and issue-archaeology prose from design/plan/finish skills
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))

### Features

- Derive verify items straight from PLAN.md task blocks
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))

### Performance Improvements

- Let pillar 3 cite an already-fresh pillar-1 run instead of re-running
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))

- Mechanize build step 2.5's items derivation via verify --plan
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))

- Mechanize verify's item derivation, parallelize command items, trim skill rationale
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))

- Opt-in parallel execution of verify command items
  ([#84](https://github.com/jacquardlabs/jig/pull/84),
  [`92bcde0`](https://github.com/jacquardlabs/jig/commit/92bcde07c219432ca83bb4e0dda2854c512dceb6))


## v1.5.0 (2026-07-18)

### Documentation

- Coach-skill demonstration evidence across 5 pipeline states
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))

- Dated build report for coach-skill (/finish step 5)
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))

- Design doc for the coach (user-invoked orchestrator)
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))

- **design-review**: Persist coach-skill pre-mortem register
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))

### Features

- Implement /coach, the user-invoked orchestrator (M6)
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))

- Implement the coach — /coach, the user-invoked orchestrator (issue #21)
  ([#82](https://github.com/jacquardlabs/jig/pull/82),
  [`ae1143f`](https://github.com/jacquardlabs/jig/commit/ae1143f514ab9bc8e1c407e1a6febe4dfdf3888b))


## v1.4.0 (2026-07-17)

### Build System

- Foreman assembles replay bundle via evidence-capture (Task 2, replay bundle)
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Foreman names the Executor's dispatch model (Task 1, replay bundle)
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Foreman states unavailable when dispatch model can't be determined (Task 3)
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Step 1.5 names a defined path for a plan growing mid-session (Task 4)
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

### Documentation

- Correct the model-attestation mechanism claim, justify bundle consolidation
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Revise replay-bundle.md per gate-design-review REVISE findings
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Sign off on PLAN.md for issue #34 (replay bundle)
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Sign off on replay-bundle.md ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Sign off revision round 2 (viva) ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- Sign off revision round 3 (viva) ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

- State the model-field's unverified-inherit limit honestly, scope corroboration to cctx/#33
  ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))

### Features

- Persist a replay bundle per build task ([#78](https://github.com/jacquardlabs/jig/pull/78),
  [`1a72f99`](https://github.com/jacquardlabs/jig/commit/1a72f997f98c8cbcaaa22be761d4f5ca2af37579))


## v1.3.0 (2026-07-17)

### Features

- Add review-consumption style rules to generated artifacts and session prose
  ([#77](https://github.com/jacquardlabs/jig/pull/77),
  [`1b25830`](https://github.com/jacquardlabs/jig/commit/1b25830511c9b467aeea46877310c770c0a54405))


## v1.2.1 (2026-07-16)

### Bug Fixes

- Plan-lint compute_load_bearing gains title-based matching
  ([#76](https://github.com/jacquardlabs/jig/pull/76),
  [`95cc4c2`](https://github.com/jacquardlabs/jig/commit/95cc4c24e8ece65ee0939f1d37fe1eb6a4cbd352))

- Pre-dogfood hardening (evidence-capture, timeout, load-bearing, task-split binding)
  ([#76](https://github.com/jacquardlabs/jig/pull/76),
  [`95cc4c2`](https://github.com/jacquardlabs/jig/commit/95cc4c24e8ece65ee0939f1d37fe1eb6a4cbd352))

- **evidence-capture**: Reject bare '.' and '..' traversal tokens
  ([#76](https://github.com/jacquardlabs/jig/pull/76),
  [`95cc4c2`](https://github.com/jacquardlabs/jig/commit/95cc4c24e8ece65ee0939f1d37fe1eb6a4cbd352))

### Documentation

- Add epic pre-mortem register for pre-dogfood-hardening
  ([#76](https://github.com/jacquardlabs/jig/pull/76),
  [`95cc4c2`](https://github.com/jacquardlabs/jig/commit/95cc4c24e8ece65ee0939f1d37fe1eb6a4cbd352))

### Testing

- Bind plan-lint and the load-bearing reference module together
  ([#76](https://github.com/jacquardlabs/jig/pull/76),
  [`95cc4c2`](https://github.com/jacquardlabs/jig/commit/95cc4c24e8ece65ee0939f1d37fe1eb6a4cbd352))


## v1.2.0 (2026-07-16)

### Bug Fixes

- Address m2-design-skill finale follow-ups ([#73](https://github.com/jacquardlabs/jig/pull/73),
  [`1c7f217`](https://github.com/jacquardlabs/jig/commit/1c7f2174042837c02e1072bb20fd1b4a217811b7))

### Features

- Implement /design skill (M2) ([#73](https://github.com/jacquardlabs/jig/pull/73),
  [`1c7f217`](https://github.com/jacquardlabs/jig/commit/1c7f2174042837c02e1072bb20fd1b4a217811b7))


## v1.1.0 (2026-07-16)

### Documentation

- /finish build report for epic/m3-plan-skill
  ([`91e227b`](https://github.com/jacquardlabs/jig/commit/91e227ba50ced7bc86a1bc4057c80ab6980143fe))

### Features

- Implement /plan skill (M3) ([#72](https://github.com/jacquardlabs/jig/pull/72),
  [`f629188`](https://github.com/jacquardlabs/jig/commit/f629188e736f5c45f3702b1da4f7311ef9b95331))


## v1.0.1 (2026-07-16)

### Bug Fixes

- Verify semantic-release triggers on a Conventional Commits PR title
  ([#65](https://github.com/jacquardlabs/jig/pull/65),
  [`c416999`](https://github.com/jacquardlabs/jig/commit/c416999f53cfde400daeb208c9fb345695628deb))


## v1.0.0 (2026-07-12)

- Initial Release
