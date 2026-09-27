"""Draft recovery enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


_drafts: dict[str, dict[str, str]] = {}


def draft_recovery(draft_id: str, content: dict[str, str], action: str) -> dict[str, str]:
    """Manage draft recovery."""
    if not draft_id:
        raise ContractError("draft-invalid")
    
    if action == "save":
        if not content:
            raise ContractError("draft-invalid")
        _drafts[draft_id] = content
        return content
    elif action == "recover":
        if draft_id not in _drafts:
            raise ContractError("draft-not-found")
        return _drafts[draft_id]
    else:
        raise ContractError("draft-action-invalid")
