"""Tests for scoped queries and forbidden identifier fields."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.query import QueryLedger, page_cursor, prepare, require_permission_scope, require_same_page  # noqa: E402


def valid() -> dict[str, object]:
    return {
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "purpose_code": "treatment",
        "resource_type": "Observation",
        "page_size": 25,
        "requested_fields": ["code", "value", "effective_at"],
    }


class QueryTests(unittest.TestCase):
    def test_scoped_clinical_fields_are_accepted(self) -> None:
        query = prepare(valid())
        self.assertEqual(query.page_size, 25)
        self.assertEqual(query.requested_fields, frozenset({"code", "value", "effective_at"}))

    def test_missing_scope_identifier_and_page_are_rejected(self) -> None:
        missing = valid()
        missing["purpose_code"] = ""
        with self.assertRaises(ContractError) as scope:
            prepare(missing)
        self.assertEqual(str(scope.exception), "query-scope-incomplete")
        named = valid()
        named["requested_fields"] = ["code", "name"]
        with self.assertRaises(ContractError) as forbidden:
            prepare(named)
        self.assertEqual(str(forbidden.exception), "query-field-forbidden")
        oversized = valid()
        oversized["page_size"] = 101
        with self.assertRaises(ContractError):
            prepare(oversized)

    def test_withdrawn_consent_rejects_query(self) -> None:
        withdrawn = valid()
        withdrawn["consent_state"] = "withdrawn"
        with self.assertRaises(ContractError) as blocked:
            prepare(withdrawn)
        self.assertEqual(str(blocked.exception), "query-consent-not-active")

    def test_nested_identifier_path_is_rejected(self) -> None:
        nested = valid()
        nested["requested_fields"] = ["code", "subject.identifier"]
        with self.assertRaises(ContractError) as blocked:
            prepare(nested)
        self.assertEqual(str(blocked.exception), "query-field-forbidden")

    def test_identifier_scope_is_rejected(self) -> None:
        named = valid()
        named["tenant_id"] = "subject.identifier"
        with self.assertRaises(ContractError) as blocked:
            prepare(named)
        self.assertEqual(str(blocked.exception), "query-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        unknown = valid()
        unknown["why_code"] = "unknown"
        with self.assertRaises(ContractError) as blocked:
            prepare(unknown)
        self.assertEqual(str(blocked.exception), "query-why-missing")

    def test_other_actor_for_same_query_is_rejected(self) -> None:
        ledger = QueryLedger()
        first = valid()
        first["actor_id"] = "reviewer-synthetic"
        ledger.prepare(first)
        other = valid()
        other["actor_id"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ledger.prepare(other)
        self.assertEqual(str(blocked.exception), "query-responsibility-mismatch")

    def test_cursor_cannot_cross_tenants(self) -> None:
        first = prepare(valid())
        cursor = page_cursor(first, 25)
        require_same_page(first, first, cursor, 25)
        other = prepare({**valid(), "tenant_id": "tenant-other"})
        with self.assertRaises(ContractError) as blocked:
            require_same_page(first, other, cursor, 25)
        self.assertEqual(blocked.exception.args[0], "query-tenant-isolated")

    def test_query_must_stay_inside_granted_scope(self) -> None:
        query = prepare(valid())
        grant = {
            "campuses": ["campus-synthetic"],
            "purposes": ["treatment"],
            "tenants": ["tenant-synthetic"],
        }
        self.assertEqual(require_permission_scope(query, grant).tenant_id, "tenant-synthetic")
        other = prepare({**valid(), "campus_id": "campus-other"})
        with self.assertRaises(ContractError) as blocked:
            require_permission_scope(other, grant)
        self.assertEqual(blocked.exception.args[0], "permission-campus-denied")


if __name__ == "__main__":
    unittest.main()
