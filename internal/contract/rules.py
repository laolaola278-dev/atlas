"""Rule-pack admission.

Only an active pack with a content digest and an open validity window may
evaluate a suggestion. Unknown, retired, and expired packs fail closed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class RulePack:
    pack_id: str
    version: str
    digest: str
    state: str
    effective_from: str
    effective_to: str


def admit(
    pack: RulePack,
    at_time: str,
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> None:
    """Raise unless this pack may evaluate a suggestion now."""
    if not pack.pack_id or not pack.version or not at_time or not actor_id:
        raise ContractError("rule-pack-incomplete")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("rule-why-missing")
    named = (pack.pack_id, actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in named):
        raise ContractError("rule-identifier-forbidden")
    if not compatible(pack.version):
        raise ContractError("rule-version-incompatible")
    if not _DIGEST.fullmatch(pack.digest):
        raise ContractError("rule-digest-invalid")
    if pack.state != "active":
        raise ContractError("rule-state-rejected")
    if at_time < pack.effective_from or at_time >= pack.effective_to:
        raise ContractError("rule-outside-window")


class RuleLedger:
    """Remember one admitted pack so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def admit(
        self,
        pack: RulePack,
        at_time: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> None:
        admit(pack, at_time, actor_id, why_code)
        recorded = self._records.get(pack.pack_id)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("rule-responsibility-mismatch")
        self._records.setdefault(pack.pack_id, incoming)

    def restore(self, pack_id: str, actor_id: str, why_code: str) -> None:
        """Restore one admitted pack without treating it as a new review."""
        if not pack_id or not actor_id or why_code in {"", "unknown", "unspecified"}:
            raise ContractError("rule-pack-incomplete")
        self._records[pack_id] = (actor_id, why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored rule decisions in stable order."""
        return tuple(sorted(self._records.items()))


def deterministic_decision(rule_decision: str, model_decision: str) -> str:
    """Return the hard-rule decision. A model cannot replace it."""
    if rule_decision not in {"allow", "deny"}:
        raise ContractError("rule-decision-invalid")
    if model_decision != rule_decision:
        raise ContractError("model-cannot-override-rule")
    return rule_decision


def pack_signature(version: str, pack_digest: str, signature_digest: str) -> dict[str, str]:
    """Accept a signed rule pack when version and digests are valid."""
    if version not in {"1.0", "1.1"}:
        raise ContractError("pack-version-invalid")
    pair = (pack_digest, signature_digest)
    if any(not _DIGEST.fullmatch(item) for item in pair):
        raise ContractError("pack-digest-invalid")
    if pack_digest == signature_digest:
        raise ContractError("pack-signature-same")
    return {"pack": pack_digest, "signature": signature_digest, "version": version}


def replay_rule(recorded: str, replayed: str, digest: str, replay_digest: str) -> str:
    """Replay one rule only when both the decision and digest match."""
    if recorded not in {"allow", "deny"} or replayed not in {"allow", "deny"}:
        raise ContractError("replay-decision-invalid")
    pair = (digest, replay_digest)
    if any(not _DIGEST.fullmatch(item) for item in pair):
        raise ContractError("replay-digest-invalid")
    if recorded != replayed or digest != replay_digest:
        raise ContractError("replay-mismatch")
    return recorded


_FALSE_POSITIVE = ("interaction", "contraindication", "dose", "allergy", "duplicate")


def false_positive_breakdown(counts: dict[str, int]) -> int:
    """Return the total only when every safety class has its own count."""
    if set(counts) != set(_FALSE_POSITIVE):
        raise ContractError("false-positive-incomplete")
    if any(not isinstance(value, int) or value < 0 for value in counts.values()):
        raise ContractError("false-positive-invalid")
    return sum(counts.values())


def class_recall(scores: dict[str, int]) -> int:
    """Accept a release only when every safety class reaches 95."""
    if set(scores) != set(_FALSE_POSITIVE):
        raise ContractError("recall-incomplete")
    if any(not isinstance(value, int) or value < 0 or value > 100 for value in scores.values()):
        raise ContractError("recall-invalid")
    if any(value < 95 for value in scores.values()):
        raise ContractError("recall-below-threshold")
    return min(scores.values())


def knowledge_countersign(first: str, second: str, digest: str) -> dict[str, str]:
    """Publish knowledge only after two distinct reviewers sign one digest."""
    if first == "" or second == "" or first == second:
        raise ContractError("knowledge-signers-invalid")
    if path_has_direct_identifier(first) or path_has_direct_identifier(second):
        raise ContractError("knowledge-signer-forbidden")
    if not _DIGEST.fullmatch(digest):
        raise ContractError("knowledge-digest-invalid")
    return {"digest": digest, "first": first, "second": second}


def rule_canary(percent: int, digest: str) -> dict[str, object]:
    """Admit one small canary slice for a signed rule digest."""
    if percent not in {1, 5, 10}:
        raise ContractError("canary-percent-invalid")
    if not _DIGEST.fullmatch(digest):
        raise ContractError("canary-digest-invalid")
    return {"digest": digest, "percent": percent}


def rule_switch(enabled: bool, decision: str) -> str:
    """Stop a disabled rule before it can allow anything."""
    if not isinstance(enabled, bool) or decision not in {"allow", "deny"}:
        raise ContractError("switch-input-invalid")
    if not enabled:
        raise ContractError("rule-disabled")
    return decision


def synthetic_case(synthetic: bool, fields: tuple[str, ...], digest: str) -> dict[str, object]:
    """Accept one synthetic case header and reject identifying fields."""
    if synthetic is not True:
        raise ContractError("case-not-synthetic")
    if not fields or any(path_has_direct_identifier(field) for field in fields):
        raise ContractError("case-identifier-forbidden")
    if not _DIGEST.fullmatch(digest):
        raise ContractError("case-digest-invalid")
    return {"digest": digest, "fields": fields, "synthetic": True}


def rule_explanation(rule_id: str, decision: str, digest: str) -> dict[str, str]:
    """Return a rule id and digest, never case text."""
    if rule_id == "" or path_has_direct_identifier(rule_id):
        raise ContractError("explain-rule-forbidden")
    if decision not in {"allow", "deny"}:
        raise ContractError("explain-decision-invalid")
    if not _DIGEST.fullmatch(digest):
        raise ContractError("explain-digest-invalid")
    return {"decision": decision, "digest": digest, "rule_id": rule_id}


_PRIORITY = ("allergy", "dose", "interaction")


def conflict_priority(findings: tuple[str, ...]) -> str:
    """Return the highest fixed priority among the supplied findings."""
    if not findings or any(item not in _PRIORITY for item in findings):
        raise ContractError("priority-finding-invalid")
    for item in _PRIORITY:
        if item in findings:
            return item
    raise ContractError("priority-finding-invalid")
