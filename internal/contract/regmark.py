"""Regulatory subset marks.

A mark names a synthetic subset and an allowed authority. It does not store
concept text.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_AUTHORITIES = frozenset({"cn-synthetic", "who-synthetic"})


def regulatory_mark(subset: str, authority: str, digest: str) -> dict[str, str]:
    """Accept one regulatory mark for a synthetic subset."""
    if subset == "" or path_has_direct_identifier(subset):
        raise ContractError("regmark-subset-forbidden")
    if authority not in _AUTHORITIES:
        raise ContractError("regmark-authority-unknown")
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("regmark-digest-invalid")
    return {"authority": authority, "digest": digest, "subset": subset}
