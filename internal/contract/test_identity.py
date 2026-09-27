"""Tests for actor context and rule-pack admission."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.identity import (  # noqa: E402
    campus_token,
    index_partition,
    rebuild_rehearsal,
    require_context,
    require_same_partition,
)
from internal.contract.rules import RuleLedger, RulePack, admit, deterministic_decision  # noqa: E402


def actor() -> dict[str, str]:
    return {
        "actor_id": "reviewer-synthetic",
        "actor_role": "attending",
        "tenant_id": "tenant-synthetic",
        "campus_id": "campus-synthetic",
        "purpose_code": "treatment",
        "why_code": "review-decision",
        "occurred_at": "2026-09-24T00:00:00Z",
    }


def pack(state: str = "active", end: str = "2027-01-01") -> RulePack:
    return RulePack("pack-1", "1.0.0", "a" * 64, state, "2026-01-01", end)


class IdentityTests(unittest.TestCase):
    def test_complete_context_keeps_every_responsibility_field(self) -> None:
        context = require_context(actor())
        self.assertEqual(context.actor_role, "attending")
        self.assertEqual(context.why_code, "review-decision")

    def test_unknown_reason_and_blank_campus_are_rejected(self) -> None:
        missing_reason = actor()
        missing_reason["why_code"] = "unknown"
        with self.assertRaises(ContractError) as why:
            require_context(missing_reason)
        self.assertEqual(str(why.exception), "actor-why-missing")
        missing_campus = actor()
        missing_campus["campus_id"] = " "
        with self.assertRaises(ContractError) as campus:
            require_context(missing_campus)
        self.assertEqual(str(campus.exception), "actor-context-incomplete")

    def test_identifier_actor_field_is_rejected(self) -> None:
        named = actor()
        named["actor_id"] = "subject.identifier"
        with self.assertRaises(ContractError) as blocked:
            require_context(named)
        self.assertEqual(str(blocked.exception), "actor-identifier-forbidden")

    def test_partition_changes_when_campus_changes(self) -> None:
        first = require_context(actor())
        second = require_context(actor())
        token = require_same_partition(first, second, "local-ref-synthetic")
        self.assertEqual(token, index_partition(first, "local-ref-synthetic"))
        other = dict(actor())
        other["campus_id"] = "campus-other"
        with self.assertRaises(ContractError) as blocked:
            require_same_partition(first, require_context(other), "local-ref-synthetic")
        self.assertEqual(blocked.exception.args[0], "index-partition-mismatch")

    def test_direct_reference_cannot_enter_index(self) -> None:
        context = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            index_partition(context, "subject.identifier")
        self.assertEqual(str(blocked.exception), "index-reference-forbidden")

    def test_cross_campus_token_forbids_merge(self) -> None:
        source = require_context(actor())
        other = dict(actor())
        other["campus_id"] = "campus-other"
        target = require_context(other)
        issued = campus_token(source, target, "ab" * 32)
        self.assertEqual(issued["merge"], "forbidden")
        self.assertEqual(len(issued["token"]), 64)

    def test_same_campus_token_is_rejected(self) -> None:
        source = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            campus_token(source, source, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "token-campus-same")

    def test_other_tenant_token_is_rejected(self) -> None:
        source = require_context(actor())
        other = dict(actor())
        other["tenant_id"] = "tenant-other"
        other["campus_id"] = "campus-other"
        with self.assertRaises(ContractError) as blocked:
            campus_token(source, require_context(other), "ab" * 32)
        self.assertEqual(str(blocked.exception), "token-tenant-mismatch")

    def test_rebuild_is_repeatable(self) -> None:
        context = require_context(actor())
        refs = ("local-a", "local-b")
        first = rebuild_rehearsal(context, refs)
        second = rebuild_rehearsal(context, refs)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)

    def test_empty_rebuild_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rebuild_rehearsal(require_context(actor()), ())
        self.assertEqual(blocked.exception.args[0], "rebuild-empty")

    def test_duplicate_rebuild_ref_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            rebuild_rehearsal(require_context(actor()), ("local-a", "local-a"))
        self.assertEqual(str(blocked.exception), "rebuild-duplicate")


class RulePackTests(unittest.TestCase):
    def test_active_pack_inside_window_is_admitted(self) -> None:
        admit(pack(), "2026-09-24")

    def test_unknown_retired_expired_and_short_digest_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as unknown:
            admit(pack("unknown"), "2026-09-24")
        self.assertEqual(str(unknown.exception), "rule-state-rejected")
        with self.assertRaises(ContractError):
            admit(pack("retired"), "2026-09-24")
        with self.assertRaises(ContractError) as expired:
            admit(pack(end="2026-02-01"), "2026-09-24")
        self.assertEqual(str(expired.exception), "rule-outside-window")
        broken = RulePack("pack-1", "1.0.0", "abc", "active", "2026-01-01", "2027-01-01")
        with self.assertRaises(ContractError) as digest:
            admit(broken, "2026-09-24")
        self.assertEqual(str(digest.exception), "rule-digest-invalid")

    def test_model_cannot_replace_hard_rule(self) -> None:
        self.assertEqual(deterministic_decision("deny", "deny"), "deny")
        with self.assertRaises(ContractError) as overridden:
            deterministic_decision("deny", "allow")
        self.assertEqual(str(overridden.exception), "model-cannot-override-rule")

    def test_identifier_pack_id_is_rejected(self) -> None:
        named = RulePack("subject.identifier", "1.0.0", "a" * 64, "active", "2026-01-01", "2027-01-01")
        with self.assertRaises(ContractError) as blocked:
            admit(named, "2026-09-24")
        self.assertEqual(str(blocked.exception), "rule-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            admit(pack(), "2026-09-24", why_code="unknown")
        self.assertEqual(str(blocked.exception), "rule-why-missing")

    def test_other_actor_for_same_pack_is_rejected(self) -> None:
        ledger = RuleLedger()
        ledger.admit(pack(), "2026-09-24", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            ledger.admit(pack(), "2026-09-24", "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "rule-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
