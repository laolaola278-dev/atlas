"""Bounded batch execution.

A batch has a fixed capacity and a deadline. Cancellation stops further
items, and a full batch raises backpressure instead of growing forever.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


@dataclass(frozen=True)
class BatchResult:
    accepted: int
    cancelled: bool


class Batch:
    """Small in-memory batch used by the contract tests."""

    def __init__(self, capacity: int) -> None:
        if capacity < 1 or capacity > 1000:
            raise ContractError("batch-capacity-invalid")
        self.capacity = capacity
        self._items: list[str] = []
        self._actors: dict[str, tuple[str, str]] = {}
        self._committed: set[str] = set()
        self._cancelled = False

    def add(
        self,
        item_id: str,
        consent_state: str = "active",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> None:
        if consent_state != "active":
            raise ContractError("batch-consent-not-active")
        stopped = self._cancelled
        if stopped:
            raise ContractError("batch-cancelled")
        blank = item_id == "" or actor_id == ""
        if blank:
            raise ContractError("batch-item-invalid")
        missing_reason = why_code in {"", "unknown", "unspecified"}
        if missing_reason:
            raise ContractError("batch-why-missing")
        named = (item_id, actor_id, why_code)
        if any(path_has_direct_identifier(value) for value in named):
            raise ContractError("batch-identifier-forbidden")
        recorded = self._actors.get(item_id)
        same_actor = recorded == (actor_id, why_code)
        if recorded is not None and not same_actor:
            raise ContractError("batch-responsibility-mismatch")
        if len(self._items) >= self.capacity:
            raise ContractError("batch-backpressure")
        if recorded is None:
            self._items.append(item_id)
            self._actors[item_id] = (actor_id, why_code)

    def cancel(self) -> None:
        self._cancelled = True

    def finish(self) -> BatchResult:
        return BatchResult(len(self._items), self._cancelled)

    def advance(self, item_id: str, state: str) -> int:
        """Move the import watermark only after a known committed item."""
        if item_id not in self._actors:
            raise ContractError("import-item-unknown")
        if state == "unknown":
            raise ContractError("import-result-unknown")
        if state != "committed":
            raise ContractError("import-state-invalid")
        self._committed.add(item_id)
        return len(self._committed)


def shard_for(key: str, shard_count: int, seen: int) -> int:
    """Return one shard, or reject a hot key before it crowds one shard."""
    if key == "" or path_has_direct_identifier(key):
        raise ContractError("shard-key-forbidden")
    if shard_count < 2 or shard_count > 64:
        raise ContractError("shard-count-invalid")
    if seen < 0:
        raise ContractError("shard-count-invalid")
    if seen >= 100:
        raise ContractError("shard-hot-key")
    return sum(key.encode("utf-8")) % shard_count


class SourceLimiter:
    """Count accepted messages per source and stop at the limit."""

    def __init__(self, limit: int) -> None:
        if limit < 1 or limit > 1000:
            raise ContractError("limit-invalid")
        self._limit = limit
        self._counts: dict[str, int] = {}

    def admit(self, source: str) -> int:
        if source == "" or path_has_direct_identifier(source):
            raise ContractError("limit-source-forbidden")
        current = self._counts.get(source, 0)
        if current >= self._limit:
            raise ContractError("limit-backpressure")
        self._counts[source] = current + 1
        return self._counts[source]


class SecondWriter:
    """Accept a bounded number of writes inside one second."""

    def __init__(self, limit: int) -> None:
        if limit < 1 or limit > 1000:
            raise ContractError("second-limit-invalid")
        self._limit = limit
        self._counts: dict[int, int] = {}

    def write(self, epoch: int) -> int:
        if epoch < 0:
            raise ContractError("second-epoch-invalid")
        current = self._counts.get(epoch, 0)
        if current >= self._limit:
            raise ContractError("second-backpressure")
        self._counts[epoch] = current + 1
        return self._counts[epoch]


def resume_at(committed: int, next_sequence: int) -> int:
    """Continue only at the sequence immediately after the commit."""
    if committed < 0 or next_sequence < 1:
        raise ContractError("resume-input-invalid")
    if next_sequence <= committed:
        raise ContractError("resume-already-committed")
    if next_sequence != committed + 1:
        raise ContractError("resume-gap")
    return next_sequence


def reconcile_loss(expected: tuple[str, ...], actual: tuple[str, ...]) -> int:
    """Accept a transfer only when every expected digest arrived."""
    sides = (expected, actual)
    if any(not side or len(side) > 100 for side in sides):
        raise ContractError("reconcile-set-invalid")
    if any(len(item) != 64 for side in sides for item in side):
        raise ContractError("reconcile-digest-invalid")
    if set(expected) - set(actual):
        raise ContractError("reconcile-missing")
    if set(actual) - set(expected):
        raise ContractError("reconcile-extra")
    return len(expected)
