"""Capacity headroom tests."""
import unittest
from internal.contract._path import install_contract_path

install_contract_path()

from internal.billing.capacity import capacity_headroom as check_capacity  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class CapacityHeadroomTests(unittest.TestCase):
    def test_sufficient_headroom_is_accepted(self) -> None:
        available = check_capacity(50, 100, 20)
        self.assertEqual(available, 50)

    def test_insufficient_headroom_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_capacity(85, 100, 20)
        self.assertTrue(blocked.exception.args[0].endswith("insufficient"))


if __name__ == "__main__":
    unittest.main()
