"""Tests for HL7 v2 segment boundaries."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.segment import (  # noqa: E402
    MessageIdempotency,
    acknowledge,
    clock_skew,
    coding_matrix,
    ingest_audit,
    parse_segments,
    point_schema,
    probe_state,
    require_pid,
    route_tenant,
    seal_message,
)


class SegmentTests(unittest.TestCase):
    def test_allowed_segments_keep_order(self) -> None:
        parsed = parse_segments(("MSH", "EVN", "OBR", "OBX"))
        self.assertEqual(parsed, ("MSH", "EVN", "OBR", "OBX"))

    def test_identifier_segment_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            parse_segments(("MSH", "PID"))
        self.assertEqual(blocked.exception.args[0], "segment-identifier-forbidden")

    def test_missing_header_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            parse_segments(("OBX",))
        self.assertEqual(str(blocked.exception), "segment-header-missing")

    def test_missing_pid_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_pid(("MSH", "OBX"), "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "pid-missing")

    def test_pid_requires_a_digest(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_pid(("MSH", "PID"), "abcd")
        self.assertEqual(str(blocked.exception), "pid-digest-invalid")

    def test_pid_digest_is_kept_without_fields(self) -> None:
        self.assertEqual(require_pid(("MSH", "PID"), "ab" * 32), "ab" * 32)

    def test_same_message_is_duplicate(self) -> None:
        gate = MessageIdempotency()
        self.assertEqual(gate.accept("ctl-synthetic", "ab" * 32), "accepted")
        self.assertEqual(gate.accept("ctl-synthetic", "ab" * 32), "duplicate")

    def test_same_control_id_with_other_digest_conflicts(self) -> None:
        gate = MessageIdempotency()
        gate.accept("ctl-synthetic", "ab" * 32)
        with self.assertRaises(ContractError) as blocked:
            gate.accept("ctl-synthetic", "cd" * 32)
        self.assertEqual(blocked.exception.args[0], "message-conflict")

    def test_small_skew_is_reported(self) -> None:
        self.assertEqual(clock_skew(1_700_000_000, 1_700_000_120), 120)

    def test_large_skew_is_isolated(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            clock_skew(1_700_000_000, 1_700_000_301)
        self.assertEqual(blocked.exception.args[0], "clock-skew-isolated")

    def test_accepted_message_returns_aa(self) -> None:
        ack = acknowledge("ctl-synthetic", "accepted", "ab" * 32)
        self.assertEqual(ack["code"], "AA")

    def test_rejected_message_returns_ar(self) -> None:
        ack = acknowledge("ctl-synthetic", "rejected", "ab" * 32)
        self.assertEqual(ack["code"], "AR")

    def test_unknown_ack_is_not_success(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            acknowledge("ctl-synthetic", "unknown", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "ack-result-unknown")

    def test_source_routes_to_one_tenant(self) -> None:
        tenant = route_tenant("feed-synthetic", {"feed-synthetic": "tenant-synthetic"})
        self.assertEqual(tenant, "tenant-synthetic")

    def test_unknown_source_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            route_tenant("feed-other", {"feed-synthetic": "tenant-synthetic"})
        self.assertEqual(blocked.exception.args[0], "route-tenant-unknown")

    def test_shared_tenant_route_is_rejected(self) -> None:
        routes = {"feed-a": "tenant-synthetic", "feed-b": "tenant-synthetic"}
        with self.assertRaises(ContractError) as blocked:
            route_tenant("feed-a", routes)
        self.assertEqual(str(blocked.exception), "route-tenant-shared")

    def test_registered_coding_is_accepted(self) -> None:
        count = coding_matrix({"code": "ab" * 32, "system": "cd" * 32}, frozenset({"ab" * 32, "cd" * 32}))
        self.assertEqual(count, 2)

    def test_unknown_coding_is_dirty(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            coding_matrix({"code": "ef" * 32}, frozenset({"ab" * 32}))
        self.assertEqual(blocked.exception.args[0], "coding-dirty")

    def test_identifier_coding_field_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            coding_matrix({"identifier": "ab" * 32}, frozenset({"ab" * 32}))
        self.assertEqual(str(blocked.exception), "coding-field-invalid")

    def test_message_is_sealed_without_body(self) -> None:
        sealed = seal_message("ab" * 32, "")
        self.assertTrue(sealed["sealed"])
        self.assertFalse(sealed["body_kept"])

    def test_message_body_cannot_be_sealed(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            seal_message("ab" * 32, "MSH|synthetic")
        self.assertEqual(blocked.exception.args[0], "seal-body-forbidden")

    def test_ingest_audit_keeps_action_and_digest(self) -> None:
        record = ingest_audit("feed-synthetic", "accept", "ab" * 32)
        self.assertEqual(record["operation"], "accept")
        self.assertNotIn("body", record)

    def test_unknown_ingest_operation_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            ingest_audit("feed-synthetic", "merge", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "ingest-audit-invalid")

    def test_declared_point_keeps_its_unit(self) -> None:
        declared = point_schema("hr", "1/min", True)
        self.assertEqual(declared["unit"], "1/min")

    def test_wrong_point_unit_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            point_schema("spo2", "1/min", True)
        self.assertEqual(blocked.exception.args[0], "point-unit-mismatch")

    def test_unknown_point_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            point_schema("name", "%", True)
        self.assertEqual(str(blocked.exception), "point-unknown")

    def test_detached_probe_has_no_value(self) -> None:
        self.assertEqual(probe_state("spo2", True, None), "detached")

    def test_detached_probe_cannot_carry_a_value(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            probe_state("spo2", True, 98)
        self.assertEqual(blocked.exception.args[0], "probe-value-forbidden")

    def test_attached_probe_requires_a_value(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            probe_state("hr", False, None)
        self.assertEqual(str(blocked.exception), "probe-value-missing")


if __name__ == "__main__":
    unittest.main()
