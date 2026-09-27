"""Tests for signed rule packs."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.rules import (  # noqa: E402
    class_recall,
    conflict_priority,
    false_positive_breakdown,
    knowledge_countersign,
    pack_signature,
    replay_rule,
    rule_canary,
    rule_explanation,
    rule_switch,
    synthetic_case,
)


class RulePackSignatureTests(unittest.TestCase):
    def test_signed_pack_keeps_version(self) -> None:
        signed = pack_signature("1.0", "ab" * 32, "cd" * 32)
        self.assertEqual(signed["version"], "1.0")
        self.assertNotIn("rules", signed)

    def test_same_pack_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            pack_signature("1.0", "ab" * 32, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "pack-signature-same")

    def test_unknown_pack_version_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            pack_signature("1.2", "ab" * 32, "cd" * 32)
        self.assertEqual(str(blocked.exception), "pack-version-invalid")

    def test_matching_replay_returns_original(self) -> None:
        self.assertEqual(replay_rule("deny", "deny", "ab" * 32, "ab" * 32), "deny")

    def test_changed_replay_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            replay_rule("deny", "allow", "ab" * 32, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "replay-mismatch")

    def test_breakdown_sums_every_class(self) -> None:
        counts = {"interaction": 1, "contraindication": 0, "dose": 2, "allergy": 0, "duplicate": 1}
        self.assertEqual(false_positive_breakdown(counts), 4)

    def test_missing_breakdown_class_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            false_positive_breakdown({"interaction": 1})
        self.assertEqual(blocked.exception.args[0], "false-positive-incomplete")

    def test_every_class_meets_recall(self) -> None:
        scores = {name: 95 for name in ("interaction", "contraindication", "dose", "allergy", "duplicate")}
        self.assertEqual(class_recall(scores), 95)

    def test_one_low_class_is_rejected(self) -> None:
        scores = {name: 95 for name in ("interaction", "contraindication", "dose", "allergy", "duplicate")}
        scores["dose"] = 94
        with self.assertRaises(ContractError) as blocked:
            class_recall(scores)
        self.assertEqual(blocked.exception.args[0], "recall-below-threshold")

    def test_two_reviewers_sign_one_digest(self) -> None:
        signed = knowledge_countersign("reviewer-a", "reviewer-b", "ab" * 32)
        self.assertEqual(signed["second"], "reviewer-b")

    def test_same_reviewer_cannot_countersign(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            knowledge_countersign("reviewer-a", "reviewer-a", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "knowledge-signers-invalid")

    def test_small_canary_is_accepted(self) -> None:
        issued = rule_canary(5, "ab" * 32)
        self.assertEqual(issued["percent"], 5)

    def test_full_rollout_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rule_canary(100, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "canary-percent-invalid")

    def test_enabled_rule_keeps_decision(self) -> None:
        self.assertEqual(rule_switch(True, "deny"), "deny")

    def test_disabled_rule_cannot_allow(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rule_switch(False, "allow")
        self.assertEqual(blocked.exception.args[0], "rule-disabled")

    def test_synthetic_case_keeps_fields(self) -> None:
        case = synthetic_case(True, ("condition",), "ab" * 32)
        self.assertTrue(case["synthetic"])

    def test_identifying_case_field_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            synthetic_case(True, ("subject.name",), "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "case-identifier-forbidden")

    def test_explanation_keeps_rule_and_digest(self) -> None:
        explained = rule_explanation("rule-dose", "deny", "ab" * 32)
        self.assertEqual(explained["rule_id"], "rule-dose")
        self.assertNotIn("case", explained)

    def test_identifying_rule_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rule_explanation("subject.name", "deny", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "explain-rule-forbidden")

    def test_allergy_outranks_dose(self) -> None:
        self.assertEqual(conflict_priority(("interaction", "dose", "allergy")), "allergy")

    def test_unknown_finding_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            conflict_priority(("note",))
        self.assertEqual(blocked.exception.args[0], "priority-finding-invalid")


if __name__ == "__main__":
    unittest.main()
