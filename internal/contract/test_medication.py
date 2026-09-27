"""Tests for deterministic medication safety decisions."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.medication import (  # noqa: E402
    MedicationLedger,
    age_weight_bound,
    allergy_cross,
    contraindication,
    critical_lab,
    derive_findings,
    dose_limit,
    evidence_citation,
    interaction_decision,
    medication_decision,
    model_timeout,
    reproductive_rule,
    uncertain_rule,
)


def findings(**overrides: bool) -> dict[str, bool]:
    values = {
        "allergy": False,
        "contraindication": False,
        "dose_limit": False,
        "duplicate": False,
        "interaction": False,
    }
    values.update(overrides)
    return values


class MedicationDecisionTests(unittest.TestCase):
    def test_clean_findings_allow_only_matching_model(self) -> None:
        self.assertEqual(medication_decision(findings(), "allow"), "allow")

    def test_any_hard_finding_denies_model_override(self) -> None:
        for name in ("interaction", "contraindication", "dose_limit", "allergy", "duplicate"):
            with self.assertRaises(ContractError) as blocked:
                medication_decision(findings(**{name: True}), "allow")
            self.assertEqual(str(blocked.exception), "model-cannot-override-rule")
            self.assertEqual(medication_decision(findings(**{name: True}), "deny"), "deny")

    def test_incomplete_findings_are_rejected(self) -> None:
        partial = findings()
        del partial["allergy"]
        with self.assertRaises(ContractError) as blocked:
            medication_decision(partial, "allow")
        self.assertEqual(str(blocked.exception), "medication-findings-invalid")

    def test_facts_derive_hard_findings(self) -> None:
        facts = {
            "active": ("med-a",),
            "allergens": ("med-b",),
            "blocked_conditions": (),
            "dose": 3,
            "dose_limit": 2,
            "ordered": ("med-a",),
            "pairs": (),
        }
        derived = derive_findings(facts)
        self.assertEqual(derived["dose_limit"], True)
        self.assertEqual(derived["duplicate"], True)
        self.assertEqual(medication_decision(derived, "deny"), "deny")
        with self.assertRaises(ContractError) as blocked:
            medication_decision(derived, "allow")
        self.assertEqual(str(blocked.exception), "model-cannot-override-rule")

    def test_identifier_medication_code_is_rejected(self) -> None:
        facts = {
            "active": (),
            "allergens": (),
            "blocked_conditions": (),
            "dose": 1,
            "dose_limit": 2,
            "ordered": ("subject.identifier",),
            "pairs": (),
        }
        with self.assertRaises(ContractError) as blocked:
            derive_findings(facts)
        self.assertEqual(str(blocked.exception), "medication-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            medication_decision(findings(), "allow", why_code="unknown")
        self.assertEqual(str(blocked.exception), "medication-why-missing")

    def test_other_actor_for_same_findings_is_rejected(self) -> None:
        ledger = MedicationLedger()
        ledger.decide(findings(), "allow", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            ledger.decide(findings(), "allow", "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "medication-responsibility-mismatch")

    def test_registered_pair_is_denied(self) -> None:
        known = frozenset({"ab" * 32, "cd" * 32})
        self.assertEqual(interaction_decision(("cd" * 32, "ab" * 32), known), "deny")

    def test_unknown_pair_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            interaction_decision(("ab" * 32, "ef" * 32), frozenset({"ab" * 32}))
        self.assertEqual(blocked.exception.args[0], "interaction-unknown")

    def test_registered_condition_is_denied(self) -> None:
        self.assertEqual(contraindication("ab" * 32, frozenset({"ab" * 32})), "deny")

    def test_unknown_condition_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            contraindication("cd" * 32, frozenset({"ab" * 32}))
        self.assertEqual(blocked.exception.args[0], "contraindication-unknown")

    def test_milligrams_convert_before_limit(self) -> None:
        self.assertEqual(dose_limit(1, "mg", 1000), "allow")

    def test_converted_dose_over_limit_is_denied(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            dose_limit(2, "mg", 1000)
        self.assertEqual(blocked.exception.args[0], "dose-limit-exceeded")

    def test_unknown_dose_unit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            dose_limit(1, "cup", 1000)
        self.assertEqual(str(blocked.exception), "dose-unit-unknown")

    def test_shared_allergy_group_is_denied(self) -> None:
        groups = {"ab" * 32: "11" * 32, "cd" * 32: "11" * 32}
        self.assertEqual(allergy_cross("ab" * 32, "cd" * 32, groups), "deny")

    def test_separate_allergy_groups_do_not_cross(self) -> None:
        groups = {"ab" * 32: "11" * 32, "cd" * 32: "22" * 32}
        with self.assertRaises(ContractError) as blocked:
            allergy_cross("ab" * 32, "cd" * 32, groups)
        self.assertEqual(blocked.exception.args[0], "allergy-no-cross")

    def test_age_and_weight_inside_bounds(self) -> None:
        self.assertEqual(age_weight_bound(3650, 70000), "inside")

    def test_weight_outside_bounds_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            age_weight_bound(3650, 499)
        self.assertEqual(blocked.exception.args[0], "weight-bound-invalid")

    def test_unrestricted_state_is_allowed(self) -> None:
        self.assertEqual(reproductive_rule("pregnancy", False), "allow")

    def test_restricted_state_is_denied(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            reproductive_rule("lactation", True)
        self.assertEqual(blocked.exception.args[0], "reproductive-restricted")

    def test_lab_inside_interval_is_accepted(self) -> None:
        self.assertEqual(critical_lab(70, 60, 100), "inside")

    def test_lab_outside_interval_is_critical(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            critical_lab(101, 60, 100)
        self.assertEqual(blocked.exception.args[0], "critical-value")

    def test_denial_requires_registered_evidence(self) -> None:
        self.assertEqual(evidence_citation("deny", "ab" * 32, frozenset({"ab" * 32})), "ab" * 32)

    def test_denial_without_evidence_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            evidence_citation("deny", "ab" * 32, frozenset())
        self.assertEqual(blocked.exception.args[0], "evidence-citation-missing")

    def test_certain_rule_is_allowed(self) -> None:
        self.assertEqual(uncertain_rule("certain"), "allow")

    def test_uncertain_rule_is_denied(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            uncertain_rule("uncertain")
        self.assertEqual(blocked.exception.args[0], "rule-uncertain-denied")

    def test_timeout_keeps_the_hard_rule(self) -> None:
        self.assertEqual(model_timeout("deny", True), "deny")

    def test_timeout_flag_must_be_boolean(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            model_timeout("deny", "true")
        self.assertEqual(blocked.exception.args[0], "timeout-input-invalid")


if __name__ == "__main__":
    unittest.main()
