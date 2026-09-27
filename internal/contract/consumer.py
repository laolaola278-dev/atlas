"""Contract consumer checks.

A consumer may act only on a registered error. It cannot retry a forbidden
response, and an unknown result stays unknown.
"""
from __future__ import annotations

from internal.contract.errors import ContractError, lookup


def consume(code: str, trace_id: str) -> str:
    """Return the only action a consumer may take for this error."""
    if trace_id == "" or any(char.isspace() for char in trace_id):
        raise ContractError("consumer-trace-invalid")
    item = lookup(code)
    if item.http_status == 403:
        raise ContractError("consumer-forbidden-retry")
    if item.http_status == 409:
        raise ContractError("consumer-conflict-retry")
    if item.retryable:
        return "reconcile"
    return "stop"


def consumer_contract(version: str, purpose: str, digest: str) -> dict[str, str]:
    """Accept one consumer contract when its declared parts match."""
    if version not in {"1.0", "1.1"}:
        raise ContractError("consumer-version-rejected")
    if purpose not in {"treatment", "review"}:
        raise ContractError("consumer-purpose-rejected")
    if len(digest) != 64:
        raise ContractError("consumer-digest-invalid")
    return {"digest": digest, "purpose": purpose, "version": version}
