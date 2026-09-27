"""Tests for schedule review enforcement."""
from __future__ import annotations
import unittest
from internal.billing.review import schedule_review

from internal.contract.errors import ContractError


class TestScheduleReview(unittest.TestCase):
    def test_invalid_system_reviewer(self) -> None:
        self.assertRaises(ContractError, schedule_review, "SCH1", "system", "approved")

    def test_valid_review(self) -> None:
        output = schedule_review("SCH1", "user123", "approved")
        self.assertEqual(output, "approved")

    def test_invalid_status(self) -> None:
        try:
            schedule_review("SCH1", "user123", "unknown")
        except ContractError as error:
            code = error.args[0]
            self.assertEqual(code, "review-status-invalid")
        else:
            self.fail("Should raise ContractError")


if __name__ == "__main__":
    unittest.main()
