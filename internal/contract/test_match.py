"""Digest-only tests for deterministic matching."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.identity import require_context  # noqa: E402
from internal.contract.match import (  # noqa: E402
    blocking_rule,
    deterministic_match,
    explanation,
    newborn_policy,
    probabilistic_candidate,
    same_name_regression,
    suppress_contacts,
)


def actor(campus: str = "campus-synthetic") -> dict[str, str]:
    return {
        "actor_id": "reviewer-synthetic",
        "actor_role": "attending",
        "campus_id": campus,
        "occurred_at": "2026-09-24T00:00:00Z",
        "purpose_code": "treatment",
        "tenant_id": "tenant-synthetic",
        "why_code": "review-decision",
    }


class DeterministicMatchTests(unittest.TestCase):
    def test_equal_digests_match(self) -> None:
        left = require_context(actor())
        right = require_context(actor())
        digest = "ab" * 32
        self.assertEqual(deterministic_match(left, right, "local-ref-synthetic", digest, digest), digest)

    def test_different_digests_do_not_guess(self) -> None:
        left = require_context(actor())
        right = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            deterministic_match(left, right, "local-ref-synthetic", "ab" * 32, "cd" * 32)
        self.assertEqual(blocked.exception.args[0], "match-digest-mismatch")

    def test_short_digest_is_rejected(self) -> None:
        left = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            deterministic_match(left, left, "local-ref-synthetic", "abcd", "abcd")
        self.assertEqual(str(blocked.exception), "match-digest-invalid")

    def test_other_campus_is_rejected(self) -> None:
        left = require_context(actor())
        right = require_context(actor("campus-other"))
        with self.assertRaises(ContractError) as blocked:
            deterministic_match(left, right, "local-ref-synthetic", "ab" * 32, "ab" * 32)
        self.assertEqual(str(blocked.exception), "index-partition-mismatch")

    def test_high_score_requires_review(self) -> None:
        left = require_context(actor())
        result = probabilistic_candidate(left, left, "local-ref-synthetic", "ab" * 32, "cd" * 32, 90)
        self.assertEqual(result, "review-required")

    def test_low_score_does_not_link(self) -> None:
        left = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            probabilistic_candidate(left, left, "local-ref-synthetic", "ab" * 32, "cd" * 32, 79)
        self.assertEqual(blocked.exception.args[0], "match-below-threshold")

    def test_score_outside_range_is_rejected(self) -> None:
        left = require_context(actor())
        with self.assertRaises(ContractError) as blocked:
            probabilistic_candidate(left, left, "local-ref-synthetic", "ab" * 32, "cd" * 32, 101)
        self.assertEqual(str(blocked.exception), "match-score-invalid")

    def test_contact_fields_are_suppressed(self) -> None:
        clean = {"resource_type": "Observation", "status": "final"}
        self.assertEqual(suppress_contacts(clean)["status"], "final")
        with self.assertRaises(ContractError) as blocked:
            suppress_contacts({**clean, "phone": "synthetic"})
        self.assertEqual(blocked.exception.args[0], "contact-suppressed")

    def test_identifier_value_is_suppressed(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            suppress_contacts({"status": "subject.identifier"})
        self.assertEqual(str(blocked.exception), "contact-identifier-forbidden")

    def test_hard_mismatch_blocks_a_high_score(self) -> None:
        findings = {"birth_year_mismatch": True, "credential_mismatch": False, "sex_mismatch": False}
        with self.assertRaises(ContractError) as blocked:
            blocking_rule(findings, 99)
        self.assertEqual(blocked.exception.args[0], "block-hard-mismatch")

    def test_clear_findings_still_require_review(self) -> None:
        findings = {"birth_year_mismatch": False, "credential_mismatch": False, "sex_mismatch": False}
        self.assertEqual(blocking_rule(findings, 90), "review-required")

    def test_incomplete_findings_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            blocking_rule({"credential_mismatch": False}, 90)
        self.assertEqual(str(blocked.exception), "block-findings-invalid")

    def test_newborn_requires_two_reviewers(self) -> None:
        decision = newborn_policy(3, 97, ("reviewer-one", "reviewer-two"))
        self.assertEqual(decision, "dual-review-required")

    def test_newborn_ordinary_score_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            newborn_policy(3, 90, ("reviewer-one", "reviewer-two"))
        self.assertEqual(blocked.exception.args[0], "newborn-score-low")

    def test_newborn_same_reviewer_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            newborn_policy(3, 97, ("reviewer-one", "reviewer-one"))
        self.assertEqual(str(blocked.exception), "newborn-same-reviewer")

    def test_same_name_does_not_override_a_mismatch(self) -> None:
        findings = {"birth_year_mismatch": True, "credential_mismatch": False, "sex_mismatch": False}
        with self.assertRaises(ContractError) as blocked:
            same_name_regression(True, findings, 100)
        self.assertEqual(blocked.exception.args[0], "same-name-different-person")

    def test_same_name_without_mismatch_still_needs_review(self) -> None:
        findings = {"birth_year_mismatch": False, "credential_mismatch": False, "sex_mismatch": False}
        self.assertEqual(same_name_regression(True, findings, 88), "review-required")

    def test_different_name_is_not_this_regression(self) -> None:
        findings = {"birth_year_mismatch": False, "credential_mismatch": False, "sex_mismatch": False}
        with self.assertRaises(ContractError) as blocked:
            same_name_regression(False, findings, 88)
        self.assertEqual(str(blocked.exception), "same-name-not-shared")

    def test_explanation_lists_only_mismatch_codes(self) -> None:
        findings = {"birth_year_mismatch": True, "credential_mismatch": False, "sex_mismatch": True}
        evidence = explanation(findings, "ab" * 32, 70)
        self.assertEqual(evidence["codes"], ("birth_year_mismatch", "sex_mismatch"))
        self.assertNotIn("name", evidence)

    def test_explanation_rejects_a_short_digest(self) -> None:
        findings = {"birth_year_mismatch": False, "credential_mismatch": False, "sex_mismatch": False}
        with self.assertRaises(ContractError) as blocked:
            explanation(findings, "abcd", 70)
        self.assertEqual(blocked.exception.args[0], "explain-digest-invalid")


if __name__ == "__main__":
    unittest.main()
