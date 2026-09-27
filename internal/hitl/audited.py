"""Review actions with an append-only audit record.

A successful queue or approval appends one hash-chained event. A rejected
draft does not create a success event. The audit payload is a digest, not
clinical text.
"""
from __future__ import annotations

import hashlib

from internal.audit.chain import AuditEvent, AuditLog
from internal.contract.consent import ConsentLedger
from internal.contract.domain import SuggestionDraft
from internal.contract.errors import ContractError
from internal.contract.evidence import EvidenceLedger
from internal.contract.medication import MedicationLedger
from internal.contract.rules import RuleLedger
from internal.hitl.review import approve_one, queue_for_review
from internal.hitl.state.machine import Suggestion


def _event(
    log: AuditLog,
    draft: SuggestionDraft,
    operation: str,
    resource_id: str,
    consent_decision: str = "",
) -> AuditEvent:
    actor = draft.actor
    payload = "|".join((
        draft.suggestion_id,
        draft.content_digest,
        operation,
        str(actor.get("why_code", "")),
    ))
    return log.append({
        "event_id": f"{draft.suggestion_id}-{operation}-{len(log.events) + 1}",
        "stream_id": log.stream_id,
        "sequence": len(log.events) + 1,
        "tenant_id": actor.get("tenant_id", ""),
        "campus_id": actor.get("campus_id", ""),
        "actor_id": actor.get("actor_id", ""),
        "actor_role": actor.get("actor_role", ""),
        "operation": operation,
        "resource_type": "Suggestion",
        "resource_id": resource_id,
        "purpose_code": actor.get("purpose_code", ""),
        "why_code": actor.get("why_code", ""),
        "policy_version": "1.0.0",
        "occurred_at": actor.get("occurred_at", ""),
        "payload_digest": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "clock_quality": "synchronized",
        "consent_decision": consent_decision or draft.consent.state,
    })


def queue_and_audit(
    draft: SuggestionDraft,
    log: AuditLog,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> Suggestion:
    """Queue a valid draft and append the audit event afterwards."""
    suggestion = queue_for_review(draft, evidence, rules, consents, medications)
    _event(log, draft, "queue-review", suggestion.suggestion_id)
    log.verify()
    return suggestion


def approve_and_audit(
    suggestion: Suggestion,
    draft: SuggestionDraft,
    log: AuditLog,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> Suggestion:
    """Approve one step and append a separate audit event."""
    if not log.events:
        raise ContractError("review-audit-missing")
    approved = approve_one(suggestion, draft, evidence, rules, consents, medications)
    _event(log, draft, "approve-one", approved.suggestion_id)
    log.verify()
    return approved


def append_review_event(
    log: AuditLog,
    draft: SuggestionDraft,
    operation: str,
    resource_id: str,
) -> AuditEvent:
    """Append one verified review event without changing suggestion state."""
    event = _event(log, draft, operation, resource_id)
    log.verify()
    return event


def append_actor_event(
    log: AuditLog,
    *,
    suggestion_id: str,
    operation: str,
    actor_id: str,
    actor_role: str,
    purpose_code: str,
    occurred_at: str,
    why_code: str,
    tenant_id: str,
    campus_id: str,
    payload_digest: str,
    consent_decision: str = "",
) -> AuditEvent:
    """Append one hash-chained event for a commit or emergency closure."""
    context = {
        "actor_id": actor_id,
        "actor_role": actor_role,
        "tenant_id": tenant_id,
        "campus_id": campus_id,
        "purpose_code": purpose_code,
        "why_code": why_code,
        "occurred_at": occurred_at,
    }
    if not all((suggestion_id, operation, payload_digest, *context.values())):
        raise ContractError("audit-context-incomplete")
    event = log.append({
        "event_id": f"{suggestion_id}-{operation}-{len(log.events) + 1}",
        "stream_id": log.stream_id,
        "sequence": len(log.events) + 1,
        **context,
        "operation": operation,
        "resource_type": "Suggestion",
        "resource_id": suggestion_id,
        "policy_version": "1.0.0",
        "payload_digest": payload_digest,
        "clock_quality": "synchronized",
        "consent_decision": consent_decision,
    })
    log.verify()
    return event
