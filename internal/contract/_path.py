"""Shared test bootstrap for contract modules.

The helper keeps each test file focused on behaviour instead of repeating
the same path setup.
"""
from __future__ import annotations

import sys
from pathlib import Path


def install_contract_path() -> None:
    """Allow tests to import the in-tree contract package."""
    root = Path(__file__).resolve().parents[2]
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
