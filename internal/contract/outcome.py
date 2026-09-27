"""Stable OperationOutcome mapping.

The same issues always produce the same issue list. Paths that contain a
direct identifier are rejected instead of being copied into the outcome.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


def operation_outcome(issues: tuple[tuple[str, str], ...]) -> dict[str, object]:
    """Return one outcome with issues sorted by path and code."""
    if not issues:
        raise ContractError("outcome-empty")
    rendered: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path, code in issues:
        if path == "" or code == "" or path_has_direct_identifier(path) or path_has_direct_identifier(code):
            raise ContractError("outcome-identifier-forbidden")
        item = (path, code)
        if item in seen:
            continue
        seen.add(item)
        rendered.append({"code": code, "severity": "error", "path": path})
    rendered.sort(key=lambda item: (item["path"], item["code"]))
    return {"issue": rendered, "resourceType": "OperationOutcome"}
