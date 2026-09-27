"""Multilingual display names.

A display entry is a language code plus a digest. Display text stays outside
this gate.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_LANGUAGES = frozenset({"en", "zh"})


def display_names(entries: dict[str, str]) -> dict[str, str]:
    """Accept one digest for each required language."""
    if set(entries) != _LANGUAGES:
        raise ContractError("display-language-invalid")
    if any(len(value) != 64 or path_has_direct_identifier(value) for value in entries.values()):
        raise ContractError("display-digest-invalid")
    return dict(sorted(entries.items()))
