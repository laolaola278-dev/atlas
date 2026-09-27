"""Tests for the startup health probe."""
import unittest

from internal.contract.errors import ContractError
from internal.contract.health import HealthLedger, probe
from internal.contract._path import install_contract_path
from tools.evidence.p0_index import require_complete

install_contract_path()


def payload() -> dict[str, str]:
    return {
        "audit_stream": "audit-stream",
        "campus_id": "campus-synthetic",
        "policy_version": "1.0.0",
        "secret_ref": "secret://atlas/signing-key",
        "tenant_id": "tenant-synthetic",
    }


class HealthProbeTests(unittest.TestCase):
    def test_probe_names_are_stable(self) -> None:
        self.assertEqual(probe.__module__, "internal.contract.health")
        self.assertTrue(callable(probe))

    def test_complete_config_is_ready(self) -> None:
        result = probe(payload())
        self.assertTrue(result["ready"])
        self.assertEqual(result["status"], "ok")
        self.assertGreater(int(str(result["indexed_batches"])), 0)

    def test_incomplete_config_is_not_ready(self) -> None:
        broken = payload()
        broken["policy_version"] = ""
        with self.assertRaises(ContractError) as blocked:
            probe(broken)
        self.assertEqual(str(blocked.exception), "config-incomplete")

    def test_inline_secret_is_not_ready(self) -> None:
        leaked = payload()
        leaked["api_token"] = "sk-synthetic"
        with self.assertRaises(ContractError) as blocked:
            probe(leaked)
        self.assertEqual(str(blocked.exception), "config-secret-inline")

    def test_unknown_reason_is_not_ready(self) -> None:
        unknown = payload()
        unknown["why_code"] = "unknown"
        with self.assertRaises(ContractError) as blocked:
            probe(unknown)
        self.assertEqual(str(blocked.exception), "health-why-missing")

    def test_index_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_complete(why_code="unknown")
        self.assertEqual(str(blocked.exception), "evidence-index-why-missing")
        self.assertGreater(require_complete(), 0)

    def test_other_actor_for_same_startup_is_rejected(self) -> None:
        ledger = HealthLedger()
        first = payload()
        first["actor_id"] = "reviewer-synthetic"
        self.assertTrue(ledger.probe(first)["ready"])
        other = payload()
        other["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ledger.probe(other)
        self.assertEqual(str(blocked.exception), "health-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
