"""Boundary tests for transaction bundles."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.bundle import require_bundle  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def bundle() -> dict[str, object]:
    return {
        "entry": [{"reference": "Observation/observation-synthetic"}],
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


if __name__ == "__main__":
    unittest.main()
