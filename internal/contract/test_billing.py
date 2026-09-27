"""Tests for billing grouper isolation."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.billing import (  # noqa: E402
    batch_reconcile,
    charge_line,
    code_version_lock,
    denial_reason,
    grouper_isolation as isolate,
    grouper_reason,
    human_review,
    local_variance,
    rule_replay,
)
from internal.contract.errors import ContractError as GateError  # noqa: E402


def _capture(source: str, target: str) -> tuple[str, str]:
    try:
        return isolate(source, target), ""
    except GateError as blocked:
        return "", blocked.args[0]


class GrouperIsolationTests(unittest.TestCase):
    def test_same_lane_is_kept(self) -> None:
        lane, problem = _capture("billing", "billing")
        self.assertEqual(problem, "")
        self.assertEqual(lane, "billing")

    def test_cross_lane_is_isolated(self) -> None:
        lane, problem = _capture("billing", "clinical")
        self.assertEqual(lane, "")
        self.assertTrue(problem.endswith("isolated"))

    def test_unknown_lane_is_invalid(self) -> None:
        lane, problem = _capture("orders", "billing")
        self.assertEqual(lane, "")
        self.assertTrue(problem.endswith("invalid"))

    def test_locked_catalog_year_is_kept(self) -> None:
        year = code_version_lock("2025", "2025")
        self.assertTrue(year.startswith("20"))

    def test_other_catalog_year_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            code_version_lock("2024", "2025")
        self.assertIn("mismatch", blocked.exception.args[0])

    def test_registered_addon_is_kept(self) -> None:
        addon = local_variance("A10", "L1")
        self.assertEqual(len(addon), 2)

    def test_unregistered_addon_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            local_variance("A10", "L9")
        self.assertIn("mismatch", blocked.exception.args[0])

    def test_registered_reason_length_is_counted(self) -> None:
        counted = grouper_reason("G1", "complication")
        self.assertGreater(counted, 4)

    def test_wrong_reason_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            grouper_reason("G1", "procedure")
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))

    def test_two_people_can_hold(self) -> None:
        decision = human_review("coder-a", "coder-b", "hold")
        self.assertEqual(decision, "hold")

    def test_system_cannot_release(self) -> None:
        with self.assertRaises(GateError) as blocked:
            human_review("system", "coder-b", "release")
        self.assertTrue(blocked.exception.args[0].endswith("forbidden"))

    def test_matching_charge_is_kept(self) -> None:
        total = charge_line(2, 50, 100)
        self.assertEqual(total, 100)

    def test_wrong_claim_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            charge_line(2, 50, 90)
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))

    def test_registered_denial_is_kept(self) -> None:
        code = denial_reason("duplicate", "2025")
        self.assertEqual(code, "duplicate")

    def test_free_text_denial_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            denial_reason("other", "2025")
        self.assertTrue(blocked.exception.args[0].endswith("unknown"))

    def test_registered_batch_total_is_kept(self) -> None:
        total = batch_reconcile("B01", 100)
        self.assertEqual(total, 100)

    def test_wrong_batch_total_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            batch_reconcile("B01", 90)
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))

    def test_registered_rule_digest_is_counted(self) -> None:
        counted = rule_replay("R1", "a" * 64)
        self.assertEqual(counted, 64)

    def test_changed_rule_digest_is_rejected(self) -> None:
        with self.assertRaises(GateError) as blocked:
            rule_replay("R1", "c" * 64)
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))


if __name__ == "__main__":
    unittest.main()
