"""Tests for stable, non-identifying contract errors."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import (  # noqa: E402
    CODES,
    ContractError,
    lookup,
    public_body,
)


class ErrorContractTests(unittest.TestCase):
    def test_every_code_is_stable_and_non_retryable_when_forbidden(self) -> None:
        forbidden = lookup("approval-missing")
        self.assertFalse(forbidden.retryable)
        self.assertEqual(forbidden.http_status, 403)
        unknown = lookup("result-unknown")
        self.assertTrue(unknown.retryable)
        self.assertGreaterEqual(len(CODES), 160)
        forbidden_identifier = lookup("identifier-forbidden")
        self.assertFalse(forbidden_identifier.retryable)
        self.assertEqual(forbidden_identifier.http_status, 403)
        specific = lookup("policy-identifier-forbidden")
        self.assertEqual(specific.http_status, 403)
        unknown_result = lookup("transaction-result-unknown")
        self.assertTrue(unknown_result.retryable)
        self.assertEqual(unknown_result.http_status, 503)

    def test_public_body_rejects_unknown_code_and_blank_trace(self) -> None:
        with self.assertRaises(ContractError) as unknown:
            public_body("free-text patient detail", "trace-1")
        self.assertEqual(str(unknown.exception), "error-code-unknown")
        with self.assertRaises(ContractError):
            public_body("tenant-missing", " ")
        body = public_body("emergency-grant-not-approval", "trace-1")
        self.assertEqual(
            set(body),
            {"code", "retryable", "status", "trace_id"},
        )
        self.assertNotIn("patient", body["code"])
        with self.assertRaises(ContractError) as named:
            public_body("identifier-forbidden", "subject.identifier")
        self.assertEqual(str(named.exception), "trace-identifier-forbidden")

    def test_invalid_status_cannot_construct_code(self) -> None:
        from internal.contract.errors import ErrorCode

        with self.assertRaises(ContractError):
            ErrorCode("bad status", False, 200)


if __name__ == "__main__":
    unittest.main()
