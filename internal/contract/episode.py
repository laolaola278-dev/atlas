"""Episode aggregation.

Events join one episode only when they share a synthetic encounter reference.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def aggregate_episode(encounter_ref: str, digests: tuple[str, ...]) -> dict[str, object]:
    """Return one episode digest count for a bounded event set."""
    if encounter_ref == "" or path_has_direct_identifier(encounter_ref):
        raise ContractError("episode-reference-forbidden")
    if not digests or len(digests) > 50:
        raise ContractError("episode-set-invalid")
    if len(set(digests)) != len(digests):
        raise ContractError("episode-duplicate")
    if any(len(item) != 64 for item in digests):
        raise ContractError("episode-digest-invalid")
    return {"count": len(digests), "encounter_ref": encounter_ref}
