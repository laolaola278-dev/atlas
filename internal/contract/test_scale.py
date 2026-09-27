"""Tests for synthetic scale plans."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.scale import scale_plan  # noqa: E402


class ScalePlanTests(unittest.TestCase):
    def test_ten_million_plan_is_not_materialized(self) -> None:
        plan = scale_plan(10_000_000, "seed-synthetic", True)
        self.assertEqual(plan["count"], 10_000_000)
        self.assertFalse(plan["materialized"])

    def test_plan_above_limit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            scale_plan(10_000_001, "seed-synthetic", True)
        self.assertEqual(blocked.exception.args[0], "scale-count-invalid")

    def test_non_synthetic_plan_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            scale_plan(1000, "seed-synthetic", False)
        self.assertEqual(str(blocked.exception), "scale-not-synthetic")

    def test_identifier_seed_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            scale_plan(1000, "subject.identifier", True)
        self.assertEqual(str(blocked.exception), "scale-seed-forbidden")


if __name__ == "__main__":
    unittest.main()
