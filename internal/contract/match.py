"""Deterministic credential matching.

The caller supplies digests, never the credential text. Equal digests inside
one partition match. A mismatch does not guess another person.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.identity import ActorContext, require_same_partition
from internal.contract.privacy import path_has_direct_identifier


def _digest(value: str) -> str:
    if len(value) != 64 or path_has_direct_identifier(value):
        raise ContractError("match-digest-invalid")
    return value


def deterministic_match(
    left: ActorContext,
    right: ActorContext,
    local_ref: str,
    left_digest: str,
    right_digest: str,
) -> str:
    """Return the shared digest when both sides name the same credential."""
    require_same_partition(left, right, local_ref)
    first = _digest(left_digest)
    second = _digest(right_digest)
    if first != second:
        raise ContractError("match-digest-mismatch")
    return first


def probabilistic_candidate(
    left: ActorContext,
    right: ActorContext,
    local_ref: str,
    name_digest: str,
    birth_digest: str,
    score: int,
) -> str:
    """Return review-required when a score is high enough to be considered."""
    require_same_partition(left, right, local_ref)
    _digest(name_digest)
    _digest(birth_digest)
    if score < 0 or score > 100:
        raise ContractError("match-score-invalid")
    if score < 80:
        raise ContractError("match-below-threshold")
    return "review-required"


def blocking_rule(findings: dict[str, bool], score: int) -> str:
    """Reject a candidate when any hard comparison disagrees."""
    required = {"birth_year_mismatch", "credential_mismatch", "sex_mismatch"}
    if set(findings) != required or any(not isinstance(value, bool) for value in findings.values()):
        raise ContractError("block-findings-invalid")
    if score < 0 or score > 100:
        raise ContractError("match-score-invalid")
    if any(findings.values()):
        raise ContractError("block-hard-mismatch")
    if score < 80:
        raise ContractError("match-below-threshold")
    return "review-required"


def newborn_policy(age_days: int, score: int, reviewers: tuple[str, str]) -> str:
    """Require two reviewers for a newborn and never auto-link."""
    if age_days < 0 or age_days > 365 or score < 0 or score > 100:
        raise ContractError("newborn-input-invalid")
    if age_days > 28:
        raise ContractError("newborn-window-closed")
    first, second = reviewers
    if first == "" or second == "":
        raise ContractError("newborn-review-missing")
    if path_has_direct_identifier(first) or path_has_direct_identifier(second):
        raise ContractError("newborn-identifier-forbidden")
    if first == second:
        raise ContractError("newborn-same-reviewer")
    if score < 95:
        raise ContractError("newborn-score-low")
    return "dual-review-required"


def same_name_regression(name_equal: bool, findings: dict[str, bool], score: int) -> str:
    """Keep a shared name from overriding a hard mismatch."""
    if not isinstance(name_equal, bool):
        raise ContractError("same-name-input-invalid")
    if not name_equal:
        raise ContractError("same-name-not-shared")
    try:
        return blocking_rule(findings, score)
    except ContractError as exc:
        if str(exc) == "block-hard-mismatch":
            raise ContractError("same-name-different-person") from exc
        raise


def explanation(findings: dict[str, bool], digest: str, score: int) -> dict[str, object]:
    """Return stable evidence codes without name or credential text."""
    required = {"birth_year_mismatch", "credential_mismatch", "sex_mismatch"}
    if set(findings) != required or score < 0 or score > 100:
        raise ContractError("explain-input-invalid")
    if len(digest) != 64 or path_has_direct_identifier(digest):
        raise ContractError("explain-digest-invalid")
    codes = tuple(name for name in sorted(required) if findings[name])
    return {"codes": codes, "digest": digest, "score": score}


CONTACT_FIELDS = frozenset({"address", "email", "phone", "telecom"})


def suppress_contacts(record: dict[str, object]) -> dict[str, object]:
    """Return the record only when no contact field is present."""
    present = CONTACT_FIELDS.intersection(record)
    if present:
        raise ContractError("contact-suppressed")
    if any(path_has_direct_identifier(str(value)) for value in record.values()):
        raise ContractError("contact-identifier-forbidden")
    return dict(record)
