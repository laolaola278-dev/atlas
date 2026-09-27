"""Subscription change notices.

A notice names the resource type and content digest. It never carries a
direct identifier, and a subscriber cannot receive another tenant's change.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def change_notice(subscription: dict[str, str], change: dict[str, str]) -> dict[str, str]:
    """Return one stable notice for a matching subscription."""
    required = ("tenant_id", "resource_type", "content_digest")
    if any(not subscription.get(name) or not change.get(name) for name in required):
        raise ContractError("subscription-incomplete")
    if subscription["tenant_id"] != change["tenant_id"]:
        raise ContractError("subscription-tenant-mismatch")
    if subscription["resource_type"] != change["resource_type"]:
        raise ContractError("subscription-type-mismatch")
    digest = change["content_digest"]
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("subscription-digest-invalid")
    named = (subscription["tenant_id"], subscription["resource_type"], change["tenant_id"])
    if any(path_has_direct_identifier(value) for value in named):
        raise ContractError("subscription-identifier-forbidden")
    return {
        "content_digest": digest,
        "resource_type": change["resource_type"],
        "tenant_id": change["tenant_id"],
    }
