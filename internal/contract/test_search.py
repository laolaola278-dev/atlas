"""Allow-list tests for search parameters."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.search import require_parameters  # noqa: E402


class SearchParameterTests(unittest.TestCase):
    def test_known_parameters_are_sorted(self) -> None:
        accepted = require_parameters(["status", "patient", "status"])
        self.assertEqual(accepted, ("patient", "status"))

    def test_empty_parameter_list_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_parameters([])
        self.assertEqual(blocked.exception.args[0], "search-parameter-missing")

    def test_identifier_parameter_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_parameters(["name"])
        self.assertEqual(str(blocked.exception), "search-parameter-forbidden")

    def test_unknown_parameter_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_parameters(["status", "free-text"])
        self.assertEqual(str(blocked.exception), "search-parameter-forbidden")


if __name__ == "__main__":
    unittest.main()
