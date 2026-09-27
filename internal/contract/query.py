"""Scoped clinical queries.

A query must name its tenant, campus, purpose, and page size. Direct
identifiers are never part of a result, even when requested.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import DIRECT_IDENTIFIERS, path_has_direct_identifier


DIRECT_IDENTIFIERS = frozenset({
    "name",
    "identifier",
    "phone",
    "address",
    "birth_date",
})
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Query:
    tenant_id: str
    campus_id: str
    purpose_code: str
    resource_type: str
    actor_id: str
    why_code: str
    page_size: int
    requested_fields: frozenset[str]


def prepare(payload: dict[str, object]) -> Query:
    """Validate scope and remove direct identifiers from the field list."""
    tenant_id = str(payload.get("tenant_id", ""))
    campus_id = str(payload.get("campus_id", ""))
    purpose_code = str(payload.get("purpose_code", ""))
    resource_type = str(payload.get("resource_type", ""))
    actor_id = str(payload.get("actor_id", "actor-synthetic"))
    why_code = str(payload.get("why_code", "treatment-review"))
    consent_state = str(payload.get("consent_state", "active"))
    if consent_state != "active":
        raise ContractError("query-consent-not-active")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("query-why-missing")
    if not all((tenant_id, campus_id, purpose_code, resource_type, actor_id)):
        raise ContractError("query-scope-incomplete")
    scoped = (tenant_id, campus_id, purpose_code, resource_type, actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in scoped):
        raise ContractError("query-identifier-forbidden")
    try:
        page_size = int(payload.get("page_size", 0))
    except (TypeError, ValueError) as exc:
        raise ContractError("query-page-invalid") from exc
    if page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ContractError("query-page-invalid")
    requested = payload.get("requested_fields", ())
    if not isinstance(requested, (list, tuple, set, frozenset)):
        raise ContractError("query-fields-invalid")
    fields = frozenset(str(field) for field in requested)
    if not fields or any(path_has_direct_identifier(field, DIRECT_IDENTIFIERS) for field in fields):
        raise ContractError("query-field-forbidden")
    return Query(
        tenant_id,
        campus_id,
        purpose_code,
        resource_type,
        actor_id,
        why_code,
        page_size,
        fields,
    )


def require_permission_scope(query: Query, grant: dict[str, object]) -> Query:
    """Accept a query only when its scope is inside the granted scope."""
    tenants = grant.get("tenants", ())
    campuses = grant.get("campuses", ())
    purposes = grant.get("purposes", ())
    if not isinstance(tenants, (list, tuple, set, frozenset)):
        raise ContractError("permission-grant-invalid")
    if not isinstance(campuses, (list, tuple, set, frozenset)) or not isinstance(purposes, (list, tuple, set, frozenset)):
        raise ContractError("permission-grant-invalid")
    if query.tenant_id not in set(map(str, tenants)):
        raise ContractError("permission-tenant-denied")
    if query.campus_id not in set(map(str, campuses)):
        raise ContractError("permission-campus-denied")
    if query.purpose_code not in set(map(str, purposes)):
        raise ContractError("permission-purpose-denied")
    return query


def page_cursor(query: Query, offset: int) -> str:
    """Return a cursor bound to one tenant, campus, and resource type."""
    if offset < 0:
        raise ContractError("query-page-invalid")
    material = "\n".join((query.tenant_id, query.campus_id, query.resource_type, str(offset)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def require_same_page(query: Query, other: Query, cursor: str, offset: int) -> None:
    """Reject a cursor presented by another tenant or campus."""
    same = (
        query.tenant_id == other.tenant_id
        and query.campus_id == other.campus_id
        and query.resource_type == other.resource_type
    )
    if not same or cursor != page_cursor(query, offset):
        raise ContractError("query-tenant-isolated")


class QueryLedger:
    """Remember one query key so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], tuple[str, str]] = {}

    def prepare(self, payload: dict[str, object]) -> Query:
        query = prepare(payload)
        key = (query.tenant_id, query.campus_id, query.purpose_code, query.resource_type)
        recorded = self._records.get(key)
        incoming = (query.actor_id, query.why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("query-responsibility-mismatch")
        self._records.setdefault(key, incoming)
        return query

    def restore(self, scope: tuple[str, str, str, str], actor_id: str, why_code: str) -> None:
        """Restore one accepted query without treating it as a new read."""
        missing_scope = len(scope) != 4 or not all(scope) or not actor_id
        if missing_scope:
            raise ContractError("query-scope-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("query-why-missing")
        self._records[scope] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, str, str, str], tuple[str, str]], ...]:
        """Return stored query decisions in stable order."""
        return tuple(sorted(self._records.items()))
