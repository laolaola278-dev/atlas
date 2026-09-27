"""Tests that review failures do not look like audited success."""
import unittest

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.audit.chain import AuditLog  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.hitl.audited import approve_and_audit, queue_and_audit  # noqa: E402


class AuditedReviewTests(unittest.TestCase):
    def test_queue_and_approval_append_two_linked_events(self) -> None:
        log = AuditLog("review-stream")
        suggestion = queue_and_audit(review_draft(), log)
        approve_and_audit(suggestion, review_draft(), log)
        self.assertEqual(
            [event.operation for event in log.events],
            ["queue-review", "approve-one"],
        )
        self.assertEqual({event.consent_decision for event in log.events}, {"active"})
        log.verify()

    def test_withdrawn_consent_appends_nothing(self) -> None:
        log = AuditLog("review-stream")
        with self.assertRaises(ContractError):
            queue_and_audit(review_draft("withdrawn"), log)
        self.assertEqual(log.events, ())

    def test_approval_without_queue_event_is_rejected(self) -> None:
        log = AuditLog("review-stream")
        suggestion = queue_and_audit(review_draft(), AuditLog("other-stream"))
        with self.assertRaises(ContractError) as missing:
            approve_and_audit(suggestion, review_draft(), log)
        self.assertEqual(str(missing.exception), "review-audit-missing")
        self.assertEqual(log.events, ())


if __name__ == "__main__":
    unittest.main()
