"""Boundary tests for transaction bundles."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.bundle import bundle_entry_references, require_bundle  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def bundle() -> dict[str, object]:
    return {
        "entry": [{"reference": "Observation/observation-synthetic"}],
        "resourceType": "Bundle",
        "type": "transaction",
    }


def fhir_entry(method: str = "POST", url: str = "Observation", token: str = "observation-synthetic") -> dict[str, object]:
    """Return one real FHIR transaction entry carrying its resource."""
    return {
        "fullUrl": "urn:uuid:6a1f6a5e-0d1e-4a1e-9a3f-2f1d0c9b8a71",
        "request": {"method": method, "url": url},
        "resource": {"id": token, "resourceType": "Observation", "status": "final"},
    }


def fhir_bundle() -> dict[str, object]:
    return {
        "entry": [fhir_entry()],
        "id": "bundle-synthetic",
        "resourceType": "Bundle",
        "type": "transaction",
    }


class BundleBoundaryTests(unittest.TestCase):
    def test_one_entry_transaction_is_accepted(self) -> None:
        require_bundle(bundle())

    def test_empty_bundle_is_rejected(self) -> None:
        empty = bundle()
        empty["entry"] = []
        with self.assertRaises(ContractError) as blocked:
            require_bundle(empty)
        self.assertEqual(blocked.exception.args[0], "bundle-empty")

    def test_duplicate_entry_is_rejected(self) -> None:
        repeated = bundle()
        repeated["entry"] = [
            {"reference": "Observation/observation-synthetic"},
            {"reference": "Observation/observation-synthetic"},
        ]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(repeated)
        self.assertEqual(str(blocked.exception), "bundle-entry-duplicate")

    def test_identifier_entry_is_rejected(self) -> None:
        named = bundle()
        named["entry"] = [{"reference": "Observation/subject.identifier"}]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(named)
        self.assertEqual(str(blocked.exception), "bundle-entry-invalid")


class FhirTransactionBundleTests(unittest.TestCase):
    """A real FHIR transaction bundle and the Atlas manifest must both resolve."""

    def test_fhir_shaped_entry_resolves_from_its_resource(self) -> None:
        require_bundle(fhir_bundle())
        self.assertEqual(bundle_entry_references(fhir_bundle()), ("Observation/observation-synthetic",))

    def test_legacy_manifest_shape_still_resolves(self) -> None:
        require_bundle(bundle())
        self.assertEqual(bundle_entry_references(bundle()), ("Observation/observation-synthetic",))

    def test_both_shapes_agree_in_one_bundle(self) -> None:
        mixed = fhir_bundle()
        mixed["entry"] = [fhir_entry(), {"reference": "ServiceRequest/service-request-synthetic"}]
        require_bundle(mixed)
        self.assertEqual(
            bundle_entry_references(mixed),
            ("Observation/observation-synthetic", "ServiceRequest/service-request-synthetic"),
        )

    def test_fhir_entry_without_a_request_is_rejected(self) -> None:
        payload = fhir_bundle()
        payload["entry"][0].pop("request")  # type: ignore[union-attr]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(payload)
        self.assertEqual(str(blocked.exception), "bundle-entry-request-invalid")

    def test_unknown_request_method_is_rejected(self) -> None:
        payload = fhir_bundle()
        payload["entry"] = [fhir_entry(method="FETCH")]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(payload)
        self.assertEqual(str(blocked.exception), "bundle-entry-request-invalid")

    def test_resource_entry_without_an_id_is_rejected(self) -> None:
        payload = fhir_bundle()
        payload["entry"] = [{"request": {"method": "POST", "url": "Observation"},
                             "resource": {"resourceType": "Observation"}}]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(payload)
        self.assertEqual(str(blocked.exception), "bundle-entry-invalid")

    def test_duplicate_fhir_entries_are_rejected(self) -> None:
        payload = fhir_bundle()
        payload["entry"] = [fhir_entry(), fhir_entry()]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(payload)
        self.assertEqual(str(blocked.exception), "bundle-entry-duplicate")

    def test_request_error_code_is_registered_as_a_client_error(self) -> None:
        from internal.contract.errors import lookup

        entry = lookup("bundle-entry-request-invalid")
        self.assertEqual(entry.http_status, 400)
        self.assertFalse(entry.retryable)

    def test_disallowed_entry_type_is_still_rejected(self) -> None:
        payload = fhir_bundle()
        payload["entry"] = [fhir_entry(url="Patient", token="patient-ref-synthetic")]
        payload["entry"][0]["resource"] = {"id": "patient-ref-synthetic", "resourceType": "Patient"}  # type: ignore[index]
        with self.assertRaises(ContractError) as blocked:
            require_bundle(payload)
        self.assertEqual(str(blocked.exception), "bundle-entry-invalid")


if __name__ == "__main__":
    unittest.main()
