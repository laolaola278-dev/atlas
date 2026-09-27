"""Human review queue for identity candidates.

A queued item stays a candidate. The queue never merges records and never
stores a direct identifier.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


class ReviewQueue:
    """One ordered queue of review-required candidates."""

    def __init__(self) -> None:
        self._items: dict[str, tuple[str, str]] = {}

    def enqueue(self, candidate_id: str, digest: str, decision: str) -> int:
        """Store one candidate and return the queue size."""
        if candidate_id == "" or path_has_direct_identifier(candidate_id):
            raise ContractError("queue-identifier-forbidden")
        if len(digest) != 64:
            raise ContractError("queue-digest-invalid")
        if decision != "review-required":
            raise ContractError("queue-decision-invalid")
        if candidate_id in self._items:
            raise ContractError("queue-duplicate")
        self._items[candidate_id] = (digest, decision)
        return len(self._items)

    def reject_merge(self, candidate_id: str) -> None:
        """Refuse to turn a queued candidate into a merged identity."""
        if candidate_id not in self._items:
            raise ContractError("queue-candidate-missing")
        raise ContractError("queue-merge-forbidden")

    def approve_merge(self, candidate_id: str, first: str, second: str) -> str:
        """Allow a merge only after two different reviewers sign."""
        if candidate_id not in self._items:
            raise ContractError("queue-candidate-missing")
        if first == "" or second == "":
            raise ContractError("merge-signature-missing")
        if path_has_direct_identifier(first) or path_has_direct_identifier(second):
            raise ContractError("queue-identifier-forbidden")
        if first == second:
            raise ContractError("merge-same-reviewer")
        digest, _decision = self._items[candidate_id]
        return digest

    def split(self, candidate_id: str, first: str, second: str, reason: str) -> dict[str, str]:
        """Record a reversible split without erasing the original digest."""
        digest = self.approve_merge(candidate_id, first, second)
        if reason in {"", "unknown", "unspecified"}:
            raise ContractError("split-reason-missing")
        if path_has_direct_identifier(reason):
            raise ContractError("queue-identifier-forbidden")
        return {"candidate_id": candidate_id, "digest": digest, "reason": reason, "action": "split"}

    def tolerate_merge(self, candidate_id: str, automatic: bool, blocked: bool, first: str, second: str) -> str:
        """Reject every automatic or blocked merge."""
        if automatic:
            raise ContractError("merge-automatic-forbidden")
        if blocked:
            raise ContractError("merge-blocked-zero-tolerance")
        if candidate_id not in self._items:
            raise ContractError("queue-candidate-missing")
        return self.approve_merge(candidate_id, first, second)
