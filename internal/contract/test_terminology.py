"""Tests for terminology release validity."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.terminology import (  # noqa: E402
    LocalExtensionRegistry,
    ReleaseLedger,
    icd_package,
    loinc_unit,
    medication_code,
    reference_integrity,
    require_active_release,
    require_known_code,
    rollback_release,
    snomed_subset,
    version_diff,
)


_SYSTEM = "http://example.invalid/atlas/CodeSystem/purpose"


class TerminologyReleaseTests(unittest.TestCase):
    def test_release_is_active_inside_its_window(self) -> None:
        release_id = require_active_release(_SYSTEM, "2026-09-24")
        self.assertEqual(release_id, "purpose-2026")

    def test_expired_release_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_active_release(_SYSTEM, "2027-01-01")
        self.assertEqual(str(blocked.exception), "terminology-release-expired")

    def test_unknown_system_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_active_release("http://example.invalid/atlas/CodeSystem/unknown", "2026-09-24")
        self.assertEqual(str(blocked.exception), "terminology-release-unknown")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_active_release(_SYSTEM, "2026-09-24", why_code="unknown")
        self.assertEqual(str(blocked.exception), "terminology-why-missing")

    def test_other_actor_for_same_system_is_rejected(self) -> None:
        ledger = ReleaseLedger()
        ledger.require(_SYSTEM, "2026-09-24", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            ledger.require(_SYSTEM, "2026-09-24", "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "terminology-responsibility-mismatch")

    def test_icd_header_is_accepted_without_codes(self) -> None:
        accepted = icd_package({"digest": "ab" * 32, "family": "ICD", "release_id": "icd-synthetic", "synthetic": True})
        self.assertEqual(accepted["family"], "ICD")
        self.assertNotIn("codes", accepted)

    def test_icd_code_table_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            icd_package({"codes": ["A00"], "digest": "ab" * 32, "family": "ICD", "release_id": "icd-synthetic", "synthetic": True})
        self.assertEqual(blocked.exception.args[0], "icd-package-forbidden")

    def test_other_family_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            icd_package({"digest": "ab" * 32, "family": "other", "release_id": "icd-synthetic", "synthetic": True})
        self.assertEqual(str(blocked.exception), "icd-family-rejected")

    def test_loinc_unit_maps_a_digest(self) -> None:
        mapped = loinc_unit("cd" * 32, "mmol/L", True)
        self.assertEqual(mapped["unit"], "mmol/L")

    def test_unknown_loinc_unit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            loinc_unit("cd" * 32, "cup", True)
        self.assertEqual(blocked.exception.args[0], "loinc-unit-unknown")

    def test_non_synthetic_loinc_map_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            loinc_unit("cd" * 32, "mmol/L", False)
        self.assertEqual(str(blocked.exception), "loinc-not-synthetic")

    def test_snomed_subset_keeps_digests_only(self) -> None:
        subset = snomed_subset("finding-synthetic", ("ab" * 32, "cd" * 32), True)
        self.assertEqual(subset["count"], 2)
        self.assertNotIn("concepts", subset)

    def test_duplicate_snomed_member_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            snomed_subset("finding-synthetic", ("ab" * 32, "ab" * 32), True)
        self.assertEqual(blocked.exception.args[0], "snomed-member-duplicate")

    def test_empty_snomed_subset_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            snomed_subset("finding-synthetic", (), True)
        self.assertEqual(str(blocked.exception), "snomed-subset-invalid")

    def test_medication_code_maps_two_digests(self) -> None:
        mapped = medication_code("ab" * 32, "cd" * 32, True)
        self.assertEqual(mapped["standard"], "cd" * 32)
        self.assertNotIn("name", mapped)

    def test_same_medication_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            medication_code("ab" * 32, "ab" * 32, True)
        self.assertEqual(blocked.exception.args[0], "medcode-same-digest")

    def test_non_synthetic_medication_map_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            medication_code("ab" * 32, "cd" * 32, False)
        self.assertEqual(str(blocked.exception), "medcode-not-synthetic")

    def test_local_extension_is_registered_once(self) -> None:
        registry = LocalExtensionRegistry()
        size = registry.register("ext-synthetic", "ab" * 32, True)
        self.assertEqual(size, 1)
        with self.assertRaises(ContractError) as blocked:
            registry.register("ext-synthetic", "cd" * 32, True)
        self.assertEqual(blocked.exception.args[0], "extension-duplicate")

    def test_non_synthetic_extension_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            LocalExtensionRegistry().register("ext-synthetic", "ab" * 32, False)
        self.assertEqual(str(blocked.exception), "extension-not-synthetic")

    def test_expired_release_can_roll_back(self) -> None:
        chosen = rollback_release("2026-01-01", "2027-01-01", "2026-01-01", "2027-02-01")
        self.assertEqual(chosen, "2026-01-01")

    def test_active_release_cannot_roll_back(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rollback_release("2026-01-01", "2027-01-01", "2026-01-01", "2026-06-01")
        self.assertEqual(blocked.exception.args[0], "rollback-still-active")

    def test_gap_before_current_release_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rollback_release("2026-01-01", "2027-01-01", "2025-01-01", "2027-02-01")
        self.assertEqual(str(blocked.exception), "rollback-order-invalid")

    def test_registered_code_digest_is_accepted(self) -> None:
        known = ("ab" * 32,)
        self.assertEqual(require_known_code("ab" * 32, known), "ab" * 32)

    def test_unknown_code_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_known_code("cd" * 32, ("ab" * 32,))
        self.assertEqual(blocked.exception.args[0], "code-unknown")

    def test_short_code_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_known_code("abcd", ("ab" * 32,))
        self.assertEqual(str(blocked.exception), "code-digest-invalid")

    def test_version_diff_counts_digest_changes(self) -> None:
        report = version_diff(("ab" * 32, "cd" * 32), ("cd" * 32, "ef" * 32))
        self.assertEqual(report, {"added": 1, "removed": 1})
        self.assertNotIn("codes", report)

    def test_unchanged_versions_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            version_diff(("ab" * 32,), ("ab" * 32,))
        self.assertEqual(blocked.exception.args[0], "diff-unchanged")

    def test_empty_version_set_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            version_diff((), ("ab" * 32,))
        self.assertEqual(str(blocked.exception), "diff-set-invalid")

    def test_every_reference_must_be_known(self) -> None:
        count = reference_integrity(("ab" * 32, "cd" * 32), ("ab" * 32, "cd" * 32))
        self.assertEqual(count, 2)

    def test_dangling_reference_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            reference_integrity(("ef" * 32,), ("ab" * 32,))
        self.assertEqual(blocked.exception.args[0], "code-unknown")

    def test_duplicate_reference_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            reference_integrity(("ab" * 32, "ab" * 32), ("ab" * 32,))
        self.assertEqual(str(blocked.exception), "reference-duplicate")


if __name__ == "__main__":
    unittest.main()
