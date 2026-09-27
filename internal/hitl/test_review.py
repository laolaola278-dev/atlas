"""Tests for the review gate in front of the state machine."""
import unittest

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.hitl.review import (  # noqa: E402
    approve_one,
    approve_second,
    dual_scope,
    first_signoff,
    project_status,
    queue_for_review,
    second_denial,
)


class ReviewGateTests(unittest.TestCase):
    def test_valid_draft_reaches_one_approval(self) -> None:
        suggestion = queue_for_review(review_draft())
        approved = approve_one(suggestion, review_draft())
        self.assertEqual(approved.state, "APPROVED_ONE")
        self.assertIn("reviewer-synthetic", approved.reviewers)

    def test_withdrawn_consent_never_enters_pending_review(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            queue_for_review(review_draft("withdrawn"))
        self.assertEqual(str(blocked.exception), "consent-not-active")

    def test_approval_rejects_a_different_suggestion(self) -> None:
        suggestion = queue_for_review(review_draft())
        swapped = review_draft(suggestion_id="other-suggestion")
        with self.assertRaises(ContractError) as mismatch:
            approve_one(suggestion, swapped)
        self.assertEqual(str(mismatch.exception), "review-suggestion-mismatch")
        self.assertEqual(suggestion.state, "PENDING_REVIEW")

    def test_withdrawn_consent_blocks_second_review(self) -> None:
        suggestion = approve_one(queue_for_review(review_draft()), review_draft())
        with self.assertRaises(ContractError) as blocked:
            approve_second(suggestion, review_draft("withdrawn"), "reviewer-second")
        self.assertEqual(str(blocked.exception), "consent-not-active")
        self.assertEqual(suggestion.state, "APPROVED_ONE")

    def test_known_state_projects(self) -> None:
        self.assertEqual(project_status("PENDING_REVIEW"), "review")

    def test_unknown_state_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            project_status("MERGED")
        self.assertEqual(blocked.exception.args[0], "projection-state-unknown")

    def test_pending_review_can_take_one_signoff(self) -> None:
        self.assertEqual(first_signoff("PENDING_REVIEW", "reviewer-synthetic"), "APPROVED_ONE")

    def test_system_cannot_sign_off(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            first_signoff("PENDING_REVIEW", "system")
        self.assertEqual(blocked.exception.args[0], "signoff-actor-forbidden")

    def test_medication_requires_two_reviewers(self) -> None:
        self.assertTrue(dual_scope("medication"))
        self.assertFalse(dual_scope("note"))

    def test_unknown_action_has_no_scope(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            dual_scope("merge")
        self.assertEqual(blocked.exception.args[0], "dual-scope-invalid")

    def test_second_denial_stops_approval(self) -> None:
        self.assertEqual(second_denial("APPROVED_ONE", "deny"), "SECOND_DENIED")

    def test_denial_from_another_state_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            second_denial("APPROVED", "deny")
        self.assertEqual(blocked.exception.args[0], "second-denial-state-invalid")


if __name__ == "__main__":
    unittest.main()
