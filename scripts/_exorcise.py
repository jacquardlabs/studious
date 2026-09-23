"""The one reader of exorcist's `exorcise --json` report (exorcist#10, contract v1).

Two consumers, one validator: `exorcise-report` checks the report before `/build`
Step 3 acts on it, and `ship-body` renders it into the PR body. A version or shape
this reader was not written against is named, never guessed at -- the contract is
the seam, and it negotiates by exact match (exorcist's `reference/report.md`).
"""
from __future__ import annotations

EXORCISE_CONTRACT_VERSION = 1


def off_contract(report: object) -> str | None:
    """Why `report` is not a contract-v1 report this reader can use, or None."""
    if not isinstance(report, dict):
        return f"contract_version None is not {EXORCISE_CONTRACT_VERSION}"
    version = report.get("contract_version")
    # bool is an int subclass; `True` must not pass as version 1.
    if isinstance(version, bool) or version != EXORCISE_CONTRACT_VERSION:
        return f"contract_version {version!r} is not {EXORCISE_CONTRACT_VERSION}"
    removed, kept, held, applied = (report.get(k) for k in ("concepts_removed", "concepts_kept", "held", "applied"))
    if not (isinstance(removed, list) and isinstance(kept, list) and isinstance(held, list)
            and isinstance(applied, list)
            and all(isinstance(k, dict) and isinstance(k.get("name"), str) for k in kept)
            and all(isinstance(h, dict) and isinstance(h.get("title"), str) for h in held)
            and all(isinstance(a, dict) for a in applied)):
        return "is malformed: concepts_removed, concepts_kept[].name, held[].title, applied[]"
    return None
