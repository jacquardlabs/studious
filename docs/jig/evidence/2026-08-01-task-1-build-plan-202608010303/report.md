# Inspector report — Task 1 (episode records, round cap, dual-write)

Verdict: CLEAR. Commit range 2e08e88..f8c0533.

- Test self-dealing: no — new tests drive the real binary against throwaway repos; episode sha
  checked against independent `git rev-parse`; legacy record checked for verdict, sha, and the
  exact `["verdict","sha","ranAt"]` shape; cap refusal asserts rc=1, the "2-round cap" wording,
  and no state advance; status hold asserts the verbatim legacy proceed/missing/stale messages.
  Python contract file pins cap and key sets as its own constants.
- Contract match: yes — open records sha/round 1; round increments with the cap enforced in bash
  (exit 1, distinct from arg-error 2); verdict dual-writes through `cmd_record` itself. The one
  choice beyond literal prose — sha refreshed to verdict-time HEAD — is what "same verdict and
  sha" requires once fix rounds land commits, and is documented by its own test.
- Technicality gaming: no — `cmd_status`/`cmd_gate_get` byte-unmodified; `.episodes` rides along
  inertly; cap refuses rather than clamps; reopen is an explicit, tested upsert.

Non-blocking observation (below CONCERN): `episode-verdict` accepts a second verdict on a closed
episode without reopen — an overwrite consistent with `record`'s upsert posture, uncovered by any
Done-means item; downstream tasks can pin it when extending the contract file.
