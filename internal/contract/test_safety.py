"""Tests for the registered bypass catalog."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.safety import (  # noqa: E402
    api_reject,
    bypass_catalog,
    canary_safety,
    defect_grade,
    db_constraint,
    migration_reject,
    privilege_reject,
    safety_signoff,
    service_reject,
    skip_switch,
)


class BypassCatalogTests(unittest.TestCase):
    def test_registered_path_can_be_counted(self) -> None:
        self.assertEqual(bypass_catalog("direct-write", False), 5)

    def test_registered_path_cannot_be_used(self) -> None:
        with self.assertRaises(ContractError) as caught:
            bypass_catalog("expired-proof", True)
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_unknown_path_is_not_in_the_catalog(self) -> None:
        with self.assertRaises(ContractError) as caught:
            bypass_catalog("side-door", False)
        self.assertTrue(caught.exception.args[0].endswith("unknown"))

    def test_required_constraint_holds(self) -> None:
        self.assertEqual(db_constraint("required", "order-synthetic", frozenset()), "required")

    def test_blank_required_value_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            db_constraint("required", "", frozenset())
        self.assertTrue(caught.exception.args[0].endswith("missing"))

    def test_seen_unique_value_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            db_constraint("unique", "order-synthetic", frozenset({"order-synthetic"}))
        self.assertTrue(caught.exception.args[0].endswith("duplicate"))

    def test_signed_ordinary_write_is_accepted(self) -> None:
        self.assertEqual(service_reject(True, True, False, "approval", False), "accepted")

    def test_unsigned_service_write_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            service_reject(False, True, False, "approval", False)
        self.assertTrue(caught.exception.args[0].endswith("unsigned"))

    def test_grant_cannot_pass_the_service(self) -> None:
        with self.assertRaises(ContractError) as caught:
            service_reject(True, True, False, "grant", False)
        self.assertTrue(caught.exception.args[0].endswith("rejected"))

    def test_fhir_json_post_is_accepted(self) -> None:
        self.assertEqual(api_reject("POST", "application/fhir+json", "orders"), "accepted")

    def test_get_write_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            api_reject("GET", "application/fhir+json", "orders")
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_plain_json_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            api_reject("POST", "application/json", "reviews")
        self.assertTrue(caught.exception.args[0].endswith("rejected"))

    def test_reviewed_backfill_is_accepted(self) -> None:
        self.assertEqual(migration_reject("backfill", True, True), "backfill")

    def test_drop_migration_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            migration_reject("drop", True, True)
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_unreviewed_migration_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            migration_reject("add-column", False, True)
        self.assertTrue(caught.exception.args[0].endswith("unreviewed"))

    def test_ordinary_reviewer_can_sign(self) -> None:
        self.assertEqual(privilege_reject("reviewer-synthetic", "sign"), "sign")

    def test_admin_account_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            privilege_reject("admin", "review")
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_system_account_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            privilege_reject("system", "sign")
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_skip_switch_query_reports_absent(self) -> None:
        self.assertEqual(skip_switch("query"), "absent")

    def test_skip_switch_cannot_be_enabled(self) -> None:
        with self.assertRaises(ContractError) as caught:
            skip_switch("enable")
        self.assertTrue(caught.exception.args[0].endswith("absent"))

    def test_closed_canary_gate_is_kept(self) -> None:
        self.assertEqual(canary_safety(5, "closed"), "closed")

    def test_open_canary_gate_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            canary_safety(10, "open")
        self.assertTrue(caught.exception.args[0].endswith("open"))

    def test_minor_defect_can_be_deferred(self) -> None:
        self.assertEqual(defect_grade("minor", "defer"), "minor")

    def test_blocker_cannot_be_deferred(self) -> None:
        with self.assertRaises(ContractError) as caught:
            defect_grade("blocker", "defer")
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))

    def test_two_reviewers_can_sign_safety(self) -> None:
        signers = ("reviewer-a", "reviewer-b")
        self.assertEqual(safety_signoff(signers, "ab" * 32), 2)

    def test_system_cannot_sign_safety(self) -> None:
        with self.assertRaises(ContractError) as caught:
            safety_signoff(("reviewer-a", "system"), "ab" * 32)
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))


if __name__ == "__main__":
    unittest.main()
