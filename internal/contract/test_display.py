"""Tests for multilingual display names."""
import unittest

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.display import display_names  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402


class DisplayNameTests(unittest.TestCase):
    def test_both_languages_keep_digests(self) -> None:
        shown = display_names({"en": "ab" * 32, "zh": "cd" * 32})
        self.assertEqual(tuple(shown), ("en", "zh"))
        self.assertNotIn("text", shown)

    def test_missing_language_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            display_names({"en": "ab" * 32})
        self.assertEqual(blocked.exception.args[0], "display-language-invalid")

    def test_display_text_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as blocked:
            display_names({"en": "plain-label", "zh": "cd" * 32})
        self.assertEqual(str(blocked.exception), "display-digest-invalid")


if __name__ == "__main__":
    unittest.main()
