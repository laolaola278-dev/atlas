"""Tests for offline import signatures."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.offline import offline_signature  # noqa: E402


class OfflineSignatureTests(unittest.TestCase):
    def test_distinct_digests_are_accepted(self) -> None:
        signed = offline_signature("ab" * 32, "cd" * 32, "signer-synthetic")
        self.assertEqual(signed["signer"], "signer-synthetic")
        self.assertNotIn("key", signed)

    def test_same_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            offline_signature("ab" * 32, "ab" * 32, "signer-synthetic")
        self.assertEqual(blocked.exception.args[0], "offline-signature-same")

    def test_identifier_signer_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            offline_signature("ab" * 32, "cd" * 32, "subject.identifier")
        self.assertEqual(str(blocked.exception), "offline-signer-forbidden")

    def test_short_signature_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            offline_signature("ab" * 32, "abcd", "signer-synthetic")
        self.assertEqual(str(blocked.exception), "offline-digest-invalid")


if __name__ == "__main__":
    unittest.main()
