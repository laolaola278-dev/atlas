"""Medication order drafts.

A draft is not an order. It keeps a synthetic reference and a digest, and it
cannot be submitted from this gate.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def order_draft(order_ref: str, digest: str, synthetic: bool) -> dict[str, str]:
    """Accept one unsubmitted synthetic draft."""
    named = order_ref.strip()
    digest_ok = len(digest) == 64
    if named == "" or path_has_direct_identifier(named):
        raise ContractError("order-reference-forbidden")
    if synthetic is not True:
        raise ContractError("order-not-synthetic")
    if not digest_ok:
        raise ContractError("order-digest-invalid")
    return {"state": "draft", "ref": named, "kept": digest}


def submit_gate(state: str, proof_kind: str) -> str:
    """Submit only an approved draft. Every other proof stops here."""
    if state != "draft":
        raise ContractError("order-state-invalid")
    if proof_kind == "":
        raise ContractError("order-proof-missing")
    if proof_kind != "approval":
        raise ContractError("order-proof-rejected")
    return "submitted"


def missing_proof(proof_id: str, digest: str) -> str:
    """Reject an order whose approval proof is absent or incomplete."""
    if proof_id == "" or digest == "":
        raise ContractError("order-proof-absent")
    if len(digest) != 64:
        raise ContractError("order-proof-digest-invalid")
    return proof_id


def subject_match(order_ref: str, proof_ref: str) -> str:
    """Accept an order only when it names the proof subject."""
    pair = (order_ref.strip(), proof_ref.strip())
    if any(item == "" for item in pair):
        raise ContractError("order-subject-missing")
    if any(path_has_direct_identifier(item) for item in pair):
        raise ContractError("order-subject-forbidden")
    if pair[0] != pair[1]:
        raise ContractError("order-subject-mismatch")
    return pair[0]


def pharmacy_receipt(state: str, receipt: str) -> str:
    """Accept a pharmacy receipt only after the order was submitted."""
    if state != "submitted":
        raise ContractError("pharmacy-state-invalid")
    if receipt == "unknown":
        raise ContractError("pharmacy-result-unknown")
    if receipt not in {"dispensed", "rejected"}:
        raise ContractError("pharmacy-receipt-invalid")
    return receipt


def duplicate_order(active: tuple[str, ...], incoming: str) -> str:
    """Reject an incoming digest that is already active."""
    if len(incoming) != 64 or any(len(item) != 64 for item in active):
        raise ContractError("duplicate-digest-invalid")
    if len(active) > 100:
        raise ContractError("duplicate-set-invalid")
    if incoming in active:
        raise ContractError("duplicate-order")
    return incoming


def cancel_or_correct(state: str, action: str) -> str:
    """Cancel a submitted order, or correct one already dispensed."""
    if state not in {"submitted", "dispensed"} or action not in {"cancel", "correct"}:
        raise ContractError("order-change-invalid")
    if state == "dispensed" and action == "cancel":
        raise ContractError("order-cancel-too-late")
    if state == "submitted" and action == "correct":
        raise ContractError("order-correct-too-early")
    return action


def isolate_emergency_order(lane: str, table: str) -> str:
    """Keep an emergency order out of the ordinary table."""
    if lane not in {"ordinary", "emergency"} or table not in {"ordinary", "emergency"}:
        raise ContractError("order-lane-invalid")
    if lane == "emergency" and table != "emergency":
        raise ContractError("order-emergency-isolated")
    if lane == "ordinary" and table == "emergency":
        raise ContractError("order-ordinary-isolated")
    return table


def order_audit(order_digest: str, event_digest: str, action: str) -> str:
    """Record an order action only when both digests match."""
    pair = (order_digest, event_digest)
    if any(len(item) != 64 for item in pair):
        raise ContractError("order-audit-digest-invalid")
    if action not in {"submit", "cancel", "correct"}:
        raise ContractError("order-audit-action-invalid")
    if order_digest != event_digest:
        raise ContractError("order-audit-mismatch")
    return action
