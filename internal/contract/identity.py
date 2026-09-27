"""Actor context for every clinical access.

A request without a person, role, tenant, campus, purpose, and reason is
rejected. An unknown reason is not a placeholder for a real justification.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    actor_role: str
    tenant_id: str
    campus_id: str
    purpose_code: str
    why_code: str
    occurred_at: str


_FIELDS = (
    "actor_id",
    "actor_role",
    "tenant_id",
    "campus_id",
    "purpose_code",
    "why_code",
    "occurred_at",
)


def require_context(payload: dict[str, object]) -> ActorContext:
    """Return a complete context or fail closed."""
    values = {name: str(payload.get(name, "")).strip() for name in _FIELDS}
    if values["why_code"] in {"", "unknown", "unspecified"}:
        raise ContractError("actor-why-missing")
    if any(not values[name] for name in _FIELDS):
        raise ContractError("actor-context-incomplete")
    if any(path_has_direct_identifier(value) for value in values.values()):
        raise ContractError("actor-identifier-forbidden")
    return ActorContext(**values)


def index_partition(context: ActorContext, local_ref: str) -> str:
    """Return a tenant and campus partition for one synthetic local reference."""
    if local_ref == "" or path_has_direct_identifier(local_ref):
        raise ContractError("index-reference-forbidden")
    material = "\n".join((context.tenant_id, context.campus_id, local_ref))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def require_same_partition(left: ActorContext, right: ActorContext, local_ref: str) -> str:
    """Reject a lookup that crosses tenant or campus."""
    same_scope = left.tenant_id == right.tenant_id and left.campus_id == right.campus_id
    if not same_scope:
        raise ContractError("index-partition-mismatch")
    return index_partition(left, local_ref)


def campus_token(source: ActorContext, target: ActorContext, digest: str) -> dict[str, str]:
    """Return a digest token that can cross campuses but cannot merge them."""
    if source.tenant_id != target.tenant_id:
        raise ContractError("token-tenant-mismatch")
    if source.campus_id == target.campus_id:
        raise ContractError("token-campus-same")
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("token-digest-invalid")
    material = "\n".join((source.tenant_id, source.campus_id, target.campus_id, digest))
    return {
        "digest": digest,
        "merge": "forbidden",
        "tenant_id": source.tenant_id,
        "token": hashlib.sha256(material.encode("utf-8")).hexdigest(),
    }


def rebuild_rehearsal(context: ActorContext, refs: tuple[str, ...]) -> tuple[str, ...]:
    """Return stable partitions for one rehearsal without storing identifiers."""
    if not refs:
        raise ContractError("rebuild-empty")
    if len(refs) > 1000:
        raise ContractError("rebuild-too-large")
    built = tuple(index_partition(context, ref) for ref in refs)
    if len(set(refs)) != len(refs):
        raise ContractError("rebuild-duplicate")
    return built
