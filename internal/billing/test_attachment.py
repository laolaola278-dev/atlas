"""Tests for attachment whitelist enforcement."""
from __future__ import annotations

import unittest
from internal.contract.errors import ContractError
from internal.billing.attachment import attachment_whitelist


class TestAttachmentWhitelist(unittest.TestCase):
    def test_forbidden_type(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            attachment_whitelist("script.exe", 1000, 5000)
        self.assertEqual(ctx.exception.args[0], "attachment-type-forbidden")

    def test_valid_attachment(self) -> None:
        result = attachment_whitelist("document.pdf", 2000, 10000)
        self.assertEqual(result, "document.pdf")

    def test_forbidden_type(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            attachment_whitelist("script.exe", 1000, 5000)
        self.assertEqual(ctx.exception.args[0], "attachment-type-forbidden")

    def test_size_exceeded(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            attachment_whitelist("doc.pdf", 10000, 5000)
        self.assertEqual(ctx.exception.args[0], "attachment-size-exceeded")

    def test_invalid_empty_filename(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            attachment_whitelist("", 1000, 5000)
        self.assertEqual(ctx.exception.args[0], "attachment-invalid")


if __name__ == "__main__":
    unittest.main()
