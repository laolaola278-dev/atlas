"""Submit idempotency enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


_submissions: dict[str, str] = {}


def submit_idempotency(submission_id: str, content_hash: str) -> str:
    """Ensure submissions are idempotent."""
    if not submission_id or not content_hash:
        raise ContractError("submission-invalid")
    
    if submission_id in _submissions:
        stored = _submissions[submission_id]
        if stored != content_hash:
            raise ContractError("submission-content-mismatch")
        return submission_id
    
    _submissions[submission_id] = content_hash
    return submission_id
