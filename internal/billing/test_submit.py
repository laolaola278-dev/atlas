"""Tests for submit idempotency enforcement."""
from __future__ import annotations

import unittest

from internal.billing.submit import submit_idempotency
from internal.contract.errors import ContractError


class TestSubmitIdempotency(unittest.TestCase):
    def test_first_submission(self) -> None:
        result = submit_idempotency("SUB1", "abc123")
        self.assertEqual(result, "SUB1")

    def test_idempotent_replay(self) -> None:
        submit_idempotency("SUB2", "def456")
        result = submit_idempotency("SUB2", "def456")
        self.assertEqual(result, "SUB2")

    def test_content_mismatch(self) -> None:
        submit_idempotency("SUB3", "ghi789")
        with self.assertRaises(ContractError) as ctx:
            submit_idempotency("SUB3", "different")
        self.assertEqual(ctx.exception.args[0], "submission-content-mismatch")

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            submit_idempotency("", "hash")
        self.assertEqual(ctx.exception.args[0], "submission-invalid")


if __name__ == "__main__":
    unittest.main()
