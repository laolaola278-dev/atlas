"""Tests for terminology cache expiry."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.cache import terminology_cache  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


class TerminologyCacheTests(unittest.TestCase):
    def test_active_release_keeps_its_digest(self) -> None:
        digest = terminology_cache("2027-01-01", "2026-09-24", "ab" * 32)
        self.assertEqual(digest, "ab" * 32)

    def test_expired_release_invalidates_cache(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            terminology_cache("2026-01-01", "2026-09-24", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "termcache-expired")

    def test_short_digest_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            terminology_cache("2027-01-01", "2026-09-24", "abcd")
        self.assertEqual(str(blocked.exception), "termcache-digest-invalid")


if __name__ == "__main__":
    unittest.main()
