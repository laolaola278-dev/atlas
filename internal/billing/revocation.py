"""Revocation enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def revocation(doc_id: str, reason: str, authorized_by: str) -> str:
    """Validate document revocation."""
    if not doc_id or not reason or not authorized_by:
        raise ContractError("revocation-invalid")
    
    valid_reasons = {"error", "duplicate", "fraud"}
    if reason not in valid_reasons:
        raise ContractError("revocation-reason-invalid")
    
    if authorized_by == "system":
        raise ContractError("revocation-unauthorized")
    
    return doc_id
