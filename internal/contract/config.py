"""Startup configuration checks.

Secrets belong in an external reference, never in the loaded config. A
service without a tenant, campus, or policy version does not start.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


SECRET_MARKERS = ("secret", "password", "private_key", "token")


@dataclass(frozen=True)
class RuntimeConfig:
    tenant_id: str
    campus_id: str
    policy_version: str
    audit_stream: str
    secret_ref: str


def load_config(payload: dict[str, object]) -> RuntimeConfig:
    """Accept only a non-secret, fully scoped configuration."""
    for key, value in payload.items():
        lowered = key.lower()
        if any(marker in lowered for marker in SECRET_MARKERS) and not lowered.endswith("_ref"):
            raise ContractError("config-secret-inline")
        if isinstance(value, str) and value.lower().startswith(("sk-", "bearer ")):
            raise ContractError("config-secret-inline")
    tenant_id = str(payload.get("tenant_id", "")).strip()
    campus_id = str(payload.get("campus_id", "")).strip()
    policy_version = str(payload.get("policy_version", "")).strip()
    audit_stream = str(payload.get("audit_stream", "")).strip()
    secret_ref = str(payload.get("secret_ref", "")).strip()
    if not all((tenant_id, campus_id, policy_version, audit_stream, secret_ref)):
        raise ContractError("config-incomplete")
    if not secret_ref.startswith("secret://"):
        raise ContractError("config-secret-ref-invalid")
    if not compatible(policy_version):
        raise ContractError("config-version-incompatible")
    scoped = (tenant_id, campus_id, audit_stream)
    if any(path_has_direct_identifier(value) for value in scoped):
        raise ContractError("config-identifier-forbidden")
    return RuntimeConfig(tenant_id, campus_id, policy_version, audit_stream, secret_ref)


def config_signature(config_digest: str, signature_digest: str) -> dict[str, str]:
    """Accept a signed config when the two digests differ."""
    pair = (config_digest, signature_digest)
    if any(len(item) != 64 for item in pair):
        raise ContractError("config-signature-invalid")
    if config_digest == signature_digest:
        raise ContractError("config-signature-same")
    return {"config": config_digest, "signature": signature_digest}
