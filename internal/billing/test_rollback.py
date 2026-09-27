"""Tests for schedule rollback enforcement."""
from __future__ import annotations
import unittest

from internal.billing.rollback import schedule_rollback
from internal.contract.errors import ContractError


class TestScheduleRollback(unittest.TestCase):
    def test_forbidden_same_version(self) -> None:
        try:
            schedule_rollback("SCHED2", "2.0", "2.0")
            self.fail("Expected error")
        except ContractError as err:
            self.assertEqual(err.args[0], "rollback-forbidden")

    def test_valid_rollback(self) -> None:
        output = schedule_rollback("SCHED1", "1.1", "1.0")
        self.assertEqual(output, "SCHED1")

    def test_invalid_empty_id(self) -> None:
        try:
            schedule_rollback("", "2.5", "2.4")
        except ContractError as error:
            self.assertEqual(error.args[0], "rollback-invalid")
        else:
            self.fail("Expected ContractError")

    def test_forbidden_forward(self) -> None:
        self.assertRaises(ContractError, schedule_rollback, "SCHED3", "1.0", "1.1")


if __name__ == "__main__":
    unittest.main()
