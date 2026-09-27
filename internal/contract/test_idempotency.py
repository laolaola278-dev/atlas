"""Tests for write-result idempotency."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.idempotency import (  # noqa: E402
    EmergencyIntentLog,
    IdempotencyLog,
    PostReviewQueue,
    audit_link,
    break_glass_reason,
    bypass_path,
    controlled_correction,
    emergency_action,
    emergency_commit_guard,
    repeat_submit,
    review_policy_version,
    withdraw_condition,
)


class IdempotencyTests(unittest.TestCase):
    def test_restored_unknown_result_cannot_be_resent(self) -> None:
        log = IdempotencyLog()
        log.restore("proof-1", "d" * 64, "unknown")
        with self.assertRaises(ContractError) as unknown:
            log.begin("proof-1", "d" * 64)
        self.assertEqual(str(unknown.exception), "result-unknown")

    def test_invalid_restored_state_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as invalid:
            IdempotencyLog().restore("proof-1", "d" * 64, "retried")
        self.assertEqual(str(invalid.exception), "idempotency-state-invalid")

    def test_identifier_key_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            IdempotencyLog().begin("subject.identifier", "d" * 64)
        self.assertEqual(str(blocked.exception), "idempotency-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            IdempotencyLog().begin("proof-1", "d" * 64, why_code="unknown")
        self.assertEqual(str(blocked.exception), "idempotency-why-missing")

    def test_replay_with_other_actor_is_rejected(self) -> None:
        log = IdempotencyLog()
        log.begin("proof-actor", "d" * 64, actor_id="reviewer-synthetic", why_code="treatment-review")
        with self.assertRaises(ContractError) as blocked:
            log.begin("proof-actor", "d" * 64, actor_id="other-reviewer", why_code="treatment-review")
        self.assertEqual(str(blocked.exception), "idempotency-responsibility-mismatch")

    def test_committed_receipt_repeats_the_same_version(self) -> None:
        log = IdempotencyLog()
        log.begin("proof-receipt", "d" * 64, "7", "reviewer-synthetic", "treatment-review")
        log.mark_committed("proof-receipt")
        first = log.receipt("proof-receipt", "d" * 64, "reviewer-synthetic", "treatment-review")
        second = log.receipt("proof-receipt", "d" * 64, "reviewer-synthetic", "treatment-review")
        self.assertEqual(first, second)
        self.assertEqual(first["target_version"], "7")

    def test_accepted_write_has_no_receipt(self) -> None:
        log = IdempotencyLog()
        log.begin("proof-pending", "d" * 64, "7", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            log.receipt("proof-pending", "d" * 64, "reviewer-synthetic", "treatment-review")
        self.assertEqual(blocked.exception.args[0], "idempotency-receipt-pending")

    def test_same_digest_returns_original_state(self) -> None:
        self.assertEqual(repeat_submit("ab" * 32, "ab" * 32, "committed"), "committed")

    def test_changed_digest_conflicts(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            repeat_submit("ab" * 32, "cd" * 32, "committed")
        self.assertEqual(blocked.exception.args[0], "repeat-conflict")

    def test_unwritten_approval_can_be_withdrawn(self) -> None:
        self.assertEqual(withdraw_condition("approved", False), "withdrawn")

    def test_written_approval_cannot_be_withdrawn(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            withdraw_condition("approved", True)
        self.assertEqual(blocked.exception.args[0], "withdraw-too-late")

    def test_declared_emergency_action_is_authorized(self) -> None:
        self.assertEqual(emergency_action("stabilize", "reviewer-synthetic"), "stabilize")

    def test_ordinary_action_is_not_emergency(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            emergency_action("note", "reviewer-synthetic")
        self.assertEqual(blocked.exception.args[0], "emergency-action-forbidden")

    def test_emergency_intent_stays_separate(self) -> None:
        log = EmergencyIntentLog()
        self.assertEqual(log.record("emergency-one", "stabilize"), "stabilize")

    def test_ordinary_key_cannot_enter_emergency_log(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            EmergencyIntentLog().record("ordinary-one", "stabilize")
        self.assertEqual(blocked.exception.args[0], "emergency-intent-forbidden")

    def test_emergency_grant_cannot_commit_ordinary(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            emergency_commit_guard("grant", "ordinary")
        self.assertEqual(blocked.exception.args[0], "emergency-commit-forbidden")

    def test_emergency_grant_can_stay_emergency(self) -> None:
        self.assertEqual(emergency_commit_guard("grant", "emergency"), "emergency")

    def test_emergency_record_enters_post_review(self) -> None:
        self.assertEqual(PostReviewQueue().enqueue("emergency-one", "emergency"), 1)

    def test_ordinary_record_cannot_enter_post_review(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            PostReviewQueue().enqueue("ordinary-one", "emergency")
        self.assertEqual(blocked.exception.args[0], "postreview-key-forbidden")

    def test_independent_reviewer_can_correct(self) -> None:
        self.assertEqual(
            controlled_correction("POST_REVIEW_REQUIRED", "reviewer-b", "reviewer-a", "treatment-review", False),
            "corrected",
        )

    def test_submitted_record_cannot_be_corrected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            controlled_correction("POST_REVIEW_REQUIRED", "reviewer-b", "reviewer-a", "treatment-review", True)
        self.assertEqual(blocked.exception.args[0], "correction-state-invalid")

    def test_registered_break_glass_reason_is_accepted(self) -> None:
        self.assertEqual(break_glass_reason("life-threat", "reviewer-synthetic"), "life-threat")

    def test_unknown_break_glass_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            break_glass_reason("unknown", "reviewer-synthetic")
        self.assertEqual(blocked.exception.args[0], "break-glass-reason-invalid")

    def test_previous_review_policy_is_accepted(self) -> None:
        self.assertEqual(review_policy_version("1.0", "1.1"), "1.0")

    def test_skipped_review_policy_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            review_policy_version("1.2", "1.1")
        self.assertEqual(blocked.exception.args[0], "review-policy-mismatch")

    def test_matching_audit_digest_links(self) -> None:
        self.assertEqual(audit_link("ab" * 32, "ab" * 32, "approve"), "approve")

    def test_changed_audit_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            audit_link("ab" * 32, "cd" * 32, "approve")
        self.assertEqual(blocked.exception.args[0], "audit-link-mismatch")

    def test_every_numbered_bypass_is_rejected(self) -> None:
        for path_id in range(1, 101):
            with self.assertRaises(ContractError) as blocked:
                bypass_path(path_id, True)
            self.assertEqual(blocked.exception.args[0], "bypass-forbidden")

    def test_path_outside_the_hundred_is_invalid(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            bypass_path(101, False)
        self.assertEqual(blocked.exception.args[0], "bypass-path-invalid")


if __name__ == "__main__":
    unittest.main()
