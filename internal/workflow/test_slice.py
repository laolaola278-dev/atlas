"""End-to-end tests for the P1 FHIR vertical slice.

These tests execute the whole chain instead of only declaring it:

    valid-patient-bundle.json -> FHIR Gate -> Validator -> AuditEvent
        -> Workflow -> HITL Review -> HITL Commit

Every value is synthetic. The assertions cover both the happy path and the
fail-closed behaviour of each stage.
"""
import tempfile
import unittest
from pathlib import Path

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.audit.file import AuditFile  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.fhir_gate import validate_resource  # noqa: E402
from internal.contract.write_intent import ApprovalProof  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.workflow.slice import (  # noqa: E402
    ATLAS_ENVELOPE_FIELDS,
    STAGES,
    SliceWorkflow,
    canonical_digest,
    load_fixture,
    official_record,
    pure_resource,
    run_vertical_slice,
    stage_audit,
    stage_bundle,
    stage_gate,
    stage_validator,
)

AUDIT_EVENT_ID = "fhir-validate-observation-synthetic-1"
RESOURCE_ID = "observation-synthetic"
PATIENT_REF = "patient-ref-synthetic"


def config() -> dict[str, str]:
    """Return the same synthetic runtime scope the review service tests use."""
    return {
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "policy_version": "1.0.0",
        "audit_stream": "review-service",
        "secret_ref": "secret://atlas/signing-key",
    }


def observation_digest() -> str:
    """Return the canonical digest of the synthetic observation fixture."""
    return canonical_digest(pure_resource(load_fixture("observation")))


class FhirVerticalSliceTests(unittest.TestCase):
    def _opened(self, service: ReviewService) -> tuple[SliceWorkflow, str]:
        """Run stages one to four and return the workflow plus its audit id."""
        digest = observation_digest()
        resource = load_fixture("observation")
        stage_bundle(load_fixture("valid-patient-bundle"))
        stage_gate(resource)
        outcome_id = stage_validator(resource, official_record(digest, "hapi-outcome-synthetic"))[1]
        event = stage_audit(
            service.log,
            actor=review_draft().actor,
            resource=resource,
            digest=digest,
            outcome_id=outcome_id,
        )
        return SliceWorkflow(service), event.event_id

    def test_slice_runs_every_stage_and_propagates_one_audit_event_id(self) -> None:
        service = ReviewService(config())
        trace = run_vertical_slice(
            service,
            review_draft(),
            validator_record=official_record(observation_digest(), "hapi-outcome-synthetic"),
        )
        self.assertEqual([stage["stage"] for stage in trace["stages"]], list(STAGES))
        self.assertEqual(set(trace["audit_event_ids"].values()), {AUDIT_EVENT_ID})
        self.assertEqual(len(trace["audit_event_ids"]), 4)
        self.assertEqual(trace["task_state"], "COMMITTED")
        self.assertTrue(trace["commit_response"]["committed"])
        self.assertEqual(trace["commit_response"]["target_version"], "target-slice")
        self.assertTrue(trace["audit_chain_verified"])
        self.assertEqual(
            [event.operation for event in service.log.events],
            ["fhir-validate", "queue-review", "approve-one", "approve-second", "ordinary-commit"],
        )
        service.log.verify()
        response = trace["fhir_resource_response"]
        self.assertEqual(response["resource"]["logical_id"], RESOURCE_ID)
        self.assertTrue(response["validation"]["valid"])
        self.assertEqual(response["validation"]["resource_digest"], observation_digest())
        projected = trace["fhir_audit_event"]
        self.assertEqual(projected["resourceType"], "AuditEvent")
        self.assertEqual(projected["id"], AUDIT_EVENT_ID)
        self.assertEqual(projected["entityDigest"], observation_digest())
        self.assertEqual(projected["action"], "fhir-validate")

    def test_slice_audit_chain_survives_a_durable_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit_path = Path(directory) / "slice-audit.jsonl"
            store_path = Path(directory) / "slice-store.json"
            service = ReviewService(config(), audit_path, store_path)
            trace = run_vertical_slice(
                service,
                review_draft(),
                validator_record=official_record(observation_digest(), "hapi-outcome-durable"),
            )
            reloaded = AuditFile(audit_path, "review-service")
            self.assertEqual(len(reloaded.log.events), len(service.log.events))
            self.assertEqual(reloaded.log.events[0].event_id, AUDIT_EVENT_ID)
            reloaded.log.verify()
            restored = ReviewService(config(), audit_path, store_path)
            suggestion_id = trace["review_receipt"]["suggestion_id"]
            self.assertEqual(restored._suggestions[suggestion_id].state, "WRITEBACK_COMMITTED")
            self.assertEqual(restored.log.events[0].payload_digest, observation_digest())
        self.assertTrue(audit_path.name.endswith(".jsonl"))

    def test_workflow_refuses_an_unverifiable_audit_event_id(self) -> None:
        service = ReviewService(config())
        workflow, audit_event_id = self._opened(service)
        digest = observation_digest()
        with self.assertRaises(ContractError) as blank:
            workflow.open_task("", resource_id=RESOURCE_ID, patient_ref=PATIENT_REF, resource_digest=digest)
        self.assertEqual(str(blank.exception), "workflow-audit-event-missing")
        with self.assertRaises(ContractError) as unknown:
            workflow.open_task(
                "fhir-validate-observation-synthetic-99",
                resource_id=RESOURCE_ID,
                patient_ref=PATIENT_REF,
                resource_digest=digest,
            )
        self.assertEqual(str(unknown.exception), "workflow-audit-event-unknown")
        with self.assertRaises(ContractError) as stale:
            workflow.open_task(
                audit_event_id,
                resource_id=RESOURCE_ID,
                patient_ref=PATIENT_REF,
                resource_digest="0" * 64,
            )
        self.assertEqual(str(stale.exception), "workflow-audit-event-mismatch")
        with self.assertRaises(ContractError) as incomplete:
            workflow.open_task(audit_event_id, resource_id=RESOURCE_ID, patient_ref="", resource_digest=digest)
        self.assertEqual(str(incomplete.exception), "workflow-slice-stage-missing")
        with self.assertRaises(ContractError) as absent:
            workflow.task(f"task-{audit_event_id}")
        self.assertEqual(str(absent.exception), "workflow-task-unknown")
        self.assertEqual([event.operation for event in service.log.events], ["fhir-validate"])

    def test_commit_before_review_is_rejected(self) -> None:
        service = ReviewService(config())
        workflow, audit_event_id = self._opened(service)
        task = workflow.open_task(
            audit_event_id,
            resource_id=RESOURCE_ID,
            patient_ref=PATIENT_REF,
            resource_digest=observation_digest(),
        )
        proof = ApprovalProof(
            "proof-early",
            "suggestion-synthetic",
            "3",
            "reviewer-second",
            "review-order",
            "d" * 64,
            "nonce-early",
            "2026-09-24T00:00:00Z",
            "2026-09-24T01:00:00Z",
        )
        with self.assertRaises(ContractError) as early:
            workflow.commit(task, proof, "2026-09-24T00:30:00Z", "target-early")
        self.assertEqual(str(early.exception), "workflow-task-state-invalid")
        self.assertEqual(task.state, "OPEN")
        self.assertEqual([event.operation for event in service.log.events], ["fhir-validate"])

    def test_bundle_stage_accepts_only_the_transaction_fixture(self) -> None:
        bundle = load_fixture("valid-patient-bundle")
        self.assertEqual(
            stage_bundle(bundle),
            ("Observation/observation-synthetic", "ServiceRequest/service-request-synthetic"),
        )
        with self.assertRaises(ContractError) as document:
            stage_bundle({**bundle, "type": "document"})
        self.assertEqual(str(document.exception), "bundle-type-invalid")
        with self.assertRaises(ContractError) as empty:
            stage_bundle({**bundle, "entry": []})
        self.assertEqual(str(empty.exception), "bundle-empty")

    def test_validator_stage_fails_closed_before_any_audit_event(self) -> None:
        service = ReviewService(config())
        resource = load_fixture("observation")
        digest = observation_digest()
        expected = load_fixture("validator-missing")
        with self.assertRaises(ContractError) as absent:
            stage_validator(resource, None)
        self.assertEqual(str(absent.exception), str(expected["expectedError"]))
        with self.assertRaises(ContractError) as unofficial:
            stage_validator(resource, {**official_record(digest, "local-1"), "engine": "local"})
        self.assertEqual(str(unofficial.exception), "validator-not-official")
        with self.assertRaises(ContractError) as stale:
            stage_validator(resource, official_record("0" * 64, "hapi-outcome-synthetic"))
        self.assertEqual(str(stale.exception), "validator-digest-mismatch")
        with self.assertRaises(ContractError) as failed:
            stage_validator(resource, official_record(digest, "hapi-outcome-synthetic", outcome="fail"))
        self.assertEqual(str(failed.exception), "validator-outcome-failed")
        self.assertEqual(service.log.events, ())

    def test_gate_stage_rejects_each_invalid_regression_fixture(self) -> None:
        expectations = {
            "invalid-profile": "profile-not-declared",
            "invalid-reference": "patient-reference-missing",
            "terminology-expired": "terminology-release-expired",
        }
        for name, expected in sorted(expectations.items()):
            codes = [issue.code for issue in validate_resource(load_fixture(name))]
            self.assertIn(expected, codes, name)
            with self.assertRaises(ContractError, msg=name):
                stage_gate(load_fixture(name))

    def test_slice_stops_at_the_validator_without_an_official_record(self) -> None:
        service = ReviewService(config())
        with self.assertRaises(ContractError) as blocked:
            run_vertical_slice(service, review_draft(), validator_record=None)
        self.assertEqual(str(blocked.exception), "validator-result-unknown")
        self.assertEqual(service.log.events, ())
        self.assertEqual(service._suggestions, {})

    def test_slice_stops_at_the_gate_for_a_rejected_resource(self) -> None:
        service = ReviewService(config())
        bundle = load_fixture("valid-patient-bundle")
        entries = stage_bundle(bundle)
        self.assertIn("Observation/observation-synthetic", entries)
        broken = {**load_fixture("observation"), "purposeCode": ""}
        with self.assertRaises(ContractError) as blocked:
            stage_gate(broken)
        self.assertEqual(str(blocked.exception), "purpose-missing")
        self.assertEqual(service.log.events, ())


class EnvelopeSeparationTests(unittest.TestCase):
    """The gate consumes the envelope, the validator consumes the projection."""

    def test_pure_resource_strips_every_atlas_provenance_field(self) -> None:
        envelope = load_fixture("observation")
        payload = pure_resource(envelope)
        self.assertEqual(sorted(ATLAS_ENVELOPE_FIELDS.intersection(payload)), [])
        self.assertLess(len(payload), len(envelope))
        self.assertEqual(payload["resourceType"], "Observation")
        self.assertEqual(payload["id"], RESOURCE_ID)
        self.assertEqual(payload["status"], "final")
        self.assertIn("code", payload)
        self.assertEqual(payload["subject"], {"reference": f"Patient/{PATIENT_REF}"})
        # stripping must not mutate the envelope the gate still needs
        self.assertIs(envelope["synthetic"], True)
        self.assertEqual(envelope["purposeCode"], "treatment")

    def test_gate_still_consumes_the_envelope_not_the_projection(self) -> None:
        envelope = load_fixture("observation")
        self.assertEqual(stage_gate(envelope), ())
        with self.assertRaises(ContractError) as stripped:
            stage_gate(pure_resource(envelope))
        self.assertEqual(str(stripped.exception), "purpose-missing")

    def test_projection_without_provenance_fails_closed(self) -> None:
        with self.assertRaises(ContractError) as raised:
            pure_resource({"resourceType": "Observation", "id": "x", "status": "final"})
        self.assertEqual(str(raised.exception), "validator-envelope-invalid")

    def test_projection_without_identity_fails_closed(self) -> None:
        with self.assertRaises(ContractError) as raised:
            pure_resource({"resourceType": "Observation", "synthetic": True})
        self.assertEqual(str(raised.exception), "validator-envelope-invalid")

    def test_claiming_the_official_engine_without_engine_provenance_fails_closed(self) -> None:
        service = ReviewService(config())
        digest = observation_digest()
        with self.assertRaises(ContractError) as raised:
            run_vertical_slice(
                service,
                review_draft(),
                validator_record=official_record(digest, "hapi-outcome-forged"),
                validator_engine="official-engine",
            )
        self.assertEqual(str(raised.exception), "validator-not-official")

    def test_digest_binds_the_projection_not_the_envelope(self) -> None:
        envelope = load_fixture("observation")
        projection = pure_resource(envelope)
        record = official_record(canonical_digest(projection), "hapi-outcome-envelope")
        digest, outcome_id = stage_validator(envelope, record)
        self.assertEqual(digest, canonical_digest(projection))
        self.assertEqual(outcome_id, "hapi-outcome-envelope")
        self.assertNotEqual(digest, canonical_digest(envelope))
        with self.assertRaises(ContractError) as mismatched:
            stage_validator(envelope, official_record(canonical_digest(envelope), "hapi-outcome-envelope"))
        self.assertEqual(str(mismatched.exception), "validator-digest-mismatch")


if __name__ == "__main__":
    unittest.main()
