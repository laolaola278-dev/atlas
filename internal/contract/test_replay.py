"""Tests for replay rejection and non-identifying cache keys."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.cache import CacheLedger, make_cache_key  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.replay import ReplayGuard, arrival_order, replay_compatible  # noqa: E402


class ReplayTests(unittest.TestCase):
    def test_contiguous_unique_nonces_are_accepted(self) -> None:
        guard = ReplayGuard()
        guard.accept("stream-synthetic", 1, "nonce-1")
        guard.accept("stream-synthetic", 2, "nonce-2")

    def test_reuse_gap_and_blank_nonce_are_rejected(self) -> None:
        guard = ReplayGuard()
        guard.accept("stream-synthetic", 1, "nonce-1")
        with self.assertRaises(ContractError) as reused:
            guard.accept("stream-synthetic", 2, "nonce-1")
        self.assertEqual(str(reused.exception), "replay-nonce-reused")
        with self.assertRaises(ContractError) as gap:
            guard.accept("stream-synthetic", 4, "nonce-4")
        self.assertEqual(str(gap.exception), "replay-sequence-invalid")
        with self.assertRaises(ContractError):
            guard.accept("stream-synthetic", 2, "")

    def test_identifier_nonce_is_rejected(self) -> None:
        guard = ReplayGuard()
        with self.assertRaises(ContractError) as blocked:
            guard.accept("stream-synthetic", 1, "subject.identifier")
        self.assertEqual(str(blocked.exception), "replay-identifier-forbidden")
        guard.accept("stream-synthetic", 1, "nonce-clean")

    def test_unknown_reason_is_rejected(self) -> None:
        guard = ReplayGuard()
        with self.assertRaises(ContractError) as blocked:
            guard.accept("stream-synthetic", 1, "nonce-1", why_code="unknown")
        self.assertEqual(str(blocked.exception), "replay-why-missing")
        guard.accept("stream-synthetic", 1, "nonce-1")

    def test_other_actor_for_recorded_sequence_is_rejected(self) -> None:
        guard = ReplayGuard()
        guard.accept("stream-synthetic", 1, "nonce-1", "reviewer-synthetic", "treatment-review")
        with self.assertRaises(ContractError) as blocked:
            guard.accept("stream-synthetic", 1, "nonce-2", "other-reviewer", "treatment-review")
        self.assertEqual(str(blocked.exception), "replay-responsibility-mismatch")

    def test_previous_minor_can_replay(self) -> None:
        version = replay_compatible("1.0", "1.1", "ab" * 32, "ab" * 32)
        self.assertEqual(version, "1.0")

    def test_skipped_version_cannot_replay(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            replay_compatible("1.0", "1.2", "ab" * 32, "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "replay-version-incompatible")

    def test_changed_digest_cannot_replay(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            replay_compatible("1.0", "1.0", "ab" * 32, "cd" * 32)
        self.assertEqual(str(blocked.exception), "replay-digest-mismatch")

    def test_expected_sequence_is_in_order(self) -> None:
        self.assertEqual(arrival_order(4, 4, 5), "in-order")

    def test_older_sequence_is_reordered(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            arrival_order(4, 3, 1)
        self.assertEqual(blocked.exception.args[0], "arrival-reordered")

    def test_late_event_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            arrival_order(4, 4, 31)
        self.assertEqual(str(blocked.exception), "arrival-late")


class CacheKeyTests(unittest.TestCase):
    def test_key_is_stable_and_contains_policy_version(self) -> None:
        first = make_cache_key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.0.0",
            ["value", "code"],
        )
        second = make_cache_key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.0.0",
            ["code", "value"],
        )
        self.assertEqual(first, second)
        self.assertIn("1.0.0", first)
        changed = make_cache_key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.1.0",
            ["code", "value"],
        )
        self.assertNotEqual(first, changed)

    def test_withdrawn_consent_changes_cache_key(self) -> None:
        active = make_cache_key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.0.0",
            ["code"],
            "active",
        )
        withdrawn = make_cache_key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.0.0",
            ["code"],
            "withdrawn",
        )
        self.assertNotEqual(active, withdrawn)
        self.assertIn("withdrawn", withdrawn)
        with self.assertRaises(ContractError) as invalid:
            make_cache_key(
                "tenant-synthetic",
                "campus-synthetic",
                "Observation",
                "1.0.0",
                ["code"],
                "unknown",
            )
        self.assertEqual(str(invalid.exception), "cache-consent-invalid")

    def test_identifier_and_missing_scope_are_rejected(self) -> None:
        with self.assertRaises(ContractError) as forbidden:
            make_cache_key(
                "tenant-synthetic",
                "campus-synthetic",
                "Patient",
                "1.0.0",
                ["name"],
            )
        self.assertEqual(str(forbidden.exception), "cache-phi-forbidden")
        with self.assertRaises(ContractError) as nested:
            make_cache_key(
                "tenant-synthetic",
                "campus-synthetic",
                "Observation",
                "1.0.0",
                ["subject.identifier"],
            )
        self.assertEqual(str(nested.exception), "cache-phi-forbidden")
        with self.assertRaises(ContractError) as scope:
            make_cache_key(
                "subject.identifier",
                "campus-synthetic",
                "Observation",
                "1.0.0",
                ["code"],
            )
        self.assertEqual(str(scope.exception), "cache-identifier-forbidden")
        with self.assertRaises(ContractError):
            make_cache_key("", "campus-synthetic", "Observation", "1.0.0", ["code"])
        with self.assertRaises(ContractError) as reason:
            make_cache_key(
                "tenant-synthetic",
                "campus-synthetic",
                "Observation",
                "1.0.0",
                ["code"],
                why_code="unknown",
            )
        self.assertEqual(str(reason.exception), "cache-why-missing")

    def test_other_actor_for_same_cache_scope_is_rejected(self) -> None:
        ledger = CacheLedger()
        ledger.key(
            "tenant-synthetic",
            "campus-synthetic",
            "Observation",
            "1.0.0",
            ["code"],
            actor_id="reviewer-synthetic",
        )
        with self.assertRaises(ContractError) as blocked:
            ledger.key(
                "tenant-synthetic",
                "campus-synthetic",
                "Observation",
                "1.0.0",
                ["code"],
                actor_id="other-reviewer",
            )
        self.assertEqual(str(blocked.exception), "cache-responsibility-mismatch")


if __name__ == "__main__":
    unittest.main()
