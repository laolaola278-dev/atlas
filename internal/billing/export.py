"""Billing export boundary.

A billing result may stay in billing. It cannot cross into another lane.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


_TARGETS = frozenset({"billing", "clinical"})


def export_guard(source: str, target: str) -> str:
    """Keep a billing export inside billing. Any other lane is refused."""
    if source != "billing" or target not in _TARGETS:
        raise ContractError("export-lane-invalid")
    if target != source:
        raise ContractError("export-forbidden")
    return target
