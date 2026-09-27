"""Device identity certificates.

A device is accepted only with a synthetic id and a certificate digest.
Certificate text stays outside this gate.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def device_certificate(device_id: str, digest: str, expired: bool) -> dict[str, str]:
    """Return the certificate digest for one active synthetic device."""
    if device_id == "" or path_has_direct_identifier(device_id):
        raise ContractError("device-id-forbidden")
    if len(digest) != 64:
        raise ContractError("device-digest-invalid")
    if expired:
        raise ContractError("device-certificate-expired")
    return {"device_id": device_id, "digest": digest, "state": "active"}


def mqtt_session(client_id: str, topic: str, clean: bool) -> dict[str, str]:
    """Accept one synthetic session on an allowed topic."""
    if client_id == "" or path_has_direct_identifier(client_id):
        raise ContractError("mqtt-client-forbidden")
    if topic not in {"points/hr", "points/spo2"}:
        raise ContractError("mqtt-topic-forbidden")
    if clean is not True:
        raise ContractError("mqtt-session-dirty")
    return {"clean": "true", "client_id": client_id, "topic": topic}


def edge_clock(skew_ms: int) -> str:
    """Grade one edge clock without changing its timestamp."""
    if skew_ms < 0:
        raise ContractError("edge-clock-invalid")
    if skew_ms <= 100:
        return "synced"
    if skew_ms <= 1000:
        return "degraded"
    raise ContractError("edge-clock-rejected")


def offline_buffer(online: bool, queued: int, limit: int) -> int:
    """Keep a bounded queue only while the edge link is down."""
    if queued < 0 or limit < 1 or limit > 1000:
        raise ContractError("buffer-input-invalid")
    if online and queued:
        raise ContractError("buffer-online-forbidden")
    if queued > limit:
        raise ContractError("buffer-overflow")
    return queued


def partition_rehearsal(left: str, right: str) -> str:
    """Continue only when both sides report the same partition."""
    if left == "" or right == "":
        raise ContractError("partition-missing")
    if path_has_direct_identifier(left) or path_has_direct_identifier(right):
        raise ContractError("partition-forbidden")
    if left != right:
        raise ContractError("partition-split")
    return left


def upgrade_rollback(current: str, target: str) -> str:
    """Roll an edge release back only to the previous minor version."""
    allowed = {"1.1": "1.0"}
    if current not in {"1.0", "1.1"} or target == "":
        raise ContractError("upgrade-version-invalid")
    if target == current:
        raise ContractError("upgrade-not-needed")
    if allowed.get(current) != target:
        raise ContractError("upgrade-rollback-forbidden")
    return target


def isolate_fault(device_id: str, healthy: bool, stream: str) -> str:
    """Keep a faulty device off the healthy stream."""
    if device_id == "" or path_has_direct_identifier(device_id):
        raise ContractError("fault-device-forbidden")
    if stream not in {"healthy", "isolated"} or not isinstance(healthy, bool):
        raise ContractError("fault-input-invalid")
    if not healthy and stream != "isolated":
        raise ContractError("fault-not-isolated")
    if healthy and stream == "isolated":
        raise ContractError("fault-healthy-isolated")
    return stream


def ingest_inventory(expected: tuple[str, ...], actual: tuple[str, ...]) -> int:
    """Accept an edge inventory only when both device lists match."""
    sides = (expected, actual)
    if any(not side or len(side) > 100 for side in sides):
        raise ContractError("inventory-set-invalid")
    if any(path_has_direct_identifier(item) or item == "" for side in sides for item in side):
        raise ContractError("inventory-device-forbidden")
    if set(expected) != set(actual):
        raise ContractError("inventory-mismatch")
    return len(set(expected))
