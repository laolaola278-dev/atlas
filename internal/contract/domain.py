"""Suggestion invariants.

A suggestion may move toward human review only when its evidence, rule pack,
consent, and actor context are all valid. This module does not approve or
write a clinical action by itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.consent import Consent, ConsentLedger, authorize
from internal.contract.errors import ContractError
from internal.contract.evidence import EvidenceLedger, EvidenceRef, validate_evidence
from internal.contract.identity import ActorContext, require_context
from internal.contract.medication import MedicationLedger, derive_findings, medication_decision
from internal.contract.rules import RuleLedger, RulePack, admit, deterministic_decision
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


@dataclass(frozen=True)
class SuggestionDraft:
    suggestion_id: str
    patient_ref: str
    action: str
    content_digest: str
    evidence: tuple[EvidenceRef, ...]
    rule_pack: RulePack
    consent: Consent
    actor: dict[str, object]
    at_time: str
    rule_decision: str = "allow"
    model_decision: str = "allow"
    medication_findings: dict[str, bool] | None = None
    medication_facts: dict[str, object] | None = None
    contract_version: str = "1.0"


def ready_for_review(
    draft: SuggestionDraft,
    evidence: EvidenceLedger | None = None,
    rules: RuleLedger | None = None,
    consents: ConsentLedger | None = None,
    medications: MedicationLedger | None = None,
) -> ActorContext:
    """Validate one draft and return the responsible actor context."""
    if not all((draft.suggestion_id, draft.patient_ref, draft.action, draft.content_digest)):
        raise ContractError("suggestion-incomplete")
    if path_has_direct_identifier(draft.patient_ref) or path_has_direct_identifier(draft.action):
        raise ContractError("suggestion-identifier-forbidden")
    if len(draft.content_digest) != 64:
        raise ContractError("suggestion-digest-invalid")
    if not compatible(draft.contract_version):
        raise ContractError("contract-version-incompatible")
    actor_id = str(draft.actor.get("actor_id", ""))
    why_code = str(draft.actor.get("why_code", ""))
    if evidence is None:
        validate_evidence(draft.evidence, actor_id, why_code)
    else:
        evidence.validate(draft.evidence, actor_id, why_code)
    if rules is None:
        admit(draft.rule_pack, draft.at_time, actor_id, why_code)
    else:
        rules.admit(draft.rule_pack, draft.at_time, actor_id, why_code)
    deterministic_decision(draft.rule_decision, draft.model_decision)
    if draft.medication_findings is not None:
        required = _medication_decision(
            medications,
            draft.medication_findings,
            draft.model_decision,
            actor_id,
            why_code,
        )
        if required != draft.rule_decision:
            raise ContractError("medication-rule-mismatch")
    if draft.medication_facts is not None:
        derived = derive_findings(draft.medication_facts)
        if draft.medication_findings is not None and derived != draft.medication_findings:
            raise ContractError("medication-findings-mismatch")
        required = _medication_decision(medications, derived, draft.model_decision, actor_id, why_code)
        if required != draft.rule_decision:
            raise ContractError("medication-rule-mismatch")
    actor = require_context(draft.actor)
    if consents is None:
        authorize(draft.consent, actor.purpose_code, draft.at_time, actor.actor_id, actor.why_code)
    else:
        consents.authorize(draft.consent, actor.purpose_code, draft.at_time, actor.actor_id, actor.why_code)
    if actor.actor_role == "system":
        raise ContractError("system-cannot-review")
    return actor


def _medication_decision(
    medications: MedicationLedger | None,
    findings: dict[str, bool],
    model_decision: str,
    actor_id: str,
    why_code: str,
) -> str:
    """Use the ledger when the review service owns one."""
    if medications is None:
        return medication_decision(findings, model_decision, actor_id, why_code)
    return medications.decide(findings, model_decision, actor_id, why_code)
