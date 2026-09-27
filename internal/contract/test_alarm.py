"""Tests for alarm debounce."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.alarm import critical_channel, debounce, downsample, point_capacity  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


class AlarmDebounceTests(unittest.TestCase):
    def test_repeated_alarm_is_raised(self) -> None:
        self.assertEqual(debounce("hr", 3, 3), "raised")

    def test_short_alarm_is_debounced(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            debounce("spo2", 1, 3)
        self.assertEqual(blocked.exception.args[0], "alarm-debounced")

    def test_unknown_point_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            debounce("name", 3, 3)
        self.assertEqual(str(blocked.exception), "alarm-point-unknown")

    def test_critical_event_stays_on_critical_channel(self) -> None:
        self.assertEqual(critical_channel("critical", "critical"), "critical")

    def test_critical_event_cannot_use_ordinary_channel(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            critical_channel("ordinary", "critical")
        self.assertEqual(blocked.exception.args[0], "channel-critical-isolated")

    def test_routine_event_cannot_use_critical_channel(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            critical_channel("critical", "routine")
        self.assertEqual(str(blocked.exception), "channel-ordinary-isolated")

    def test_routine_point_can_downsample(self) -> None:
        self.assertEqual(downsample("hr", "routine", 5), 5)

    def test_critical_point_keeps_every_sample(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            downsample("spo2", "critical", 5)
        self.assertEqual(blocked.exception.args[0], "sample-critical-forbidden")
        self.assertEqual(downsample("spo2", "critical", 1), 1)

    def test_points_fit_the_budget(self) -> None:
        self.assertEqual(point_capacity(2, 5, 20), 10)

    def test_points_over_budget_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            point_capacity(5, 5, 20)
        self.assertEqual(blocked.exception.args[0], "capacity-exceeded")


if __name__ == "__main__":
    unittest.main()
