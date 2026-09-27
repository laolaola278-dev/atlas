"""Queue tests for identity candidates."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.queue import ReviewQueue  # noqa: E402


class ReviewQueueTests(unittest.TestCase):
    def test_review_required_candidate_is_queued(self) -> None:
        queue = ReviewQueue()
        size = queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        self.assertEqual(size, 1)

    def test_automatic_decision_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            ReviewQueue().enqueue("candidate-synthetic", "ab" * 32, "matched")
        self.assertEqual(blocked.exception.args[0], "queue-decision-invalid")

    def test_duplicate_candidate_is_rejected(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        self.assertEqual(str(blocked.exception), "queue-duplicate")

    def test_queued_candidate_cannot_merge(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.reject_merge("candidate-synthetic")
        self.assertEqual(str(blocked.exception), "queue-merge-forbidden")

    def test_two_reviewers_can_approve(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        digest = queue.approve_merge("candidate-synthetic", "reviewer-one", "reviewer-two")
        self.assertEqual(digest, "ab" * 32)

    def test_one_reviewer_cannot_sign_twice(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.approve_merge("candidate-synthetic", "reviewer-one", "reviewer-one")
        self.assertEqual(blocked.exception.args[0], "merge-same-reviewer")

    def test_blank_signature_is_rejected(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.approve_merge("candidate-synthetic", "reviewer-one", "")
        self.assertEqual(str(blocked.exception), "merge-signature-missing")

    def test_split_keeps_original_digest(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        record = queue.split("candidate-synthetic", "reviewer-one", "reviewer-two", "wrong-link")
        again = queue.split("candidate-synthetic", "reviewer-one", "reviewer-two", "wrong-link")
        self.assertEqual(record, again)
        self.assertEqual(record["action"], "split")
        self.assertEqual(record["digest"], "ab" * 32)

    def test_split_without_reason_is_rejected(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.split("candidate-synthetic", "reviewer-one", "reviewer-two", "unknown")
        self.assertEqual(blocked.exception.args[0], "split-reason-missing")

    def test_automatic_merge_is_never_tolerated(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.tolerate_merge("candidate-synthetic", True, False, "reviewer-one", "reviewer-two")
        self.assertEqual(blocked.exception.args[0], "merge-automatic-forbidden")

    def test_blocked_candidate_is_never_merged(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "ab" * 32, "review-required")
        with self.assertRaises(ContractError) as blocked:
            queue.tolerate_merge("candidate-synthetic", False, True, "reviewer-one", "reviewer-two")
        self.assertEqual(str(blocked.exception), "merge-blocked-zero-tolerance")

    def test_manual_clear_merge_still_needs_two_reviewers(self) -> None:
        queue = ReviewQueue()
        queue.enqueue("candidate-synthetic", "cd" * 32, "review-required")
        digest = queue.tolerate_merge("candidate-synthetic", False, False, "reviewer-one", "reviewer-two")
        self.assertEqual(digest, "cd" * 32)


if __name__ == "__main__":
    unittest.main()
