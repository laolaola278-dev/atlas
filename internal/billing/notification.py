"""Notification idempotency enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


_sent_notifications: dict[str, str] = {}


def notification_idempotency(notification_id: str, recipient: str, content_hash: str) -> str:
    """Ensure notifications are not sent multiple times to the same recipient."""
    if not notification_id or not recipient or not content_hash:
        raise ContractError("notification-invalid")
    
    key = f"{notification_id}:{recipient}"
    if key in _sent_notifications:
        stored_hash = _sent_notifications[key]
        if stored_hash != content_hash:
            raise ContractError("notification-content-mismatch")
        return notification_id
    
    _sent_notifications[key] = content_hash
    return notification_id
