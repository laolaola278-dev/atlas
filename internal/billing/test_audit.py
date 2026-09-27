"""Billing audit trail checks."""
from internal.contract._path import install_contract_path
import unittest

install_contract_path()

from internal.billing.audit import item_audit as link  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class ItemAuditTests(unittest.TestCase):
    def test_distinct_digests_are_linked(self) -> None:
        self.assertEqual(link("item123", "event456", "charge"), "event456")

    def test_circular_reference_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            link("same", "same", "charge")
        self.assertTrue(blocked.exception.args[0].endswith("circular"))


if __name__ == "__main__":
    unittest.main()
