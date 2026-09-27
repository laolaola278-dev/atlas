"""Startup health probe.

A service is ready only after configuration loads and the P0 evidence index
checks out. Any startup error stays failed closed.
"""
from __future__ import annotations

from internal.contract.config import load_config
from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from tools.evidence.p0_index import require_complete


def probe(payload: dict[str, object]) -> dict[str, str | bool]:
    """Return readiness only when startup checks all pass."""
    config = load_config(payload)
    actor_id = str(payload.get("actor_id", "actor-synthetic"))
    why_code = str(payload.get("why_code", "startup-check"))
    if not actor_id:
        raise ContractError("health-actor-missing")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("health-why-missing")
    if path_has_direct_identifier(actor_id) or path_has_direct_identifier(why_code):
        raise ContractError("health-identifier-forbidden")
    indexed = require_complete()
    return {
        "status": "ok",
        "ready": True,
        "tenant_id": config.tenant_id,
        "indexed_batches": str(indexed),
    }


class HealthLedger:
    """Remember one startup scope so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], tuple[str, str]] = {}

    def probe(self, payload: dict[str, object]) -> dict[str, str | bool]:
        result = probe(payload)
        key = (str(result["tenant_id"]), str(payload.get("campus_id", "")))
        incoming = (
            str(payload.get("actor_id", "actor-synthetic")),
            str(payload.get("why_code", "startup-check")),
        )
        recorded = self._records.get(key)
        if recorded is not None and recorded != incoming:
            raise ContractError("health-responsibility-mismatch")
        self._records[key] = incoming
        return result

    def restore(self, tenant_id: str, campus_id: str, actor_id: str, why_code: str) -> None:
        """Restore one startup scope without treating it as a new probe."""
        if not tenant_id or not campus_id or not actor_id:
            raise ContractError("health-actor-missing")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("health-why-missing")
        self._records[(tenant_id, campus_id)] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, str], tuple[str, str]], ...]:
        """Return stored startup scopes in stable order."""
        return tuple(sorted(self._records.items()))
