"""HITL write-eligibility state machine.

This is the P0 safety reference. An emergency grant can record one emergency
fact, but it can never enter the ordinary approved or committed path.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class TransitionError(ValueError):
    """Raised when a clinical write transition is not allowed."""


ORDINARY_COMMITTED = "WRITEBACK_COMMITTED"
FORBIDDEN_FROM_EMERGENCY = {
    "APPROVED",
    "WRITEBACK_PENDING",
    ORDINARY_COMMITTED,
}

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"EVIDENCE_READY", "GENERATION_FAILED"},
    "GENERATION_FAILED": {"RETRYING", "EXPIRED"},
    "RETRYING": {"DRAFT", "EXPIRED"},
    "EVIDENCE_READY": {"PENDING_REVIEW", "BLOCKED"},
    "BLOCKED": {"RETRYING", "EXPIRED"},
    "PENDING_REVIEW": {
        "APPROVED_ONE",
        "REJECTED",
        "NEEDS_INFO",
        "WITHDRAWN",
        "EXPIRED",
        "EMERGENCY_OVERRIDE",
    },
    "NEEDS_INFO": {"EVIDENCE_READY", "REJECTED"},
    "APPROVED_ONE": {"SECOND_REVIEW_PENDING", "APPROVED"},
    "SECOND_REVIEW_PENDING": {
        "APPROVED",
        "REJECTED",
        "EXPIRED",
        "EMERGENCY_OVERRIDE",
    },
    "APPROVED": {"WRITEBACK_PENDING", "WITHDRAWN", "ROLLED_BACK"},
    "WRITEBACK_PENDING": {"WRITEBACK_COMMITTED", "WRITE_UNKNOWN", "WRITE_FAILED"},
    "WRITE_UNKNOWN": {"WRITEBACK_COMMITTED", "WRITE_FAILED"},
    "WRITE_FAILED": {"MANUAL_RECONCILIATION"},
    "MANUAL_RECONCILIATION": {"WRITEBACK_COMMITTED", "ROLLED_BACK"},
    "WITHDRAWN": {"EVIDENCE_READY"},
    "ROLLED_BACK": {"ARCHIVED"},
    "WRITEBACK_COMMITTED": {"ARCHIVED"},
    "EMERGENCY_OVERRIDE": {"EMERGENCY_PENDING_CONFIRMATION", "CORRECTION_REQUIRED"},
    "EMERGENCY_PENDING_CONFIRMATION": {
        "EMERGENCY_RECORDED",
        "EMERGENCY_UNKNOWN",
        "CORRECTION_REQUIRED",
    },
    "EMERGENCY_UNKNOWN": {"EMERGENCY_RECORDED", "CORRECTION_REQUIRED"},
    "EMERGENCY_RECORDED": {"POST_REVIEW_REQUIRED"},
    "POST_REVIEW_REQUIRED": {"RECONCILIATION_CONFIRMED", "CORRECTION_REQUIRED"},
    "CORRECTION_REQUIRED": {"RECONCILIATION_CONFIRMED"},
    "RECONCILIATION_CONFIRMED": {"ARCHIVED"},
    "REJECTED": set(),
    "EXPIRED": set(),
    "ARCHIVED": set(),
}


@dataclass
class Suggestion:
    """Mutable safety projection for one suggestion version."""

    suggestion_id: str
    patient_ref: str
    action: str
    state: str = "DRAFT"
    version: int = 1
    write_intent_id: str | None = None
    submitted: bool = False
    reviewers: set[str] = field(default_factory=set)
    reviewer_roles: dict[str, str] = field(default_factory=dict)
    emergency_nonce: str | None = None
    content_digest: str = ""
    emergency_grant_id: str = ""
    correction_recorded: bool = False
    history: list[tuple[str, str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.suggestion_id or not self.patient_ref or not self.action:
            raise TransitionError("suggestion-context-incomplete")
        if self.state not in TRANSITIONS:
            raise TransitionError("state-unknown")


def _reject(code: str) -> None:
    raise TransitionError(code)


def transition(
    suggestion: Suggestion,
    target: str,
    actor: str,
    *,
    reason: str,
    second_review_required: bool = False,
    emergency_nonce: str | None = None,
) -> Suggestion:
    """Move one step or fail closed. The suggestion is not changed on failure."""
    if not actor or not reason:
        _reject("actor-or-reason-missing")
    if target not in TRANSITIONS:
        _reject("target-unknown")
    allowed = TRANSITIONS[suggestion.state]
    if target not in allowed:
        _reject("transition-forbidden")
    if suggestion.state.startswith("EMERGENCY") or suggestion.state in {
        "POST_REVIEW_REQUIRED",
        "CORRECTION_REQUIRED",
        "RECONCILIATION_CONFIRMED",
    }:
        if target in FORBIDDEN_FROM_EMERGENCY:
            _reject("emergency-cannot-enter-ordinary-commit")
    if target == "SECOND_REVIEW_PENDING" and not second_review_required:
        _reject("second-review-not-required")
    if target == "APPROVED" and suggestion.state == "APPROVED_ONE" and second_review_required:
        _reject("second-review-required")
    if target == "APPROVED" and suggestion.state == "SECOND_REVIEW_PENDING":
        if actor in suggestion.reviewers:
            _reject("second-reviewer-not-independent")
    if target == "WITHDRAWN" and suggestion.write_intent_id:
        _reject("intent-exists-use-rollback")
    if target == "ROLLED_BACK" and suggestion.state == "APPROVED" and not suggestion.write_intent_id:
        _reject("no-intent-use-withdrawn")
    if target == "WRITEBACK_PENDING" and suggestion.write_intent_id is None:
        _reject("write-intent-missing")
    if target == "EMERGENCY_PENDING_CONFIRMATION":
        if not emergency_nonce or emergency_nonce == suggestion.emergency_nonce:
            _reject("emergency-nonce-invalid")
    snapshot = Suggestion(
        suggestion_id=suggestion.suggestion_id,
        patient_ref=suggestion.patient_ref,
        action=suggestion.action,
        state=suggestion.state,
        version=suggestion.version,
        write_intent_id=suggestion.write_intent_id,
        submitted=suggestion.submitted,
        reviewers=set(suggestion.reviewers),
        reviewer_roles=dict(suggestion.reviewer_roles),
        emergency_nonce=suggestion.emergency_nonce,
        content_digest=suggestion.content_digest,
        emergency_grant_id=suggestion.emergency_grant_id,
        history=list(suggestion.history),
    )
    suggestion.state = target
    suggestion.version += 1
    if target in {"APPROVED_ONE", "APPROVED"}:
        suggestion.reviewers.add(actor)
        suggestion.reviewer_roles.setdefault(actor, "")
    if target == "EMERGENCY_PENDING_CONFIRMATION":
        suggestion.emergency_nonce = emergency_nonce
    if target == ORDINARY_COMMITTED:
        suggestion.submitted = True
    suggestion.history.append((snapshot.state, target, actor))
    return suggestion
