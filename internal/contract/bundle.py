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


REQUEST_METHODS = frozenset({"DELETE", "GET", "PATCH", "POST", "PUT"})


def entry_reference(item: object) -> str:
    """Return the logical reference one bundle entry points at.

    Two shapes are accepted. A real FHIR transaction entry carries the resource
    itself, so the reference is derived from its resourceType and id. The Atlas
    manifest shape names the reference directly. Both must resolve to Type/id;
    an entry that resolves to nothing is rejected by require_bundle.
    """
    if not isinstance(item, dict):
        return ""
    direct = item.get("reference")
    if isinstance(direct, str) and direct:
        return direct
    resource = item.get("resource")
    if isinstance(resource, dict):
        kind = str(resource.get("resourceType", ""))
        token = str(resource.get("id", ""))
        if kind and token:
            return f"{kind}/{token}"
    return ""


def bundle_entry_references(payload: dict[str, object]) -> tuple[str, ...]:
    """Return every entry reference in bundle order."""
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return ()
    return tuple(entry_reference(item) for item in entries)


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
        if isinstance(item, dict) and isinstance(item.get("resource"), dict):
            # A FHIR-shaped entry must also say what to do with the resource,
            # otherwise the transaction has no server-side meaning.
            request = item.get("request")
            method = str(request.get("method", "")) if isinstance(request, dict) else ""
            url = str(request.get("url", "")) if isinstance(request, dict) else ""
            if method not in REQUEST_METHODS or not url:
                raise ContractError("bundle-entry-request-invalid")
        reference = entry_reference(item)
        kind, _, token = str(reference).partition("/")
        if kind not in ENTRY_TYPES or token == "" or path_has_direct_identifier(token):
            raise ContractError("bundle-entry-invalid")
        if reference in seen:
            raise ContractError("bundle-entry-duplicate")
        seen.add(str(reference))
