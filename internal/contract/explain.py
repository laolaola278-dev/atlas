"""Synthetic order journeys.

A journey is a sequence of states, not an order body. It is accepted only when
the fixture is synthetic and the steps stay on the declared path.
"""
from __future__ import annotations

import re

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier

_PATHS = {
    "ordinary": ("draft", "submitted", "dispensed"),
    "emergency": ("draft", "recorded", "reviewed"),
}


def synthetic_journey(kind: str, steps: tuple[str, ...], synthetic: bool) -> int:
    """Accept one complete synthetic journey and return its step count."""
    if synthetic is not True:
        raise ContractError("journey-not-synthetic")
    expected = _PATHS.get(kind)
    if expected is None:
        raise ContractError("journey-kind-invalid")
    if steps != expected:
        raise ContractError("journey-path-invalid")
    return len(steps)


_GUIDE = {"dose-bound": 12, "allergy-stop": 18, "interaction-hold": 24}


def guide_entry(code: str, synthetic: bool) -> int:
    """Return the page of one synthetic guide entry."""
    if synthetic is not True:
        raise ContractError("guide-not-synthetic")
    page = _GUIDE.get(code)
    if page is None:
        raise ContractError("guide-entry-unknown")
    return page


def lab_timepoint(collected_at: str, reported_at: str) -> str:
    """Accept a lab only when collection is at or before the report."""
    pair = (collected_at.strip(), reported_at.strip())
    if any(item == "" for item in pair):
        raise ContractError("lab-time-missing")
    if any(len(item) != 20 or not item.endswith("Z") for item in pair):
        raise ContractError("lab-time-invalid")
    if pair[0] > pair[1]:
        raise ContractError("lab-time-inverted")
    return pair[0]


_HITS = frozenset({"allergy", "dose", "interaction", "duplicate"})


def hit_path(steps: tuple[str, ...]) -> int:
    """Accept a short path of distinct hard-rule hits."""
    if len(steps) == 0 or len(steps) > 4:
        raise ContractError("hit-path-invalid")
    unknown = [step for step in steps if step not in _HITS]
    if unknown:
        raise ContractError("hit-step-unknown")
    if len(frozenset(steps)) != len(steps):
        raise ContractError("hit-step-repeated")
    return len(steps)


_VOTES = frozenset({"abstain", "allow", "deny"})


def model_boundary(rule_decision: str, model_vote: str) -> str:
    """Keep the hard rule when a model vote disagrees."""
    if rule_decision not in _VOTES - {"abstain"}:
        raise ContractError("model-boundary-invalid")
    if model_vote not in _VOTES:
        raise ContractError("model-vote-invalid")
    if model_vote != "abstain" and model_vote != rule_decision:
        raise ContractError("model-cannot-override-rule")
    return rule_decision


def evidence_block(decision: str, digest: str, known: frozenset[str]) -> str:
    """Block an explanation that has no registered evidence."""
    if decision not in {"allow", "deny"}:
        raise ContractError("evidence-decision-invalid")
    if digest == "":
        raise ContractError("evidence-missing")
    if len(digest) != 64 or digest not in known:
        raise ContractError("evidence-unlocatable")
    return decision


_EXPLAIN = (("1.1", "1.1"), ("1.1", "1.0"), ("1.0", "1.0"))


def explain_version(shown: str, current: str) -> str:
    """Accept the current explanation or its immediately previous minor."""
    if current not in {"1.0", "1.1"} or shown == "":
        raise ContractError("explain-version-invalid")
    if (current, shown) not in _EXPLAIN:
        raise ContractError("explain-version-mismatch")
    return shown


_PACK = ("guide", "lab", "rule")


def review_pack(items: tuple[str, ...], digest: str, synthetic: bool) -> int:
    """Accept one synthetic review pack with the three required items."""
    if synthetic is not True:
        raise ContractError("review-pack-not-synthetic")
    if items != _PACK:
        raise ContractError("review-pack-incomplete")
    if len(digest) != 64:
        raise ContractError("review-pack-digest-invalid")
    return len(items)


def counterfactual_guard(mode: str, action: str) -> str:
    """Show a counterfactual. Never let it execute."""
    if mode not in {"factual", "counterfactual"}:
        raise ContractError("counterfactual-mode-invalid")
    if action not in {"show", "execute"}:
        raise ContractError("counterfactual-action-invalid")
    if mode == "counterfactual" and action == "execute":
        raise ContractError("counterfactual-execute-forbidden")
    return action


def explain_audit(shown: str, recorded: str, action: str) -> str:
    """Link an explanation audit only when both digests match."""
    if action not in {"show", "block"}:
        raise ContractError("explain-audit-action-invalid")
    lengths = {len(shown), len(recorded)}
    if lengths != {64}:
        raise ContractError("explain-audit-digest-invalid")
    if shown != recorded:
        raise ContractError("explain-audit-mismatch")
    return action


_SECTIONS = ("guide", "lab", "rule")
_LABEL = re.compile(r"[a-z][a-z-]{2,15}")


def clinical_readability(sections: dict[str, str]) -> int:
    """Accept three short labels. Free text stays outside this gate."""
    if tuple(sections) != _SECTIONS:
        raise ContractError("readability-sections-invalid")
    for value in sections.values():
        if path_has_direct_identifier(value):
            raise ContractError("readability-identifier-forbidden")
        if _LABEL.fullmatch(value) is None:
            raise ContractError("readability-text-forbidden")
    return len(sections)
