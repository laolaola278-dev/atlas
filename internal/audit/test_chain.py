"""Tamper tests for the audit hash chain."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from internal.audit.chain import GENESIS, AuditLog, to_fhir_audit_event  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def event(sequence: int, operation: str = "review") -> dict[str, object]:
    return {
        "event_id": f"event-{sequence}",
        "stream_id": "stream-synthetic",
        "sequence": sequence,
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "actor_id": "reviewer-synthetic",
        "actor_role": "attending",
        "operation": operation,
        "resource_type": "Suggestion",
        "resource_id": "suggestion-synthetic",
        "purpose_code": "treatment",
        "why_code": "review-decision",
        "policy_version": "1.0.0",
        "occurred_at": "2026-09-24T00:00:00Z",
        "payload_digest": "a" * 64,
        "clock_quality": "synchronized",
    }


class AuditChainTests(unittest.TestCase):
    def test_append_links_previous_hash_and_verifies(self) -> None:
        log = AuditLog("stream-synthetic")
        first = log.append(event(1))
        second = log.append(event(2, "commit"))
        self.assertEqual(first.previous_hash, GENESIS)
        self.assertEqual(second.previous_hash, first.event_hash)
        log.verify()

    def test_missing_why_and_skipped_sequence_are_rejected(self) -> None:
        log = AuditLog("stream-synthetic")
        missing = event(1)
        missing["why_code"] = ""
        with self.assertRaises(ContractError) as why:
            log.append(missing)
        self.assertEqual(str(why.exception), "audit-why-missing")
        with self.assertRaises(ContractError) as sequence:
            log.append(event(2))
        self.assertEqual(str(sequence.exception), "audit-sequence-invalid")
        self.assertEqual(log.events, ())

    def test_changed_actor_breaks_verification(self) -> None:
        log = AuditLog("stream-synthetic")
        log.append(event(1))
        original = log.events[0]
        tampered = original.__class__(**{**original.__dict__, "actor_id": "other-user"})
        log._events[0] = tampered
        with self.assertRaises(ContractError) as broken:
            log.verify()
        self.assertEqual(str(broken.exception), "audit-hash-mismatch")

    def test_skipped_policy_version_is_rejected(self) -> None:
        log = AuditLog("stream-synthetic")
        skipped = event(1)
        skipped["policy_version"] = "1.2"
        with self.assertRaises(ContractError) as blocked:
            log.append(skipped)
        self.assertEqual(str(blocked.exception), "audit-version-incompatible")
        self.assertEqual(log.events, ())

    def test_identifier_actor_is_rejected(self) -> None:
        log = AuditLog("stream-synthetic")
        named = event(1)
        named["actor_id"] = "subject.identifier"
        with self.assertRaises(ContractError) as blocked:
            log.append(named)
        self.assertEqual(str(blocked.exception), "audit-identifier-forbidden")
        self.assertEqual(log.events, ())

    def test_identifier_stream_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            AuditLog("subject.identifier")
        self.assertEqual(str(blocked.exception), "audit-identifier-forbidden")

    def test_fhir_mapping_keeps_codes_and_digest(self) -> None:
        log = AuditLog("stream-synthetic")
        mapped = to_fhir_audit_event(log.append(event(1)))
        self.assertEqual(mapped["resourceType"], "AuditEvent")
        self.assertEqual(mapped["action"], "review")
        self.assertEqual(len(str(mapped["entityDigest"])), 64)
        self.assertNotIn("actor_id", mapped)
        self.assertNotIn("resource_id", mapped)


if __name__ == "__main__":
    unittest.main()
