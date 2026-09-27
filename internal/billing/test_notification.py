"""Notification idempotency tests."""
import unittest
from internal.contract._path import install_contract_path

install_contract_path()

from internal.billing.notification import notification_idempotency as check_notify  # noqa: E402
from internal.contract.errors import ContractError as Denied  # noqa: E402


class NotificationIdempotencyTests(unittest.TestCase):
    def test_first_notification_is_accepted(self) -> None:
        notification_id = check_notify("N001", "recipient-001", "hash1")
        self.assertEqual(notification_id, "N001")

    def test_duplicate_notification_with_same_content_is_accepted(self) -> None:
        check_notify("N002", "recipient-002", "hash2")
        notification_id = check_notify("N002", "recipient-002", "hash2")
        self.assertEqual(notification_id, "N002")

    def test_duplicate_notification_with_different_content_is_refused(self) -> None:
        check_notify("N003", "recipient-003", "hash3")
        with self.assertRaises(Denied) as blocked:
            check_notify("N003", "recipient-003", "hash3_modified")
        self.assertTrue(blocked.exception.args[0].endswith("mismatch"))


if __name__ == "__main__":
    unittest.main()
