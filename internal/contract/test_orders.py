"""Tests for unsubmitted medication order drafts."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.orders import (  # noqa: E402
    cancel_or_correct,
    duplicate_order,
    isolate_emergency_order,
    missing_proof,
    order_audit,
    order_draft as draft_order,
    pharmacy_receipt,
    subject_match,
    submit_gate,
)


class OrderDraftTests(unittest.TestCase):
    def test_synthetic_draft_stays_unsubmitted(self) -> None:
        drafted = draft_order("order-synthetic", "ab" * 32, True)
        self.assertEqual(drafted["state"], "draft")
        self.assertEqual(len(drafted), 3)

    def test_real_order_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            draft_order("order-synthetic", "cd" * 32, False)
        self.assertEqual(blocked.exception.args[0], "order-not-synthetic")

    def test_identifying_reference_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            draft_order("subject.identifier", "ef" * 32, True)
        self.assertEqual(str(blocked.exception), "order-reference-forbidden")

    def test_approval_can_pass_the_gate(self) -> None:
        self.assertEqual(submit_gate("draft", "approval"), "submitted")

    def test_missing_proof_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            submit_gate("draft", "")
        self.assertEqual(blocked.exception.args[0], "order-proof-missing")

    def test_grant_cannot_submit_an_order(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            submit_gate("draft", "grant")
        self.assertEqual(blocked.exception.args[0], "order-proof-rejected")

    def test_complete_proof_is_kept(self) -> None:
        kept = missing_proof("proof-synthetic", "ab" * 32)
        self.assertTrue(kept.startswith("proof-"))

    def test_absent_proof_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            missing_proof("", "")
        self.assertEqual(blocked.exception.args[0], "order-proof-absent")

    def test_same_subject_is_accepted(self) -> None:
        matched = subject_match("subject-ref", "subject-ref")
        self.assertIn("ref", matched)

    def test_other_subject_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            subject_match("left-ref", "right-ref")
        self.assertEqual(blocked.exception.args[0], "order-subject-mismatch")

    def test_dispensed_receipt_is_kept(self) -> None:
        self.assertEqual(pharmacy_receipt("submitted", "dispensed"), "dispensed")

    def test_unknown_pharmacy_receipt_is_retryable(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            pharmacy_receipt("submitted", "unknown")
        self.assertEqual(blocked.exception.args[0], "pharmacy-result-unknown")

    def test_new_order_digest_is_accepted(self) -> None:
        self.assertEqual(duplicate_order(("ab" * 32,), "cd" * 32), "cd" * 32)

    def test_active_order_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            duplicate_order(("ab" * 32,), "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "duplicate-order")

    def test_submitted_order_can_be_cancelled(self) -> None:
        self.assertEqual(cancel_or_correct("submitted", "cancel"), "cancel")

    def test_dispensed_order_cannot_be_cancelled(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            cancel_or_correct("dispensed", "cancel")
        self.assertEqual(blocked.exception.args[0], "order-cancel-too-late")

    def test_emergency_order_stays_in_its_table(self) -> None:
        self.assertEqual(isolate_emergency_order("emergency", "emergency"), "emergency")

    def test_emergency_order_cannot_enter_ordinary_table(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            isolate_emergency_order("emergency", "ordinary")
        self.assertEqual(blocked.exception.args[0], "order-emergency-isolated")

    def test_matching_order_audit_is_kept(self) -> None:
        self.assertEqual(order_audit("ab" * 32, "ab" * 32, "submit"), "submit")

    def test_changed_order_audit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            order_audit("ab" * 32, "cd" * 32, "submit")
        self.assertEqual(blocked.exception.args[0], "order-audit-mismatch")


if __name__ == "__main__":
    unittest.main()
