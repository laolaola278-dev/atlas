"""Billing batch capacity limit."""
from __future__ import annotations

from internal.contract.errors import ContractError


def batch_cap(items: int, cap: int) -> int:
    """Enforce a billing batch item cap."""
    if type(items) is not int or type(cap) is not int:
        raise ContractError("batch-cap-invalid")
    if items < 1 or cap < 1 or cap > 10000:
        raise ContractError("batch-cap-invalid")
    if items > cap:
        raise ContractError("batch-cap-exceeded")
    return items
