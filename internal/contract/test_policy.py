"""Fail-closed tests for policy decisions and idempotent writes."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.idempotency import IdempotencyLog  # noqa: E402
from internal.contract.policy import PolicyLedger, evaluate  # noqa: E402


def allowed_request() -> dict[str, object]:
    return {
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "purpose_code": "treatment",
        "policy_version": "1.0.0",
        "action": "review",
        "emergency": False,
        "fields": frozenset(),
    }


class PolicyTests(unittest.TestCase):
    def test_complete_request_allows_and_names_policy_version(self) -> None:
        decision = evaluate(allowed_request())
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.policy_version, "1.0.0")
        self.assertEqual(decision.reason_codes, ("allowed",))

    def test_unknown_field_missing_purpose_and_emergency_are_denied(self) -> None:
        unknown = allowed_request()
        unknown["note"] = "free text"
        self.assertEqual(evaluate(unknown).reason_codes, ("unknown-field",))
        missing = allowed_request()
        missing["purpose_code"] = ""
        self.assertIn("purpose-missing", evaluate(missing).reason_codes)
        emergency = allowed_request()
        emergency["emergency"] = True
        decision = evaluate(emergency)
        self.assertFalse(decision.allowed)
        self.assertIn("emergency-reason-missing", decision.reason_codes)

    def test_withdrawn_consent_is_denied_without_emergency(self) -> None:
        withdrawn = allowed_request()
        withdrawn["consent_state"] = "withdrawn"
        decision = evaluate(withdrawn)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("consent-not-active",))
        emergency = allowed_request()
        emergency["consent_state"] = "withdrawn"
        emergency["emergency"] = True
        emergency["fields"] = frozenset({"emergency-reason"})
        self.assertTrue(evaluate(emergency).allowed)

    def test_skipped_policy_version_is_denied(self) -> None:
        skipped = allowed_request()
        skipped["policy_version"] = "1.2"
        decision = evaluate(skipped)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("policy-version-incompatible",))

    def test_identifier_scope_is_denied(self) -> None:
        named = allowed_request()
        named["tenant_id"] = "subject.identifier"
        decision = evaluate(named)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("policy-identifier-forbidden",))

    def test_unknown_reason_is_denied(self) -> None:
        unknown = allowed_request()
        unknown["why_code"] = "unknown"
        decision = evaluate(unknown)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("actor-why-missing",))

    def test_other_actor_for_same_scope_is_denied(self) -> None:
        ledger = PolicyLedger()
        first = allowed_request()
        first["actor_id"] = "reviewer-synthetic"
        first["resource_id"] = "observation-synthetic"
        self.assertTrue(ledger.evaluate(first).allowed)
        other = allowed_request()
        other["actor_id"] = "other-reviewer"
        other["resource_id"] = "observation-synthetic"
        decision = ledger.evaluate(other)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason_codes, ("policy-responsibility-mismatch",))


class IdempotencyTests(unittest.TestCase):
    def test_same_key_replays_but_different_payload_conflicts(self) -> None:
        log = IdempotencyLog()
        first = log.begin("key-1", "digest-a")
        replay = log.begin("key-1", "digest-a")
        self.assertEqual(first, replay)
        with self.assertRaises(ContractError) as conflict:
            log.begin("key-1", "digest-b")
        self.assertEqual(str(conflict.exception), "idempotency-conflict")

    def test_unknown_result_cannot_be_retried_or_committed(self) -> None:
        log = IdempotencyLog()
        log.begin("key-2", "digest-a")
        log.mark_unknown("key-2")
        with self.assertRaises(ContractError) as retry:
            log.begin("key-2", "digest-a")
        self.assertEqual(str(retry.exception), "result-unknown")
        with self.assertRaises(ContractError):
            log.mark_committed("key-2")

    def test_blank_key_is_rejected(self) -> None:
        log = IdempotencyLog()
        with self.assertRaises(ContractError) as invalid:
            log.begin("", "digest-a")
        self.assertEqual(str(invalid.exception), "idempotency-key-invalid")


if __name__ == "__main__":
    unittest.main()
