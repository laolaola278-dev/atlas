"""HL7 v2 segment boundaries.

The parser accepts a small allow-list of segment names. Identifier segments
and free text stay outside this gate.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_ALLOWED = frozenset({"MSH", "EVN", "OBR", "OBX"})
_FORBIDDEN = frozenset({"PID", "NK1", "GT1"})


def parse_segments(names: tuple[str, ...]) -> tuple[str, ...]:
    """Return allowed segment names in order."""
    if not names or len(names) > 20:
        raise ContractError("segment-set-invalid")
    if names[0] != "MSH":
        raise ContractError("segment-header-missing")
    if any(name in _FORBIDDEN for name in names):
        raise ContractError("segment-identifier-forbidden")
    if any(name not in _ALLOWED for name in names):
        raise ContractError("segment-unknown")
    return names


def require_pid(names: tuple[str, ...], pid_digest: str) -> str:
    """Reject a message that omits the patient segment or its digest."""
    if "PID" not in names:
        raise ContractError("pid-missing")
    if len(pid_digest) != 64:
        raise ContractError("pid-digest-invalid")
    return pid_digest


class MessageIdempotency:
    """Remember one message control id and its digest."""

    def __init__(self) -> None:
        self._seen: dict[str, str] = {}

    def accept(self, control_id: str, digest: str) -> str:
        if control_id == "" or len(digest) != 64:
            raise ContractError("message-key-invalid")
        recorded = self._seen.get(control_id)
        if recorded is None:
            self._seen[control_id] = digest
            return "accepted"
        if recorded != digest:
            raise ContractError("message-conflict")
        return "duplicate"


def clock_skew(local_epoch: int, remote_epoch: int) -> int:
    """Return the skew, or isolate a clock that drifted too far."""
    if local_epoch < 0 or remote_epoch < 0:
        raise ContractError("clock-epoch-invalid")
    skew = abs(local_epoch - remote_epoch)
    if skew > 300:
        raise ContractError("clock-skew-isolated")
    return skew


def acknowledge(control_id: str, outcome: str, digest: str) -> dict[str, str]:
    """Return an ACK code, or isolate a rejected message as dead."""
    if control_id == "" or len(digest) != 64:
        raise ContractError("ack-message-invalid")
    if outcome == "accepted":
        code = "AA"
    elif outcome == "rejected":
        code = "AR"
    elif outcome == "unknown":
        raise ContractError("ack-result-unknown")
    else:
        raise ContractError("ack-outcome-invalid")
    return {"code": code, "control_id": control_id, "digest": digest}


def route_tenant(source: str, routes: dict[str, str]) -> str:
    """Return the only tenant registered for this source."""
    if source == "" or not routes:
        raise ContractError("route-source-invalid")
    tenant = routes.get(source, "")
    if tenant == "":
        raise ContractError("route-tenant-unknown")
    if list(routes.values()).count(tenant) != 1:
        raise ContractError("route-tenant-shared")
    return tenant


_CODING_FIELDS = frozenset({"code", "system"})


def coding_matrix(cells: dict[str, str], known: frozenset[str]) -> int:
    """Accept only registered code digests in the allowed fields."""
    if not cells or set(cells) - _CODING_FIELDS:
        raise ContractError("coding-field-invalid")
    if not known:
        raise ContractError("coding-registry-invalid")
    for value in cells.values():
        dirty = len(value) != 64 or value not in known
        if dirty:
            raise ContractError("coding-dirty")
    return len(cells)


def seal_message(digest: str, body: str) -> dict[str, object]:
    """Seal a message by digest and refuse to keep its body."""
    if len(digest) != 64:
        raise ContractError("seal-digest-invalid")
    if body != "":
        raise ContractError("seal-body-forbidden")
    return {"body_kept": False, "digest": digest, "sealed": True}


def ingest_audit(source: str, operation: str, digest: str) -> dict[str, str]:
    """Record one ingest action without the message body."""
    if source == "" or operation not in {"accept", "reject", "duplicate"}:
        raise ContractError("ingest-audit-invalid")
    if len(digest) != 64 or path_has_direct_identifier(source):
        raise ContractError("ingest-audit-forbidden")
    return {"digest": digest, "operation": operation, "source": source}


_POINTS = frozenset({"hr", "spo2"})
_POINT_UNITS = {"hr": "1/min", "spo2": "%"}


def point_schema(point: str, unit: str, synthetic: bool) -> dict[str, str]:
    """Accept one declared point and its unit."""
    if synthetic is not True:
        raise ContractError("point-not-synthetic")
    if point not in _POINTS:
        raise ContractError("point-unknown")
    if unit != _POINT_UNITS[point]:
        raise ContractError("point-unit-mismatch")
    return {"point": point, "unit": unit}


def probe_state(point: str, detached: bool, value: int | None) -> str:
    """Mark a detached probe and reject a value that arrived with it."""
    if point not in _POINTS or not isinstance(detached, bool):
        raise ContractError("probe-input-invalid")
    if detached and value is not None:
        raise ContractError("probe-value-forbidden")
    if not detached and value is None:
        raise ContractError("probe-value-missing")
    if value is not None and value < 0:
        raise ContractError("probe-value-invalid")
    return "detached" if detached else "attached"
