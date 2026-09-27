"""Offline import signatures.

A signature is a digest bound to a package digest and a synthetic signer.
The gate does not store a key or signature text.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def offline_signature(package_digest: str, signature_digest: str, signer: str) -> dict[str, str]:
    """Accept one offline signature when both digests are distinct."""
    pair = (package_digest, signature_digest)
    if any(len(item) != 64 or path_has_direct_identifier(item) for item in pair):
        raise ContractError("offline-digest-invalid")
    if package_digest == signature_digest:
        raise ContractError("offline-signature-same")
    if signer == "" or path_has_direct_identifier(signer):
        raise ContractError("offline-signer-forbidden")
    return {"package": package_digest, "signature": signature_digest, "signer": signer}
