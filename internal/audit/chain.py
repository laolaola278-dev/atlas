"""Append-only audit hash chain.

The canonical encoding has a fixed field order. A changed actor, purpose,
sequence, or previous hash changes the event hash and breaks verification.
"""
from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


GENESIS = "0" * 64
REQUIRED = (
    "event_id",
    "stream_id",
    "sequence",
    "tenant_id",
    "campus_id",
    "actor_id",
    "actor_role",
    "operation",
    "resource_type",
    "resource_id",
    "purpose_code",
    "why_code",
    "policy_version",
    "occurred_at",
    "payload_digest",
    "clock_quality",
    "consent_decision",
)


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    stream_id: str
    sequence: int
    tenant_id: str
    campus_id: str
    actor_id: str
    actor_role: str
    operation: str
    resource_type: str
    resource_id: str
    purpose_code: str
    why_code: str
    policy_version: str
    occurred_at: str
    payload_digest: str
    clock_quality: str
    consent_decision: str
    previous_hash: str
    event_hash: str


def _canonical(fields: dict[str, str]) -> bytes:
    return "\n".join(f"{name}={fields[name]}" for name in (*REQUIRED, "previous_hash")).encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class AuditLog:
    """One stream. Events can only be appended, never replaced."""

    def __init__(self, stream_id: str, sink: Callable[[AuditEvent], None] | None = None) -> None:
        if not stream_id:
            raise ContractError("audit-stream-invalid")
        if path_has_direct_identifier(stream_id):
            raise ContractError("audit-identifier-forbidden")
        self.stream_id = stream_id
        self.sink = sink
        self._events: list[AuditEvent] = []

    def append(self, fields: dict[str, object]) -> AuditEvent:
        values = {name: str(fields.get(name, "")) for name in REQUIRED}
        if values["why_code"] in {"", "unknown"}:
            raise ContractError("audit-why-missing")
        if any(not values[name] for name in REQUIRED if name not in {"sequence", "why_code", "consent_decision"}):
            raise ContractError("audit-context-incomplete")
        if not values["consent_decision"]:
            values["consent_decision"] = "unspecified"
        if not compatible(values["policy_version"]):
            raise ContractError("audit-version-incompatible")
        if any(path_has_direct_identifier(value) for value in values.values()):
            raise ContractError("audit-identifier-forbidden")
        sequence = len(self._events) + 1
        if int(fields.get("sequence", sequence)) != sequence:
            raise ContractError("audit-sequence-invalid")
        values["sequence"] = str(sequence)
        if values["stream_id"] != self.stream_id:
            raise ContractError("audit-stream-mismatch")
        previous = self._events[-1].event_hash if self._events else GENESIS
        encoded = _canonical({**values, "previous_hash": previous})
        event = AuditEvent(
            previous_hash=previous,
            event_hash=_digest(encoded),
            **{name: values[name] if name != "sequence" else sequence for name in REQUIRED},
        )
        self._events.append(event)
        if self.sink is not None:
            self.sink(event)
        return event

    def verify(self) -> None:
        previous = GENESIS
        for index, event in enumerate(self._events, start=1):
            if event.sequence != index or event.previous_hash != previous:
                raise ContractError("audit-chain-broken")
            values = {name: str(getattr(event, name)) for name in REQUIRED}
            encoded = _canonical({**values, "previous_hash": previous})
            if _digest(encoded) != event.event_hash:
                raise ContractError("audit-hash-mismatch")
            previous = event.event_hash

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


def to_fhir_audit_event(event: AuditEvent) -> dict[str, object]:
    """Map one chain event to a FHIR AuditEvent without free text."""
    mapped = {
        "action": event.operation,
        "agentRole": event.actor_role,
        "entityDigest": event.payload_digest,
        "id": event.event_id,
        "occurredAt": event.occurred_at,
        "outcome": event.consent_decision,
        "purposeCode": event.purpose_code,
        "resourceType": "AuditEvent",
        "subtype": event.resource_type,
    }
    if any(path_has_direct_identifier(str(value)) for value in mapped.values()):
        raise ContractError("audit-fhir-identifier-forbidden")
    if len(event.payload_digest) != 64 or len(event.event_hash) != 64:
        raise ContractError("audit-fhir-digest-invalid")
    mapped["eventHash"] = event.event_hash
    return mapped
