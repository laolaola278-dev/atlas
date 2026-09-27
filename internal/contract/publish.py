"""Release approval.

A terminology release is published only after two different approvers sign
its digest.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def approve_release(digest: str, first: str, second: str) -> dict[str, str]:
    """Return a publish record for one signed release digest."""
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("publish-digest-invalid")
    if first == "" or second == "":
        raise ContractError("publish-signature-missing")
    if path_has_direct_identifier(first) or path_has_direct_identifier(second):
        raise ContractError("publish-signer-forbidden")
    if first == second:
        raise ContractError("publish-same-approver")
    return {"digest": digest, "first": first, "second": second, "state": "published"}
