"""Version tests for the capability statement."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.capability import require_statement  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def statement() -> dict[str, object]:
    return {
        "fhirVersion": "1.0.0",
        "resourceType": "CapabilityStatement",
        "software": {"name": "atlas"},
        "status": "active",
    }


class CapabilityVersionTests(unittest.TestCase):
    def test_current_version_is_accepted(self) -> None:
        self.assertEqual(require_statement(statement()), "1.0.0")

    def test_previous_minor_is_accepted(self) -> None:
        previous = statement()
        previous["fhirVersion"] = "1"
        self.assertEqual(require_statement(previous), "1")

    def test_missing_version_is_rejected(self) -> None:
        blank = statement()
        blank["fhirVersion"] = ""
        with self.assertRaises(ContractError) as blocked:
            require_statement(blank)
        self.assertEqual(blocked.exception.args[0], "capability-version-missing")

    def test_skipped_minor_is_rejected(self) -> None:
        skipped = statement()
        skipped["fhirVersion"] = "1.2"
        with self.assertRaises(ContractError) as blocked:
            require_statement(skipped)
        self.assertEqual(str(blocked.exception), "capability-version-incompatible")


if __name__ == "__main__":
    unittest.main()
