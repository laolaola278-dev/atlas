"""Synthetic fixtures for HITL review tests.

The values are labels, not patient data. Tests share this builder so the
safety assertions stay in the individual test files.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from internal.contract.consent import Consent  # noqa: E402
from internal.contract.domain import SuggestionDraft  # noqa: E402
from internal.contract.evidence import EvidenceRef  # noqa: E402
from internal.contract.rules import RulePack  # noqa: E402


def install_hitl_path() -> None:
    """Keep the package root available for HITL tests."""
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)


def review_draft(consent_state: str = "active", suggestion_id: str = "suggestion-synthetic") -> SuggestionDraft:
    """Build one complete synthetic suggestion draft."""
    return SuggestionDraft(
        suggestion_id,
        "patient-ref-synthetic",
        "review-order",
        "d" * 64,
        (EvidenceRef("lab", "source-lab", "Observation/lab", "1", "e" * 64),),
        RulePack("pack-1", "1.0.0", "f" * 64, "active", "2026-01-01", "2028-01-01"),
        Consent("consent-1", "1", consent_state, "treatment", "2026-01-01", "2027-01-01"),
        {
            "actor_id": "reviewer-synthetic",
            "actor_role": "attending",
            "tenant_id": "tenant-synthetic",
            "campus_id": "campus-synthetic",
            "purpose_code": "treatment",
            "why_code": "review-decision",
            "occurred_at": "2026-09-24T00:00:00Z",
        },
        "2026-09-24",
    )
