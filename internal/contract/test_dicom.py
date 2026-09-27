"""Tests for the DICOM metadata index."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.dicom import (  # noqa: E402
    dicom_index,
    image_access,
    integrity_sample,
    model_input,
    object_checksum,
    cross_campus_object,
    study_token,
    synthetic_fixture,
    storage_watermark,
    transfer_syntax,
)
from internal.contract.errors import ContractError  # noqa: E402


class DicomIndexTests(unittest.TestCase):
    def test_metadata_digests_are_indexed(self) -> None:
        indexed = dicom_index("ab" * 32, "cd" * 32, "ef" * 32, ("modality",))
        self.assertEqual(indexed["study"], "ab" * 32)
        self.assertNotIn("pixels", indexed)

    def test_pixel_field_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            dicom_index("ab" * 32, "cd" * 32, "ef" * 32, ("PixelData",))
        self.assertEqual(blocked.exception.args[0], "dicom-pixel-forbidden")

    def test_reused_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            dicom_index("ab" * 32, "ab" * 32, "ef" * 32, ("modality",))
        self.assertEqual(str(blocked.exception), "dicom-digest-reused")

    def test_model_receives_only_a_digest(self) -> None:
        self.assertEqual(model_input(("modality",), "ab" * 32), "ab" * 32)

    def test_pixel_payload_cannot_enter_model(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            model_input(("pixels",), "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "model-pixel-forbidden")

    def test_matching_object_digests_pass(self) -> None:
        self.assertEqual(object_checksum("ab" * 32, "ab" * 32, ""), "ab" * 32)

    def test_changed_object_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            object_checksum("ab" * 32, "cd" * 32, "")
        self.assertEqual(blocked.exception.args[0], "object-digest-mismatch")

    def test_object_body_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            object_checksum("ab" * 32, "ab" * 32, "pixels")
        self.assertEqual(str(blocked.exception), "object-body-forbidden")

    def test_accession_becomes_a_token(self) -> None:
        issued = study_token("accession-synthetic", "ab" * 32)
        self.assertEqual(issued["token"], "ab" * 32)
        self.assertEqual(issued["accession_kept"], "false")

    def test_numeric_accession_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            study_token("A123", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "study-accession-forbidden")

    def test_declared_syntax_is_accepted(self) -> None:
        self.assertEqual(transfer_syntax("1.2.840.10008.1.2.1"), "1.2.840.10008.1.2.1")

    def test_other_syntax_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            transfer_syntax("1.2.840.10008.1.2.4.91")
        self.assertEqual(blocked.exception.args[0], "syntax-not-allowed")

    def test_image_access_keeps_role_and_digest(self) -> None:
        record = image_access("reviewer", "view", "ab" * 32)
        self.assertEqual(record["action"], "view")
        self.assertNotIn("pixels", record)

    def test_unknown_image_action_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            image_access("reviewer", "export", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "image-access-invalid")

    def test_small_object_can_share_metadata(self) -> None:
        self.assertEqual(cross_campus_object(1000, False), "metadata-only")

    def test_large_object_cannot_cross_campus(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            cross_campus_object(1_000_001, False)
        self.assertEqual(blocked.exception.args[0], "object-cross-campus-forbidden")
        self.assertEqual(cross_campus_object(1_000_001, True), "local")

    def test_synthetic_fixture_keeps_metadata(self) -> None:
        fixture = synthetic_fixture(True, ("modality",), "ab" * 32)
        self.assertTrue(fixture["synthetic"])
        self.assertNotIn("pixels", fixture["fields"])

    def test_fixture_pixels_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            synthetic_fixture(True, ("PixelData",), "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "fixture-pixel-forbidden")

    def test_storage_accepts_room(self) -> None:
        self.assertEqual(storage_watermark(10, 5, 20), 15)

    def test_storage_rejects_overflow(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            storage_watermark(18, 5, 20)
        self.assertEqual(blocked.exception.args[0], "storage-watermark-full")

    def test_sample_matches_declared_digests(self) -> None:
        self.assertEqual(integrity_sample(("ab" * 32, "cd" * 32), ("cd" * 32,)), 1)

    def test_sample_outside_declared_set_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            integrity_sample(("ab" * 32,), ("cd" * 32,))
        self.assertEqual(blocked.exception.args[0], "sample-mismatch")


if __name__ == "__main__":
    unittest.main()
