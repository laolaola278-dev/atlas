"""Official validator evidence.

Local structural checks are not an official HAPI result. A resource may pass
only when a recorded official outcome names the same digest and says pass.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def require_official(payload: dict[str, object], record: dict[str, object] | None) -> str:
    """Return the official outcome id, or fail closed when it is absent."""
    digest = str(payload.get("contentDigest", ""))
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("validator-digest-invalid")
    if record is None:
        raise ContractError("validator-result-unknown")
    if record.get("engine") != "hapi" or record.get("official") is not True:
        raise ContractError("validator-not-official")
    if str(record.get("contentDigest", "")) != digest:
        raise ContractError("validator-digest-mismatch")
    if record.get("outcome") != "pass":
        raise ContractError("validator-outcome-failed")
    outcome_id = str(record.get("outcomeId", ""))
    if outcome_id == "" or path_has_direct_identifier(outcome_id):
        raise ContractError("validator-outcome-invalid")
    return outcome_id
