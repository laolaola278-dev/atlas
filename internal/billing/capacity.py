"""Capacity headroom enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def capacity_headroom(current_usage: int, max_capacity: int, headroom_percent: int) -> int:
    """Ensure system maintains required capacity headroom."""
    if current_usage < 0 or max_capacity <= 0 or headroom_percent < 0 or headroom_percent > 100:
        raise ContractError("capacity-invalid")
    
    available = max_capacity - current_usage
    required_headroom = (max_capacity * headroom_percent) // 100
    
    if available < required_headroom:
        raise ContractError("capacity-headroom-insufficient")
    
    return available
