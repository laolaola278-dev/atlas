"""Simulated clinical practitioner workflows against the audit hash chain.

Three roles are simulated with synthetic fixtures only:
- Attending physician: ordinary HITL review path (generate -> review -> approve -> writeback)
- Emergency physician: break-glass path (grant -> act -> post-review)
- Pharmacist: order verification path (receive -> interaction check -> approve)

Every step appends to a stream-specific AuditLog; each scenario ends with a
full chain verification. No real patient data appears in any field.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.audit.chain import AuditLog, AuditEvent

TENANT = "tenant-synthetic"
CAMPUS = "campus-synthetic"
OCCURRED = "2026-10-04T08:00:00Z"
POLICY = "1.0.0"
DIGEST = "b" * 64


@dataclass(frozen=True)
class Step:
    operation: str
    actor_id: str
    actor_role: str
    resource_type: str
    resource_id: str
    why_code: str
    purpose_code: str = "treatment"
    consent_decision: str = "granted"


def run_workflow(stream_id: str, steps: list[Step]) -> tuple[AuditLog, tuple[AuditEvent, ...]]:
    """Append every step to one stream and verify the finished chain."""
    log = AuditLog(stream_id)
    recorded: list[AuditEvent] = []
    for index, step in enumerate(steps, start=1):
        recorded.append(log.append({
            "event_id": f"{stream_id}-event-{index}",
            "stream_id": stream_id,
            "sequence": index,
            "tenant_id": TENANT,
            "campus_id": CAMPUS,
            "actor_id": step.actor_id,
            "actor_role": step.actor_role,
            "operation": step.operation,
            "resource_type": step.resource_type,
            "resource_id": step.resource_id,
            "purpose_code": step.purpose_code,
            "why_code": step.why_code,
            "policy_version": POLICY,
            "occurred_at": OCCURRED,
            "payload_digest": DIGEST,
            "clock_quality": "synchronized",
            "consent_decision": step.consent_decision,
        }))
    log.verify()
    return log, tuple(recorded)


def attending_ordinary_workflow() -> tuple[AuditLog, tuple[AuditEvent, ...]]:
    """DRAFT -> PENDING_REVIEW -> APPROVED -> WRITEBACK_COMMITTED with audit."""
    return run_workflow("stream-attending-synthetic", [
        Step("generate", "ai-service-synthetic", "system", "Suggestion",
             "suggestion-synthetic", "suggestion-generated", consent_decision="unspecified"),
        Step("consent-check", "consent-service-synthetic", "system", "Consent",
             "consent-synthetic", "consent-verified"),
        Step("review", "physician-synthetic", "attending", "Suggestion",
             "suggestion-synthetic", "review-decision"),
        Step("approve", "physician-synthetic", "attending", "ApprovalProof",
             "proof-synthetic", "approval-signed"),
        Step("writeback-commit", "writeback-service-synthetic", "system", "Order",
             "order-synthetic", "writeback-committed"),
    ])


def emergency_break_glass_workflow() -> tuple[AuditLog, tuple[AuditEvent, ...]]:
    """EMERGENCY_OVERRIDE -> EMERGENCY_RECORDED -> POST_REVIEW_REQUIRED."""
    return run_workflow("stream-emergency-synthetic", [
        Step("emergency-grant", "er-physician-synthetic", "emergency-attending",
             "EmergencyActionGrant", "grant-synthetic", "break-glass-justified",
             purpose_code="emergency-treatment", consent_decision="unspecified"),
        Step("emergency-act", "er-physician-synthetic", "emergency-attending",
             "MedicationOrder", "emergency-order-synthetic", "life-threatening-delay",
             purpose_code="emergency-treatment", consent_decision="unspecified"),
        Step("post-review-request", "er-physician-synthetic", "emergency-attending",
             "ReviewTask", "post-review-synthetic", "post-hoc-review-required",
             purpose_code="emergency-treatment", consent_decision="unspecified"),
    ])


def pharmacist_verification_workflow() -> tuple[AuditLog, tuple[AuditEvent, ...]]:
    """Order receipt -> deterministic interaction check -> dispense approval."""
    return run_workflow("stream-pharmacy-synthetic", [
        Step("order-received", "pharmacy-service-synthetic", "system", "MedicationOrder",
             "rx-synthetic", "order-received"),
        Step("interaction-check", "rule-engine-synthetic", "system", "RuleResult",
             "interaction-result-synthetic", "hard-rule-evaluated"),
        Step("dispense-approve", "pharmacist-synthetic", "pharmacist", "MedicationOrder",
             "rx-synthetic", "dispense-approved"),
    ])
