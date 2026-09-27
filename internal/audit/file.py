"""Durable append-only audit file.

The file stores canonical event lines. Loading verifies the hash chain before
the events can be used. A truncated or rewritten line fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from internal.audit.chain import REQUIRED, AuditEvent, AuditLog
from internal.contract.errors import ContractError


def _line(event: AuditEvent) -> str:
    payload = {name: getattr(event, name) for name in (*REQUIRED, "previous_hash", "event_hash")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class AuditFile:
    """One stream file. Existing lines are never rewritten."""

    def __init__(self, path: Path, stream_id: str) -> None:
        self.path = path
        self.stream_id = stream_id
        self.log = self._load()

    def append(self, fields: dict[str, object]) -> AuditEvent:
        return self.log.append(fields)

    def reload(self) -> AuditLog:
        self.log = self._load()
        return self.log

    def _load(self) -> AuditLog:
        # Replay without the sink attached: a load must never rewrite history.
        # Attaching the sink before the replay duplicated every stored line on
        # each open, so a second restart failed closed on audit-sequence-invalid.
        log = AuditLog(self.stream_id)
        if not self.path.exists():
            log.sink = self._persist
            return log
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw:
                continue
            try:
                fields = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ContractError("audit-file-corrupt") from exc
            if not isinstance(fields, dict):
                raise ContractError("audit-file-corrupt")
            log.append(fields)
            stored = log.events[-1]
            if stored.event_hash != fields.get("event_hash") or stored.previous_hash != fields.get("previous_hash"):
                raise ContractError("audit-file-tampered")
        log.verify()
        log.sink = self._persist
        return log

    def _persist(self, event: AuditEvent) -> None:
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(_line(event) + "\n")
