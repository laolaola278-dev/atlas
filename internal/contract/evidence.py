"""Evidence references for one suggestion.

A suggestion cannot be reviewed unless every cited source has a locator,
version, and content digest. References form a DAG: cycles are rejected.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    source_id: str
    locator: str
    source_version: str
    value_digest: str
    depends_on: tuple[str, ...] = ()
    source_kind: str = "observation"


_SOURCE_KINDS = {"guideline", "observation", "medication", "order"}


def require_locatable(refs: tuple[EvidenceRef, ...]) -> None:
    """Reject evidence that cannot be traced to a clinical source."""
    if not refs:
        raise ContractError("evidence-unlocatable")
    for ref in refs:
        if ref.source_kind not in _SOURCE_KINDS:
            raise ContractError("evidence-unlocatable")
        if not ref.locator or not ref.source_version:
            raise ContractError("evidence-unlocatable")


def validate_evidence(
    refs: tuple[EvidenceRef, ...],
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> None:
    """Reject incomplete, duplicate, or cyclic evidence."""
    if not refs:
        raise ContractError("evidence-missing")
    if not actor_id:
        raise ContractError("evidence-incomplete")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("evidence-why-missing")
    if path_has_direct_identifier(actor_id) or path_has_direct_identifier(why_code):
        raise ContractError("evidence-identifier-forbidden")
    seen: set[str] = set()
    graph: dict[str, tuple[str, ...]] = {}
    for ref in refs:
        if not all((ref.evidence_id, ref.source_id, ref.locator, ref.source_version, ref.value_digest)):
            raise ContractError("evidence-incomplete")
        if not compatible(ref.source_version):
            raise ContractError("evidence-version-incompatible")
        if path_has_direct_identifier(ref.locator) or path_has_direct_identifier(ref.evidence_id):
            raise ContractError("evidence-identifier-forbidden")
        if ref.evidence_id in seen:
            raise ContractError("evidence-duplicate")
        seen.add(ref.evidence_id)
        graph[ref.evidence_id] = ref.depends_on
    for ref in refs:
        for dependency in ref.depends_on:
            if dependency not in seen:
                raise ContractError("evidence-dangling")
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str) -> None:
        if node in visited:
            return
        if node in visiting:
            raise ContractError("evidence-cycle")
        visiting.add(node)
        for dependency in graph[node]:
            walk(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        walk(node)


class EvidenceLedger:
    """Remember one evidence graph so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, ...], tuple[str, str]] = {}

    def validate(
        self,
        refs: tuple[EvidenceRef, ...],
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> None:
        validate_evidence(refs, actor_id, why_code)
        key = tuple(sorted(ref.evidence_id for ref in refs))
        recorded = self._records.get(key)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("evidence-responsibility-mismatch")
        self._records.setdefault(key, incoming)

    def restore(self, evidence_ids: tuple[str, ...], actor_id: str, why_code: str) -> None:
        """Restore one accepted graph without treating it as a new review."""
        if not evidence_ids or not actor_id or why_code in {"", "unknown", "unspecified"}:
            raise ContractError("evidence-incomplete")
        self._records[tuple(sorted(evidence_ids))] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[str, ...], tuple[str, str]], ...]:
        """Return stored evidence decisions in stable order."""
        return tuple(sorted(self._records.items()))
