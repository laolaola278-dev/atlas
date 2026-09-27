"""Consumer tests for stable contract errors."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.consumer import consume, consumer_contract  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


class ContractConsumerTests(unittest.TestCase):
    def test_unknown_result_is_reconciled(self) -> None:
        self.assertEqual(consume("result-unknown", "trace-synthetic"), "reconcile")

    def test_validation_error_stops(self) -> None:
        self.assertEqual(consume("resource-version-missing", "trace-synthetic"), "stop")

    def test_forbidden_error_cannot_be_retried(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            consume("approval-missing", "trace-synthetic")
        self.assertEqual(blocked.exception.args[0], "consumer-forbidden-retry")

    def test_unknown_code_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            consume("free-text", "trace-synthetic")
        self.assertEqual(str(blocked.exception), "error-code-unknown")

    def test_conflict_cannot_be_retried(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            consume("version-conflict", "trace-synthetic")
        self.assertEqual(str(blocked.exception), "consumer-conflict-retry")

    def test_matching_contract_is_accepted(self) -> None:
        accepted = consumer_contract("1.0", "treatment", "ab" * 32)
        self.assertEqual(accepted["purpose"], "treatment")

    def test_unknown_purpose_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            consumer_contract("1.0", "marketing", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "consumer-purpose-rejected")

    def test_short_contract_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            consumer_contract("1.0", "treatment", "abcd")
        self.assertEqual(str(blocked.exception), "consumer-digest-invalid")


if __name__ == "__main__":
    unittest.main()
