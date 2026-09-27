"""Billing amount range validation."""
from __future__ import annotations

from internal.contract.errors import ContractError


def amount_range(amount: int, min_amount: int, max_amount: int) -> int:
    """Enforce a billing amount within allowed range."""
    if type(amount) is not int or type(min_amount) is not int or type(max_amount) is not int:
        raise ContractError("billing-amount-invalid")
    if min_amount < 1 or max_amount < min_amount:
        raise ContractError("billing-amount-invalid")
    if amount < min_amount or amount > max_amount:
        raise ContractError("billing-amount-out-of-range")
    return amount
