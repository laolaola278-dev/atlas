"""Clinical practitioner simulation tests against the audit hash chain.

Every fixture is synthetic. Tests assert the chain accepts well-formed
clinical workflows, links every step, detects tampering in clinical events,
and keeps the emergency stream separate from the ordinary commit path.
"""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from internal.audit.chain import GENESIS, AuditLog  # noqa: E402
from internal.audit.clinical_simulation import (  # noqa: E402
    attending_ordinary_workflow,
    emergency_break_glass_workflow,
    pharmacist_verification_workflow,
)
from internal.contract.errors import ContractError  # noqa: E402


class AttendingWorkflowTests(unittest.TestCase):
    def test_ordinary_workflow_records_five_linked_events(self) -> None:
        log, events = attending_ordinary_workflow()
        self.assertEqual(len(events), 5)
        self.assertEqual(events[0].previous_hash, GENESIS)
        for previous, current in zip(events, events[1:]):
            self.assertEqual(current.previous_hash, previous.event_hash)
        self.assertEqual([event.sequence for event in events], [1, 2, 3, 4, 5])
        log.verify()

    def test_approval_step_is_signed_by_physician(self) -> None:
        _, events = attending_ordinary_workflow()
        approval = events[3]
        self.assertEqual(approval.operation, "approve")
        self.assertEqual(approval.actor_role, "attending")
        self.assertEqual(approval.why_code, "approval-signed")
        self.assertEqual(approval.consent_decision, "granted")

    def test_tampered_approval_breaks_chain(self) -> None:
        log, _ = attending_ordinary_workflow()
        original = log.events[3]
        log._events[3] = original.__class__(**{**original.__dict__, "actor_id": "impostor-synthetic"})
        with self.assertRaises(ContractError) as broken:
            log.verify()
        self.assertEqual(str(broken.exception), "audit-hash-mismatch")


class EmergencyWorkflowTests(unittest.TestCase):
    def test_break_glass_records_three_events(self) -> None:
        log, events = emergency_break_glass_workflow()
        self.assertEqual(len(events), 3)
        self.assertEqual(events[0].purpose_code, "emergency-treatment")
        self.assertEqual(events[1].operation, "emergency-act")
        self.assertEqual(events[2].operation, "post-review-request")
        log.verify()

    def test_emergency_stream_does_not_mix_with_ordinary_stream(self) -> None:
        emergency_log, _ = emergency_break_glass_workflow()
        ordinary_log, _ = attending_ordinary_workflow()
        with self.assertRaises(ContractError) as crossed:
            emergency_log.append({
                "event_id": "crossed-synthetic",
                "stream_id": ordinary_log.stream_id,
                "sequence": 4,
                "tenant_id": "tenant-synthetic",
                "campus_id": "campus-synthetic",
                "actor_id": "er-physician-synthetic",
                "actor_role": "emergency-attending",
                "operation": "writeback-commit",
                "resource_type": "Order",
                "resource_id": "order-synthetic",
                "purpose_code": "treatment",
                "why_code": "writeback-committed",
                "policy_version": "1.0.0",
                "occurred_at": "2026-10-04T08:00:00Z",
                "payload_digest": "b" * 64,
                "clock_quality": "synchronized",
                "consent_decision": "granted",
            })
        self.assertEqual(str(crossed.exception), "audit-stream-mismatch")

    def test_emergency_event_without_why_is_rejected(self) -> None:
        log = AuditLog("stream-emergency-synthetic")
        with self.assertRaises(ContractError) as missing:
            log.append({
                "event_id": "emergency-event-synthetic",
                "stream_id": "stream-emergency-synthetic",
                "sequence": 1,
                "tenant_id": "tenant-synthetic",
                "campus_id": "campus-synthetic",
                "actor_id": "er-physician-synthetic",
                "actor_role": "emergency-attending",
                "operation": "emergency-act",
                "resource_type": "MedicationOrder",
                "resource_id": "emergency-order-synthetic",
                "purpose_code": "emergency-treatment",
                "why_code": "",
                "policy_version": "1.0.0",
                "occurred_at": "2026-10-04T08:00:00Z",
                "payload_digest": "b" * 64,
                "clock_quality": "synchronized",
            })
        self.assertEqual(str(missing.exception), "audit-why-missing")


class PharmacistWorkflowTests(unittest.TestCase):
    def test_pharmacy_workflow_records_interaction_check(self) -> None:
        log, events = pharmacist_verification_workflow()
        self.assertEqual(len(events), 3)
        check = events[1]
        self.assertEqual(check.operation, "interaction-check")
        self.assertEqual(check.actor_role, "system")
        self.assertEqual(check.why_code, "hard-rule-evaluated")
        final = events[2]
        self.assertEqual(final.actor_role, "pharmacist")
        self.assertEqual(final.operation, "dispense-approve")
        log.verify()

    def test_deleted_event_breaks_chain(self) -> None:
        log, _ = pharmacist_verification_workflow()
        del log._events[1]
        with self.assertRaises(ContractError) as broken:
            log.verify()
        self.assertEqual(str(broken.exception), "audit-chain-broken")


if __name__ == "__main__":
    unittest.main()
