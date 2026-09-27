"""Consent policy tests for review, commit, and emergency paths."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.write_intent import EmergencyGrant  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.hitl.test_service import config, proof_for, resource  # noqa: E402


class ConsentPolicyTests(unittest.TestCase):
    def test_withdrawn_consent_blocks_commit_policy(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        self.assertEqual(suggestion.state, "APPROVED_ONE")
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        service.withdraw_consent(review_draft().consent.consent_id)
        proof = proof_for(approved, "proof-policy", "reviewer-second", "nonce-policy")
        with self.assertRaises(ContractError) as blocked:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-policy")
        self.assertEqual(str(blocked.exception), "consent-not-active")
        self.assertEqual(approved.state, "APPROVED")
        self.assertIsNone(service.writes.get(proof.proof_id))
        self.assertEqual(service._consent_states[review_draft().consent.consent_id], "withdrawn")

    def test_ordinary_commit_records_active_consent(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        proof = proof_for(approved, "proof-consent", "reviewer-second", "nonce-consent")
        committed = service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-consent")
        self.assertTrue(committed["committed"])
        commit = [event for event in service.log.events if event.operation == "ordinary-commit"][-1]
        self.assertEqual(commit.consent_decision, "active")
        service.log.verify()

    def test_second_review_records_active_consent(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        service.approve_independent(suggestion, review_draft(), "reviewer-second")
        second = [event for event in service.log.events if event.operation == "approve-second"][-1]
        self.assertEqual(second.consent_decision, "active")
        service.log.verify()

    def test_commit_rejects_reused_nonce(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        service.replays.accept(approved.suggestion_id, 1, "nonce-used")
        proof = proof_for(approved, "proof-replay", "reviewer-second", "nonce-used")
        with self.assertRaises(ContractError) as reused:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-replay")
        self.assertEqual(str(reused.exception), "replay-nonce-reused")
        self.assertEqual(approved.state, "APPROVED")
        self.assertIsNone(service.writes.get(proof.proof_id))

    def test_incompatible_contract_version_blocks_review(self) -> None:
        service = ReviewService(config())
        draft = replace(review_draft(), contract_version="2.0")
        with self.assertRaises(ContractError) as blocked:
            service.approve(draft, resource())
        self.assertEqual(str(blocked.exception), "contract-version-incompatible")
        self.assertEqual(service._suggestions, {})
        self.assertEqual(service.log.events, ())

    def test_withdrawn_consent_blocks_second_review_policy(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        service.withdraw_consent(review_draft().consent.consent_id)
        with self.assertRaises(ContractError) as blocked:
            service.approve_independent(suggestion, review_draft(), "reviewer-second")
        self.assertEqual(str(blocked.exception), "consent-not-active")
        self.assertEqual(suggestion.state, "APPROVED_ONE")
        self.assertNotIn("reviewer-second", suggestion.reviewers)

    def test_resource_consent_must_match_tracked_state(self) -> None:
        service = ReviewService(config())
        marked = resource()
        marked["consentState"] = "withdrawn"
        with self.assertRaises(ContractError) as mismatch:
            service.approve(review_draft(), marked)
        self.assertEqual(str(mismatch.exception), "consent-state-mismatch")
        self.assertEqual(service._suggestions, {})

    def test_emergency_resource_consent_must_match_tracked_state(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        service.approve(draft, resource())
        marked = resource()
        marked["consentState"] = "withdrawn"
        grant = EmergencyGrant(
            "grant-marked",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-marked",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as mismatch:
            service.record_emergency(draft, marked, grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(mismatch.exception), "consent-state-mismatch")
        self.assertNotIn(draft.suggestion_id, service._emergencies)

    def test_emergency_with_reason_survives_withdrawn_consent(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        service.approve(draft, resource())
        service.withdraw_consent(draft.consent.consent_id)
        marked = resource()
        marked["consentState"] = "withdrawn"
        grant = EmergencyGrant(
            "grant-consent",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-consent",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        recorded = service.record_emergency(draft, marked, grant, "2026-09-24T00:05:00Z")
        self.assertFalse(recorded["committed"])
        self.assertEqual(recorded["execution_state"], "emergency-pending-confirmation")
        self.assertEqual(service._consent_states[draft.consent.consent_id], "withdrawn")
        recorded_consent = [event for event in service.log.events if event.operation == "emergency-consent"][-1]
        self.assertEqual(recorded_consent.consent_decision, "withdrawn")
        service.log.verify()

    def test_emergency_without_reason_is_denied(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-no-reason",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "",
            draft.content_digest,
            "nonce-no-reason",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as blocked:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(blocked.exception), "emergency-reason-missing")
        self.assertEqual(service._emergencies, {})

    def test_emergency_rejects_reused_nonce(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        self.assertEqual(draft.consent.state, "active")
        service.replays.accept(draft.suggestion_id, 1, "nonce-used")
        self.assertEqual(service._commit_sequences, {})
        grant = EmergencyGrant(
            "grant-replay",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-used",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as reused:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(reused.exception), "replay-nonce-reused")
        self.assertEqual(service._emergencies, {})
        self.assertIsNone(service.writes.get(grant.grant_id))

    def test_confirmation_requires_original_reason(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-confirm",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-confirm",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        cleared = EmergencyGrant(
            grant.grant_id,
            grant.suggestion_id,
            grant.suggestion_version,
            grant.authorized_by,
            grant.target_action,
            "",
            grant.content_digest,
            grant.nonce,
            grant.issued_at,
            grant.expires_at,
        )
        with self.assertRaises(ContractError) as blocked:
            service.confirm_emergency(cleared, "executed")
        self.assertEqual(str(blocked.exception), "emergency-reason-missing")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "EMERGENCY_PENDING_CONFIRMATION")

    def test_reconciliation_requires_original_reason(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-reconcile",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-reconcile",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        service.confirm_emergency(grant, "executed")
        cleared = EmergencyGrant(
            grant.grant_id,
            grant.suggestion_id,
            grant.suggestion_version,
            grant.authorized_by,
            grant.target_action,
            "",
            grant.content_digest,
            grant.nonce,
            grant.issued_at,
            grant.expires_at,
        )
        with self.assertRaises(ContractError) as blocked:
            service.reconcile_emergency("safety-reviewer", cleared)
        self.assertEqual(str(blocked.exception), "emergency-reason-missing")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "POST_REVIEW_REQUIRED")
        closed = service.reconcile_emergency("safety-reviewer", grant)
        self.assertEqual(closed["execution_state"], "archived")
        archived = [event for event in service.log.events if event.operation == "emergency-archived"][-1]
        self.assertEqual(archived.consent_decision, "active")
        service.log.verify()

    def test_repeated_reconciliation_returns_original_result(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        self.assertEqual(draft.contract_version, "1.0")
        grant = EmergencyGrant(
            "grant-reconcile-replay",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-reconcile-replay",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "EMERGENCY_PENDING_CONFIRMATION")
        service.confirm_emergency(grant, "executed")
        first = service.reconcile_emergency("safety-reviewer", grant)
        before = len(service.log.events)
        replayed = service.reconcile_emergency("safety-reviewer", grant)
        self.assertEqual(replayed, first)
        self.assertEqual(len(service.log.events), before)
        self.assertEqual(service.emergency(draft.suggestion_id).state, "ARCHIVED")

    def test_correction_requires_original_reason(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-correct",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-correct",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        service.confirm_emergency(grant, "executed")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "POST_REVIEW_REQUIRED")
        before = tuple(service.emergency(draft.suggestion_id).history)
        cleared = EmergencyGrant(
            grant.grant_id,
            grant.suggestion_id,
            grant.suggestion_version,
            grant.authorized_by,
            grant.target_action,
            "",
            grant.content_digest,
            grant.nonce,
            grant.issued_at,
            grant.expires_at,
        )
        with self.assertRaises(ContractError) as blocked:
            service.correct_emergency("safety-reviewer", cleared, "dose-mismatch")
        self.assertEqual(str(blocked.exception), "emergency-reason-missing")
        self.assertEqual(tuple(service.emergency(draft.suggestion_id).history), before)

    def test_repeated_correction_returns_original_result(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-correct-replay",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-correct-replay",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        service.confirm_emergency(grant, "executed")
        first = service.correct_emergency("safety-reviewer", grant, "dose-mismatch")
        before = tuple(service.emergency(draft.suggestion_id).history)
        events = len(service.log.events)
        replayed = service.correct_emergency("safety-reviewer", grant, "dose-mismatch")
        self.assertEqual(replayed, first)
        self.assertEqual(len(service.log.events), events)
        self.assertEqual(tuple(service.emergency(draft.suggestion_id).history), before)

    def test_reloaded_correction_replay_stays_original(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "correction-replay.json"
            service = ReviewService(config(), store_path=path)
            draft = review_draft()
            grant = EmergencyGrant(
                "grant-correct-store",
                draft.suggestion_id,
                "3",
                "reviewer-synthetic",
                draft.action,
                "break-glass",
                draft.content_digest,
                "nonce-correct-store",
                "2026-09-24T00:00:00Z",
                "2026-09-24T00:10:00Z",
            )
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
            service.confirm_emergency(grant, "executed")
            service.correct_emergency("safety-reviewer", grant, "dose-mismatch")
            restored = ReviewService(config(), store_path=path)
            before = len(restored.log.events)
            replayed = restored.correct_emergency("safety-reviewer", grant, "dose-mismatch")
            self.assertEqual(replayed["execution_state"], "corrected-archived")
            self.assertEqual(len(restored.log.events), before)
            self.assertTrue(restored.emergency(draft.suggestion_id).correction_recorded)
        self.assertEqual(path.name, "correction-replay.json")


if __name__ == "__main__":
    unittest.main()
