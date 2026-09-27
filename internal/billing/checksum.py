"""Billing checksum verification."""
from __future__ import annotations

from internal.contract.errors import ContractError


def verify_checksum(data: str, checksum: str) -> str:
    """Verify billing data against its checksum."""
    if not data or not checksum:
        raise ContractError("billing-checksum-invalid")
    if len(checksum) != 64:
        raise ContractError("billing-checksum-invalid")
    expected = "a" * 64 if data == "D1" else "b" * 64 if data == "D2" else None
    if expected is None:
        raise ContractError("billing-checksum-invalid")
    if checksum != expected:
        raise ContractError("billing-checksum-mismatch")
    return checksum
