"""Export boundary checks for billing."""
from internal.contract._path import install_contract_path
import unittest

install_contract_path()

from internal.contract.errors import ContractError as Denied  # noqa: E402
from internal.billing.export import export_guard as guard  # noqa: E402


def outcome(source, target):
    try:
        kept = guard(source, target)
    except Denied as blocked:
        return blocked.args[0]
    return kept


class ExportGuardTests(unittest.TestCase):
    def test_billing_to_billing_returns_the_lane(self) -> None:
        self.assertEqual(outcome("billing", "billing"), "billing")

    def test_billing_to_clinical_is_forbidden(self) -> None:
        self.assertTrue(str(outcome("billing", "clinical")).endswith("forbidden"))


if __name__ == "__main__":
    unittest.main()
