"""P0 evidence index.

The index maps each P0 batch to one existing file and one registered test.
A missing file or an unregistered test fails closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_ROOT = Path(__file__).resolve().parents[2]
_PLAN = _ROOT / "plan" / "batches.jsonl"
_INDEX = _ROOT / "docs" / "evidence" / "p0" / "index.json"


def load_index() -> tuple[dict[str, str], ...]:
    """Return the registered P0 evidence rows."""
    try:
        payload = json.loads(_INDEX.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("evidence-index-corrupt") from exc
    rows = payload.get("rows")
    if payload.get("synthetic") is not True or not isinstance(rows, list) or not rows:
        raise ContractError("evidence-index-corrupt")
    loaded: list[dict[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise ContractError("evidence-index-corrupt")
        row = {
            "batch_id": str(item.get("batch_id", "")),
            "output_path": str(item.get("output_path", "")),
            "test_name": str(item.get("test_name", "")),
        }
        if not all(row.values()):
            raise ContractError("evidence-index-corrupt")
        loaded.append(row)
    return tuple(loaded)


def require_complete(actor_id: str = "actor-synthetic", why_code: str = "startup-check") -> int:
    """Reject an index row whose file or planned batch is absent."""
    if not actor_id:
        raise ContractError("evidence-index-actor-missing")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("evidence-index-why-missing")
    if path_has_direct_identifier(actor_id) or path_has_direct_identifier(why_code):
        raise ContractError("evidence-index-identifier-forbidden")
    planned = _planned_batches()
    rows = load_index()
    seen: set[str] = set()
    for row in rows:
        batch_id = row["batch_id"]
        if batch_id in seen or batch_id not in planned:
            raise ContractError("evidence-batch-unregistered")
        seen.add(batch_id)
        if not (_ROOT / row["output_path"]).is_file():
            raise ContractError("evidence-output-missing")
        test_path = _ROOT / Path(*row["test_name"].split(".")).with_suffix(".py")
        if not test_path.is_file():
            raise ContractError("evidence-test-missing")
    if not seen:
        raise ContractError("evidence-index-corrupt")
    return len(seen)


def _planned_batches() -> set[str]:
    try:
        lines = _PLAN.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ContractError("evidence-plan-corrupt") from exc
    batches: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        item = json.loads(line)
        if str(item.get("phase", "")) == "P0":
            batches.add(str(item["id"]))
    return batches
