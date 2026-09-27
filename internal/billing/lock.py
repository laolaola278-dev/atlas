"""Billing lock state enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def lock_state(batch_id: str, is_locked: bool, operation: str) -> str:
    """Enforce billing batch lock state for operations."""
    if not batch_id or operation not in ("read", "modify"):
        raise ContractError("billing-lock-invalid")
    if is_locked and operation == "modify":
        raise ContractError("billing-lock-violation")
    return batch_id
