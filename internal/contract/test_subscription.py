"""Isolation tests for subscription notices."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.subscription import change_notice  # noqa: E402


def subscription() -> dict[str, str]:
    return {
        "content_digest": "ab" * 32,
        "resource_type": "Observation",
        "tenant_id": "tenant-synthetic",
    }


class SubscriptionNoticeTests(unittest.TestCase):
    def test_matching_change_returns_digest_only(self) -> None:
        notice = change_notice(subscription(), subscription())
        self.assertEqual(set(notice), {"content_digest", "resource_type", "tenant_id"})
        self.assertEqual(notice["resource_type"], "Observation")

    def test_other_tenant_is_rejected(self) -> None:
        other = dict(subscription())
        other["tenant_id"] = "tenant-other"
        with self.assertRaises(ContractError) as blocked:
            change_notice(subscription(), other)
        self.assertEqual(blocked.exception.args[0], "subscription-tenant-mismatch")

    def test_short_digest_is_rejected(self) -> None:
        changed = dict(subscription())
        changed["content_digest"] = "abcd"
        with self.assertRaises(ContractError) as blocked:
            change_notice(subscription(), changed)
        self.assertEqual(str(blocked.exception), "subscription-digest-invalid")

    def test_same_notice_is_stable(self) -> None:
        first = change_notice(subscription(), subscription())
        second = change_notice(subscription(), subscription())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
