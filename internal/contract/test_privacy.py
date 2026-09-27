"""Tests for privacy projection and version compatibility."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.privacy import ProjectionLedger, project  # noqa: E402
from internal.contract.version import compatible  # noqa: E402


class PrivacyTests(unittest.TestCase):
    def test_allowed_clinical_field_remains(self) -> None:
        projected = project(
            {"code": "synthetic-code", "name": "synthetic-name", "value": "12"},
            frozenset({"code", "value"}),
        )
        self.assertEqual(projected, {"code": "synthetic-code", "value": "12"})

    def test_identifier_allow_list_and_empty_projection_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as forbidden:
            project({"name": "synthetic-name"}, frozenset({"name"}))
        self.assertEqual(str(forbidden.exception), "privacy-field-forbidden")
        with self.assertRaises(ContractError) as empty:
            project({"name": "synthetic-name"}, frozenset({"code"}))
        self.assertEqual(str(empty.exception), "privacy-projection-empty")

    def test_withdrawn_consent_returns_no_projection(self) -> None:
        with self.assertRaises(ContractError) as withdrawn:
            project(
                {"code": "synthetic-code", "value": "12"},
                frozenset({"code", "value"}),
                "withdrawn",
            )
        self.assertEqual(str(withdrawn.exception), "privacy-consent-not-active")

    def test_nested_identifier_cannot_leave_projection(self) -> None:
        with self.assertRaises(ContractError) as nested:
            project(
                {"code": {"identifier": "synthetic-token"}, "value": "12"},
                frozenset({"code", "value"}),
            )
        self.assertEqual(str(nested.exception), "privacy-field-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            project(
                {"code": "synthetic-code", "value": "12"},
                frozenset({"code", "value"}),
                why_code="unknown",
            )
        self.assertEqual(str(blocked.exception), "privacy-why-missing")

    def test_other_actor_for_same_projection_is_rejected(self) -> None:
        ledger = ProjectionLedger()
        fields = frozenset({"code", "value"})
        record = {"code": "synthetic-code", "value": "12"}
        ledger.project(record, fields, actor_id="reviewer-synthetic")
        with self.assertRaises(ContractError) as blocked:
            ledger.project(record, fields, actor_id="other-reviewer")
        self.assertEqual(str(blocked.exception), "privacy-responsibility-mismatch")


class VersionTests(unittest.TestCase):
    def test_current_and_previous_minor_are_compatible(self) -> None:
        self.assertTrue(compatible("1.1", current=(1, 1)))
        self.assertTrue(compatible("1.0", current=(1, 1)))

    def test_future_major_and_malformed_versions_are_rejected(self) -> None:
        self.assertFalse(compatible("2.0", current=(1, 1)))
        self.assertFalse(compatible("1.2", current=(1, 1)))
        with self.assertRaises(ContractError):
            compatible("beta", current=(1, 1))


if __name__ == "__main__":
    unittest.main()
