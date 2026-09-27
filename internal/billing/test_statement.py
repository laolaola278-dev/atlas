"""Synthetic statement checks."""
import unittest
from internal.contract._path import install_contract_path

install_contract_path()

from internal.billing.statement import synthetic_statement as count_rows  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class StatementTests(unittest.TestCase):
    def test_registered_rows_are_counted(self) -> None:
        self.assertEqual(count_rows("S1", 3, True), 3)

    def test_real_input_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            count_rows("S1", 3, False)
        self.assertTrue(blocked.exception.args[0].endswith("synthetic"))


if __name__ == "__main__":
    unittest.main()
