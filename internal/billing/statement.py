"""Synthetic billing statements.

A statement is a count of registered lines. No bill text is created.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


_LINES = {"S1": 3, "S2": 5}


def synthetic_statement(code: str, rows: int, synthetic: bool) -> int:
    """Count rows only for a registered synthetic statement."""
    if type(rows) is not int or type(synthetic) is not bool:
        raise ContractError("statement-invalid")
    if synthetic is not True:
        raise ContractError("statement-not-synthetic")
    expected = _LINES.get(code)
    if expected is None or rows < 1 or rows > 20:
        raise ContractError("statement-invalid")
    if rows != expected:
        raise ContractError("statement-mismatch")
    return rows
