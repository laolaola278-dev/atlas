"""Cache keys for non-identifying clinical projections.

Keys bind tenant, campus, resource type, and policy version. Direct
identifiers are rejected so a cache cannot become a patient index.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


FORBIDDEN_KEY_PARTS = frozenset({
    "name",
    "identifier",
    "phone",
    "address",
    "birth_date",
    "patient_id",
    "resource_id",
})


def make_cache_key(
    tenant_id: str,
    campus_id: str,
    resource_type: str,
    policy_version: str,
    fields: tuple[str, ...] | list[str],
    consent_state: str = "active",
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> str:
    """Return a stable key or fail closed."""
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("cache-why-missing")
    if not all((tenant_id, campus_id, resource_type, policy_version, consent_state, actor_id)):
        raise ContractError("cache-scope-incomplete")
    scoped = (tenant_id, campus_id, resource_type, actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in scoped):
        raise ContractError("cache-identifier-forbidden")
    if consent_state not in {"active", "withdrawn", "expired", "undetermined"}:
        raise ContractError("cache-consent-invalid")
    if not fields:
        raise ContractError("cache-fields-missing")
    normalized = tuple(sorted(str(field) for field in fields))
    if any(path_has_direct_identifier(field, FORBIDDEN_KEY_PARTS) for field in normalized):
        raise ContractError("cache-phi-forbidden")
    if any(not field or any(char.isspace() for char in field) for field in normalized):
        raise ContractError("cache-field-invalid")
    joined = ",".join(normalized)
    parts = (tenant_id, campus_id, resource_type, policy_version, consent_state, actor_id, why_code, joined)
    return "|".join(parts)


class CacheLedger:
    """Remember one cache scope so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], tuple[str, str]] = {}

    def key(
        self,
        tenant_id: str,
        campus_id: str,
        resource_type: str,
        policy_version: str,
        fields: tuple[str, ...] | list[str],
        consent_state: str = "active",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> str:
        value = make_cache_key(
            tenant_id,
            campus_id,
            resource_type,
            policy_version,
            fields,
            consent_state,
            actor_id,
            why_code,
        )
        scope = (tenant_id, campus_id, resource_type, policy_version)
        recorded = self._records.get(scope)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("cache-responsibility-mismatch")
        self._records[scope] = incoming
        return value

    def restore(self, scope: tuple[str, str, str, str], actor_id: str, why_code: str) -> None:
        """Restore one cache scope without treating it as a new read."""
        complete = len(scope) == 4 and all(scope) and bool(actor_id)
        if not complete:
            raise ContractError("cache-scope-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("cache-why-missing")
        self._records[scope] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, str, str, str], tuple[str, str]], ...]:
        """Return stored cache scopes in stable order."""
        return tuple(sorted(self._records.items()))


def terminology_cache(release_to: str, at_time: str, digest: str) -> str:
    """Return a cache digest only while its terminology release is active."""
    if release_to == "" or at_time == "":
        raise ContractError("termcache-window-incomplete")
    if at_time >= release_to:
        raise ContractError("termcache-expired")
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("termcache-digest-invalid")
    return digest
