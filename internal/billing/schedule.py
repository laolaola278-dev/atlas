"""Synthetic scheduling enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def synthetic_schedule(schedule_id: str, slots: list[dict[str, str]], max_slots: int) -> str:
    """Validate synthetic scheduling constraints."""
    if not schedule_id or not slots:
        raise ContractError("schedule-invalid")
    
    if len(slots) > max_slots:
        raise ContractError("schedule-capacity-exceeded")
    
    return schedule_id
