"""Tests for document arrival rates."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.docgen import (  # noqa: E402
    adopt_boundary,
    arrival_rate,
    cited_evidence,
    doc_retry,
    doc_rollback,
    draft_isolation,
    redact_output,
    required_chapters,
    segment_p95,
    synthetic_load,
    template_schema,
    term_check,
)
from internal.contract.errors import ContractError  # noqa: E402


class ArrivalRateTests(unittest.TestCase):
    def test_full_delivery_is_one_hundred(self) -> None:
        rate = arrival_rate(100, 100)
        self.assertGreaterEqual(rate, 95)
        self.assertLessEqual(rate, 100)

    def test_low_delivery_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            arrival_rate(10, 100)
        self.assertIn("below", caught.exception.args[0])

    def test_zero_expected_is_invalid(self) -> None:
        with self.assertRaises(ContractError) as caught:
            arrival_rate(0, 0)
        self.assertIn("invalid", caught.exception.args[0])

    def test_current_template_schema_is_accepted(self) -> None:
        fields = {"section": "plan", "title": "order-note", "version": "1.1"}
        self.assertEqual(template_schema(fields), "1.1")

    def test_template_text_is_rejected(self) -> None:
        fields = {"section": "plan", "title": "order note", "version": "1.1"}
        with self.assertRaises(ContractError) as caught:
            template_schema(fields)
        self.assertIn("text", caught.exception.args[0])

    def test_three_chapters_are_required(self) -> None:
        chapters = ("assessment", "plan", "orders")
        self.assertEqual(required_chapters(chapters), 3)

    def test_skipped_chapter_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            required_chapters(("assessment", "orders"))
        self.assertIn("missing", caught.exception.args[0])

    def test_registered_term_keeps_its_label(self) -> None:
        known = frozenset({"ab" * 32})
        self.assertEqual(term_check("plan", "ab" * 32, known), "plan")

    def test_unregistered_term_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            term_check("plan", "cd" * 32, frozenset({"ab" * 32}))
        self.assertIn("unregistered", caught.exception.args[0])

    def test_draft_stays_in_the_draft_table(self) -> None:
        self.assertEqual(draft_isolation("draft", "draft"), "draft")

    def test_draft_cannot_enter_the_accepted_table(self) -> None:
        with self.assertRaises(ContractError) as caught:
            draft_isolation("draft", "accepted")
        self.assertIn("isolated", caught.exception.args[0])

    def test_human_can_adopt_a_draft(self) -> None:
        self.assertEqual(adopt_boundary("reviewer-synthetic", "draft"), "accepted")

    def test_model_cannot_adopt_a_draft(self) -> None:
        with self.assertRaises(ContractError) as caught:
            adopt_boundary("model", "draft")
        self.assertIn("forbidden", caught.exception.args[0])

    def test_fast_segments_stay_inside_budget(self) -> None:
        samples = {"render": (10, 20, 30), "review": (5, 5, 5), "term": (8, 9, 10)}
        self.assertLessEqual(segment_p95(samples, 50), 50)

    def test_slow_segment_exceeds_budget(self) -> None:
        samples = {"render": (100, 200, 900), "review": (5,), "term": (5,)}
        with self.assertRaises(ContractError) as caught:
            segment_p95(samples, 100)
        self.assertIn("exceeded", caught.exception.args[0])

    def test_unsealed_document_can_roll_back(self) -> None:
        self.assertEqual(doc_rollback("1.1", "1.0", False), "1.0")

    def test_sealed_document_cannot_roll_back(self) -> None:
        with self.assertRaises(ContractError) as caught:
            doc_rollback("1.1", "1.0", True)
        self.assertIn("sealed", caught.exception.args[0])

    def test_registered_citations_are_counted(self) -> None:
        known = frozenset({"ab" * 32, "cd" * 32})
        self.assertEqual(cited_evidence(("ab" * 32, "cd" * 32), known), 2)

    def test_unknown_citation_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            cited_evidence(("ef" * 32,), frozenset({"ab" * 32}))
        self.assertIn("unregistered", caught.exception.args[0])

    def test_small_synthetic_load_is_counted(self) -> None:
        self.assertEqual(synthetic_load(10, 100, True), 1000)

    def test_oversized_load_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            synthetic_load(1000, 2000, True)
        self.assertIn("exceeded", caught.exception.args[0])

    def test_finished_document_is_not_retried(self) -> None:
        self.assertEqual(doc_retry(1, "done"), "done")

    def test_unknown_document_can_be_retried(self) -> None:
        with self.assertRaises(ContractError) as caught:
            doc_retry(1, "unknown")
        self.assertIn("unknown", caught.exception.args[0])

    def test_safe_labels_are_counted(self) -> None:
        self.assertEqual(redact_output(("plan", "section")), 2)

    def test_unknown_label_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as caught:
            redact_output(("note",))
        self.assertIn("forbidden", caught.exception.args[0])


if __name__ == "__main__":
    unittest.main()
