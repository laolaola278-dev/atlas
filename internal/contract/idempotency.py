"""Idempotency for clinical writes.

The same key with a different payload conflicts. An unknown result stays
unknown and must be reconciled; it is not permission to send the write again.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


@dataclass(frozen=True)
class WriteRecord:
    key: str
    payload_digest: str
    state: str
    target_version: str = ""
    actor_id: str = "actor-synthetic"
    why_code: str = "treatment-review"


class IdempotencyLog:
    """In-memory log used by the contract tests and later service adapter."""

    def __init__(self) -> None:
        self._records: dict[str, WriteRecord] = {}

    def begin(
        self,
        key: str,
        payload_digest: str,
        target_version: str = "",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> WriteRecord:
        if not key or not payload_digest or not actor_id:
            raise ContractError("idempotency-key-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("idempotency-why-missing")
        named = (key, actor_id, why_code)
        if any(path_has_direct_identifier(value) for value in named):
            raise ContractError("idempotency-identifier-forbidden")
        current = self._records.get(key)
        if current is None:
            record = WriteRecord(key, payload_digest, "accepted", target_version, actor_id, why_code)
            self._records[key] = record
            return record
        if current.payload_digest != payload_digest:
            raise ContractError("idempotency-conflict")
        if current.actor_id != actor_id or current.why_code != why_code:
            raise ContractError("idempotency-responsibility-mismatch")
        if current.state == "unknown":
            raise ContractError("result-unknown")
        return current

    def get(self, key: str) -> WriteRecord | None:
        """Return a record without creating one."""
        return self._records.get(key)

    def mark_unknown(self, key: str) -> WriteRecord:
        current = self._require(key)
        record = WriteRecord(
            current.key,
            current.payload_digest,
            "unknown",
            current.target_version,
            current.actor_id,
            current.why_code,
        )
        self._records[key] = record
        return record

    def mark_committed(self, key: str) -> WriteRecord:
        current = self._require(key)
        if current.state == "unknown":
            raise ContractError("result-unknown")
        record = WriteRecord(
            current.key,
            current.payload_digest,
            "committed",
            current.target_version,
            current.actor_id,
            current.why_code,
        )
        self._records[key] = record
        return record

    def receipt(self, key: str, payload_digest: str, actor_id: str, why_code: str) -> dict[str, str]:
        """Return the stored committed result without accepting another write."""
        current = self.begin(key, payload_digest, "", actor_id, why_code)
        if current.state != "committed":
            raise ContractError("idempotency-receipt-pending")
        return {"key": current.key, "state": current.state, "target_version": current.target_version}

    def restore(
        self,
        key: str,
        payload_digest: str,
        state: str,
        target_version: str = "",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> WriteRecord:
        """Restore one previously stored result without treating it as a new write."""
        if not key or not payload_digest or not actor_id or state not in {"accepted", "unknown", "committed"}:
            raise ContractError("idempotency-state-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("idempotency-why-missing")
        record = WriteRecord(key, payload_digest, state, target_version, actor_id, why_code)
        self._records[key] = record
        return record

    def _require(self, key: str) -> WriteRecord:
        try:
            return self._records[key]
        except KeyError as exc:
            raise ContractError("idempotency-key-unknown") from exc


def repeat_submit(recorded_digest: str, incoming_digest: str, recorded_state: str) -> str:
    """Return the original state when the same digest is submitted again."""
    pair = (recorded_digest, incoming_digest)
    if any(len(item) != 64 for item in pair):
        raise ContractError("repeat-digest-invalid")
    if recorded_state not in {"committed", "rejected"}:
        raise ContractError("repeat-state-invalid")
    if recorded_digest != incoming_digest:
        raise ContractError("repeat-conflict")
    return recorded_state


def withdraw_condition(state: str, written: bool) -> str:
    """Withdraw only an approval that has not been written back."""
    if state not in {"approved", "committed"} or not isinstance(written, bool):
        raise ContractError("withdraw-input-invalid")
    if written or state == "committed":
        raise ContractError("withdraw-too-late")
    return "withdrawn"


_EMERGENCY_ACTIONS = frozenset({"stabilize", "isolate"})


def emergency_action(action: str, authorizer: str) -> str:
    """Authorize one declared emergency action by a human."""
    if action not in _EMERGENCY_ACTIONS:
        raise ContractError("emergency-action-forbidden")
    if authorizer == "" or authorizer == "system":
        raise ContractError("emergency-authorizer-forbidden")
    return action


class EmergencyIntentLog:
    """Store emergency intents apart from ordinary writes."""

    def __init__(self) -> None:
        self._records: dict[str, str] = {}

    def record(self, key: str, action: str) -> str:
        if not key.startswith("emergency-") or path_has_direct_identifier(key):
            raise ContractError("emergency-intent-forbidden")
        if action not in _EMERGENCY_ACTIONS:
            raise ContractError("emergency-action-forbidden")
        recorded = self._records.get(key)
        if recorded is not None and recorded != action:
            raise ContractError("emergency-intent-conflict")
        self._records.setdefault(key, action)
        return action


def emergency_commit_guard(proof_kind: str, commit_kind: str) -> str:
    """Reject an emergency proof before it can enter an ordinary commit."""
    if proof_kind not in {"approval", "grant"} or commit_kind not in {"ordinary", "emergency"}:
        raise ContractError("commit-kind-invalid")
    if proof_kind == "grant" and commit_kind == "ordinary":
        raise ContractError("emergency-commit-forbidden")
    return commit_kind


class PostReviewQueue:
    """Hold emergency records until a human reviews them."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def enqueue(self, key: str, kind: str) -> int:
        if not key.startswith("emergency-") or path_has_direct_identifier(key):
            raise ContractError("postreview-key-forbidden")
        if kind != "emergency":
            raise ContractError("postreview-kind-invalid")
        if key in self._items:
            raise ContractError("postreview-duplicate")
        self._items[key] = kind
        return len(self._items)


def controlled_correction(state: str, reviewer: str, authorizer: str, reason: str, submitted: bool) -> str:
    """Record a correction only for an unsubmitted emergency under review."""
    if state != "POST_REVIEW_REQUIRED" or submitted:
        raise ContractError("correction-state-invalid")
    if reviewer == "" or reviewer in {authorizer, "system"}:
        raise ContractError("correction-reviewer-not-independent")
    if reason in {"", "unknown", "unspecified"} or path_has_direct_identifier(reason):
        raise ContractError("correction-reason-missing")
    return "corrected"


_BREAK_GLASS = frozenset({"life-threat", "system-down"})


def break_glass_reason(code: str, authorizer: str) -> str:
    """Accept one registered break-glass reason from a human."""
    if code not in _BREAK_GLASS:
        raise ContractError("break-glass-reason-invalid")
    if authorizer == "" or authorizer == "system":
        raise ContractError("break-glass-authorizer-forbidden")
    return code


def review_policy_version(proof_version: str, current: str) -> str:
    """Accept the current review policy or its immediately previous minor."""
    allowed = {"1.1": {"1.1", "1.0"}, "1.0": {"1.0"}}
    if current not in allowed or proof_version == "":
        raise ContractError("review-policy-invalid")
    if proof_version not in allowed[current]:
        raise ContractError("review-policy-mismatch")
    return proof_version


def audit_link(event_digest: str, proof_digest: str, operation: str) -> str:
    """Link an audit event only when it carries the proof digest."""
    pair = (event_digest, proof_digest)
    if any(len(item) != 64 for item in pair):
        raise ContractError("audit-link-digest-invalid")
    if operation not in {"approve", "deny", "correct"}:
        raise ContractError("audit-link-operation-invalid")
    if event_digest != proof_digest:
        raise ContractError("audit-link-mismatch")
    return operation


def bypass_path(path_id: int, approved: bool) -> str:
    """Reject every numbered bypass, approved or not."""
    if path_id < 1 or path_id > 100:
        raise ContractError("bypass-path-invalid")
    if not isinstance(approved, bool):
        raise ContractError("bypass-path-invalid")
    raise ContractError("bypass-forbidden")
