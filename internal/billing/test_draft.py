"""Tests for draft recovery enforcement."""
from __future__ import annotations

import unittest

from internal.billing.draft import draft_recovery
from internal.contract.errors import ContractError


class TestDraftRecovery(unittest.TestCase):
    def test_save_and_recover(self) -> None:
        content = {"text": "draft content"}
        draft_recovery("DR1", content, "save")
        recovered = draft_recovery("DR1", {}, "recover")
        self.assertEqual(recovered, content)

    def test_recover_not_found(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            draft_recovery("DR999", {}, "recover")
        self.assertEqual(ctx.exception.args[0], "draft-not-found")

    def test_invalid_action(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            draft_recovery("DR1", {"text": "content"}, "delete")
        self.assertEqual(ctx.exception.args[0], "draft-action-invalid")

    def test_invalid_empty_id(self) -> None:
        with self.assertRaises(ContractError) as ctx:
            draft_recovery("", {"text": "content"}, "save")
        self.assertEqual(ctx.exception.args[0], "draft-invalid")


if __name__ == "__main__":
    unittest.main()
