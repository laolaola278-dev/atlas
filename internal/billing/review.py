"""Schedule review enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def schedule_review(schedule_id: str, reviewer: str, status: str) -> str:
    """Validate schedule review status."""
    if not schedule_id or not reviewer or reviewer == "system":
        raise ContractError("review-invalid")
    
    valid_statuses = {"approved", "rejected", "needs-revision"}
    if status not in valid_statuses:
        raise ContractError("review-status-invalid")
    
    return status
