"""Billing time window enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def time_window(submitted: int, deadline: int) -> int:
    """Accept a billing submission only within the allowed window."""
    if type(submitted) is not int or type(deadline) is not int:
        raise ContractError("billing-window-invalid")
    if submitted < 1 or deadline < 1:
        raise ContractError("billing-window-invalid")
    if submitted > deadline:
        raise ContractError("billing-window-expired")
    return submitted
