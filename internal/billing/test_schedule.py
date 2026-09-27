"""Tests for synthetic schedule enforcement."""
from __future__ import annotations

import unittest

from internal.billing.schedule import synthetic_schedule
from internal.contract.errors import ContractError


class TestSyntheticSchedule(unittest.TestCase):
    def test_valid_schedule(self) -> None:
        slots = [{"time": "09:00"}, {"time": "10:00"}]
        result = synthetic_schedule("SCH1", slots, 10)
        self.assertEqual(result, "SCH1")

    def test_capacity_exceeded(self) -> None:
        slots = [{"time": str(i)} for i in range(15)]
        with self.assertRaises(ContractError) as ctx:
            synthetic_schedule("SCH1", slots, 10)
        self.assertEqual(ctx.exception.args[0], "schedule-capacity-exceeded")

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            synthetic_schedule("", [{"time": "09:00"}], 10)
        self.assertEqual(ctx.exception.args[0], "schedule-invalid")


if __name__ == "__main__":
    unittest.main()
