"""Projection tests for export records."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.transfer import project_export  # noqa: E402


def record() -> dict[str, object]:
    return {
        "code": "synthetic-code",
        "effective_at": "2026-09-24T00:00:00Z",
        "identifier": "hidden",
        "status": "final",
        "unit": "synthetic-unit",
        "value": "12",
    }


class ExportProjectionTests(unittest.TestCase):
    def test_projection_keeps_only_requested_fields(self) -> None:
        projected = project_export(record(), {"status", "value"})
        self.assertEqual(projected, {"status": "final", "value": "12"})
        self.assertNotIn("identifier", projected)

    def test_missing_requested_value_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            project_export({"status": "final"}, {"status", "value"})
        self.assertEqual(blocked.exception.args[0], "transfer-field-missing")

    def test_identifier_field_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            project_export(record(), {"status", "identifier"})
        self.assertEqual(str(blocked.exception), "transfer-field-forbidden")

    def test_identifier_value_is_rejected(self) -> None:
        leaked = record()
        leaked["status"] = "subject.identifier"
        with self.assertRaises(ContractError) as blocked:
            project_export(leaked, {"status"})
        self.assertEqual(str(blocked.exception), "transfer-identifier-forbidden")


if __name__ == "__main__":
    unittest.main()
