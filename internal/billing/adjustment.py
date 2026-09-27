"""Billing adjustment reason validation."""
from __future__ import annotations

from internal.contract.errors import ContractError


_ALLOWED_REASONS = frozenset(["coding-error", "rate-change", "service-correction"])


def adjustment_reason(reason: str, amount_delta: int) -> str:
    """Validate billing adjustment with a documented reason."""
    if not reason or reason not in _ALLOWED_REASONS:
        raise ContractError("billing-adjustment-invalid")
    if type(amount_delta) is not int or amount_delta == 0:
        raise ContractError("billing-adjustment-invalid")
    return reason
