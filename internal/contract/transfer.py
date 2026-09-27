"""Import and export field allow-lists.

Transfers carry only declared clinical fields. Direct identifiers and
unknown fields are rejected before a file can be imported or exported.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


EXPORT_FIELDS = frozenset({"code", "value", "unit", "effective_at", "status"})
IMPORT_FIELDS = frozenset({"code", "value", "unit", "effective_at"})
FORBIDDEN = frozenset({"name", "identifier", "phone", "address", "birth_date", "patient_id"})


def check_transfer(
    direction: str,
    fields: set[str] | frozenset[str],
    consent_state: str = "active",
    tenant_id: str = "tenant-synthetic",
    campus_id: str = "campus-synthetic",
    purpose_code: str = "treatment",
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> frozenset[str]:
    """Return the accepted field set or fail closed."""
    if consent_state != "active":
        raise ContractError("transfer-consent-not-active")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("transfer-why-missing")
    if not all((tenant_id, campus_id, purpose_code, actor_id)):
        raise ContractError("transfer-scope-incomplete")
    scoped = (tenant_id, campus_id, purpose_code, actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in scoped):
        raise ContractError("transfer-identifier-forbidden")
    if direction == "export":
        allowed = EXPORT_FIELDS
    elif direction == "import":
        allowed = IMPORT_FIELDS
    else:
        raise ContractError("transfer-direction-invalid")
    requested = frozenset(fields)
    if not requested:
        raise ContractError("transfer-fields-missing")
    if any(path_has_direct_identifier(field, FORBIDDEN) for field in requested) or not requested <= allowed:
        raise ContractError("transfer-field-forbidden")
    return requested


def project_export(record: dict[str, object], fields: set[str] | frozenset[str]) -> dict[str, str]:
    """Return only accepted export fields, in stable order."""
    accepted = check_transfer("export", fields)
    projected = {name: str(record.get(name, "")) for name in sorted(accepted)}
    if any(value == "" for value in projected.values()):
        raise ContractError("transfer-field-missing")
    if any(path_has_direct_identifier(value, FORBIDDEN) for value in projected.values()):
        raise ContractError("transfer-identifier-forbidden")
    return projected


class TransferLedger:
    """Remember one transfer so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str], tuple[str, str]] = {}

    def check(
        self,
        direction: str,
        fields: set[str] | frozenset[str],
        consent_state: str = "active",
        tenant_id: str = "tenant-synthetic",
        campus_id: str = "campus-synthetic",
        purpose_code: str = "treatment",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> frozenset[str]:
        accepted = check_transfer(
            direction,
            fields,
            consent_state,
            tenant_id,
            campus_id,
            purpose_code,
            actor_id,
            why_code,
        )
        key = (direction, tenant_id, campus_id, purpose_code)
        incoming = (actor_id, why_code)
        previous = self._records.get(key, incoming)
        if previous != incoming:
            raise ContractError("transfer-responsibility-mismatch")
        self._records[key] = incoming
        return accepted

    def restore(self, scope: tuple[str, str, str, str], actor_id: str, why_code: str) -> None:
        """Restore one accepted transfer without treating it as a new export."""
        complete = len(scope) == 4 and all(scope) and bool(actor_id)
        if not complete:
            raise ContractError("transfer-scope-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("transfer-why-missing")
        self._records[scope] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, str, str, str], tuple[str, str]], ...]:
        """Return stored transfer decisions in stable order."""
        return tuple(sorted(self._records.items()))
