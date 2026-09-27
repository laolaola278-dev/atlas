"""Bundle transaction boundaries.

A transaction bundle must name its type and carry one to twenty entries.
Each entry points at an allowed clinical resource. This is not the official
HAPI validator.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


ENTRY_TYPES = frozenset({
    "AllergyIntolerance",
    "Condition",
    "DiagnosticReport",
    "DocumentReference",
    "Encounter",
    "MedicationRequest",
    "Observation",
    "Procedure",
    "ServiceRequest",
})


def require_bundle(payload: dict[str, object]) -> None:
    """Reject a bundle that has no transaction boundary."""
    if payload.get("resourceType") != "Bundle":
        raise ContractError("bundle-type-rejected")
    if payload.get("type") != "transaction":
        raise ContractError("bundle-type-invalid")
    entries = payload.get("entry")
    if not isinstance(entries, list) or not entries:
        raise ContractError("bundle-empty")
    if len(entries) > 20:
        raise ContractError("bundle-too-large")
    seen: set[str] = set()
    for item in entries:
        reference = item.get("reference") if isinstance(item, dict) else ""
        kind, _, token = str(reference).partition("/")
        if kind not in ENTRY_TYPES or token == "" or path_has_direct_identifier(token):
            raise ContractError("bundle-entry-invalid")
        if reference in seen:
            raise ContractError("bundle-entry-duplicate")
        seen.add(str(reference))
