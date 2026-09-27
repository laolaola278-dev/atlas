"""Electronic signature enforcement."""
from __future__ import annotations

from internal.contract.errors import ContractError


def electronic_signature(doc_id: str, signer: str, signature_hash: str) -> str:
    """Validate electronic signature."""
    if not doc_id or not signer or not signature_hash:
        raise ContractError("signature-invalid")
    
    if len(signature_hash) != 64:
        raise ContractError("signature-format-invalid")
    
    return signature_hash
