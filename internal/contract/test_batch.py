"""Tests for bounded batches and transfer allow-lists."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.batch import (  # noqa: E402
    Batch,
    SecondWriter,
    SourceLimiter,
    reconcile_loss,
    resume_at,
    shard_for,
)
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.transfer import TransferLedger, check_transfer  # noqa: E402


class BatchTests(unittest.TestCase):
    def test_capacity_and_cancellation_stop_growth(self) -> None:
        batch = Batch(2)
        batch.add("item-1")
        batch.add("item-2")
        with self.assertRaises(ContractError) as full:
            batch.add("item-3")
        self.assertEqual(str(full.exception), "batch-backpressure")
        batch.cancel()
        with self.assertRaises(ContractError) as cancelled:
            batch.add("item-4")
        self.assertEqual(str(cancelled.exception), "batch-cancelled")
        self.assertEqual(batch.finish().accepted, 2)

    def test_withdrawn_consent_rejects_new_item(self) -> None:
        batch = Batch(2)
        with self.assertRaises(ContractError) as blocked:
            batch.add("item-withdrawn", "withdrawn")
        self.assertEqual(str(blocked.exception), "batch-consent-not-active")
        self.assertEqual(batch.finish().accepted, 0)

    def test_identifier_item_is_rejected(self) -> None:
        batch = Batch(2)
        with self.assertRaises(ContractError) as blocked:
            batch.add("subject.identifier")
        self.assertEqual(str(blocked.exception), "batch-identifier-forbidden")
        self.assertEqual(batch.finish().accepted, 0)

    def test_unknown_reason_is_rejected(self) -> None:
        batch = Batch(2)
        with self.assertRaises(ContractError) as blocked:
            batch.add("item-1", why_code="unknown")
        self.assertEqual(str(blocked.exception), "batch-why-missing")
        self.assertEqual(batch.finish().accepted, 0)

    def test_other_actor_for_same_item_is_rejected(self) -> None:
        batch = Batch(2)
        batch.add("item-1", actor_id="reviewer-synthetic", why_code="treatment-review")
        with self.assertRaises(ContractError) as blocked:
            batch.add("item-1", actor_id="other-reviewer", why_code="treatment-review")
        self.assertEqual(str(blocked.exception), "batch-responsibility-mismatch")
        self.assertEqual(batch.finish().accepted, 1)

    def test_zero_capacity_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            Batch(0)

    def test_unknown_import_does_not_advance(self) -> None:
        batch = Batch(2)
        batch.add("item-1")
        with self.assertRaises(ContractError) as unknown:
            batch.advance("item-1", "unknown")
        self.assertEqual(unknown.exception.args[0], "import-result-unknown")
        self.assertEqual(batch.advance("item-1", "committed"), 1)
        self.assertEqual(batch.advance("item-1", "committed"), 1)

    def test_unseen_import_item_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            Batch(2).advance("item-missing", "committed")
        self.assertEqual(str(blocked.exception), "import-item-unknown")

    def test_hot_key_is_rejected(self) -> None:
        chosen = shard_for("campus-synthetic", 8, 3)
        self.assertIn(chosen, range(8))
        with self.assertRaises(ContractError) as blocked:
            shard_for("campus-synthetic", 8, 100)
        self.assertEqual(blocked.exception.args[0], "shard-hot-key")

    def test_identifier_key_cannot_choose_a_shard(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            shard_for("subject.identifier", 8, 1)
        self.assertEqual(str(blocked.exception), "shard-key-forbidden")

    def test_source_limit_stops_further_messages(self) -> None:
        limiter = SourceLimiter(1)
        self.assertEqual(limiter.admit("feed-synthetic"), 1)
        with self.assertRaises(ContractError) as blocked:
            limiter.admit("feed-synthetic")
        self.assertEqual(blocked.exception.args[0], "limit-backpressure")

    def test_identifier_source_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            SourceLimiter(2).admit("subject.identifier")
        self.assertEqual(str(blocked.exception), "limit-source-forbidden")

    def test_one_second_stops_at_its_limit(self) -> None:
        writer = SecondWriter(1)
        self.assertEqual(writer.write(1_700_000_000), 1)
        with self.assertRaises(ContractError) as blocked:
            writer.write(1_700_000_000)
        self.assertEqual(blocked.exception.args[0], "second-backpressure")
        self.assertEqual(writer.write(1_700_000_001), 1)

    def test_negative_epoch_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            SecondWriter(2).write(-1)
        self.assertEqual(str(blocked.exception), "second-epoch-invalid")

    def test_resume_continues_after_commit(self) -> None:
        self.assertEqual(resume_at(4, 5), 5)

    def test_resume_cannot_repeat_a_commit(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            resume_at(4, 4)
        self.assertEqual(blocked.exception.args[0], "resume-already-committed")

    def test_resume_cannot_skip(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            resume_at(4, 6)
        self.assertEqual(str(blocked.exception), "resume-gap")

    def test_matching_digests_reconcile(self) -> None:
        self.assertEqual(reconcile_loss(("ab" * 32,), ("ab" * 32,)), 1)

    def test_missing_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            reconcile_loss(("ab" * 32, "cd" * 32), ("ab" * 32,))
        self.assertEqual(blocked.exception.args[0], "reconcile-missing")

    def test_extra_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            reconcile_loss(("ab" * 32,), ("ab" * 32, "cd" * 32))
        self.assertEqual(str(blocked.exception), "reconcile-extra")


class TransferTests(unittest.TestCase):
    def test_declared_export_fields_are_accepted(self) -> None:
        accepted = check_transfer("export", {"code", "value", "status"})
        self.assertEqual(accepted, frozenset({"code", "value", "status"}))

    def test_identifier_and_import_status_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as forbidden:
            check_transfer("export", {"code", "name"})
        self.assertEqual(str(forbidden.exception), "transfer-field-forbidden")
        with self.assertRaises(ContractError):
            check_transfer("import", {"status"})

    def test_withdrawn_consent_rejects_transfer(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            check_transfer("export", {"code", "value"}, "withdrawn")
        self.assertEqual(str(blocked.exception), "transfer-consent-not-active")

    def test_nested_identifier_path_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            check_transfer("export", {"code", "subject.identifier"})
        self.assertEqual(str(blocked.exception), "transfer-field-forbidden")

    def test_missing_scope_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            check_transfer("export", {"code"}, tenant_id="")
        self.assertEqual(str(blocked.exception), "transfer-scope-incomplete")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            check_transfer("export", {"code"}, why_code="unknown")
        self.assertEqual(str(blocked.exception), "transfer-why-missing")

    def test_other_actor_for_same_transfer_is_rejected(self) -> None:
        ledger = TransferLedger()
        ledger.check("export", {"code"}, actor_id="reviewer-synthetic")
        with self.assertRaises(ContractError) as blocked:
            ledger.check("export", {"code"}, actor_id="other-reviewer")
        self.assertEqual(str(blocked.exception), "transfer-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
