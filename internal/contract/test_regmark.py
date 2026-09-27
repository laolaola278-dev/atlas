"""Tests for regulatory subset marks."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.regmark import regulatory_mark  # noqa: E402


class RegulatoryMarkTests(unittest.TestCase):
    def test_allowed_authority_is_recorded(self) -> None:
        mark = regulatory_mark("finding-synthetic", "cn-synthetic", "ab" * 32)
        self.assertEqual(mark["authority"], "cn-synthetic")
        self.assertNotIn("concepts", mark)

    def test_unknown_authority_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            regulatory_mark("finding-synthetic", "other", "ab" * 32)
        self.assertEqual(blocked.exception.args[0], "regmark-authority-unknown")

    def test_identifier_subset_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            regulatory_mark("subject.identifier", "cn-synthetic", "ab" * 32)
        self.assertEqual(str(blocked.exception), "regmark-subset-forbidden")


if __name__ == "__main__":
    unittest.main()
