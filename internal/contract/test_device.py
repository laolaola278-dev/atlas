"""Tests for device identity certificates."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.device import (  # noqa: E402
    device_certificate,
    edge_clock,
    ingest_inventory,
    isolate_fault,
    mqtt_session,
    offline_buffer,
    partition_rehearsal,
    upgrade_rollback,
)
from internal.contract.errors import ContractError  # noqa: E402


class DeviceCertificateTests(unittest.TestCase):
    def test_active_certificate_keeps_digest(self) -> None:
        issued = device_certificate("device-synthetic", "ab" * 32, False)
        self.assertEqual(issued["state"], "active")
        self.assertNotIn("pem", issued)

    def test_expired_certificate_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            device_certificate("device-synthetic", "ab" * 32, True)
        self.assertEqual(blocked.exception.args[0], "device-certificate-expired")

    def test_identifier_device_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            device_certificate("subject.identifier", "ab" * 32, False)
        self.assertEqual(str(blocked.exception), "device-id-forbidden")

    def test_clean_session_uses_allowed_topic(self) -> None:
        session = mqtt_session("device-synthetic", "points/hr", True)
        self.assertEqual(session["clean"], "true")

    def test_other_topic_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            mqtt_session("device-synthetic", "patient/name", True)
        self.assertEqual(blocked.exception.args[0], "mqtt-topic-forbidden")

    def test_dirty_session_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            mqtt_session("device-synthetic", "points/hr", False)
        self.assertEqual(str(blocked.exception), "mqtt-session-dirty")

    def test_small_edge_skew_is_synced(self) -> None:
        self.assertEqual(edge_clock(50), "synced")

    def test_medium_edge_skew_is_degraded(self) -> None:
        self.assertEqual(edge_clock(500), "degraded")

    def test_large_edge_skew_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            edge_clock(1001)
        self.assertEqual(blocked.exception.args[0], "edge-clock-rejected")

    def test_offline_queue_stays_inside_limit(self) -> None:
        self.assertEqual(offline_buffer(False, 3, 5), 3)

    def test_online_queue_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            offline_buffer(True, 1, 5)
        self.assertEqual(blocked.exception.args[0], "buffer-online-forbidden")

    def test_queue_over_limit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            offline_buffer(False, 6, 5)
        self.assertEqual(str(blocked.exception), "buffer-overflow")

    def test_same_partition_continues(self) -> None:
        self.assertEqual(partition_rehearsal("zone-a", "zone-a"), "zone-a")

    def test_split_partition_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            partition_rehearsal("zone-a", "zone-b")
        self.assertEqual(blocked.exception.args[0], "partition-split")

    def test_edge_can_roll_back_one_minor(self) -> None:
        self.assertEqual(upgrade_rollback("1.1", "1.0"), "1.0")

    def test_edge_cannot_skip_a_rollback(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            upgrade_rollback("1.0", "1.1")
        self.assertEqual(blocked.exception.args[0], "upgrade-rollback-forbidden")

    def test_faulty_device_stays_isolated(self) -> None:
        self.assertEqual(isolate_fault("device-synthetic", False, "isolated"), "isolated")

    def test_faulty_device_cannot_use_healthy_stream(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            isolate_fault("device-synthetic", False, "healthy")
        self.assertEqual(blocked.exception.args[0], "fault-not-isolated")

    def test_matching_inventory_is_accepted(self) -> None:
        self.assertEqual(ingest_inventory(("device-a", "device-b"), ("device-b", "device-a")), 2)

    def test_missing_device_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            ingest_inventory(("device-a", "device-b"), ("device-a",))
        self.assertEqual(blocked.exception.args[0], "inventory-mismatch")


if __name__ == "__main__":
    unittest.main()
