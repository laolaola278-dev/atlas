"""Form version enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def form_version(form_id: str, version: str) -> str:
    """Validate form version compatibility."""
    if not form_id or not version:
        raise ContractError("form-version-invalid")
    
    major, minor = version.split(".")[:2]
    if int(major) < 1:
        raise ContractError("form-version-unsupported")
    
    return version
