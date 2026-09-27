"""Consent decisions.

Only an active, unexpired consent for the requested purpose can allow access.
Withdrawn, expired, and undetermined states fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


@dataclass(frozen=True)
class Consent:
    consent_id: str
    version: str
    state: str
    purpose_code: str
    effective_from: str
    effective_to: str


def authorize(
    consent: Consent,
    purpose_code: str,
    at_time: str,
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> None:
    """Raise unless this consent permits the purpose at the given time."""
    if not consent.consent_id or not consent.version or not consent.purpose_code or not actor_id:
        raise ContractError("consent-incomplete")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("consent-why-missing")
    named = (consent.consent_id, consent.purpose_code, actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in named):
        raise ContractError("consent-identifier-forbidden")
    if not compatible(consent.version):
        raise ContractError("consent-version-incompatible")
    if consent.state != "active":
        raise ContractError("consent-not-active")
    if consent.purpose_code != purpose_code:
        raise ContractError("consent-purpose-mismatch")
    if not at_time or at_time < consent.effective_from or at_time >= consent.effective_to:
        raise ContractError("consent-outside-window")


class ConsentLedger:
    """Remember one authorization so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def authorize(
        self,
        consent: Consent,
        purpose_code: str,
        at_time: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> None:
        authorize(consent, purpose_code, at_time, actor_id, why_code)
        recorded = self._records.get(consent.consent_id)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("consent-responsibility-mismatch")
        self._records.setdefault(consent.consent_id, incoming)

    def restore(self, consent_id: str, actor_id: str, why_code: str) -> None:
        """Restore one authorization without treating it as a new review."""
        if not consent_id or not actor_id or why_code in {"", "unknown", "unspecified"}:
            raise ContractError("consent-incomplete")
        self._records[consent_id] = (actor_id, why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored consent decisions in stable order."""
        return tuple(sorted(self._records.items()))
