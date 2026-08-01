# Inspector report — Task 3 (vocabulary landing)

Verdict: CONCERN — lens 2 (contract match); lenses 1 and 3 clean. Range 1c90732..449e505
(e0ca1e0 change + 449e505 executability FIX).

- Test self-dealing: clean — EpisodeVocabularyTest parses the real table and the real GATES
  block with non-vacuity guards, and pins the literal RETRY_TOKEN so both files drifting
  together still fails. 19 tests pass under pytest and standalone.
- Technicality gaming: clean — the six driver-test files updated only their mock rules to speak
  GATES[gate].retry; no assertion weakened; the FIX commit added only a shebang + exec bit.
- Contract match — the CONCERN: retokenizing GATES leaves epic-driver.js internally token-split
  in a functionally live way. The audit-compile prompt (:1459) still instructs "PASS | FIX AND
  RE-AUDIT | NEEDS DISCUSSION", the acceptance-compile prompt (:592) "SHIP | FIX AND RE-CHECK |
  HOLD", and the narrowing probe (:355) requires exactly "FIX AND RE-AUDIT" — while the retry
  loops (:2073, :2442) and narrowing entries (:1664, :2366) now match only FIX AND RE-REVIEW.
  A dispatched compiler following its prompt returns the old token, fails the retry match, and
  parks; the #130 narrowing path goes dead. Not this block's defect (its Do scoped the driver to
  lines 79–80, shipped exactly that) — a plan-coverage gap: no remaining task owns the driver's
  embedded prompt strings.

Forward lane: architecture-auditor (cross-surface contract split, #274's pattern).
