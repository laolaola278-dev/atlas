"""Attachment whitelist enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


def attachment_whitelist(filename: str, size_bytes: int, max_size: int) -> str:
    """Validate attachment against whitelist."""
    if not filename:
        raise ContractError("attachment-invalid")
    
    ext = filename[filename.rfind("."):].lower() if "." in filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise ContractError("attachment-type-forbidden")
    
    if size_bytes > max_size:
        raise ContractError("attachment-size-exceeded")
    
    return filename
