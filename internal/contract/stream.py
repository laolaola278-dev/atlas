"""Ordered clinical event stream.

Events must arrive with contiguous sequence numbers. A late event is marked
and retained for reconciliation, but it is not eligible for a new write.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


@dataclass(frozen=True)
class StreamEvent:
    stream_id: str
    sequence: int
    event_id: str
    late: bool
    actor_id: str = "actor-synthetic"
    why_code: str = "treatment-review"


class EventStream:
    """In-memory stream watermark for one clinical stream."""

    def __init__(self, stream_id: str) -> None:
        if not stream_id:
            raise ContractError("stream-invalid")
        if path_has_direct_identifier(stream_id):
            raise ContractError("stream-identifier-forbidden")
        self.stream_id = stream_id
        self._next = 1
        self._events: list[StreamEvent] = []
        self._actors: dict[int, tuple[str, str]] = {}

    def observe(
        self,
        sequence: int,
        event_id: str,
        watermark: int,
        consent_state: str = "active",
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> StreamEvent:
        if sequence < 1 or not event_id or not actor_id:
            raise ContractError("stream-event-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("stream-why-missing")
        named = (event_id, actor_id, why_code)
        if any(path_has_direct_identifier(value) for value in named):
            raise ContractError("stream-identifier-forbidden")
        if consent_state != "active":
            raise ContractError("stream-consent-not-active")
        if sequence < self._next or sequence <= watermark:
            recorded = self._actors.get(sequence)
            if recorded is not None and recorded != (actor_id, why_code):
                raise ContractError("stream-responsibility-mismatch")
            event = StreamEvent(self.stream_id, sequence, event_id, True, actor_id, why_code)
            self._events.append(event)
            return event
        if sequence != self._next:
            raise ContractError("stream-gap")
        event = StreamEvent(self.stream_id, sequence, event_id, False, actor_id, why_code)
        self._events.append(event)
        self._actors[sequence] = (actor_id, why_code)
        self._next += 1
        return event

    def restore(self, sequence: int, event_id: str, late: bool, actor_id: str, why_code: str) -> None:
        """Restore one observed event without accepting it as a new write."""
        if sequence < 1 or not event_id or not actor_id:
            raise ContractError("stream-event-invalid")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("stream-why-missing")
        restored = StreamEvent(self.stream_id, sequence, event_id, late, actor_id, why_code)
        self._events.append(restored)
        if late:
            return
        self._actors[sequence] = (actor_id, why_code)
        if sequence >= self._next:
            self._next = sequence + 1

    def records(self) -> tuple[tuple[int, str, bool, str, str], ...]:
        """Return observed events in arrival order."""
        stored = [
            (event.sequence, event.event_id, event.late, event.actor_id, event.why_code)
            for event in self._events
        ]
        return tuple(stored)

    def writable(self) -> tuple[StreamEvent, ...]:
        """Return only events that may drive a new clinical action."""
        return tuple(event for event in self._events if not event.late)
