"""Tests for release approval."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.publish import approve_release  # noqa: E402


class ReleaseApprovalTests(unittest.TestCase):
    def test_two_approvers_publish(self) -> None:
        published = approve_release("ab" * 32, "approver-one", "approver-two")
        self.assertEqual(published["state"], "published")

    def test_one_approver_cannot_publish(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            approve_release("ab" * 32, "approver-one", "approver-one")
        self.assertEqual(blocked.exception.args[0], "publish-same-approver")

    def test_blank_approver_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            approve_release("ab" * 32, "approver-one", "")
        self.assertEqual(str(blocked.exception), "publish-signature-missing")


if __name__ == "__main__":
    unittest.main()
