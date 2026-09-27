"""Synthetic FHIR profile fixtures.

These fixtures contain no patient identifiers. They only prove that a
resource declares one profile from the local catalog.
"""
from __future__ import annotations

import json
from pathlib import Path

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_ROOT = Path(__file__).resolve().parents[2]
_CATALOG = _ROOT / "api" / "fhir" / "profiles" / "catalog.json"
_FIXTURES = _ROOT / "testdata" / "fhir" / "synthetic"


def load_catalog() -> dict[str, str]:
    """Return profile URLs keyed by resource type."""
    try:
        payload = json.loads(_CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("profile-catalog-corrupt") from exc
    profiles = payload.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        raise ContractError("profile-catalog-corrupt")
    loaded: dict[str, str] = {}
    for item in profiles:
        if not isinstance(item, dict):
            raise ContractError("profile-catalog-corrupt")
        resource_type = str(item.get("resource_type", ""))
        profile_url = str(item.get("profile_url", ""))
        if not resource_type or not profile_url:
            raise ContractError("profile-catalog-corrupt")
        loaded[resource_type] = profile_url
    return loaded


DIFFERENTIAL = {
    "Observation": {"required": frozenset({"status"}), "forbidden": frozenset({"name", "identifier"})},
    "ServiceRequest": {"required": frozenset({"priority"}), "forbidden": frozenset({"name", "identifier"})},
}


def require_differential(payload: dict[str, object]) -> None:
    """Reject a declared profile that misses a required field or carries a forbidden one."""
    require_declared_profile(payload)
    resource_type = str(payload.get("resourceType", ""))
    rules = DIFFERENTIAL.get(resource_type)
    if rules is None:
        raise ContractError("profile-differential-missing")
    required = rules["required"]
    forbidden = rules["forbidden"]
    absent = [name for name in sorted(required) if payload.get(name) in {None, ""}]
    present = [name for name in sorted(forbidden) if name in payload]
    if absent:
        raise ContractError("profile-required-missing")
    if present:
        raise ContractError("profile-forbidden-present")


def require_declared_profile(payload: dict[str, object]) -> str:
    """Reject a resource whose profile is absent from the local catalog."""
    catalog = load_catalog()
    resource_type = str(payload.get("resourceType", ""))
    expected = catalog.get(resource_type, "")
    meta = payload.get("meta", {})
    profiles = meta.get("profile", []) if isinstance(meta, dict) else []
    if not expected or not isinstance(profiles, list) or expected not in profiles:
        raise ContractError("profile-not-declared")
    if payload.get("synthetic") is not True:
        raise ContractError("profile-fixture-not-synthetic")
    actor_id = str(payload.get("actorId", "actor-synthetic"))
    why_code = str(payload.get("whyCode", "treatment-review"))
    if not actor_id:
        raise ContractError("profile-actor-missing")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("profile-why-missing")
    if path_has_direct_identifier(actor_id) or path_has_direct_identifier(why_code):
        raise ContractError("profile-identifier-forbidden")
    return expected


class ProfileLedger:
    """Remember one resource profile so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def require(self, payload: dict[str, object]) -> str:
        profile = require_declared_profile(payload)
        resource_type = str(payload.get("resourceType", ""))
        actor_id = str(payload.get("actorId", "actor-synthetic"))
        why_code = str(payload.get("whyCode", "treatment-review"))
        recorded = self._records.get(resource_type)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("profile-responsibility-mismatch")
        self._records.setdefault(resource_type, incoming)
        return profile

    def restore(self, resource_type: str, actor_id: str, why_code: str) -> None:
        """Restore one accepted profile without treating it as a new review."""
        if not resource_type or not actor_id:
            raise ContractError("profile-actor-missing")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("profile-why-missing")
        self._records[resource_type] = (actor_id, why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored profile decisions in stable order."""
        return tuple(sorted(self._records.items()))


def load_synthetic_fixture(name: str) -> dict[str, object]:
    """Load one named synthetic fixture and require its declared profile."""
    path = _FIXTURES / f"{name}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("profile-fixture-corrupt") from exc
    if not isinstance(payload, dict):
        raise ContractError("profile-fixture-corrupt")
    require_declared_profile(payload)
    return payload
