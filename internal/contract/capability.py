"""Capability statement version checks.

The statement must name this software and a compatible FHIR version. A
missing or skipped version fails closed. This is not an official capability
discovery endpoint.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.version import compatible


def require_statement(payload: dict[str, object]) -> str:
    """Return the accepted FHIR version."""
    if payload.get("resourceType") != "CapabilityStatement":
        raise ContractError("capability-type-rejected")
    if payload.get("status") != "active":
        raise ContractError("capability-status-invalid")
    software = payload.get("software")
    name = str(software.get("name", "")) if isinstance(software, dict) else ""
    if name != "atlas":
        raise ContractError("capability-software-invalid")
    version = str(payload.get("fhirVersion", ""))
    if version == "":
        raise ContractError("capability-version-missing")
    if not compatible(version):
        raise ContractError("capability-version-incompatible")
    return version
