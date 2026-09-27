"""Structural tests for the minimal FHIR gate."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.fhir_gate import FhirLedger, require_valid, validate_resource  # noqa: E402


def resource() -> dict[str, object]:
    return {
        "resourceType": "Observation",
        "id": "observation-synthetic",
        "meta": {
            "versionId": "1",
            "profile": ["http://example.invalid/atlas/observation"],
        },
        "purposeCode": "treatment",
        "subject": {"reference": "Patient/patient-ref-synthetic"},
    }


class FhirGateTests(unittest.TestCase):
    def test_complete_observation_has_no_issues(self) -> None:
        self.assertEqual(validate_resource(resource()), ())
        require_valid(resource())

    def test_unknown_type_missing_profile_and_purpose_are_rejected(self) -> None:
        unknown = resource()
        unknown["resourceType"] = "Binary"
        with self.assertRaises(ContractError) as rejected:
            require_valid(unknown)
        self.assertEqual(str(rejected.exception), "resource-type-rejected")
        missing_profile = resource()
        missing_profile["meta"] = {"versionId": "1", "profile": []}
        issues = validate_resource(missing_profile)
        self.assertIn("profile-missing", [issue.code for issue in issues])
        missing_purpose = resource()
        missing_purpose["purposeCode"] = ""
        with self.assertRaises(ContractError) as purpose:
            require_valid(missing_purpose)
        self.assertEqual(str(purpose.exception), "purpose-missing")

    def test_clinical_resource_requires_patient_reference(self) -> None:
        missing = resource()
        missing.pop("subject")
        with self.assertRaises(ContractError) as rejected:
            require_valid(missing)
        self.assertEqual(str(rejected.exception), "patient-reference-missing")
        person = resource()
        person["resourceType"] = "Patient"
        person.pop("subject")
        self.assertEqual(validate_resource(person), ())

    def test_patient_demographic_fields_are_rejected(self) -> None:
        named = resource()
        named["resourceType"] = "Patient"
        named.pop("subject")
        named["birthDate"] = "2000-01-01"
        with self.assertRaises(ContractError) as birth:
            require_valid(named)
        self.assertEqual(str(birth.exception), "patient-identifier-forbidden")
        contact = resource()
        contact["resourceType"] = "Patient"
        contact.pop("subject")
        contact["telecom"] = [{"system": "phone", "value": "synthetic"}]
        issues = validate_resource(contact)
        self.assertIn("patient-identifier-forbidden", [issue.code for issue in issues])

    def test_encounter_requires_status_and_ordered_period(self) -> None:
        visit = resource()
        visit["resourceType"] = "Encounter"
        visit["status"] = "in-progress"
        visit["period"] = {"start": "2026-09-24T00:00:00Z", "end": "2026-09-24T01:00:00Z"}
        self.assertEqual(validate_resource(visit), ())
        unknown = dict(visit)
        unknown["status"] = "unknown"
        with self.assertRaises(ContractError) as blocked:
            require_valid(unknown)
        self.assertEqual(str(blocked.exception), "encounter-status-invalid")
        inverted = dict(visit)
        inverted["period"] = {"start": "2026-09-24T02:00:00Z", "end": "2026-09-24T01:00:00Z"}
        issues = validate_resource(inverted)
        self.assertIn("encounter-period-inverted", [issue.code for issue in issues])

    def test_observation_unit_and_reference_range(self) -> None:
        measured = resource()
        measured["valueQuantity"] = {"value": 12, "unit": "synthetic-unit"}
        measured["referenceRange"] = {"low": 4, "high": 20}
        self.assertEqual(validate_resource(measured), ())
        bare = dict(measured)
        bare["valueQuantity"] = {"value": 12}
        with self.assertRaises(ContractError) as missing_unit:
            require_valid(bare)
        self.assertEqual(str(missing_unit.exception), "observation-quantity-invalid")
        swapped = dict(measured)
        swapped["referenceRange"] = {"low": 20, "high": 4}
        issues = validate_resource(swapped)
        self.assertIn("observation-range-inverted", [issue.code for issue in issues])

    def test_condition_requires_known_clinical_status(self) -> None:
        problem = resource()
        problem["resourceType"] = "Condition"
        problem["clinicalStatus"] = "active"
        self.assertEqual(validate_resource(problem), ())
        blank = dict(problem)
        blank["clinicalStatus"] = ""
        with self.assertRaises(ContractError) as missing:
            require_valid(blank)
        self.assertEqual(str(missing.exception), "condition-status-missing")
        unknown = dict(problem)
        unknown["clinicalStatus"] = "unspecified"
        issues = validate_resource(unknown)
        self.assertEqual(issues[0].code, "condition-status-invalid")

    def test_medication_dose_needs_amount_unit_and_route(self) -> None:
        order = resource()
        order["resourceType"] = "MedicationRequest"
        order["dose"] = {"value": 5, "unit": "synthetic-unit", "route": "oral"}
        self.assertEqual(validate_resource(order), ())
        zero = dict(order)
        zero["dose"] = {"value": 0, "unit": "synthetic-unit", "route": "oral"}
        with self.assertRaises(ContractError) as blocked:
            require_valid(zero)
        self.assertEqual(str(blocked.exception), "medication-dose-invalid")
        omitted = dict(order)
        del omitted["dose"]
        self.assertEqual(validate_resource(omitted), ())

    def test_allergy_requires_known_severity(self) -> None:
        allergy = resource()
        allergy["resourceType"] = "AllergyIntolerance"
        allergy["severity"] = "severe"
        self.assertFalse(validate_resource(allergy))
        blank = {**allergy, "severity": ""}
        codes = [issue.code for issue in validate_resource(blank)]
        self.assertEqual(codes[0], "allergy-severity-missing")
        unknown = {**allergy, "severity": "unspecified"}
        with self.assertRaises(ContractError) as blocked:
            require_valid(unknown)
        self.assertEqual(blocked.exception.args[0], "allergy-severity-invalid")

    def test_procedure_requires_status_and_ordered_time(self) -> None:
        done = resource()
        done["resourceType"] = "Procedure"
        done["status"] = "completed"
        done["performed"] = {"start": "2026-09-24T00:00:00Z", "end": "2026-09-24T01:00:00Z"}
        self.assertEqual(len(validate_resource(done)), 0)
        blank = dict(done)
        blank["status"] = ""
        codes = tuple(issue.code for issue in validate_resource(blank))
        self.assertIn("procedure-status-missing", codes)
        swapped = dict(done)
        swapped["performed"] = {"end": "2026-09-24T00:00:00Z", "start": "2026-09-24T02:00:00Z"}
        with self.assertRaises(ContractError) as blocked:
            require_valid(swapped)
        self.assertEqual(blocked.exception.args[0], "procedure-time-inverted")

    def test_report_requires_known_conclusion_status(self) -> None:
        report = resource()
        report["resourceType"] = "DiagnosticReport"
        report["status"] = "final"
        self.assertEqual(tuple(validate_resource(report)), ())
        missing = dict(report, status="")
        found = [issue.code for issue in validate_resource(missing)]
        self.assertTrue(found and found[0] == "report-status-missing")
        unknown = dict(report, status="unspecified")
        with self.assertRaises(ContractError) as blocked:
            require_valid(unknown)
        self.assertTrue(str(blocked.exception) == "report-status-invalid")

    def test_document_requires_content_digest(self) -> None:
        document = resource()
        document["resourceType"] = "DocumentReference"
        document["contentDigest"] = "ab" * 32
        self.assertEqual(validate_resource(document), ())
        absent = dict(document)
        absent.pop("contentDigest")
        with self.assertRaises(ContractError) as missing:
            require_valid(absent)
        self.assertEqual(str(missing.exception), "document-hash-missing")
        short = dict(document)
        short["contentDigest"] = "ABCD"
        codes = {issue.code for issue in validate_resource(short)}
        self.assertIn("document-hash-invalid", codes)

    def test_service_request_requires_known_priority(self) -> None:
        order = resource()
        order["resourceType"] = "ServiceRequest"
        order["priority"] = "urgent"
        self.assertEqual(validate_resource(order), ())
        absent = dict(order)
        del absent["priority"]
        with self.assertRaises(ContractError) as missing:
            require_valid(absent)
        self.assertEqual(missing.exception.args[0], "request-priority-missing")
        unknown = {**order, "priority": "unspecified"}
        found = tuple(issue.code for issue in validate_resource(unknown))
        self.assertEqual(found[:1], ("request-priority-invalid",))

    def test_provenance_requires_source_chain(self) -> None:
        origin = resource()
        origin["resourceType"] = "Provenance"
        origin["target"] = {"reference": "Observation/observation-synthetic"}
        origin["recorded"] = "2026-09-24T00:00:00Z"
        origin["agent"] = {"reference": "Practitioner/reviewer-synthetic"}
        self.assertEqual(validate_resource(origin), ())
        bare = dict(origin)
        bare.pop("target")
        with self.assertRaises(ContractError) as missing:
            require_valid(bare)
        self.assertEqual(missing.exception.args[0], "provenance-target-missing")
        named = dict(origin)
        named["agent"] = {"reference": "Practitioner/subject.identifier"}
        codes = [issue.code for issue in validate_resource(named)]
        self.assertIn("provenance-agent-missing", codes)

    def test_withdrawn_consent_rejects_resource(self) -> None:
        withdrawn = resource()
        withdrawn["consentState"] = "withdrawn"
        captured: ContractError | None = None
        try:
            require_valid(withdrawn)
        except ContractError as exc:
            captured = exc
        self.assertIsNotNone(captured)
        self.assertEqual(str(captured), "consent-not-active")

    def test_emergency_validation_keeps_other_structural_errors(self) -> None:
        withdrawn = resource()
        withdrawn["consentState"] = "withdrawn"
        withdrawn["purposeCode"] = ""
        with self.assertRaises(ContractError) as blocked:
            require_valid(withdrawn, emergency=True)
        self.assertEqual(str(blocked.exception), "purpose-missing")

    def test_skipped_resource_version_is_rejected(self) -> None:
        skipped = resource()
        skipped["meta"] = {"versionId": "1.2", "profile": ["http://example.invalid/atlas/observation"]}
        with self.assertRaises(ContractError) as blocked:
            require_valid(skipped)
        self.assertEqual(str(blocked.exception), "resource-version-incompatible")

    def test_expired_code_system_is_rejected(self) -> None:
        expired = resource()
        expired["codeSystem"] = "http://example.invalid/atlas/CodeSystem/purpose"
        expired["reviewedAt"] = "2027-01-01"
        with self.assertRaises(ContractError) as blocked:
            require_valid(expired)
        self.assertEqual(str(blocked.exception), "terminology-release-expired")

    def test_synthetic_resource_requires_catalog_profile(self) -> None:
        declared = resource()
        declared["synthetic"] = True
        declared["meta"] = {
            "versionId": "1",
            "profile": ["http://example.invalid/atlas/StructureDefinition/observation"],
        }
        self.assertEqual(validate_resource(declared), ())
        unknown = resource()
        unknown["synthetic"] = True
        unknown["meta"] = {"versionId": "1", "profile": ["http://example.invalid/atlas/unknown"]}
        with self.assertRaises(ContractError) as blocked:
            require_valid(unknown)
        self.assertEqual(str(blocked.exception), "profile-not-declared")

    def test_identifier_patient_reference_is_rejected(self) -> None:
        named = resource()
        named["subject"] = {"reference": "Patient/subject.identifier"}
        with self.assertRaises(ContractError) as blocked:
            require_valid(named)
        self.assertEqual(str(blocked.exception), "patient-reference-missing")

    def test_unknown_reason_is_rejected(self) -> None:
        unknown = resource()
        unknown["whyCode"] = "unknown"
        captured: ContractError | None = None
        try:
            require_valid(unknown)
        except ContractError as exc:
            captured = exc
        self.assertEqual(getattr(captured, "args", ("",))[0], "actor-why-missing")

    def test_other_actor_for_same_resource_is_rejected(self) -> None:
        ledger = FhirLedger()
        first = resource()
        first["actorId"] = "reviewer-synthetic"
        ledger.require(first)
        other = resource()
        other["actorId"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ledger.require(other)
        self.assertEqual(str(blocked.exception), "fhir-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
