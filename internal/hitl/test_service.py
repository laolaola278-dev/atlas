"""Integration tests for the in-process review service."""
import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.audit.file import AuditFile  # noqa: E402
from internal.contract.domain import SuggestionDraft  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.write_intent import ApprovalProof, EmergencyGrant  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.hitl.state.machine import Suggestion  # noqa: E402


def config() -> dict[str, str]:
    return {
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "policy_version": "1.0.0",
        "audit_stream": "review-service",
        "secret_ref": "secret://atlas/signing-key",
    }


def resource() -> dict[str, object]:
    return {
        "resourceType": "Observation",
        "id": "observation-synthetic",
        "synthetic": True,
        "meta": {"versionId": "1", "profile": ["http://example.invalid/atlas/StructureDefinition/observation"]},
        "purposeCode": "treatment",
        "codeSystem": "http://example.invalid/atlas/CodeSystem/purpose",
        "reviewedAt": "2026-09-24",
        "subject": {"reference": "Patient/patient-ref-synthetic"},
    }


def proof_for(suggestion, proof_id: str, reviewer_id: str, nonce: str, digest: str | None = None) -> ApprovalProof:
    """Build one synthetic approval proof for a tracked suggestion."""
    return ApprovalProof(
        proof_id,
        suggestion.suggestion_id,
        str(suggestion.version),
        reviewer_id,
        suggestion.action,
        suggestion.content_digest if digest is None else digest,
        nonce,
        "2026-09-24T00:00:00Z",
        "2026-09-24T01:00:00Z",
    )


def grant_for(draft, grant_id: str, nonce: str) -> EmergencyGrant:
    """Build one synthetic emergency grant bound to its draft actor."""
    return EmergencyGrant(
        grant_id,
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


class ReviewServiceTests(unittest.TestCase):
    def test_complete_request_approves_and_audits_both_steps(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        self.assertEqual(suggestion.state, "APPROVED_ONE")
        self.assertEqual(
            [event.operation for event in service.log.events],
            ["queue-review", "approve-one"],
        )
        service.log.verify()

    def test_wrong_campus_and_invalid_resource_append_nothing(self) -> None:
        service = ReviewService(config())
        foreign = review_draft()
        foreign.actor["campus_id"] = "other-campus"
        with self.assertRaises(ContractError) as campus:
            service.approve(foreign, resource())
        self.assertEqual(str(campus.exception), "campus-mismatch")
        broken = resource()
        broken["purposeCode"] = ""
        with self.assertRaises(ContractError):
            service.approve(review_draft(), broken)
        self.assertEqual(service.log.events, ())

    def test_review_resource_must_declare_catalog_profile(self) -> None:
        service = ReviewService(config())
        unknown = resource()
        unknown["meta"] = {"versionId": "1", "profile": ["http://example.invalid/atlas/unknown"]}
        with self.assertRaises(ContractError) as blocked:
            service.approve(review_draft(), unknown)
        self.assertEqual(str(blocked.exception), "profile-not-declared")
        self.assertEqual(service._suggestions, {})

    def test_other_patient_resource_appends_nothing(self) -> None:
        service = ReviewService(config())
        other = resource()
        other["subject"] = {"reference": "Patient/other-synthetic"}
        with self.assertRaises(ContractError) as mismatch:
            service.approve(review_draft(), other)
        self.assertEqual(str(mismatch.exception), "patient-reference-mismatch")
        self.assertEqual(service.log.events, ())

    def test_other_purpose_appends_nothing(self) -> None:
        service = ReviewService(config())
        other = resource()
        other["purposeCode"] = "research"
        with self.assertRaises(ContractError) as mismatch:
            service.approve(review_draft(), other)
        self.assertEqual(str(mismatch.exception), "purpose-mismatch")
        self.assertEqual(service.log.events, ())

    def test_new_draft_cannot_reactivate_withdrawn_consent(self) -> None:
        service = ReviewService(config())
        service.approve(review_draft(), resource())
        service.withdraw_consent(review_draft().consent.consent_id)
        revived = review_draft(suggestion_id="suggestion-revived")
        marked = resource()
        marked["consentState"] = "withdrawn"
        with self.assertRaises(ContractError) as blocked:
            service.approve(revived, marked)
        self.assertEqual(str(blocked.exception), "consent-not-active")
        self.assertEqual(service._consent_states[review_draft().consent.consent_id], "withdrawn")
        self.assertNotIn(revived.suggestion_id, service._suggestions)

    def test_durable_review_reloads_the_same_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-audit.jsonl"
            service = ReviewService(config(), path)
            suggestion = service.approve(review_draft(), resource())
            loaded = AuditFile(path, "review-service")
            self.assertEqual(
                [event.operation for event in loaded.log.events],
                ["queue-review", "approve-one"],
            )
            self.assertEqual(loaded.log.events[-1].resource_id, suggestion.suggestion_id)
            loaded.log.verify()
        self.assertTrue(path.name.endswith(".jsonl"))

    def test_reloaded_unknown_receipt_cannot_be_retried(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            proof = proof_for(approved, "proof-store", "reviewer-second", "nonce-store")
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
            service.mark_commit_unknown(proof.proof_id)
            restored = ReviewService(config(), store_path=path)
            with self.assertRaises(ContractError) as replay:
                restored.commit_ordinary(restored._suggestions[approved.suggestion_id], proof, "2026-09-24T00:30:00Z", "target-4")
            self.assertEqual(str(replay.exception), "result-unknown")
            self.assertEqual(restored.writes.get(proof.proof_id).target_version, "target-4")
            self.assertEqual(restored._suggestions[approved.suggestion_id].state, "WRITEBACK_COMMITTED")
        self.assertTrue(path.name.endswith(".json"))

    def test_reloaded_withdrawal_blocks_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            service.withdraw_consent(review_draft().consent.consent_id)
            restored = ReviewService(config(), store_path=path)
            proof = proof_for(approved, "proof-withdrawn", "reviewer-second", "nonce-withdrawn")
            with self.assertRaises(ContractError) as blocked:
                restored.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
            self.assertEqual(str(blocked.exception), "consent-not-active")
            self.assertEqual(restored._suggestions[approved.suggestion_id].state, "APPROVED")

    def test_reloaded_retired_rule_blocks_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule-store.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            service.retire_rule_pack(review_draft().rule_pack.pack_id)
            restored = ReviewService(config(), store_path=path)
            self.assertEqual(restored._rule_states[review_draft().rule_pack.pack_id], "retired")
            with self.assertRaises(ContractError) as blocked:
                restored.approve_independent(suggestion, review_draft(), "reviewer-second")
            self.assertEqual(str(blocked.exception), "rule-state-rejected")
            self.assertEqual(restored._suggestions[suggestion.suggestion_id].state, "APPROVED_ONE")
        self.assertEqual(path.suffix, ".json")

    def test_changed_store_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            raw = path.read_text(encoding="utf-8").replace("APPROVED_ONE", "APPROVED")
            path.write_text(raw, encoding="utf-8")
            with self.assertRaises(ContractError) as tampered:
                ReviewService(config(), store_path=path)
            self.assertEqual(str(tampered.exception), "review-store-tampered")

    def test_other_campus_cannot_open_store(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            ReviewService(config(), store_path=path).approve(review_draft(), resource())
            foreign = config()
            foreign["campus_id"] = "other-campus"
            with self.assertRaises(ContractError) as mismatch:
                ReviewService(foreign, store_path=path)
            self.assertEqual(str(mismatch.exception), "review-store-scope-mismatch")

    def test_reloaded_emergency_keeps_its_grant(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            service = ReviewService(config(), store_path=path)
            draft = review_draft()
            grant = EmergencyGrant(
                "grant-store", draft.suggestion_id, "3", "reviewer-synthetic", draft.action,
                "break-glass", draft.content_digest, "nonce-store",
                "2026-09-24T00:00:00Z", "2026-09-24T00:10:00Z",
            )
            other = EmergencyGrant(
                "grant-other", draft.suggestion_id, "3", "reviewer-synthetic", draft.action,
                "break-glass", draft.content_digest, "nonce-other",
                "2026-09-24T00:00:00Z", "2026-09-24T00:10:00Z",
            )
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
            restored = ReviewService(config(), store_path=path)
            with self.assertRaises(ContractError) as mismatch:
                restored.confirm_emergency(other, "executed")
            self.assertEqual(str(mismatch.exception), "emergency-grant-mismatch")
            confirmed = restored.confirm_emergency(grant, "executed")
            self.assertEqual(confirmed["execution_state"], "post-review-required")
            self.assertEqual(restored.emergency(draft.suggestion_id).state, "POST_REVIEW_REQUIRED")

    def test_inline_secret_prevents_startup(self) -> None:
        leaked = config()
        leaked["api_token"] = "sk-synthetic"
        with self.assertRaises(ContractError) as secret:
            ReviewService(leaked)
        self.assertEqual(str(secret.exception), "config-secret-inline")

    def test_same_reviewer_cannot_complete_second_review(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        with self.assertRaises(ContractError) as same:
            service.approve_independent(suggestion, review_draft(), "reviewer-synthetic")
        self.assertEqual(str(same.exception), "second-reviewer-not-independent")
        self.assertEqual(suggestion.state, "APPROVED_ONE")
        self.assertEqual(suggestion.reviewers, {"reviewer-synthetic"})

    def test_model_override_cannot_enter_review(self) -> None:
        service = ReviewService(config())
        overridden = replace(review_draft(), rule_decision="deny", model_decision="allow")
        with self.assertRaises(ContractError) as blocked:
            service.approve(overridden, resource())
        self.assertEqual(str(blocked.exception), "model-cannot-override-rule")
        self.assertEqual(service._suggestions, {})

    def test_policy_sees_withdrawn_consent_before_review(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        service.withdraw_consent(review_draft().consent.consent_id)
        marked = resource()
        marked["consentState"] = "withdrawn"
        with self.assertRaises(ContractError) as blocked:
            service.approve(review_draft(suggestion_id="suggestion-second"), marked)
        self.assertEqual(str(blocked.exception), "consent-not-active")
        self.assertNotIn("suggestion-second", service._suggestions)
        self.assertEqual(suggestion.state, "APPROVED_ONE")

    def test_medication_finding_rejects_model_allow(self) -> None:
        service = ReviewService(config())
        found = {
            "allergy": True,
            "contraindication": False,
            "dose_limit": False,
            "duplicate": False,
            "interaction": False,
        }
        blocked_draft = replace(review_draft(), medication_findings=found, model_decision="allow")
        with self.assertRaises(ContractError) as blocked:
            service.approve(blocked_draft, resource())
        self.assertEqual(str(blocked.exception), "model-cannot-override-rule")
        denied = replace(blocked_draft, rule_decision="deny", model_decision="deny")
        approved = service.approve(denied, resource())
        self.assertEqual(approved.state, "APPROVED_ONE")
        self.assertEqual(approved.reviewer_roles["reviewer-synthetic"], "attending")

    def test_changed_rule_digest_cannot_commit(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        service._rule_digests[review_draft().rule_pack.pack_id] = "a" * 64
        proof = proof_for(approved, "proof-rule", "reviewer-second", "nonce-rule")
        with self.assertRaises(ContractError) as mismatch:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-rule")
        self.assertEqual(str(mismatch.exception), "rule-digest-mismatch")
        self.assertEqual(approved.state, "APPROVED")
        self.assertIsNone(service.writes.get(proof.proof_id))

    def test_reloaded_rule_digest_mismatch_blocks_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule-digest.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            restored = ReviewService(config(), store_path=path)
            restored._rule_digests[review_draft().rule_pack.pack_id] = "b" * 64
            proof = proof_for(approved, "proof-restored-rule", "reviewer-second", "nonce-restored-rule")
            with self.assertRaises(ContractError) as mismatch:
                restored.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-restored-rule")
            self.assertEqual(str(mismatch.exception), "rule-digest-mismatch")
            self.assertEqual(restored._suggestions[approved.suggestion_id].state, "APPROVED")
        self.assertEqual(path.suffix, ".json")

    def test_changed_evidence_digest_cannot_commit(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        evidence_id = review_draft().evidence[0].evidence_id
        service._evidence_digests[evidence_id] = "c" * 64
        proof = proof_for(approved, "proof-evidence", "reviewer-second", "nonce-evidence")
        with self.assertRaises(ContractError) as mismatch:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-evidence")
        self.assertEqual(str(mismatch.exception), "evidence-digest-mismatch")
        self.assertEqual(approved.state, "APPROVED")
        self.assertIsNone(service.writes.get(proof.proof_id))

    def test_reloaded_evidence_digest_mismatch_blocks_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence-digest.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            stored = json.loads(path.read_text(encoding="utf-8"))
            body = json.loads(stored["body"])
            body["drafts"][0]["evidence"][0]["value_digest"] = "a" * 64
            encoded = json.dumps(body, sort_keys=True, separators=(",", ":"))
            stored = {"body": encoded, "digest": hashlib.sha256(encoded.encode("utf-8")).hexdigest()}
            path.write_text(json.dumps(stored, sort_keys=True), encoding="utf-8")
            restored = ReviewService(config(), store_path=path)
            changed = restored._drafts[approved.suggestion_id]
            proof = proof_for(approved, "proof-restored-evidence", "reviewer-second", "nonce-restored-evidence")
            with self.assertRaises(ContractError) as mismatch:
                restored.review_saved(approved.suggestion_id, changed, "2026-09-24T00:30:00Z")
            self.assertEqual(str(mismatch.exception), "evidence-digest-mismatch")
            self.assertEqual(restored._suggestions[approved.suggestion_id].state, "APPROVED")
        self.assertEqual(path.suffix, ".json")

    def test_unlocatable_evidence_cannot_commit(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        changed = replace(draft.evidence[0], source_kind="narrative")
        invalid = replace(draft, evidence=(changed,))
        with self.assertRaises(ContractError) as blocked:
            service.approve(invalid, resource())
        self.assertEqual(str(blocked.exception), "evidence-unlocatable")
        self.assertEqual(service._suggestions, {})

    def test_reloaded_source_kind_stays_locatable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source-kind.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            restored = ReviewService(config(), store_path=path)
            saved = next(iter(restored._drafts.values()))
            self.assertEqual(saved.evidence[0].source_kind, "observation")
        self.assertEqual(path.suffix, ".json")

    def test_independent_review_can_commit_but_grant_cannot(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        self.assertEqual(approved.state, "APPROVED")
        proof = proof_for(approved, "proof-1", "reviewer-second", "nonce-1")
        mismatched = proof_for(approved, "proof-mismatch", "reviewer-second", "nonce-mismatch", "e" * 64)
        with self.assertRaises(ContractError) as mismatch:
            service.commit_ordinary(approved, mismatched, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(mismatch.exception), "approval-mismatch")
        self.assertEqual(approved.state, "APPROVED")
        outsider = proof_for(approved, "proof-outsider", "reviewer-outsider", "nonce-outsider")
        with self.assertRaises(ContractError) as outsider_error:
            service.commit_ordinary(approved, outsider, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(outsider_error.exception), "approval-reviewer-not-recorded")
        self.assertEqual(approved.state, "APPROVED")
        self.assertIsNone(service.writes.get(outsider.proof_id))
        approved.reviewer_roles["reviewer-second"] = ""
        with self.assertRaises(ContractError) as missing_role:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(missing_role.exception), "approval-role-mismatch")
        self.assertEqual(approved.state, "APPROVED")
        approved.reviewer_roles["reviewer-second"] = "attending"
        service.withdraw_consent(review_draft().consent.consent_id)
        with self.assertRaises(ContractError) as consent:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(consent.exception), "consent-not-active")
        self.assertEqual(approved.state, "APPROVED")
        service._consent_states[review_draft().consent.consent_id] = "active"
        late = proof_for(approved, "proof-late", "reviewer-second", "nonce-late")
        with self.assertRaises(ContractError) as expired:
            service.commit_ordinary(approved, late, "2027-01-01T00:00:00Z", "target-late")
        self.assertEqual(str(expired.exception), "consent-outside-window")
        self.assertIsNone(service.writes.get(late.proof_id))
        committed = service.commit_ordinary(
            approved,
            proof,
            "2026-09-24T00:30:00Z",
            "target-4",
        )
        self.assertTrue(committed["committed"])
        self.assertEqual(approved.state, "WRITEBACK_COMMITTED")
        self.assertEqual(service.writes.get(proof.proof_id).state, "committed")
        self.assertTrue(approved.submitted)
        self.assertIn("ordinary-commit", [event.operation for event in service.log.events])
        service.log.verify()
        before = len(service.log.events)
        replayed = service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(replayed["execution_state"], "writeback-committed")
        self.assertEqual(len(service.log.events), before)
        other = proof_for(approved, "proof-2", "reviewer-second", "nonce-2")
        with self.assertRaises(ContractError) as second:
            service.commit_ordinary(approved, other, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(second.exception), "commit-state-invalid")
        grant = EmergencyGrant(
            "grant-1",
            approved.suggestion_id,
            str(approved.version),
            "reviewer-synthetic",
            approved.action,
            "break-glass",
            "d" * 64,
            "nonce-2",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as blocked:
            service.commit_ordinary(approved, grant, "2026-09-24T00:05:00Z", "target-4")  # type: ignore[arg-type]
        self.assertEqual(str(blocked.exception), "emergency-grant-not-approval")

    def test_emergency_authorizer_must_match_actor(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-other",
            draft.suggestion_id,
            "3",
            "clinician-other",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-other",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as mismatch:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(mismatch.exception), "emergency-authorizer-mismatch")
        self.assertEqual(service.log.events, ())

    def test_wrong_emergency_version_appends_nothing(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-bad-version",
            draft.suggestion_id,
            "1",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-bad-version",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        with self.assertRaises(ContractError) as mismatch:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(mismatch.exception), "emergency-version-mismatch")
        self.assertEqual(service.log.events, ())
        self.assertIsNone(service.writes.get(grant.grant_id))

    def test_emergency_record_never_becomes_ordinary_commit(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-service",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-emergency",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        recorded = service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertFalse(recorded["committed"])
        self.assertEqual(recorded["execution_state"], "emergency-pending-confirmation")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "EMERGENCY_PENDING_CONFIRMATION")
        confirmed = service.confirm_emergency(grant, "executed")
        self.assertFalse(confirmed["committed"])
        self.assertEqual(service.emergency(draft.suggestion_id).state, "POST_REVIEW_REQUIRED")
        self.assertIn("emergency-post-review", [event.operation for event in service.log.events])
        with self.assertRaises(ContractError) as same:
            service.reconcile_emergency(grant.authorized_by, grant)
        self.assertEqual(str(same.exception), "post-reviewer-not-independent")
        closed = service.reconcile_emergency("safety-reviewer", grant, {
            "actor_role": "safety-officer",
            "purpose_code": "treatment",
            "occurred_at": "2026-09-24T00:12:00Z",
        })
        archived = [event for event in service.log.events if event.operation == "emergency-archived"][-1]
        self.assertEqual(archived.actor_role, "safety-officer")
        self.assertEqual(archived.occurred_at, "2026-09-24T00:12:00Z")
        self.assertEqual(service._actors["safety-reviewer"]["actor_role"], "safety-officer")
        self.assertFalse(closed["committed"])
        self.assertEqual(service.emergency(draft.suggestion_id).state, "ARCHIVED")
        self.assertFalse(service.emergency(draft.suggestion_id).submitted)
        self.assertIn("emergency-archived", [event.operation for event in service.log.events])
        service.log.verify()
        self.assertIn("emergency-pending", [event.operation for event in service.log.events])
        with self.assertRaises(ContractError) as replay:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(replay.exception), "idempotency-conflict")
        proof = proof_for(service.emergency(draft.suggestion_id), "proof-after-emergency", "reviewer-second", "nonce-ordinary")
        with self.assertRaises(ContractError):
            service.commit_ordinary(service.emergency(draft.suggestion_id), proof, "2026-09-24T00:30:00Z", "target-4")

    def test_unknown_commit_cannot_be_retried(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        proof = proof_for(approved, "proof-unknown", "reviewer-second", "nonce-unknown")
        service.writes.begin(proof.proof_id, proof.content_digest)
        service.mark_commit_unknown(proof.proof_id)
        with self.assertRaises(ContractError) as unknown:
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(unknown.exception), "result-unknown")

    def test_unknown_emergency_receipt_cannot_be_resent(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-unknown",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-unknown-emergency",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        with self.assertRaises(ContractError) as unknown:
            service.confirm_emergency(grant, "unknown")
        self.assertEqual(str(unknown.exception), "result-unknown")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "EMERGENCY_UNKNOWN")
        self.assertIn("emergency-unknown", [event.operation for event in service.log.events])
        service.log.verify()
        with self.assertRaises(ContractError) as resent:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:06:00Z")
        self.assertEqual(str(resent.exception), "result-unknown")

    def test_correction_keeps_original_emergency_fact(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-correction",
            draft.suggestion_id,
            "3",
            "reviewer-synthetic",
            draft.action,
            "break-glass",
            draft.content_digest,
            "nonce-correction",
            "2026-09-24T00:00:00Z",
            "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        service.confirm_emergency(grant, "executed")
        before = tuple(service.emergency(draft.suggestion_id).history)
        with self.assertRaises(ContractError) as same:
            service.correct_emergency(grant.authorized_by, grant, "dose-mismatch")
        self.assertEqual(str(same.exception), "correction-reviewer-not-independent")
        corrected = service.correct_emergency("safety-reviewer", grant, "dose-mismatch", {
            "actor_role": "quality-reviewer",
            "purpose_code": "treatment",
            "occurred_at": "2026-09-24T00:16:00Z",
        })
        changed = [event for event in service.log.events if event.operation == "emergency-corrected"][-1]
        self.assertEqual(changed.actor_role, "quality-reviewer")
        self.assertEqual(changed.occurred_at, "2026-09-24T00:16:00Z")
        self.assertFalse(corrected["committed"])
        self.assertEqual(corrected["execution_state"], "corrected-archived")
        self.assertIn("emergency-corrected", [event.operation for event in service.log.events])
        service.log.verify()
        self.assertEqual(service.emergency(draft.suggestion_id).state, "ARCHIVED")
        self.assertEqual(tuple(service.emergency(draft.suggestion_id).history[:len(before)]), before)
        self.assertIn(("EMERGENCY_RECORDED", "POST_REVIEW_REQUIRED", grant.authorized_by), before)

    def test_second_emergency_does_not_confirm_the_first(self) -> None:
        service = ReviewService(config())
        first = review_draft(suggestion_id="suggestion-one")
        second = review_draft(suggestion_id="suggestion-two")
        first_grant = grant_for(first, "grant-one", "nonce-one")
        second_grant = grant_for(second, "grant-two", "nonce-two")
        service.record_emergency(first, resource(), first_grant, "2026-09-24T00:05:00Z")
        service.record_emergency(second, resource(), second_grant, "2026-09-24T00:05:00Z")
        service.confirm_emergency(second_grant, "executed")
        self.assertEqual(service.emergency(first.suggestion_id).state, "EMERGENCY_PENDING_CONFIRMATION")
        self.assertEqual(service.emergency(second.suggestion_id).state, "POST_REVIEW_REQUIRED")

    def test_other_grant_cannot_confirm_pending_emergency(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = EmergencyGrant(
            "grant-bound", draft.suggestion_id, "3", "reviewer-synthetic", draft.action,
            "break-glass", draft.content_digest, "nonce-bound",
            "2026-09-24T00:00:00Z", "2026-09-24T00:10:00Z",
        )
        other = EmergencyGrant(
            "grant-other", draft.suggestion_id, "3", "reviewer-synthetic", draft.action,
            "break-glass", draft.content_digest, "nonce-other",
            "2026-09-24T00:00:00Z", "2026-09-24T00:10:00Z",
        )
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        with self.assertRaises(ContractError) as mismatch:
            service.confirm_emergency(other, "executed")
        self.assertEqual(str(mismatch.exception), "emergency-grant-mismatch")
        self.assertEqual(service.emergency(draft.suggestion_id).state, "EMERGENCY_PENDING_CONFIRMATION")

    def test_untracked_or_changed_draft_cannot_advance(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        forged = Suggestion(
            suggestion.suggestion_id,
            suggestion.patient_ref,
            suggestion.action,
            state="APPROVED",
            content_digest=suggestion.content_digest,
        )
        proof = proof_for(forged, "proof-forged", "reviewer-second", "nonce-forged")
        with self.assertRaises(ContractError) as blocked:
            service.commit_ordinary(forged, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(str(blocked.exception), "commit-state-invalid")
        self.assertEqual(suggestion.state, "APPROVED_ONE")
        changed = review_draft()
        changed_digest = SuggestionDraft(**{**changed.__dict__, "content_digest": "e" * 64})
        with self.assertRaises(ContractError) as mismatch:
            service.approve_independent(suggestion, changed_digest, "reviewer-second")
        self.assertEqual(str(mismatch.exception), "review-digest-mismatch")
        service.withdraw_consent(review_draft().consent.consent_id)
        with self.assertRaises(ContractError) as withdrawn:
            service.approve_independent(suggestion, review_draft(), "reviewer-second")
        self.assertEqual(str(withdrawn.exception), "consent-not-active")
        service._consent_states[review_draft().consent.consent_id] = "active"
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second", {
            "actor_role": "consultant",
            "tenant_id": "tenant-synthetic",
            "campus_id": "campus-synthetic",
            "purpose_code": "treatment",
            "why_code": "second-review",
            "occurred_at": "2026-09-24T00:20:00Z",
        })
        second = [event for event in service.log.events if event.operation == "approve-second"][-1]
        self.assertEqual(second.actor_role, "consultant")
        self.assertEqual(second.occurred_at, "2026-09-24T00:20:00Z")
        proof = proof_for(approved, "proof-role", "reviewer-second", "nonce-role")
        committed = service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-role")
        commit = [event for event in service.log.events if event.operation == "ordinary-commit"][-1]
        self.assertEqual(commit.actor_id, "reviewer-second")
        self.assertEqual(commit.actor_role, "consultant")
        self.assertTrue(committed["committed"])
        self.assertEqual(approved.version, service._suggestions[approved.suggestion_id].version)
        self.assertEqual(commit.purpose_code, "treatment")
        self.assertEqual(approved.reviewer_roles["reviewer-second"], "consultant")

    def test_reloaded_actor_role_is_used_for_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actor-store.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second", {
                "actor_role": "consultant",
                "tenant_id": "tenant-synthetic",
                "campus_id": "campus-synthetic",
                "purpose_code": "treatment",
                "why_code": "second-review",
                "occurred_at": "2026-09-24T00:20:00Z",
            })
            restored = ReviewService(config(), store_path=path)
            proof = proof_for(approved, "proof-restored-role", "reviewer-second", "nonce-restored-role")
            restored.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-role")
            commit = [event for event in restored.log.events if event.operation == "ordinary-commit"][-1]
            self.assertEqual(commit.actor_role, "consultant")
            self.assertEqual(restored._suggestions[approved.suggestion_id].reviewer_roles["reviewer-second"], "consultant")
        self.assertEqual(restored._actors["reviewer-second"]["actor_role"], "consultant")
        self.assertEqual(path.suffix, ".json")

    def test_reloaded_rule_decision_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule-decision.json"
            denied = replace(review_draft(), rule_decision="deny", model_decision="deny")
            service = ReviewService(config(), store_path=path)
            service.approve(denied, resource())
            restored = ReviewService(config(), store_path=path)
            saved = next(iter(restored._drafts.values()))
            self.assertEqual((saved.rule_decision, saved.model_decision), ("deny", "deny"))
            changed = replace(saved, model_decision="allow")
            with self.assertRaises(ContractError) as mismatch:
                restored.review_saved(saved.suggestion_id, changed, saved.at_time)
            self.assertEqual(str(mismatch.exception), "rule-decision-mismatch")
        self.assertTrue(path.name.endswith(".json"))

    def test_reloaded_medication_finding_stays_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "medication-findings.json"
            found = {
                "allergy": True,
                "contraindication": False,
                "dose_limit": False,
                "duplicate": False,
                "interaction": False,
            }
            denied = replace(review_draft(), medication_findings=found, rule_decision="deny", model_decision="deny")
            ReviewService(config(), store_path=path).approve(denied, resource())
            restored = ReviewService(config(), store_path=path)
            saved = next(iter(restored._drafts.values()))
            self.assertTrue(saved.medication_findings["allergy"])
            changed = replace(saved, medication_findings={**saved.medication_findings, "allergy": False})
            with self.assertRaises(ContractError) as mismatch:
                restored.review_saved(saved.suggestion_id, changed, saved.at_time)
            self.assertEqual(str(mismatch.exception), "medication-findings-mismatch")
        self.assertEqual(path.name, "medication-findings.json")

    def test_derived_medication_facts_block_model_allow(self) -> None:
        service = ReviewService(config())
        facts = {
            "active": (),
            "allergens": ("med-b",),
            "blocked_conditions": (),
            "dose": 1,
            "dose_limit": 2,
            "ordered": ("med-b",),
            "pairs": (),
        }
        blocked_draft = replace(review_draft(), medication_facts=facts, model_decision="allow")
        with self.assertRaises(ContractError) as blocked:
            service.approve(blocked_draft, resource())
        self.assertEqual(str(blocked.exception), "model-cannot-override-rule")
        self.assertFalse(service._suggestions)
        self.assertIsNone(service.writes.get("proof-derived"))

    def test_reloaded_medication_facts_cannot_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "medication-facts.json"
            facts = {
                "active": (),
                "allergens": ("med-b",),
                "blocked_conditions": (),
                "dose": 1,
                "dose_limit": 2,
                "ordered": ("med-b",),
                "pairs": (),
            }
            denied = replace(
                review_draft(),
                medication_facts=facts,
                rule_decision="deny",
                model_decision="deny",
            )
            ReviewService(config(), store_path=path).approve(denied, resource())
            restored = ReviewService(config(), store_path=path)
            saved = next(iter(restored._drafts.values()))
            self.assertEqual(saved.medication_facts["ordered"], ("med-b",))
            changed = replace(saved, medication_facts={**facts, "ordered": ()})
            with self.assertRaises(ContractError) as mismatch:
                restored.review_saved(saved.suggestion_id, changed, saved.at_time)
            self.assertEqual(str(mismatch.exception), "medication-facts-mismatch")
        self.assertEqual(path.name, "medication-facts.json")


if __name__ == "__main__":
    unittest.main()
