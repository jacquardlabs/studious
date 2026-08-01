# Inspector report — Task 2 (findings ledger)

Verdict: CONCERN — lens 2 (contract match); lenses 1 and 3 clean. Commit e1f91e7.

- Test self-dealing: clean — refusals asserted with rc + jq-read state absence; waiver reason
  read back from the record; the quotable line derived from a verified multi-step fixture;
  severity-laundering dodge covered.
- Technicality gaming: clean — adversarial probes beyond the suite (different gate, different
  mix, round-2 regression-of reference) behaved correctly; counts computed by jq over state;
  identity checked against stored severity; #245's carriedFindings untouched.
- Contract match — the CONCERN: a Critical reaches `--status waived` with no `--waiver` and no
  recorded reason, then appears in neither count of `episode-get`'s line — the silent set-aside
  the waiver rule exists to prevent, reachable via the sibling status the plan left unruled.
  Faithful implementation of the block's perimeter, not gaming. Fix is one line (extend the
  rule-2 guard at bin/gate-ledger:~672 to carried|waived for Criticals) or an explicit Task-4
  prose constraint.

Forward lane: architecture-auditor (downstream-consumed contract narrower than its name).
