"""Schedule rollback enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def schedule_rollback(schedule_id: str, from_version: str, to_version: str) -> str:
    """Allow rollback only from 1.1 to 1.0."""
    if not schedule_id or not from_version or not to_version:
        raise ContractError("rollback-invalid")
    
    if from_version == "1.1" and to_version == "1.0":
        return schedule_id
    
    raise ContractError("rollback-forbidden")
