"""Transaction watermarks for clinical writes.

A committed result may advance the watermark. An unknown result stays below
the watermark and cannot be replayed as a new clinical write.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from dataclasses import dataclass


def _accepted_state(state: str) -> str:
    """Keep only states that a transaction watermark can store."""
    if state not in {"accepted", "unknown", "committed"}:
        raise ContractError("transaction-state-invalid")
    return state


@dataclass(frozen=True)
class TransactionMark:
    """One accepted, unknown, or committed clinical write."""

    sequence: int = 0
    key: str = ""
    payload_digest: str = ""
    state: str = "accepted"
    actor_id: str = "actor-synthetic"
    why_code: str = "treatment-review"


class TransactionWatermark:
    """One ordered write stream. Unknown results never move the watermark."""

    def __init__(self, stream_id: str) -> None:
        if not stream_id:
            raise ContractError("transaction-stream-invalid")
        if path_has_direct_identifier(stream_id):
            raise ContractError("transaction-identifier-forbidden")
        self.stream_id = stream_id
        self._next = 1
        self._committed = 0
        self._records: dict[str, TransactionMark] = {}

    def begin(
        self,
        key: str,
        payload_digest: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> TransactionMark:
        """Accept one new write or return the original committed result."""
        if not key or len(payload_digest) != 64 or not actor_id:
            raise ContractError("transaction-key-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("transaction-why-missing")
        named = (key, actor_id, why_code)
        if any(path_has_direct_identifier(value) for value in named):
            raise ContractError("transaction-identifier-forbidden")
        current = self._records.get(key)
        if current is None:
            record = TransactionMark(
                self._next,
                key,
                payload_digest,
                _accepted_state("accepted"),
                actor_id,
                why_code,
            )
            self._records[key] = record
            self._next += 1
            return record
        if current.payload_digest != payload_digest:
            raise ContractError("transaction-conflict")
        if current.actor_id != actor_id or current.why_code != why_code:
            raise ContractError("transaction-responsibility-mismatch")
        if current.state == "unknown":
            raise ContractError("transaction-result-unknown")
        return current

    def commit(self, key: str) -> TransactionMark:
        """Advance the watermark only after the original result is known."""
        current = self._require(key)
        if current.state == "unknown":
            raise ContractError("transaction-result-unknown")
        if current.state == "committed":
            return current
        record = TransactionMark(
            current.sequence,
            current.key,
            current.payload_digest,
            _accepted_state("committed"),
            current.actor_id,
            current.why_code,
        )
        self._records[key] = record
        self._committed = max(self._committed, current.sequence)
        return record

    def mark_unknown(self, key: str) -> TransactionMark:
        """Freeze one result without moving the committed watermark."""
        current = self._require(key)
        if current.state == "committed":
            raise ContractError("transaction-already-committed")
        record = TransactionMark(
            current.sequence,
            current.key,
            current.payload_digest,
            _accepted_state("unknown"),
            current.actor_id,
            current.why_code,
        )
        self._records[key] = record
        return record

    def restore(
        self,
        key: str,
        payload_digest: str,
        state: str,
        sequence: int,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> TransactionMark:
        """Restore one stored transaction without treating it as a new write."""
        if not key or len(payload_digest) != 64 or sequence < 1 or not actor_id:
            raise ContractError("transaction-key-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("transaction-why-missing")
        record = TransactionMark(sequence, key, payload_digest, _accepted_state(state), actor_id, why_code)
        self._records[key] = record
        self._next = max(self._next, sequence + 1)
        if state == "committed":
            self._committed = max(self._committed, sequence)
        return record

    def records(self) -> tuple[TransactionMark, ...]:
        """Return stored transactions in sequence order."""
        return tuple(sorted(self._records.values(), key=lambda item: item.sequence))

    def watermark(self) -> int:
        """Return the highest committed sequence."""
        return self._committed

    def _require(self, key: str) -> TransactionMark:
        try:
            return self._records[key]
        except KeyError as exc:
            raise ContractError("transaction-key-unknown") from exc
