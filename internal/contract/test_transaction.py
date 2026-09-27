"""Tests for transaction watermarks and unknown results."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.transaction import TransactionWatermark  # noqa: E402


class TransactionWatermarkTests(unittest.TestCase):
    def test_committed_write_advances_watermark_once(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        first = stream.begin("proof-1", "a" * 64)
        committed = stream.commit("proof-1")
        replayed = stream.begin("proof-1", "a" * 64)
        self.assertEqual(committed.sequence, first.sequence)
        self.assertEqual(replayed, committed)
        self.assertEqual(stream.watermark(), 1)

    def test_unknown_result_does_not_advance_or_replay(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        stream.begin("proof-unknown", "b" * 64)
        unknown = stream.mark_unknown("proof-unknown")
        self.assertEqual(unknown.state, "unknown")
        self.assertEqual(stream.watermark(), 0)
        with self.assertRaises(ContractError) as replayed:
            stream.begin("proof-unknown", "b" * 64)
        self.assertEqual(str(replayed.exception), "transaction-result-unknown")
        with self.assertRaises(ContractError) as committed:
            stream.commit("proof-unknown")
        self.assertEqual(str(committed.exception), "transaction-result-unknown")

    def test_changed_payload_conflicts_before_commit(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        stream.begin("proof-conflict", "c" * 64)
        with self.assertRaises(ContractError) as conflict:
            stream.begin("proof-conflict", "d" * 64)
        self.assertEqual(str(conflict.exception), "transaction-conflict")
        self.assertEqual(stream.watermark(), 0)

    def test_identifier_key_is_rejected(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        with self.assertRaises(ContractError) as blocked:
            stream.begin("subject.identifier", "e" * 64)
        self.assertEqual(str(blocked.exception), "transaction-identifier-forbidden")
        self.assertEqual(stream.watermark(), 0)

    def test_identifier_stream_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            TransactionWatermark("subject.identifier")
        self.assertEqual(str(blocked.exception), "transaction-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        with self.assertRaises(ContractError) as blocked:
            stream.begin("proof-1", "f" * 64, why_code="unknown")
        self.assertEqual(str(blocked.exception), "transaction-why-missing")
        self.assertEqual(stream.watermark(), 0)

    def test_replay_with_other_actor_is_rejected(self) -> None:
        stream = TransactionWatermark("stream-synthetic")
        stream.begin("proof-actor", "a" * 64, "reviewer-synthetic", "treatment-review")
        stream.commit("proof-actor")
        with self.assertRaises(ContractError) as blocked:
            stream.begin("proof-actor", "a" * 64, "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "transaction-responsibility-mismatch")
        self.assertEqual(stream.watermark(), 1)


if __name__ == "__main__":
    unittest.main()
