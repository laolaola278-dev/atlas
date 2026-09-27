"""Tests for reloadable, tamper-evident audit files."""
import tempfile
import unittest
from pathlib import Path

from internal.contract._path import install_contract_path

install_contract_path()
from internal.audit.file import AuditFile  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


def fields(sequence: int) -> dict[str, object]:
    return {
        "event_id": f"event-{sequence}",
        "stream_id": "audit-file",
        "sequence": sequence,
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "actor_id": "reviewer-synthetic",
        "actor_role": "attending",
        "operation": "review",
        "resource_type": "Suggestion",
        "resource_id": "suggestion-synthetic",
        "purpose_code": "treatment",
        "why_code": "review-decision",
        "policy_version": "1.0.0",
        "occurred_at": "2026-09-24T00:00:00Z",
        "payload_digest": "a" * 64,
        "clock_quality": "synchronized",
    }


class AuditFileTests(unittest.TestCase):
    def test_reloaded_file_verifies_the_same_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            original = AuditFile(path, "audit-file")
            original.append(fields(1))
            original.append(fields(2))
            loaded = AuditFile(path, "audit-file")
            self.assertEqual(
                [event.event_hash for event in loaded.log.events],
                [event.event_hash for event in original.log.events],
            )
            loaded.log.verify()

    def test_repeated_reload_does_not_rewrite_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            original = AuditFile(path, "audit-file")
            original.append(fields(1))
            original.append(fields(2))
            written = len(path.read_text(encoding="utf-8").splitlines())
            self.assertEqual(written, 2)
            first = AuditFile(path, "audit-file")
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), written)
            second = AuditFile(path, "audit-file")
            self.assertEqual(len(second.log.events), len(first.log.events))
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), written)
            second.append(fields(3))
            third = AuditFile(path, "audit-file")
            self.assertEqual([event.event_id for event in third.log.events], ["event-1", "event-2", "event-3"])
            third.log.verify()

    def test_rewritten_line_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "audit.jsonl"
            AuditFile(path, "audit-file").append(fields(1))
            lines = path.read_text(encoding="utf-8").splitlines()
            lines[0] = lines[0].replace("reviewer-synthetic", "other-user")
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            with self.assertRaises(ContractError) as tampered:
                AuditFile(path, "audit-file")
            self.assertEqual(str(tampered.exception), "audit-file-tampered")


if __name__ == "__main__":
    unittest.main()
