"""Review gates for catalog profiles and terminology releases."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from internal.hitl.fixtures import install_hitl_path, review_draft
from internal.hitl.test_service import config, grant_for, proof_for, resource

install_hitl_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.write_intent import ApprovalProof  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402


def unrelated_resource(resource_id: str) -> dict[str, object]:
    """Return a resource that does not reuse the recorded terminology or profile."""
    payload = resource()
    payload["resourceType"] = "ServiceRequest"
    payload["priority"] = "routine"
    payload["id"] = resource_id
    payload["meta"] = {
        "versionId": "1",
        "profile": ["http://example.invalid/atlas/StructureDefinition/service-request"],
    }
    payload.pop("codeSystem")
    payload.pop("reviewedAt")
    return payload


class ReviewCatalogTests(unittest.TestCase):
    def test_expired_code_system_blocks_review(self) -> None:
        service = ReviewService(config())
        expired = resource()
        expired["reviewedAt"] = "2027-01-01"
        with self.assertRaises(ContractError) as blocked:
            service.approve(review_draft(), expired)
        self.assertEqual(str(blocked.exception), "terminology-release-expired")
        self.assertEqual(service.log.events, ())

    def test_active_code_system_still_reaches_review(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        self.assertEqual(suggestion.state, "APPROVED_ONE")

    def test_direct_identifier_blocks_review(self) -> None:
        service = ReviewService(config())
        named = resource()
        named["name"] = "synthetic-label"
        with self.assertRaises(ContractError) as blocked:
            service.approve(review_draft(), named)
        self.assertEqual(str(blocked.exception), "direct-identifier-forbidden")
        self.assertEqual(service.log.events, ())

    def test_nested_identifier_blocks_review(self) -> None:
        service = ReviewService(config())
        nested = resource()
        nested["subject"] = {"reference": "Patient/patient-ref-synthetic", "identifier": "synthetic-token"}
        with self.assertRaises(ContractError) as blocked:
            service.approve(review_draft(), nested)
        self.assertEqual(str(blocked.exception), "direct-identifier-forbidden")
        self.assertEqual(service._suggestions, {})

    def test_ordinary_commit_advances_transaction_watermark(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        proof = proof_for(approved, "proof-watermark", "reviewer-second", "nonce-watermark")
        service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        self.assertEqual(service.transactions.watermark(), 1)

    def test_unknown_after_commit_keeps_watermark(self) -> None:
        service = ReviewService(config())
        suggestion = service.approve(review_draft(), resource())
        approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
        proof = proof_for(approved, "proof-unknown", "reviewer-second", "nonce-unknown")
        service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
        service.mark_commit_unknown(proof.proof_id)
        self.assertEqual(service.transactions.watermark(), 1)
        self.assertEqual(service.writes.get(proof.proof_id).state, "unknown")

    def test_unknown_emergency_receipt_does_not_advance_watermark(self) -> None:
        service = ReviewService(config())
        draft = review_draft()
        grant = grant_for(draft, "grant-watermark", "nonce-watermark")
        service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        with self.assertRaises(ContractError):
            service.confirm_emergency(grant, "unknown")
        self.assertEqual(service.transactions.watermark(), 0)

    def test_reloaded_watermark_stays_committed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review-store.json"
            service = ReviewService(config(), store_path=path)
            self.assertEqual(service.transactions.watermark(), 0)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            proof = proof_for(approved, "proof-reload", "reviewer-second", "nonce-reload")
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-4")
            restored = ReviewService(config(), store_path=path)
            self.assertEqual(restored.transactions.watermark(), 1)
            replayed = restored.transactions.begin(
                proof.proof_id,
                approved.content_digest,
                proof.reviewer_id,
                proof.why_code,
            )
            self.assertEqual(replayed.state, "committed")
            self.assertEqual(restored.transactions.watermark(), 1)

    def test_other_actor_for_same_review_scope_is_rejected(self) -> None:
        service = ReviewService(config())
        service.approve(review_draft(), resource())
        other = review_draft("active", "suggestion-other")
        other.actor["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            service.approve(other, resource())
        self.assertEqual(str(blocked.exception), "policy-responsibility-mismatch")
        self.assertEqual(len(service._suggestions), 1)

    def test_reloaded_policy_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "policy-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-other")
            other.actor["actor_id"] = "other-reviewer"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, resource())
            self.assertEqual(str(blocked.exception), "policy-responsibility-mismatch")

    def test_reloaded_evidence_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-other")
            other.actor["actor_id"] = "other-reviewer"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, unrelated_resource("request-evidence"))
            self.assertEqual(str(blocked.exception), "evidence-responsibility-mismatch")

    def test_reloaded_rule_pack_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rule-actor-store.json"
            service = ReviewService(config(), store_path=path)
            current = review_draft()
            current = replace(current, evidence=current.evidence[:1])
            service.approve(current, resource())
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-other")
            other_evidence = (
                replace(
                    other.evidence[0],
                    evidence_id="other-lab",
                    source_id="source-other",
                    locator="Observation/other-lab",
                ),
            )
            other = replace(other, evidence=other_evidence)
            other.actor["actor_id"] = "other-reviewer"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, unrelated_resource("request-rule"))
            self.assertEqual(str(blocked.exception), "rule-responsibility-mismatch")

    def test_reloaded_consent_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "consent-actor-store.json"
            service = ReviewService(config(), store_path=path)
            current = review_draft()
            current = replace(current, evidence=current.evidence[:1])
            service.approve(current, resource())
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-other")
            other_evidence = (
                replace(
                    other.evidence[0],
                    evidence_id="consent-lab",
                    source_id="source-consent",
                    locator="Observation/consent-lab",
                ),
            )
            other_pack = replace(other.rule_pack, pack_id="pack-consent")
            other = replace(other, evidence=other_evidence, rule_pack=other_pack)
            other.actor["actor_id"] = "other-reviewer"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, unrelated_resource("request-consent"))
            self.assertEqual(str(blocked.exception), "consent-responsibility-mismatch")

    def test_reloaded_medication_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "medication-actor-store.json"
            findings = {
                "allergy": False,
                "contraindication": False,
                "dose_limit": False,
                "duplicate": False,
                "interaction": False,
            }
            service = ReviewService(config(), store_path=path)
            current = replace(review_draft(), medication_findings=findings)
            service.approve(current, resource())
            restored = ReviewService(config(), store_path=path)
            prior = current.evidence[0]
            other_evidence = (prior.__class__(
                "medication-lab", "source-medication", "Observation/medication-lab", prior.source_version, prior.value_digest,
            ),)
            other = replace(
                review_draft("active", "suggestion-medication"),
                evidence=other_evidence,
                rule_pack=replace(current.rule_pack, pack_id="pack-medication"),
                consent=replace(current.consent, consent_id="consent-medication"),
                medication_findings=findings,
            )
            other.actor["actor_id"] = "other-reviewer"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, unrelated_resource("request-medication"))
            self.assertEqual(str(blocked.exception), "medication-responsibility-mismatch")

    def test_reloaded_resource_rejects_changed_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fhir-actor-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-fhir")
            other.actor["why_code"] = "terminology-rereview"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, resource())
            self.assertEqual(str(blocked.exception), "terminology-responsibility-mismatch")

    def test_reloaded_profile_rejects_changed_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile-actor-store.json"
            bare = resource()
            removed = ("codeSystem", "reviewedAt")
            while removed:
                field = removed[0]
                removed = removed[1:]
                del bare[field]
            service = ReviewService(config(), store_path=path)
            self.assertNotIn("codeSystem", bare)
            service.approve(review_draft(), bare)
            restored = ReviewService(config(), store_path=path)
            other = review_draft("active", "suggestion-profile")
            other.actor["why_code"] = "profile-rereview"
            with self.assertRaises(ContractError) as blocked:
                restored.approve(other, bare)
            self.assertEqual(str(blocked.exception), "profile-responsibility-mismatch")

    def test_reloaded_write_rejects_other_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "write-actor-store.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            proof = proof_for(approved, "proof-write", "reviewer-second", "nonce-write")
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-write")
            restored = ReviewService(config(), store_path=path)
            replayed = restored.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-write")
            self.assertEqual(replayed["execution_state"], "writeback-committed")
            other = ApprovalProof(
                proof.proof_id,
                proof.suggestion_id,
                proof.suggestion_version,
                "reviewer-other",
                proof.target_action,
                proof.content_digest,
                "nonce-other-write",
                proof.issued_at,
                proof.expires_at,
            )
            with self.assertRaises(ContractError) as blocked:
                restored.commit_ordinary(approved, other, "2026-09-24T00:30:00Z", "target-write")
            self.assertEqual(str(blocked.exception), "write-responsibility-mismatch")

    def test_reloaded_projection_rejects_other_reviewer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "projection-store.json"
            service = ReviewService(config(), store_path=path)
            first = service.approve(review_draft(), resource())
            other_draft = review_draft("active", "suggestion-projected")
            other_resource = unrelated_resource("request-projected")
            second = service.approve(other_draft, other_resource)
            first = service.approve_independent(first, review_draft(), "reviewer-second")
            second = service.approve_independent(second, other_draft, "reviewer-third")
            proof = proof_for(first, "proof-project", "reviewer-second", "nonce-project")
            committed_at = "2026-09-24T00:30:00Z"
            service.commit_ordinary(first, proof, committed_at, "target-project")
            restored = ReviewService(config(), store_path=path)
            other_proof = proof_for(second, "proof-project-other", "reviewer-third", "nonce-project-other")
            with self.assertRaises(ContractError) as blocked:
                later = "2026-09-24T00:31:00Z"
                restored.commit_ordinary(second, other_proof, later, "target-project-other")
            self.assertEqual(str(blocked.exception), "privacy-responsibility-mismatch")

    def test_reloaded_query_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "query-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            payload = {
                "actor_id": "reviewer-synthetic",
                "campus_id": "campus-synthetic",
                "page_size": 10,
                "purpose_code": "treatment",
                "requested_fields": ["suggestion_id", "state"],
                "resource_type": "Suggestion",
                "tenant_id": "tenant-synthetic",
                "why_code": "treatment-review",
            }
            rows = service.read_saved("query", payload)
            self.assertEqual(rows[0]["state"], "APPROVED_ONE")
            restored = ReviewService(config(), store_path=path)
            replayed = restored.read_saved("query", payload)
            self.assertEqual(replayed[0]["suggestion_id"], rows[0]["suggestion_id"])
            other = dict(payload)
            other["actor_id"] = "reviewer-other"
            with self.assertRaises(ContractError) as blocked:
                restored.read_saved("query", other)
            self.assertEqual(str(blocked.exception), "query-responsibility-mismatch")

    def test_reloaded_transfer_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transfer-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            payload = {
                "why_code": "treatment-review",
                "purpose_code": "treatment",
                "fields": ["status"],
                "direction": "export",
                "consent_state": "active",
                "actor_id": "reviewer-synthetic",
            }
            rows = service.read_saved("export", payload)
            self.assertEqual(rows[0]["status"], "APPROVED_ONE")
            restored = ReviewService(config(), store_path=path)
            replayed = restored.read_saved("export", payload)
            self.assertEqual(replayed, rows)
            other = dict(payload)
            other["actor_id"] = "reviewer-other"
            with self.assertRaises(ContractError) as blocked:
                restored.read_saved("export", other)
            self.assertEqual(str(blocked.exception), "transfer-responsibility-mismatch")

    def test_reloaded_cache_rejects_other_purpose_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache-store.json"
            service = ReviewService(config(), store_path=path)
            service.approve(review_draft(), resource())
            payload = {
                "actor_id": "reviewer-synthetic",
                "campus_id": "campus-synthetic",
                "page_size": 10,
                "purpose_code": "treatment",
                "requested_fields": ["state"],
                "resource_type": "Suggestion",
                "tenant_id": "tenant-synthetic",
                "why_code": "treatment-review",
            }
            rows = service.read_saved("query", payload)
            self.assertEqual(rows[0]["state"], "APPROVED_ONE")
            restored = ReviewService(config(), store_path=path)
            other = dict(payload)
            other["purpose_code"] = "quality-review"
            other["actor_id"] = "reviewer-other"
            with self.assertRaises(ContractError) as blocked:
                restored.read_saved("query", other)
            self.assertEqual(str(blocked.exception), "cache-responsibility-mismatch")

    def test_reloaded_health_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "health-store.json"
            first = dict(config())
            first["actor_id"] = "reviewer-synthetic"
            ReviewService(first, store_path=path)
            other = dict(config())
            other["actor_id"] = "reviewer-other"
            with self.assertRaises(ContractError) as blocked:
                ReviewService(other, store_path=path)
            self.assertEqual(str(blocked.exception), "health-responsibility-mismatch")

    def test_reloaded_stream_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stream-store.json"
            service = ReviewService(config(), store_path=path)
            payload = {
                "actor_id": "reviewer-synthetic",
                "event_id": "event-synthetic",
                "sequence": 1,
                "why_code": "treatment-review",
            }
            rows = service.read_saved("stream", payload)
            self.assertEqual(rows[0]["late"], "false")
            restored = ReviewService(config(), store_path=path)
            other = dict(payload)
            other["actor_id"] = "reviewer-other"
            other["event_id"] = "event-other"
            with self.assertRaises(ContractError) as blocked:
                restored.read_saved("stream", other)
            self.assertEqual(str(blocked.exception), "stream-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
