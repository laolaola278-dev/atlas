"""Stability tests for OperationOutcome mapping."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.outcome import operation_outcome  # noqa: E402


class OperationOutcomeTests(unittest.TestCase):
    def test_same_issues_keep_the_same_order(self) -> None:
        first = (("status", "report-status-missing"), ("priority", "request-priority-missing"))
        second = (("priority", "request-priority-missing"), ("status", "report-status-missing"))
        self.assertEqual(operation_outcome(first), operation_outcome(second))
        issues = operation_outcome(first)["issue"]
        self.assertEqual(issues[0]["path"], "priority")

    def test_duplicate_issue_is_emitted_once(self) -> None:
        repeated = (("status", "report-status-missing"), ("status", "report-status-missing"))
        issues = operation_outcome(repeated)["issue"]
        self.assertEqual(len(issues), 1)

    def test_identifier_path_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            operation_outcome((("subject.identifier", "direct-identifier-forbidden"),))
        self.assertEqual(blocked.exception.args[0], "outcome-identifier-forbidden")

    def test_empty_issue_list_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            operation_outcome(())
        self.assertEqual(str(blocked.exception), "outcome-empty")


if __name__ == "__main__":
    unittest.main()
