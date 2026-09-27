"""Replay tests for emergency confirmation."""
import unittest

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.contract.write_intent import EmergencyGrant  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.hitl.test_service import config, resource  # noqa: E402


def confirmation_grant(draft, nonce: str) -> EmergencyGrant:
    """Build one synthetic emergency grant for a confirmation replay."""
    return EmergencyGrant(
        "grant-confirmation-replay",
        draft.suggestion_id,
        "3",
        "reviewer-synthetic",
        draft.action,
        "break-glass",
        draft.content_digest,
        nonce,
        "2026-09-24T00:00:00Z",
        "2026-09-24T00:10:00Z",
    )


class ConfirmationReplayTests(unittest.TestCase):
    def test_unknown_receipt_records_withdrawn_consent(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        service.approve(draft, resource())
        grant = confirmation_grant(draft, "nonce-unknown-consent")
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        service.withdraw_consent(draft.consent.consent_id)
        with self.assertRaises(Exception) as unknown:
            service.confirm_emergency(grant, "unknown")
        self.assertEqual(str(unknown.exception), "result-unknown")
        recorded = [event for event in service.log.events if event.operation == "emergency-unknown"][-1]
        self.assertEqual(recorded.consent_decision, "withdrawn")

    def test_repeated_confirmation_keeps_one_audit_event(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = confirmation_grant(draft, "nonce-confirmation-replay")
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        first = service.confirm_emergency(grant, "executed")
        before = len(service.log.events)
        self.assertEqual(service.confirm_emergency(grant, "executed"), first)
        self.assertEqual(len(service.log.events), before)


if __name__ == "__main__":
    unittest.main()
