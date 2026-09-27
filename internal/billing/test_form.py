"""Tests for form version enforcement."""
from __future__ import annotations

import unittest

from internal.billing.form import form_version
from internal.contract.errors import ContractError


class TestFormVersion(unittest.TestCase):
    def test_valid_version(self) -> None:
        result = form_version("F1", "1.2")
        self.assertEqual(result, "1.2")

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            form_version("", "1.0")
        self.assertEqual(ctx.exception.args[0], "form-version-invalid")

    def test_unsupported_version(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            form_version("F1", "0.5")
        self.assertEqual(ctx.exception.args[0], "form-version-unsupported")


if __name__ == "__main__":
    unittest.main()
