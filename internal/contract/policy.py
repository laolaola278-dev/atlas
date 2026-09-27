"""Fail-closed access policy.

Unknown fields, missing purpose, or a missing policy version never allow a
clinical read or write. Emergency access is a separate reason, not a bypass.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


CONTRACT_VERSION = "1.0.0"


@dataclass(frozen=True)
class AccessRequest:
    tenant_id: str
    campus_id: str
    purpose_code: str
    policy_version: str
    action: str
    actor_id: str = "actor-synthetic"
    why_code: str = "treatment-review"
    emergency: bool = False
    fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    policy_version: str
    reason_codes: tuple[str, ...]


_KNOWN_FIELDS = frozenset({
    "tenant_id",
    "campus_id",
    "purpose_code",
    "policy_version",
    "action",
    "actor_id",
    "why_code",
    "emergency",
    "fields",
    "consent_state",
    "resource_id",
})


def evaluate(payload: dict[str, object]) -> AccessDecision:
    """Evaluate one request. Any uncertainty returns denied."""
    unknown = set(payload) - _KNOWN_FIELDS
    if unknown:
        return AccessDecision(False, CONTRACT_VERSION, ("unknown-field",))
    try:
        request = AccessRequest(
            tenant_id=str(payload.get("tenant_id", "")),
            campus_id=str(payload.get("campus_id", "")),
            purpose_code=str(payload.get("purpose_code", "")),
            policy_version=str(payload.get("policy_version", "")),
            action=str(payload.get("action", "")),
            actor_id=str(payload.get("actor_id", "actor-synthetic")),
            why_code=str(payload.get("why_code", "treatment-review")),
            emergency=bool(payload.get("emergency", False)),
            fields=frozenset(payload.get("fields", ())),
        )
        consent_state = str(payload.get("consent_state", "active"))
    except (TypeError, ValueError) as exc:
        raise ContractError("policy-payload-invalid") from exc
    reasons: list[str] = []
    if not compatible(request.policy_version):
        reasons.append("policy-version-incompatible")
    if not request.tenant_id or not request.campus_id:
        reasons.append("scope-missing")
    if not request.purpose_code or not request.action:
        reasons.append("purpose-missing")
    if not request.actor_id:
        reasons.append("actor-context-incomplete")
    if request.why_code in {"", "unknown", "unspecified"}:
        reasons.append("actor-why-missing")
    scoped = (
        request.tenant_id,
        request.campus_id,
        request.purpose_code,
        request.action,
        request.actor_id,
        request.why_code,
    )
    if any(path_has_direct_identifier(value) for value in scoped):
        reasons.append("policy-identifier-forbidden")
    if request.emergency and "emergency-reason" not in request.fields:
        reasons.append("emergency-reason-missing")
    if consent_state != "active" and not request.emergency:
        reasons.append("consent-not-active")
    if reasons:
        return AccessDecision(False, CONTRACT_VERSION, tuple(reasons))
    return AccessDecision(True, CONTRACT_VERSION, ("allowed",))


class PolicyLedger:
    """Remember one access scope so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str, str, str], tuple[str, str]] = {}

    def evaluate(self, payload: dict[str, object]) -> AccessDecision:
        decision = evaluate(payload)
        if not decision.allowed:
            return decision
        key = (
            str(payload.get("tenant_id", "")),
            str(payload.get("campus_id", "")),
            str(payload.get("purpose_code", "")),
            str(payload.get("action", "")),
            str(payload.get("resource_id", "")),
        )
        incoming = (
            str(payload.get("actor_id", "actor-synthetic")),
            str(payload.get("why_code", "treatment-review")),
        )
        recorded = self._records.get(key)
        if recorded is not None and recorded[0] != incoming[0]:
            return AccessDecision(False, CONTRACT_VERSION, ("policy-responsibility-mismatch",))
        self._records.setdefault(key, incoming)
        return decision

    def restore(self, key: tuple[str, ...], actor_id: str, why_code: str) -> None:
        """Restore one allowed decision without treating it as a new request."""
        if len(key) != 5 or not all(key) or not actor_id or why_code in {"", "unknown", "unspecified"}:
            raise ContractError("policy-payload-invalid")
        self._records[key] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, ...], tuple[str, str]], ...]:
        """Return stored policy decisions in stable order."""
        return tuple(sorted(self._records.items()))
