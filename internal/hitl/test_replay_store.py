"""Persistence tests for replay nonces."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from internal.hitl.fixtures import install_hitl_path, review_draft

install_hitl_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.write_intent import EmergencyGrant  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.hitl.test_service import config, proof_for, resource  # noqa: E402


def stored_grant(draft, grant_id: str, nonce: str) -> EmergencyGrant:
    """Build one synthetic emergency grant for a stored replay."""
    return EmergencyGrant(
        grant_id,
        draft.suggestion_id,
        "3",
        "reviewer-synthetic",
        draft.action,
        "break-glass",
        draft.content_digest,
        nonce,
        "2026-09-24T00:00:00Z",
        "2026-09-24T00:10:00Z",
    )


class ReplayStoreTests(unittest.TestCase):
    def test_reloaded_nonce_stays_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replay.json"
            service = ReviewService(config(), store_path=path)
            draft = review_draft()
            grant = stored_grant(draft, "grant-store-replay", "nonce-store")
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
            restored = ReviewService(config(), store_path=path)
            repeated = stored_grant(draft, "grant-store-replay-2", "nonce-store")
            with self.assertRaises(ContractError) as reused:
                restored.record_emergency(draft, resource(), repeated, "2026-09-24T00:06:00Z")
            self.assertEqual(str(reused.exception), "replay-nonce-reused")
            self.assertEqual(restored.emergency(draft.suggestion_id).emergency_nonce, nonce_value())
        self.assertTrue(path.name.startswith("replay"))

    def test_reloaded_commit_nonce_stays_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "commit-replay.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            proof = proof_for(approved, "proof-store", "reviewer-second", "nonce-commit-store")
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-store")
            restored = ReviewService(config(), store_path=path)
            restored._suggestions[approved.suggestion_id].state = "APPROVED"
            restored._suggestions[approved.suggestion_id].submitted = False
            repeated = proof_for(approved, "proof-store-2", "reviewer-second", "nonce-commit-store")
            with self.assertRaises(ContractError) as reused:
                restored.commit_ordinary(approved, repeated, "2026-09-24T00:31:00Z", "target-store-2")
            self.assertEqual(str(reused.exception), "replay-nonce-reused")
        self.assertTrue(path.name.startswith("commit"))

    def test_reloaded_replay_rejects_other_actor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "actor-replay.json"
            service = ReviewService(config(), store_path=path)
            suggestion = service.approve(review_draft(), resource())
            approved = service.approve_independent(suggestion, review_draft(), "reviewer-second")
            proof = proof_for(approved, "proof-actor", "reviewer-second", "nonce-actor")
            service.commit_ordinary(approved, proof, "2026-09-24T00:30:00Z", "target-actor")
            restored = ReviewService(config(), store_path=path)
            with self.assertRaises(ContractError) as blocked:
                restored.replays.accept(approved.suggestion_id, 1, "nonce-other", "other-reviewer", "treatment-review")
            self.assertEqual(str(blocked.exception), "replay-responsibility-mismatch")
        self.assertTrue(path.name.startswith("actor"))

    def test_reloaded_contract_version_blocks_saved_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "version.json"
            draft = replace(review_draft(), contract_version="1.0")
            service = ReviewService(config(), store_path=path)
            service.approve(draft, resource())
            saved = next(iter(service._drafts.values()))
            incompatible = replace(saved, contract_version="2.0")
            restored = ReviewService(config(), store_path=path)
            with self.assertRaises(ContractError) as blocked:
                restored.review_saved(saved.suggestion_id, incompatible, saved.at_time)
            self.assertEqual(str(blocked.exception), "contract-version-incompatible")
        self.assertTrue(path.name.startswith("version"))

    def test_incompatible_contract_version_blocks_emergency(self) -> None:
        service = ReviewService(config())
        draft = replace(review_draft(), contract_version="2.0")
        grant = stored_grant(draft, "grant-version", "nonce-version")
        with self.assertRaises(ContractError) as blocked:
            service.record_emergency(draft, resource(), grant, "2026-09-24T00:05:00Z")
        self.assertEqual(str(blocked.exception), "contract-version-incompatible")
        self.assertEqual(service._emergencies, {})
        self.assertIsNone(service.writes.get(grant.grant_id))


def nonce_value() -> str:
    """Return the synthetic nonce used by the stored grant."""
    return "nonce-store"


if __name__ == "__main__":
    unittest.main()
