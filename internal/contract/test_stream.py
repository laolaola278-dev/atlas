"""Tests for late events and stream gaps."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.stream import EventStream  # noqa: E402


class StreamTests(unittest.TestCase):
    def test_contiguous_events_are_writable(self) -> None:
        stream = EventStream("stream-synthetic")
        first = stream.observe(1, "event-1", 0)
        second = stream.observe(2, "event-2", 0)
        self.assertFalse(first.late)
        self.assertEqual(stream.writable(), (first, second))

    def test_late_event_is_retained_but_not_writable(self) -> None:
        stream = EventStream("stream-synthetic")
        stream.observe(1, "event-1", 0)
        late = stream.observe(1, "event-late", 1)
        self.assertTrue(late.late)
        self.assertEqual(len(stream.writable()), 1)

    def test_gap_is_rejected(self) -> None:
        stream = EventStream("stream-synthetic")
        with self.assertRaises(ContractError) as gap:
            stream.observe(3, "event-3", 0)
        self.assertEqual(str(gap.exception), "stream-gap")
        self.assertEqual(stream.writable(), ())

    def test_withdrawn_consent_rejects_new_event(self) -> None:
        stream = EventStream("stream-synthetic")
        with self.assertRaises(ContractError) as blocked:
            stream.observe(1, "event-withdrawn", 0, "withdrawn")
        self.assertEqual(str(blocked.exception), "stream-consent-not-active")
        self.assertEqual(stream.writable(), ())

    def test_identifier_event_is_rejected(self) -> None:
        stream = EventStream("stream-synthetic")
        with self.assertRaises(ContractError) as blocked:
            stream.observe(1, "subject.identifier", 0)
        self.assertEqual(str(blocked.exception), "stream-identifier-forbidden")
        self.assertEqual(stream.writable(), ())

    def test_identifier_stream_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            EventStream("subject.identifier")
        self.assertEqual(str(blocked.exception), "stream-identifier-forbidden")

    def test_unknown_reason_is_rejected(self) -> None:
        stream = EventStream("stream-synthetic")
        with self.assertRaises(ContractError) as blocked:
            stream.observe(1, "event-1", 0, why_code="unknown")
        self.assertEqual(str(blocked.exception), "stream-why-missing")
        self.assertEqual(stream.writable(), ())

    def test_other_actor_for_recorded_sequence_is_rejected(self) -> None:
        stream = EventStream("stream-synthetic")
        stream.observe(1, "event-1", 0, actor_id="reviewer-synthetic", why_code="treatment-review")
        with self.assertRaises(ContractError) as blocked:
            stream.observe(1, "event-late", 1, actor_id="other-reviewer", why_code="treatment-review")
        self.assertEqual(str(blocked.exception), "stream-responsibility-mismatch")
        self.assertEqual(len(stream.writable()), 1)


if __name__ == "__main__":
    unittest.main()
