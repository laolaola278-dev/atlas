"""Tests for synthetic order journeys."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.explain import (  # noqa: E402
    clinical_readability,
    counterfactual_guard,
    evidence_block,
    explain_audit,
    explain_version,
    guide_entry,
    hit_path,
    lab_timepoint,
    model_boundary,
    review_pack,
    synthetic_journey,
)


class SyntheticJourneyTests(unittest.TestCase):
    def test_ordinary_journey_has_three_steps(self) -> None:
        steps = ("draft", "submitted", "dispensed")
        self.assertEqual(synthetic_journey("ordinary", steps, True), 3)

    def test_skipped_step_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            synthetic_journey("ordinary", ("draft", "dispensed"), True)
        self.assertEqual(blocked.exception.args[0], "journey-path-invalid")

    def test_real_journey_is_rejected(self) -> None:
        steps = ("draft", "recorded", "reviewed")
        with self.assertRaises(ContractError) as blocked:
            synthetic_journey("emergency", steps, False)
        self.assertEqual(str(blocked.exception), "journey-not-synthetic")

    def test_known_guide_entry_returns_page(self) -> None:
        self.assertEqual(guide_entry("dose-bound", True), 12)

    def test_unknown_guide_entry_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            guide_entry("free-text", True)
        self.assertEqual(blocked.exception.args[0], "guide-entry-unknown")

    def test_ordered_lab_times_are_kept(self) -> None:
        collected = lab_timepoint("2026-01-02T03:04:05Z", "2026-01-02T03:09:05Z")
        self.assertTrue(collected.endswith("Z"))

    def test_report_before_collection_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            lab_timepoint("2026-01-02T04:00:00Z", "2026-01-02T03:00:00Z")
        code = blocked.exception.args[0]
        self.assertTrue(code.startswith("lab-"))

    def test_distinct_hit_path_keeps_its_length(self) -> None:
        length = hit_path(("allergy", "dose", "interaction"))
        self.assertGreater(length, 1)

    def test_unknown_hit_step_is_rejected(self) -> None:
        try:
            hit_path(("note",))
        except ContractError as blocked:
            self.assertIn("unknown", blocked.args[0])
        else:
            self.fail("unknown step was accepted")

    def test_agreeing_model_keeps_the_rule(self) -> None:
        kept = model_boundary("deny", "abstain")
        self.assertIn("deny", kept)

    def test_disagreeing_model_cannot_override(self) -> None:
        try:
            model_boundary("allow", "deny")
        except ContractError as blocked:
            self.assertIn("override", blocked.args[0])
        else:
            self.fail("override was accepted")

    def test_registered_evidence_keeps_the_decision(self) -> None:
        kept = evidence_block("allow", "cd" * 32, frozenset({"cd" * 32}))
        self.assertIn("allow", kept)

    def test_blank_evidence_blocks_the_decision(self) -> None:
        try:
            evidence_block("deny", "", frozenset({"cd" * 32}))
        except ContractError as blocked:
            self.assertIn("missing", blocked.args[0])
        else:
            self.fail("blank evidence was accepted")

    def test_previous_explanation_version_is_accepted(self) -> None:
        shown = explain_version("1.0", "1.1")
        self.assertTrue(shown.startswith("1."))

    def test_skipped_explanation_version_is_rejected(self) -> None:
        try:
            explain_version("1.2", "1.1")
        except ContractError as blocked:
            self.assertIn("mismatch", blocked.args[0])
        else:
            self.fail("skipped version was accepted")

    def test_complete_review_pack_has_three_items(self) -> None:
        count = review_pack(("guide", "lab", "rule"), "ef" * 32, True)
        self.assertEqual(count, 3)

    def test_missing_pack_item_is_rejected(self) -> None:
        try:
            review_pack(("guide", "lab"), "ef" * 32, True)
        except ContractError as blocked:
            self.assertIn("incomplete", blocked.args[0])
        else:
            self.fail("short pack was accepted")

    def test_counterfactual_can_be_shown(self) -> None:
        shown = counterfactual_guard("counterfactual", "show")
        self.assertEqual(shown, "show")

    def test_counterfactual_cannot_execute(self) -> None:
        blocked = ""
        try:
            counterfactual_guard("counterfactual", "execute")
        except ContractError as exc:
            blocked = exc.args[0]
        self.assertEqual(blocked, "counterfactual-execute-forbidden")

    def test_matching_explanation_audit_is_kept(self) -> None:
        linked = explain_audit("ab" * 32, "ab" * 32, "show")
        self.assertIn("show", linked)

    def test_changed_explanation_audit_is_rejected(self) -> None:
        blocked = ""
        try:
            explain_audit("ab" * 32, "cd" * 32, "block")
        except ContractError as exc:
            blocked = exc.args[0]
        self.assertIn("mismatch", blocked)

    def test_labeled_sections_are_readable(self) -> None:
        sections = {"guide": "dose-bound", "lab": "inside", "rule": "allergy"}
        self.assertEqual(clinical_readability(sections), len(sections))

    def test_free_text_is_not_readable(self) -> None:
        sections = {"guide": "dose bound", "lab": "inside", "rule": "allergy"}
        with self.assertRaises(ContractError) as caught:
            clinical_readability(sections)
        self.assertTrue(caught.exception.args[0].endswith("forbidden"))


if __name__ == "__main__":
    unittest.main()
