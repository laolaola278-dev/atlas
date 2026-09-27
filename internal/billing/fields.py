"""Required fields and conditions enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def required_fields(form_id: str, fields: dict[str, str], required: list[str]) -> None:
    """Check required fields are present."""
    if not form_id or not fields:
        raise ContractError("fields-invalid")
    
    missing = [f for f in required if f not in fields or not fields[f]]
    if missing:
        raise ContractError("fields-required-missing")
