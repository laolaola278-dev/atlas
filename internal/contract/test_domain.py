"""Integration tests for suggestion review readiness."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.consent import Consent, ConsentLedger  # noqa: E402
from internal.contract.domain import SuggestionDraft, ready_for_review  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.evidence import EvidenceLedger, EvidenceRef  # noqa: E402
from internal.contract.medication import MedicationLedger  # noqa: E402
from internal.contract.rules import RuleLedger, RulePack  # noqa: E402


def draft(role: str = "attending", state: str = "active") -> SuggestionDraft:
    evidence = (
        EvidenceRef("lab", "source-lab", "Observation/lab", "1", "b" * 64),
    )
    return SuggestionDraft(
        suggestion_id="suggestion-synthetic",
        patient_ref="patient-ref-synthetic",
        action="review-order",
        content_digest="c" * 64,
        evidence=evidence,
        rule_pack=RulePack("pack-1", "1.0.0", "a" * 64, "active", "2026-01-01", "2027-01-01"),
        consent=Consent("consent-1", "1", state, "treatment", "2026-01-01", "2027-01-01"),
        actor={
            "actor_id": "reviewer-synthetic",
            "actor_role": role,
            "tenant_id": "tenant-synthetic",
            "campus_id": "campus-synthetic",
            "purpose_code": "treatment",
            "why_code": "review-decision",
            "occurred_at": "2026-09-24T00:00:00Z",
        },
        at_time="2026-09-24",
    )


class DomainTests(unittest.TestCase):
    def test_complete_human_context_is_ready(self) -> None:
        actor = ready_for_review(draft())
        self.assertEqual(actor.actor_id, "reviewer-synthetic")

    def test_withdrawn_consent_and_system_role_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as withdrawn:
            ready_for_review(draft(state="withdrawn"))
        self.assertEqual(str(withdrawn.exception), "consent-not-active")
        with self.assertRaises(ContractError) as system:
            ready_for_review(draft(role="system"))
        self.assertEqual(str(system.exception), "system-cannot-review")

    def test_missing_evidence_is_rejected(self) -> None:
        incomplete = draft()
        broken = SuggestionDraft(**{**incomplete.__dict__, "evidence": ()})
        with self.assertRaises(ContractError) as missing:
            ready_for_review(broken)
        self.assertEqual(str(missing.exception), "evidence-missing")

    def test_skipped_rule_version_is_rejected(self) -> None:
        current = draft()
        skipped = SuggestionDraft(
            **{**current.__dict__, "rule_pack": RulePack("pack-1", "1.2", "a" * 64, "active", "2026-01-01", "2027-01-01")}
        )
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(skipped)
        self.assertEqual(str(blocked.exception), "rule-version-incompatible")

    def test_skipped_evidence_version_is_rejected(self) -> None:
        current = draft()
        evidence = (
            EvidenceRef("lab", "source-lab", "Observation/lab", "1.2", "b" * 64),
        )
        skipped = SuggestionDraft(**{**current.__dict__, "evidence": evidence})
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(skipped)
        self.assertEqual(str(blocked.exception), "evidence-version-incompatible")

    def test_skipped_consent_version_is_rejected(self) -> None:
        current = draft()
        consent = Consent("consent-1", "1.2", "active", "treatment", "2026-01-01", "2027-01-01")
        skipped = SuggestionDraft(**{**current.__dict__, "consent": consent})
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(skipped)
        self.assertEqual(str(blocked.exception), "consent-version-incompatible")

    def test_identifier_patient_reference_is_rejected(self) -> None:
        current = draft()
        named = SuggestionDraft(**{**current.__dict__, "patient_ref": "subject.identifier"})
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(named)
        self.assertEqual(str(blocked.exception), "suggestion-identifier-forbidden")

    def test_other_actor_for_same_evidence_is_rejected(self) -> None:
        ledger = EvidenceLedger()
        ready_for_review(draft(), ledger)
        other = draft()
        other.actor["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(other, ledger)
        self.assertEqual(str(blocked.exception), "evidence-responsibility-mismatch")

    def test_other_actor_for_same_rule_pack_is_rejected(self) -> None:
        ledger = RuleLedger()
        ready_for_review(draft(), None, ledger)
        other = draft()
        other.actor["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(other, None, ledger)
        self.assertEqual(str(blocked.exception), "rule-responsibility-mismatch")

    def test_other_actor_for_same_consent_is_rejected(self) -> None:
        ledger = ConsentLedger()
        ready_for_review(draft(), None, None, ledger)
        other = draft()
        other.actor["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(other, None, None, ledger)
        self.assertEqual(str(blocked.exception), "consent-responsibility-mismatch")

    def test_other_actor_for_same_medication_findings_is_rejected(self) -> None:
        ledger = MedicationLedger()
        findings = {
            "allergy": False,
            "contraindication": False,
            "dose_limit": False,
            "duplicate": False,
            "interaction": False,
        }
        current = SuggestionDraft(**{**draft().__dict__, "medication_findings": findings})
        ready_for_review(current, None, None, None, ledger)
        other = SuggestionDraft(**{**current.__dict__, "actor": {**current.actor, "actor_id": "other-reviewer"}})
        with self.assertRaises(ContractError) as blocked:
            ready_for_review(other, None, None, None, ledger)
        self.assertEqual(str(blocked.exception), "medication-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
