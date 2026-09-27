"""Tests for revocation enforcement."""
from __future__ import annotations
import unittest
from internal.contract.errors import ContractError

from internal.billing.revocation import revocation


class TestRevocation(unittest.TestCase):
    def test_valid_revocation(self) -> None:
        result = revocation("DOC1", "error", "reviewer456")
        self.assertEqual(result, "DOC1")

    def test_invalid_reason(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            revocation("D1", "unknown", "user123")
        err = ctx.exception.args[0]
        self.assertEqual(err, "revocation-reason-invalid")

    def test_unauthorized_system(self) -> None:
        try:
            revocation("DOC2", "error", "system")
            self.fail("Expected ContractError")
        except ContractError as e:
            self.assertEqual(e.args[0], "revocation-unauthorized")

    def test_invalid_empty_id(self) -> None:
        try:
            revocation("", "error", "user789")
            self.fail("Expected ContractError")
        except ContractError as e:
            self.assertEqual(e.args[0], "revocation-invalid")


if __name__ == "__main__":
    unittest.main()
