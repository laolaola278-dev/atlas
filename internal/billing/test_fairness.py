"""Fairness reporting tests."""
import unittest
from internal.contract._path import install_contract_path

install_contract_path()

from internal.billing.fairness import fairness_report as check_fairness  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class FairnessReportTests(unittest.TestCase):
    def test_fairness_within_threshold_is_accepted(self) -> None:
        variances = check_fairness("S001", ["age", "gender"], 0.1)
        self.assertIsInstance(variances, dict)
        self.assertEqual(len(variances), 2)

    def test_fairness_exceeding_threshold_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_fairness("S002", ["age", "gender"], 0.01)
        self.assertTrue(blocked.exception.args[0].endswith("exceeded"))


if __name__ == "__main__":
    unittest.main()
