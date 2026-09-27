"""Tests for startup configuration rejection."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.config import config_signature, load_config  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def config() -> dict[str, str]:
    return {
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "policy_version": "1.0.0",
        "audit_stream": "audit-stream",
        "secret_ref": "secret://atlas/signing-key",
    }


class ConfigTests(unittest.TestCase):
    def test_reference_based_config_loads(self) -> None:
        loaded = load_config(config())
        self.assertEqual(loaded.policy_version, "1.0.0")
        self.assertTrue(loaded.secret_ref.startswith("secret://"))

    def test_inline_secret_and_missing_scope_are_rejected(self) -> None:
        leaked = config()
        leaked["api_token"] = "sk-synthetic"
        with self.assertRaises(ContractError) as secret:
            load_config(leaked)
        self.assertEqual(str(secret.exception), "config-secret-inline")
        missing = config()
        missing["policy_version"] = ""
        with self.assertRaises(ContractError) as incomplete:
            load_config(missing)
        self.assertEqual(str(incomplete.exception), "config-incomplete")
        bad_ref = config()
        bad_ref["secret_ref"] = "plain-value"
        with self.assertRaises(ContractError):
            load_config(bad_ref)

    def test_skipped_policy_version_is_rejected(self) -> None:
        skipped = config()
        skipped["policy_version"] = "1.2"
        with self.assertRaises(ContractError) as blocked:
            load_config(skipped)
        self.assertEqual(str(blocked.exception), "config-version-incompatible")

    def test_identifier_scope_is_rejected(self) -> None:
        named = config()
        named["tenant_id"] = "subject.identifier"
        with self.assertRaises(ContractError) as blocked:
            load_config(named)
        self.assertEqual(str(blocked.exception), "config-identifier-forbidden")

    def test_distinct_config_signature_is_accepted(self) -> None:
        signed = config_signature("ab" * 32, "cd" * 32)
        self.assertEqual(signed["signature"], "cd" * 32)
        self.assertNotIn("secret", signed)

    def test_same_config_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            config_signature("ab" * 32, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "config-signature-same")


if __name__ == "__main__":
    unittest.main()
