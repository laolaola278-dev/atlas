"""Replay protection for clinical commands.

A nonce can be accepted once. Sequence numbers must be contiguous for a
stream; a gap, rewind, or reuse is rejected instead of being replayed.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


class ReplayGuard:
    """In-memory guard for one process. Persistence comes with the service."""

    def __init__(self) -> None:
        self._next: dict[str, int] = {}
        self._nonces: dict[str, set[str]] = {}
        self._actors: dict[tuple[str, int], tuple[str, str]] = {}

    def accept(
        self,
        stream_id: str,
        sequence: int,
        nonce: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> None:
        if not stream_id or not nonce or not actor_id:
            raise ContractError("replay-context-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("replay-why-missing")
        named = (stream_id, nonce, actor_id, why_code)
        if any(path_has_direct_identifier(value) for value in named):
            raise ContractError("replay-identifier-forbidden")
        if sequence < 1:
            raise ContractError("replay-sequence-invalid")
        seen = self._nonces.setdefault(stream_id, set())
        if nonce in seen:
            raise ContractError("replay-nonce-reused")
        expected = self._next.get(stream_id, 1)
        if sequence != expected:
            recorded = self._actors.get((stream_id, sequence))
            if recorded is not None and recorded != (actor_id, why_code):
                raise ContractError("replay-responsibility-mismatch")
            raise ContractError("replay-sequence-invalid")
        seen.add(nonce)
        self._actors[(stream_id, sequence)] = (actor_id, why_code)
        self._next[stream_id] = expected + 1


def replay_compatible(stored_version: str, current_version: str, stored_digest: str, current_digest: str) -> str:
    """Accept a replay only for the current or previous minor version."""
    allowed = {current_version}
    if current_version == "1.1":
        allowed.add("1.0")
    if stored_version not in allowed or current_version not in {"1.0", "1.1"}:
        raise ContractError("replay-version-incompatible")
    pair = (stored_digest, current_digest)
    if any(len(item) != 64 for item in pair):
        raise ContractError("replay-digest-invalid")
    if stored_digest != current_digest:
        raise ContractError("replay-digest-mismatch")
    return stored_version


def arrival_order(expected: int, actual: int, delay_seconds: int) -> str:
    """Reject a reordered or late event without changing the watermark."""
    if expected < 1 or actual < 1 or delay_seconds < 0:
        raise ContractError("arrival-input-invalid")
    if actual < expected:
        raise ContractError("arrival-reordered")
    if actual != expected:
        raise ContractError("arrival-gap")
    if delay_seconds > 30:
        raise ContractError("arrival-late")
    return "in-order"
