"""Exhaustive safety tests for the HITL reference state machine."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from internal.hitl.state.machine import (  # noqa: E402
    FORBIDDEN_FROM_EMERGENCY,
    TRANSITIONS,
    Suggestion,
    TransitionError,
    transition,
)


def new_suggestion() -> Suggestion:
    return Suggestion("sug-1", "patient-ref-synthetic", "order-draft")


def reach_approved(second: bool = False) -> Suggestion:
    item = new_suggestion()
    transition(item, "EVIDENCE_READY", "system", reason="evidence")
    transition(item, "PENDING_REVIEW", "system", reason="queued")
    transition(item, "APPROVED_ONE", "reviewer-a", reason="first")
    if second:
        transition(
            item,
            "SECOND_REVIEW_PENDING",
            "policy",
            reason="dual",
            second_review_required=True,
        )
        transition(item, "APPROVED", "reviewer-b", reason="second")
    else:
        transition(item, "APPROVED", "policy", reason="single")
    return item


class StateMachineTests(unittest.TestCase):
    def test_ordinary_commit_requires_intent_and_stops_repeat(self) -> None:
        item = reach_approved()
        with self.assertRaises(TransitionError) as missing:
            transition(item, "WRITEBACK_PENDING", "adapter", reason="send")
        self.assertEqual(str(missing.exception), "write-intent-missing")
        item.write_intent_id = "intent-1"
        transition(item, "WRITEBACK_PENDING", "adapter", reason="send")
        transition(item, "WRITEBACK_COMMITTED", "target", reason="acked")
        with self.assertRaises(TransitionError):
            transition(item, "WRITEBACK_PENDING", "adapter", reason="again")

    def test_withdraw_and_rollback_are_mutually_exclusive(self) -> None:
        withdrawn = reach_approved()
        transition(withdrawn, "WITHDRAWN", "reviewer-a", reason="before-intent")
        self.assertEqual(withdrawn.state, "WITHDRAWN")
        rolled = reach_approved()
        rolled.write_intent_id = "intent-2"
        with self.assertRaises(TransitionError) as blocked:
            transition(rolled, "WITHDRAWN", "reviewer-a", reason="too-late")
        self.assertEqual(str(blocked.exception), "intent-exists-use-rollback")
        transition(rolled, "ROLLED_BACK", "reviewer-a", reason="not-submitted")
        self.assertEqual(rolled.state, "ROLLED_BACK")

    def test_second_reviewer_must_be_independent(self) -> None:
        item = new_suggestion()
        transition(item, "EVIDENCE_READY", "system", reason="evidence")
        transition(item, "PENDING_REVIEW", "system", reason="queued")
        transition(item, "APPROVED_ONE", "reviewer-a", reason="first")
        transition(
            item,
            "SECOND_REVIEW_PENDING",
            "policy",
            reason="dual",
            second_review_required=True,
        )
        with self.assertRaises(TransitionError) as same:
            transition(item, "APPROVED", "reviewer-a", reason="self")
        self.assertEqual(str(same.exception), "second-reviewer-not-independent")
        transition(item, "APPROVED", "reviewer-b", reason="independent")
        self.assertEqual(item.reviewers, {"reviewer-a", "reviewer-b"})

    def test_emergency_chain_cannot_reach_ordinary_commit(self) -> None:
        item = new_suggestion()
        transition(item, "EVIDENCE_READY", "system", reason="evidence")
        transition(item, "PENDING_REVIEW", "system", reason="queued")
        transition(item, "EMERGENCY_OVERRIDE", "clinician", reason="break-glass")
        transition(
            item,
            "EMERGENCY_PENDING_CONFIRMATION",
            "clinician",
            reason="issued",
            emergency_nonce="nonce-1",
        )
        with self.assertRaises(TransitionError):
            transition(
                item,
                "EMERGENCY_PENDING_CONFIRMATION",
                "clinician",
                reason="replay",
                emergency_nonce="nonce-1",
            )
        transition(item, "EMERGENCY_UNKNOWN", "adapter", reason="timeout")
        transition(item, "EMERGENCY_RECORDED", "reconciler", reason="confirmed")
        transition(item, "POST_REVIEW_REQUIRED", "audit", reason="frozen")
        transition(item, "RECONCILIATION_CONFIRMED", "safety", reason="reviewed")
        transition(item, "ARCHIVED", "audit", reason="closed")
        self.assertNotIn("APPROVED", {step[1] for step in item.history})
        self.assertNotIn("WRITEBACK_COMMITTED", {step[1] for step in item.history})

    def test_every_undeclared_edge_is_rejected_without_mutation(self) -> None:
        for source, allowed in TRANSITIONS.items():
            item = new_suggestion()
            item.state = source
            before = item.version
            for target in FORBIDDEN_FROM_EMERGENCY | {"DRAFT", "ARCHIVED"}:
                if target in allowed or target == source:
                    continue
                with self.assertRaises(TransitionError):
                    transition(item, target, "actor", reason="probe")
                self.assertEqual(item.state, source)
                self.assertEqual(item.version, before)

    def test_missing_context_and_reason_fail_closed(self) -> None:
        with self.assertRaises(TransitionError):
            Suggestion("", "patient", "action")
        item = new_suggestion()
        with self.assertRaises(TransitionError) as missing:
            transition(item, "EVIDENCE_READY", "", reason="")
        self.assertEqual(str(missing.exception), "actor-or-reason-missing")
        self.assertEqual(item.state, "DRAFT")


if __name__ == "__main__":
    unittest.main()
