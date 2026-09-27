"""Human review entry point.

The state machine cannot approve a suggestion until the domain checks accept
its evidence, rule pack, consent, and human actor.
"""
from __future__ import annotations

from internal.contract.consent import ConsentLedger
from internal.contract.domain import SuggestionDraft, ready_for_review
from internal.contract.errors import ContractError
from internal.contract.evidence import EvidenceLedger
from internal.contract.medication import MedicationLedger
from internal.contract.rules import RuleLedger
from internal.hitl.state.machine import Suggestion, TransitionError, transition


def queue_for_review(
    draft: SuggestionDraft,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> Suggestion:
    """Move a valid draft to pending review. Invalid drafts do not change."""
    actor = ready_for_review(draft, evidence, rules, consents, medications)
    suggestion = Suggestion(draft.suggestion_id, draft.patient_ref, draft.action)
    suggestion.content_digest = draft.content_digest
    try:
        transition(suggestion, "EVIDENCE_READY", actor.actor_id, reason=actor.why_code)
        transition(suggestion, "PENDING_REVIEW", actor.actor_id, reason=actor.why_code)
    except TransitionError as exc:
        raise ContractError(str(exc)) from exc
    return suggestion


def approve_one(
    suggestion: Suggestion,
    draft: SuggestionDraft,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> Suggestion:
    """Record one human approval only after the same draft checks pass again."""
    actor = ready_for_review(draft, evidence, rules, consents, medications)
    if suggestion.suggestion_id != draft.suggestion_id:
        raise ContractError("review-suggestion-mismatch")
    if suggestion.state != "PENDING_REVIEW":
        raise ContractError("review-state-invalid")
    try:
        transition(suggestion, "APPROVED_ONE", actor.actor_id, reason=actor.why_code)
    except TransitionError as exc:
        raise ContractError(str(exc)) from exc
    return suggestion


def first_signoff(state: str, actor_id: str) -> str:
    """Allow one human signoff only from pending review."""
    if state != "PENDING_REVIEW":
        raise ContractError("signoff-state-invalid")
    if actor_id == "" or actor_id == "system":
        raise ContractError("signoff-actor-forbidden")
    return "APPROVED_ONE"


_DUAL_ACTIONS = frozenset({"medication", "writeback"})


def dual_scope(action: str) -> bool:
    """Return whether this action needs an independent second reviewer."""
    if action not in {"medication", "writeback", "note"}:
        raise ContractError("dual-scope-invalid")
    return action in _DUAL_ACTIONS


def approve_second(
    suggestion: Suggestion,
    draft: SuggestionDraft,
    second_actor_id: str,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> Suggestion:
    """Require an independent second reviewer before ordinary approval."""
    if suggestion.state != "APPROVED_ONE":
        raise ContractError("second-review-state-invalid")
    ready_for_review(draft, evidence, rules, consents, medications)
    if suggestion.suggestion_id != draft.suggestion_id or suggestion.content_digest != draft.content_digest:
        raise ContractError("review-suggestion-mismatch")
    if not second_actor_id or second_actor_id in suggestion.reviewers:
        raise ContractError("second-reviewer-not-independent")
    if second_actor_id == "system":
        raise ContractError("system-cannot-review")
    try:
        transition(
            suggestion,
            "SECOND_REVIEW_PENDING",
            second_actor_id,
            reason="second-review",
            second_review_required=True,
        )
        transition(suggestion, "APPROVED", second_actor_id, reason="second-review")
    except TransitionError as exc:
        raise ContractError(str(exc)) from exc
    return suggestion


def second_denial(state: str, decision: str) -> str:
    """Stop a second reviewer denial before approval."""
    if state != "APPROVED_ONE":
        raise ContractError("second-denial-state-invalid")
    if decision == "deny":
        return "SECOND_DENIED"
    if decision == "approve":
        return "SECOND_REVIEW_PENDING"
    raise ContractError("second-denial-invalid")


_PROJECTION = {
    "DRAFT": "draft",
    "PENDING_REVIEW": "review",
    "APPROVED": "approved",
    "WRITEBACK_PENDING": "writeback",
}


def project_status(state: str) -> str:
    """Project one known suggestion state without changing it."""
    if state not in _PROJECTION:
        raise ContractError("projection-state-unknown")
    return _PROJECTION[state]
