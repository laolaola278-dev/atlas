"""Billing item audit trail.

Every billing action must be linked to an immutable audit event.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


def item_audit(item_digest: str, event_digest: str, action: str) -> str:
    """Link a billing item to its audit event."""
    if not item_digest or not event_digest or not action:
        raise ContractError("billing-audit-invalid")
    if item_digest == event_digest:
        raise ContractError("billing-audit-circular")
    return event_digest
