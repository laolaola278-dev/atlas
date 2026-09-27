"""Tests for electronic signature enforcement."""
from __future__ import annotations

import unittest

from internal.billing.signature import electronic_signature
from internal.contract.errors import ContractError


class TestElectronicSignature(unittest.TestCase):
    def test_valid_signature(self) -> None:
        sig = "a" * 64
        result = electronic_signature("D1", "user123", sig)
        self.assertEqual(result, sig)

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            electronic_signature("", "user123", "a" * 64)
        self.assertEqual(ctx.exception.args[0], "signature-invalid")

    def test_invalid_format(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            electronic_signature("D1", "user123", "short")
        self.assertEqual(ctx.exception.args[0], "signature-format-invalid")


if __name__ == "__main__":
    unittest.main()
