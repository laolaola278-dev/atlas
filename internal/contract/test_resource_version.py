"""Conflict tests for one stored resource version."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import CODES, ContractError  # noqa: E402
from internal.contract.version import require_resource_version  # noqa: E402


class ResourceVersionTests(unittest.TestCase):
    def test_matching_version_is_accepted(self) -> None:
        self.assertEqual(require_resource_version("4", "4"), "4")

    def test_blank_version_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_resource_version("", "4")
        self.assertEqual(blocked.exception.args[0], "resource-version-missing")

    def test_changed_version_conflicts(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_resource_version("3", "4")
        self.assertEqual(str(blocked.exception), "version-conflict")
        self.assertEqual(CODES["version-conflict"].http_status, 409)

    def test_non_numeric_version_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_resource_version("v4", "4")
        self.assertEqual(str(blocked.exception), "resource-version-invalid")


if __name__ == "__main__":
    unittest.main()
