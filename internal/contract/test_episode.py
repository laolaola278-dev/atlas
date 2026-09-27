"""Tests for episode aggregation."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.episode import aggregate_episode  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


class EpisodeTests(unittest.TestCase):
    def test_events_join_one_encounter(self) -> None:
        episode = aggregate_episode("encounter-synthetic", ("ab" * 32, "cd" * 32))
        self.assertEqual(episode["count"], 2)
        self.assertNotIn("events", episode)

    def test_duplicate_event_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            aggregate_episode("encounter-synthetic", ("ab" * 32, "ab" * 32))
        self.assertEqual(blocked.exception.args[0], "episode-duplicate")

    def test_identifier_reference_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            aggregate_episode("subject.identifier", ("ab" * 32,))
        self.assertEqual(str(blocked.exception), "episode-reference-forbidden")


if __name__ == "__main__":
    unittest.main()
