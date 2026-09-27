"""Tests that emergency grants cannot become ordinary commits."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.write_intent import (  # noqa: E402
    ApprovalProof,
    EmergencyGrant,
    NonceLedger,
    bind_proof,
    emergency_record,
    issue_proof,
    ordinary_commit,
    ordinary_intent,
    proof_expiry,
    target_version_conflict,
    unknown_receipt,
    WriteLedger,
)


def proof() -> ApprovalProof:
    return ApprovalProof(
        "proof-1",
        "suggestion-synthetic",
        "3",
        "reviewer-synthetic",
        "review-order",
        "c" * 64,
        "nonce-1",
        "2026-09-24T00:00:00Z",
        "2026-09-24T01:00:00Z",
    )


def grant() -> EmergencyGrant:
    return EmergencyGrant(
        "grant-1",
        "suggestion-synthetic",
        "3",
        "clinician-synthetic",
        "review-order",
        "break-glass",
        "c" * 64,
        "nonce-2",
        "2026-09-24T00:00:00Z",
        "2026-09-24T00:10:00Z",
    )


class WriteIntentTests(unittest.TestCase):
    def test_matching_proof_commits_once(self) -> None:
        result = ordinary_commit(
            proof(),
            "suggestion-synthetic",
            "3",
            "review-order",
            "c" * 64,
            "2026-09-24T00:30:00Z",
            "target-4",
        )
        self.assertTrue(result["committed"])
        self.assertEqual(result["write_kind"], "ordinary")

    def test_other_reviewer_for_same_proof_is_rejected(self) -> None:
        ledger = WriteLedger()
        current = proof()
        ledger.commit(
            current,
            current.suggestion_id,
            current.suggestion_version,
            current.target_action,
            current.content_digest,
            "2026-09-24T00:30:00Z",
            "target-4",
        )
        other = ApprovalProof(
            current.proof_id,
            current.suggestion_id,
            current.suggestion_version,
            "other-reviewer",
            current.target_action,
            current.content_digest,
            current.nonce,
            current.issued_at,
            current.expires_at,
            current.why_code,
        )
        with self.assertRaises(ContractError) as blocked:
            ledger.commit(
                other,
                other.suggestion_id,
                other.suggestion_version,
                other.target_action,
                other.content_digest,
                "2026-09-24T00:30:00Z",
                "target-4",
            )
        self.assertEqual(str(blocked.exception), "write-responsibility-mismatch")

    def test_expired_or_mismatched_proof_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as expired:
            ordinary_commit(
                proof(),
                "suggestion-synthetic",
                "3",
                "review-order",
                "c" * 64,
                "2026-09-24T02:00:00Z",
                "target-4",
            )
        self.assertEqual(str(expired.exception), "write-window-closed")
        current = proof()
        incompatible = ApprovalProof(
            current.proof_id,
            current.suggestion_id,
            current.suggestion_version,
            current.reviewer_id,
            current.target_action,
            current.content_digest,
            current.nonce,
            current.issued_at,
            current.expires_at,
            contract_version="1.2",
        )
        with self.assertRaises(ContractError) as version:
            ordinary_commit(
                incompatible,
                "suggestion-synthetic",
                "3",
                "review-order",
                "c" * 64,
                "2026-09-24T00:30:00Z",
                "target-4",
            )
        self.assertEqual(str(version.exception), "write-version-incompatible")
        with self.assertRaises(ContractError) as mismatch:
            ordinary_commit(
                proof(),
                "suggestion-synthetic",
                "4",
                "review-order",
                "c" * 64,
                "2026-09-24T00:30:00Z",
                "target-4",
            )
        self.assertEqual(str(mismatch.exception), "approval-mismatch")

    def test_emergency_grant_cannot_commit_and_records_separately(self) -> None:
        with self.assertRaises(ContractError) as wrong_type:
            ordinary_commit(
                grant(),  # type: ignore[arg-type]
                "suggestion-synthetic",
                "3",
                "review-order",
                "c" * 64,
                "2026-09-24T00:05:00Z",
                "target-4",
            )
        self.assertEqual(str(wrong_type.exception), "emergency-grant-not-approval")
        recorded = emergency_record(
            grant(),
            "suggestion-synthetic",
            "3",
            "review-order",
            "c" * 64,
            "2026-09-24T00:05:00Z",
        )
        self.assertFalse(recorded["committed"])
        self.assertEqual(recorded["execution_state"], "emergency-recorded")
        current = grant()
        incompatible = EmergencyGrant(
            current.grant_id,
            current.suggestion_id,
            current.suggestion_version,
            current.authorized_by,
            current.target_action,
            current.reason_code,
            current.content_digest,
            current.nonce,
            current.issued_at,
            current.expires_at,
            "1.2",
        )
        with self.assertRaises(ContractError) as version:
            emergency_record(
                incompatible,
                "suggestion-synthetic",
                "3",
                "review-order",
                "c" * 64,
                "2026-09-24T00:05:00Z",
            )
        self.assertEqual(str(version.exception), "write-version-incompatible")

    def test_identifier_action_is_rejected(self) -> None:
        current = proof()
        named = ApprovalProof(
            current.proof_id,
            current.suggestion_id,
            current.suggestion_version,
            current.reviewer_id,
            "subject.identifier",
            current.content_digest,
            current.nonce,
            current.issued_at,
            current.expires_at,
        )
        with self.assertRaises(ContractError) as blocked:
            ordinary_commit(
                named,
                "suggestion-synthetic",
                "3",
                "subject.identifier",
                "c" * 64,
                "2026-09-24T00:30:00Z",
                "target-4",
            )
        self.assertEqual(str(blocked.exception), "write-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        current = proof()
        named = ApprovalProof(
            current.proof_id,
            current.suggestion_id,
            current.suggestion_version,
            current.reviewer_id,
            current.target_action,
            current.content_digest,
            current.nonce,
            current.issued_at,
            current.expires_at,
            "unknown",
        )
        with self.assertRaises(ContractError) as blocked:
            ordinary_commit(
                named,
                "suggestion-synthetic",
                "3",
                "review-order",
                "c" * 64,
                "2026-09-24T00:30:00Z",
                "target-4",
            )
        self.assertEqual(str(blocked.exception), "write-why-missing")

    def test_two_reviewers_issue_one_proof(self) -> None:
        issued = issue_proof("reviewer-a", "reviewer-b", "ab" * 32)
        self.assertEqual(issued["state"], "issued")
        self.assertIn("reviewer-b", issued["signers"])

    def test_same_reviewer_cannot_issue_proof(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            issue_proof("reviewer-a", "reviewer-a", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "proof-signers-invalid")

    def test_matching_binding_is_accepted(self) -> None:
        self.assertEqual(bind_proof("subject-ref", "subject-ref", "note", "note", "3", "3"), "bound")

    def test_changed_patient_breaks_binding(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            bind_proof("subject-ref", "other-ref", "note", "note", "3", "3")
        self.assertEqual(blocked.exception.args[0], "proof-binding-mismatch")

    def test_nonce_can_be_used_once(self) -> None:
        ledger = NonceLedger()
        self.assertEqual(ledger.use("ab" * 32), "used")
        with self.assertRaises(ContractError) as blocked:
            ledger.use("ab" * 32)
        self.assertEqual(blocked.exception.args[0], "nonce-reused")

    def test_proof_before_expiry_is_active(self) -> None:
        self.assertEqual(proof_expiry("2026-09-24T00:00:00Z", "2026-09-24T01:00:00Z", "2026-09-24T00:30:00Z"), "active")

    def test_proof_at_expiry_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            proof_expiry("2026-09-24T00:00:00Z", "2026-09-24T01:00:00Z", "2026-09-24T01:00:00Z")
        self.assertEqual(blocked.exception.args[0], "proof-expired")

    def test_ordinary_approval_is_an_ordinary_intent(self) -> None:
        self.assertEqual(ordinary_intent("ordinary", "approval"), "ordinary")

    def test_emergency_grant_is_not_ordinary(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            ordinary_intent("ordinary", "grant")
        self.assertEqual(blocked.exception.args[0], "intent-not-ordinary")

    def test_same_target_version_is_accepted(self) -> None:
        self.assertEqual(target_version_conflict("3", "3"), "3")

    def test_changed_target_version_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            target_version_conflict("3", "4")
        self.assertEqual(blocked.exception.args[0], "target-version-conflict")

    def test_committed_receipt_matches(self) -> None:
        self.assertEqual(unknown_receipt("committed", "committed"), "committed")

    def test_unknown_receipt_is_retryable(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            unknown_receipt("committed", "unknown")
        self.assertEqual(blocked.exception.args[0], "receipt-result-unknown")


if __name__ == "__main__":
    unittest.main()
