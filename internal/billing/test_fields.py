"""Tests for required fields enforcement."""
from __future__ import annotations

import unittest

from internal.billing.fields import required_fields
from internal.contract.errors import ContractError


class TestRequiredFields(unittest.TestCase):
    def test_all_fields_present(self) -> None:
        fields = {"name": "John", "age": "30"}
        required_fields("F1", fields, ["name", "age"])

    def test_missing_field(self) -> None:
        fields = {"name": "John"}
        with self.assertRaises(ContractError) as ctx:
            required_fields("F1", fields, ["name", "age"])
        self.assertEqual(ctx.exception.args[0], "fields-required-missing")

    def test_empty_field_value(self) -> None:
        fields = {"name": "John", "age": ""}
        with self.assertRaises(ContractError) as ctx:
            required_fields("F1", fields, ["name", "age"])
        self.assertEqual(ctx.exception.args[0], "fields-required-missing")

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            required_fields("", {"name": "John"}, ["name"])
        self.assertEqual(ctx.exception.args[0], "fields-invalid")


if __name__ == "__main__":
    unittest.main()
