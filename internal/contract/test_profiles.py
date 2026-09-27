"""Tests for the local FHIR profile catalog."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.profiles import (  # noqa: E402
    ProfileLedger,
    load_synthetic_fixture,
    require_declared_profile,
    require_differential,
)


class ProfileCatalogTests(unittest.TestCase):
    def test_synthetic_observation_declares_catalog_profile(self) -> None:
        payload = load_synthetic_fixture("observation")
        profile = require_declared_profile(payload)
        self.assertTrue(profile.endswith("/observation"))

    def test_unknown_profile_is_rejected(self) -> None:
        payload = load_synthetic_fixture("observation")
        payload["meta"] = {"profile": ["http://example.invalid/atlas/unknown"]}
        with self.assertRaises(ContractError) as blocked:
            require_declared_profile(payload)
        self.assertEqual(str(blocked.exception), "profile-not-declared")

    def test_non_synthetic_fixture_is_rejected(self) -> None:
        payload = load_synthetic_fixture("observation")
        payload["synthetic"] = False
        with self.assertRaises(ContractError) as blocked:
            require_declared_profile(payload)
        self.assertEqual(str(blocked.exception), "profile-fixture-not-synthetic")

    def test_unknown_reason_is_rejected(self) -> None:
        payload = load_synthetic_fixture("observation")
        payload["whyCode"] = "unknown"
        with self.assertRaises(ContractError) as blocked:
            require_declared_profile(payload)
        self.assertEqual(str(blocked.exception), "profile-why-missing")

    def test_other_actor_for_same_resource_is_rejected(self) -> None:
        ledger = ProfileLedger()
        first = load_synthetic_fixture("observation")
        first["actorId"] = "reviewer-synthetic"
        ledger.require(first)
        other = load_synthetic_fixture("observation")
        other["actorId"] = "other-reviewer"
        with self.assertRaises(ContractError) as blocked:
            ledger.require(other)
        self.assertEqual(str(blocked.exception), "profile-responsibility-mismatch")

    def test_differential_requires_status_and_rejects_name(self) -> None:
        payload = load_synthetic_fixture("observation")
        payload["status"] = "final"
        require_differential(payload)
        missing = dict(payload)
        missing.pop("status")
        with self.assertRaises(ContractError) as absent:
            require_differential(missing)
        self.assertEqual(absent.exception.args[0], "profile-required-missing")
        named = dict(payload)
        named["name"] = "synthetic"
        with self.assertRaises(ContractError) as forbidden:
            require_differential(named)
        self.assertEqual(str(forbidden.exception), "profile-forbidden-present")


if __name__ == "__main__":
    unittest.main()
