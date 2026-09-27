"""Billing batch capacity, time window, checksum, amount range, lock state, and adjustment reason checks."""
import unittest
from internal.contract._path import install_contract_path

install_contract_path()

from internal.billing.batch import batch_cap as check_cap  # noqa: E402
from internal.billing.window import time_window as check_window  # noqa: E402
from internal.billing.checksum import verify_checksum as check_sum  # noqa: E402
from internal.billing.amount import amount_range as check_amount  # noqa: E402
from internal.billing.lock import lock_state as check_lock  # noqa: E402
from internal.billing.adjustment import adjustment_reason as check_adjust  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class BatchCapTests(unittest.TestCase):
    def test_items_within_cap_are_accepted(self) -> None:
        self.assertEqual(check_cap(50, 100), 50)

    def test_items_exceeding_cap_are_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_cap(200, 100)
        self.assertTrue(blocked.exception.args[0].endswith("exceeded"))


class TimeWindowTests(unittest.TestCase):
    def test_submission_before_deadline_is_accepted(self) -> None:
        self.assertEqual(check_window(1000, 2000), 1000)

    def test_submission_after_deadline_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_window(3000, 2000)
        self.assertTrue(blocked.exception.args[0].endswith("expired"))


class ChecksumTests(unittest.TestCase):
    def test_matching_checksum_is_accepted(self) -> None:
        self.assertEqual(check_sum("D1", "a" * 64), "a" * 64)

    def test_mismatched_checksum_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_sum("D1", "b" * 64)
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))


class AmountRangeTests(unittest.TestCase):
    def test_amount_within_range_is_accepted(self) -> None:
        self.assertEqual(check_amount(500, 100, 1000), 500)

    def test_amount_below_minimum_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_amount(50, 100, 1000)
        self.assertTrue(blocked.exception.args[0].endswith("out-of-range"))


class LockStateTests(unittest.TestCase):
    def test_unlocked_batch_allows_modification(self) -> None:
        self.assertEqual(check_lock("B1", False, "modify"), "B1")

    def test_locked_batch_blocks_modification(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_lock("B1", True, "modify")
        self.assertTrue(blocked.exception.args[0].endswith("violation"))


class AdjustmentReasonTests(unittest.TestCase):
    def test_valid_adjustment_with_reason_is_accepted(self) -> None:
        self.assertEqual(check_adjust("coding-error", 100), "coding-error")

    def test_adjustment_without_valid_reason_is_refused(self) -> None:
        with self.assertRaises(Denied) as blocked:
            check_adjust("unknown", 100)
        self.assertTrue(blocked.exception.args[0].endswith("invalid"))


if __name__ == "__main__":
    unittest.main()
