"""Tests for official validator evidence."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.validator import require_official  # noqa: E402


def resource() -> dict[str, object]:
    return {"contentDigest": "ab" * 32, "synthetic": True}


def official() -> dict[str, object]:
    return {
        "contentDigest": "ab" * 32,
        "engine": "hapi",
        "official": True,
        "outcome": "pass",
        "outcomeId": "outcome-synthetic",
    }


class OfficialValidatorTests(unittest.TestCase):
    def test_matching_official_pass_is_accepted(self) -> None:
        self.assertEqual(require_official(resource(), official()), "outcome-synthetic")

    def test_missing_record_is_unknown(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            require_official(resource(), None)
        self.assertEqual(blocked.exception.args[0], "validator-result-unknown")

    def test_local_pass_is_not_official(self) -> None:
        local = official()
        local["official"] = False
        with self.assertRaises(ContractError) as blocked:
            require_official(resource(), local)
        self.assertEqual(str(blocked.exception), "validator-not-official")

    def test_changed_digest_is_rejected(self) -> None:
        changed = official()
        changed["contentDigest"] = "cd" * 32
        with self.assertRaises(ContractError) as blocked:
            require_official(resource(), changed)
        self.assertEqual(str(blocked.exception), "validator-digest-mismatch")


if __name__ == "__main__":
    unittest.main()
