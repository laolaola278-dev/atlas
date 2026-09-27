"""Synthetic scale plans.

A plan records a count and a seed. It does not materialize records and it
does not accept a direct identifier.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def scale_plan(count: int, seed: str, synthetic: bool) -> dict[str, object]:
    """Accept one bounded synthetic plan without generating its records."""
    if synthetic is not True:
        raise ContractError("scale-not-synthetic")
    if count < 1 or count > 10_000_000:
        raise ContractError("scale-count-invalid")
    if seed == "" or path_has_direct_identifier(seed):
        raise ContractError("scale-seed-forbidden")
    return {"count": count, "materialized": False, "seed": seed, "synthetic": True}
