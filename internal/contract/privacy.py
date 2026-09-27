"""Privacy projection for clinical records.

Direct identifiers are removed before a record can leave the service.
An empty projection is not useful and is rejected rather than returned.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


DIRECT_IDENTIFIERS = frozenset({
    "name",
    "identifier",
    "phone",
    "address",
    "birth_date",
    "patient_id",
})


def project(
    record: dict[str, object],
    allowed_fields: frozenset[str],
    consent_state: str = "active",
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> dict[str, object]:
    """Return only allowed, non-identifying fields."""
    if consent_state != "active":
        raise ContractError("privacy-consent-not-active")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("privacy-why-missing")
    if not record or not allowed_fields or not actor_id:
        raise ContractError("privacy-scope-missing")
    named = (actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in named):
        raise ContractError("privacy-field-forbidden")
    if allowed_fields & DIRECT_IDENTIFIERS:
        raise ContractError("privacy-field-forbidden")
    projected = {
        field: value
        for field, value in record.items()
        if field in allowed_fields and field not in DIRECT_IDENTIFIERS
    }
    if find_direct_identifier(projected):
        raise ContractError("privacy-field-forbidden")
    if not projected:
        raise ContractError("privacy-projection-empty")
    return projected


class ProjectionLedger:
    """Remember one projection so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, ...], tuple[str, str]] = {}

    def project(
        self,
        record: dict[str, object],
        allowed_fields: frozenset[str],
        consent_state: str = "active",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> dict[str, object]:
        projected = project(record, allowed_fields, consent_state, actor_id, why_code)
        key = tuple(sorted(projected))
        recorded = self._records.get(key)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("privacy-responsibility-mismatch")
        self._records.setdefault(key, incoming)
        return projected

    def restore(self, fields: tuple[str, ...], actor_id: str, why_code: str) -> None:
        """Restore one projection without treating it as a new commit."""
        if not fields or not actor_id:
            raise ContractError("privacy-scope-missing")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("privacy-why-missing")
        self._records[tuple(sorted(fields))] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, ...], tuple[str, str]], ...]:
        """Return stored projections in stable order."""
        return tuple(sorted(self._records.items()))


def find_direct_identifier(value: object, prefix: str = "") -> str:
    """Return the first direct-identifier path found anywhere in a payload."""
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            if key in DIRECT_IDENTIFIERS:
                return path
            found = find_direct_identifier(value[key], path)
            if found:
                return found
    if isinstance(value, list):
        for index, item in enumerate(value):
            found = find_direct_identifier(item, f"{prefix}[{index}]")
            if found:
                return found
    return ""


def path_has_direct_identifier(field: str, forbidden: frozenset[str] = DIRECT_IDENTIFIERS) -> bool:
    """Return whether any path segment names a direct identifier."""
    parts = field.replace("[", ".").replace("]", "").split(".")
    return any(part in forbidden for part in parts)
