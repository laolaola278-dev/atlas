"""Tests for evidence integrity and consent fail-closed behavior."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.consent import Consent, ConsentLedger, authorize  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.evidence import EvidenceLedger, EvidenceRef, validate_evidence  # noqa: E402


def ref(evidence_id: str, depends_on: tuple[str, ...] = ()) -> EvidenceRef:
    return EvidenceRef(
        evidence_id,
        f"source-{evidence_id}",
        f"Observation/{evidence_id}",
        "1",
        "b" * 64,
        depends_on,
    )


class EvidenceTests(unittest.TestCase):
    def test_complete_dag_is_accepted(self) -> None:
        validate_evidence((ref("lab"), ref("summary", ("lab",))))

    def test_missing_duplicate_dangling_and_cycle_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as missing:
            validate_evidence(())
        self.assertEqual(str(missing.exception), "evidence-missing")
        with self.assertRaises(ContractError):
            validate_evidence((ref("lab"), ref("lab")))
        with self.assertRaises(ContractError):
            validate_evidence((ref("summary", ("missing",)),))
        with self.assertRaises(ContractError) as cycle:
            validate_evidence((ref("left", ("right",)), ref("right", ("left",))))
        self.assertEqual(str(cycle.exception), "evidence-cycle")

    def test_identifier_locator_is_rejected(self) -> None:
        named = EvidenceRef("lab", "source-lab", "subject.identifier", "1", "b" * 64)
        with self.assertRaises(ContractError) as blocked:
            validate_evidence((named,))
        self.assertEqual(str(blocked.exception), "evidence-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            validate_evidence((ref("lab"),), why_code="unknown")
        self.assertEqual(str(blocked.exception), "evidence-why-missing")

    def test_other_actor_for_same_graph_is_rejected(self) -> None:
        ledger = EvidenceLedger()
        graph = (ref("lab"),)
        ledger.validate(graph, "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            ledger.validate(graph, "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "evidence-responsibility-mismatch")


class ConsentTests(unittest.TestCase):
    def test_active_matching_window_allows(self) -> None:
        authorize(
            Consent("c-1", "1", "active", "treatment", "2026-01-01", "2026-12-31"),
            "treatment",
            "2026-06-01",
        )

    def test_withdrawn_expired_and_wrong_purpose_are_denied(self) -> None:
        base = Consent("c-1", "1", "withdrawn", "treatment", "2026-01-01", "2026-12-31")
        with self.assertRaises(ContractError) as withdrawn:
            authorize(base, "treatment", "2026-06-01")
        self.assertEqual(str(withdrawn.exception), "consent-not-active")
        expired = Consent("c-1", "1", "active", "treatment", "2026-01-01", "2026-02-01")
        with self.assertRaises(ContractError):
            authorize(expired, "treatment", "2026-06-01")
        with self.assertRaises(ContractError):
            authorize(
                Consent("c-1", "1", "undetermined", "research", "2026-01-01", "2026-12-31"),
                "treatment",
                "2026-06-01",
            )

    def test_identifier_consent_id_is_rejected(self) -> None:
        named = Consent("subject.identifier", "1", "active", "treatment", "2026-01-01", "2026-12-31")
        with self.assertRaises(ContractError) as blocked:
            authorize(named, "treatment", "2026-06-01")
        self.assertEqual(str(blocked.exception), "consent-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        current = Consent("c-1", "1", "active", "treatment", "2026-01-01", "2026-12-31")
        with self.assertRaises(ContractError) as blocked:
            authorize(current, "treatment", "2026-06-01", why_code="unknown")
        self.assertEqual(str(blocked.exception), "consent-why-missing")

    def test_other_actor_for_same_consent_is_rejected(self) -> None:
        ledger = ConsentLedger()
        current = Consent("c-1", "1", "active", "treatment", "2026-01-01", "2026-12-31")
        ledger.authorize(current, "treatment", "2026-06-01", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            ledger.authorize(current, "treatment", "2026-06-01", "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "consent-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
