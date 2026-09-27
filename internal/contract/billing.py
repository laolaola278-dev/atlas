"""Billing grouper isolation.

A grouper result stays in its own lane. Billing cannot enter clinical, and
clinical cannot enter billing.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


_LANES = frozenset({"billing", "clinical"})
_CROSS = frozenset({("billing", "clinical"), ("clinical", "billing")})


def grouper_isolation(source: str, target: str) -> str:
    """Keep one grouper result inside the lane it already occupies."""
    pair = (source, target)
    if source not in _LANES or target not in _LANES:
        raise ContractError("grouper-lane-invalid")
    if pair in _CROSS:
        raise ContractError("grouper-isolated")
    return source


_YEARS = frozenset({"2024", "2025"})


def code_version_lock(submitted: str, locked: str) -> str:
    """Accept a billing code only on the locked catalog year."""
    pair = (submitted, locked)
    if submitted not in _YEARS or locked not in _YEARS:
        raise ContractError("code-version-unknown")
    if pair[0] != pair[1]:
        raise ContractError("code-version-mismatch")
    return locked


_ADDON = {"A10": "L1", "B20": "L2"}


def local_variance(national: str, addon: str) -> str:
    """Accept only the addon registered for one national catalog code."""
    expected = _ADDON.get(national)
    if expected is None:
        raise ContractError("local-code-unknown")
    if addon != expected:
        raise ContractError("local-code-mismatch")
    return expected


_WHY = (("G1", "complication"), ("G2", "procedure"))


def grouper_reason(group: str, reason: str) -> int:
    """Count a registered grouper reason. Free text is not returned."""
    matched = [item for item in _WHY if item[0] == group]
    if not matched:
        raise ContractError("group-reason-unknown")
    if matched[0][1] != reason:
        raise ContractError("group-reason-mismatch")
    return len(matched[0][1])


_DECISIONS = frozenset({"hold", "release"})


def human_review(first: str, second: str, decision: str) -> str:
    """Require two different people. A system actor cannot release billing."""
    actors = (first, second)
    if decision not in _DECISIONS:
        raise ContractError("billing-review-invalid")
    if any(not item or item == "system" or item == actors[0] and actors[0] == actors[1] for item in actors):
        raise ContractError("billing-review-forbidden")
    if actors[0] == actors[1]:
        raise ContractError("billing-review-forbidden")
    return decision


def charge_line(quantity: int, unit_cents: int, claimed: int) -> int:
    """Accept a charge only when quantity times unit price equals the claim."""
    numbers = (quantity, unit_cents, claimed)
    if any(type(item) is not int for item in numbers):
        raise ContractError("charge-line-invalid")
    if quantity < 1 or quantity > 99 or unit_cents < 1 or unit_cents > 100_000:
        raise ContractError("charge-line-invalid")
    total = quantity * unit_cents
    if claimed != total:
        raise ContractError("charge-line-mismatch")
    return total


_DENIALS = frozenset({"duplicate", "uncovered", "late"})


def denial_reason(code: str, year: str) -> str:
    """Return a registered denial code for one locked catalog year."""
    if year not in _YEARS:
        raise ContractError("denial-year-unknown")
    if code not in _DENIALS:
        raise ContractError("denial-reason-unknown")
    return code


_BATCHES = {"B01": 100, "B02": 250}


def batch_reconcile(batch: str, claimed: int) -> int:
    """Accept a registered batch only when the claimed total matches."""
    if type(claimed) is not int:
        raise ContractError("batch-total-invalid")
    expected = _BATCHES.get(batch)
    if expected is None:
        raise ContractError("batch-unknown")
    if claimed != expected:
        raise ContractError("batch-total-mismatch")
    return expected


_REPLAY = frozenset({("R1", "a" * 64), ("R2", "b" * 64)})


def rule_replay(rule: str, digest: str) -> int:
    """Count a registered billing-rule digest. Rule text is not returned."""
    known = {item[0] for item in _REPLAY}
    if rule not in known:
        raise ContractError("rule-replay-unknown")
    if (rule, digest) not in _REPLAY:
        raise ContractError("rule-replay-mismatch")
    return len(digest)
