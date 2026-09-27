"""Deterministic medication safety checks.

These checks cover interaction, contraindication, dose limit, allergy, and
duplicate therapy. A model decision cannot replace the rule decision.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.rules import deterministic_decision


def medication_decision(
    findings: dict[str, bool],
    model_decision: str,
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> str:
    """Return deny when any hard medication finding is present."""
    required = {"interaction", "contraindication", "dose_limit", "allergy", "duplicate"}
    if set(findings) != required or any(not isinstance(value, bool) for value in findings.values()):
        raise ContractError("medication-findings-invalid")
    if not actor_id:
        raise ContractError("medication-facts-incomplete")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("medication-why-missing")
    if path_has_direct_identifier(actor_id) or path_has_direct_identifier(why_code):
        raise ContractError("medication-identifier-forbidden")
    rule_decision = "deny" if any(findings.values()) else "allow"
    return deterministic_decision(rule_decision, model_decision)


class MedicationLedger:
    """Remember one finding set so a later actor cannot decide it silently."""

    def __init__(self) -> None:
        self._records: dict[tuple[tuple[str, bool], ...], tuple[str, str]] = {}

    def decide(
        self,
        findings: dict[str, bool],
        model_decision: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> str:
        decision = medication_decision(findings, model_decision, actor_id, why_code)
        key = tuple(sorted(findings.items()))
        recorded = self._records.get(key)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("medication-responsibility-mismatch")
        self._records.setdefault(key, incoming)
        return decision

    def restore(self, findings: tuple[tuple[str, bool], ...], actor_id: str, why_code: str) -> None:
        """Restore one finding decision without treating it as a new review."""
        if not findings or not actor_id or why_code in {"", "unknown", "unspecified"}:
            raise ContractError("medication-facts-incomplete")
        self._records[tuple(sorted(findings))] = (actor_id, why_code)

    def records(self) -> tuple[tuple[tuple[tuple[str, bool], ...], tuple[str, str]], ...]:
        """Return stored medication decisions in stable order."""
        return tuple(sorted(self._records.items()))


def derive_findings(facts: dict[str, object]) -> dict[str, bool]:
    """Derive the five hard findings from complete synthetic facts."""
    required = {"pairs", "blocked_conditions", "dose", "dose_limit", "allergens", "ordered", "active"}
    if set(facts) != required:
        raise ContractError("medication-facts-incomplete")
    pairs = facts["pairs"]
    blocked = facts["blocked_conditions"]
    allergens = facts["allergens"]
    ordered = facts["ordered"]
    active = facts["active"]
    if not all(isinstance(values, tuple) for values in (pairs, blocked, allergens, ordered, active)):
        raise ContractError("medication-facts-incomplete")
    dose = facts["dose"]
    limit = facts["dose_limit"]
    if not isinstance(dose, int) or not isinstance(limit, int) or dose < 0 or limit <= 0:
        raise ContractError("medication-facts-incomplete")
    coded = (*pairs, *blocked, *allergens, *ordered, *active)
    if any(not isinstance(item, str) or path_has_direct_identifier(item) for item in coded):
        raise ContractError("medication-identifier-forbidden")
    return {
        "allergy": bool(set(allergens) & set(ordered)),
        "contraindication": bool(blocked),
        "dose_limit": dose > limit,
        "duplicate": bool(set(ordered) & set(active)),
        "interaction": bool(pairs),
    }


def interaction_decision(pair: tuple[str, str], known: frozenset[str]) -> str:
    """Deny only a registered pair. Order does not change the decision."""
    if len(pair) != 2 or pair[0] == pair[1]:
        raise ContractError("interaction-pair-invalid")
    if any(len(item) != 64 for item in pair):
        raise ContractError("interaction-digest-invalid")
    if not known or any(item not in known for item in pair):
        raise ContractError("interaction-unknown")
    return "deny"


def contraindication(condition: str, known: frozenset[str]) -> str:
    """Deny a registered condition. An unknown condition is not safe."""
    if len(condition) != 64:
        raise ContractError("contraindication-digest-invalid")
    if not known:
        raise ContractError("contraindication-registry-invalid")
    if condition not in known:
        raise ContractError("contraindication-unknown")
    return "deny"


_DOSE_UNITS = frozenset({"mg", "ug"})
_TO_UG = {"mg": 1000, "ug": 1}


def dose_limit(amount: int, unit: str, limit_ug: int) -> str:
    """Deny a dose that exceeds the limit after a fixed unit conversion."""
    if unit not in _DOSE_UNITS:
        raise ContractError("dose-unit-unknown")
    if amount < 0 or limit_ug <= 0:
        raise ContractError("dose-input-invalid")
    converted = amount * _TO_UG[unit]
    if converted > limit_ug:
        raise ContractError("dose-limit-exceeded")
    return "allow"


def allergy_cross(allergen: str, candidate: str, groups: dict[str, str]) -> str:
    """Deny when a known allergen and the candidate share one group."""
    pair = (allergen, candidate)
    if any(len(item) != 64 for item in pair) or allergen == candidate:
        raise ContractError("allergy-digest-invalid")
    if not groups or any(len(value) != 64 for value in groups.values()):
        raise ContractError("allergy-group-invalid")
    if allergen not in groups or candidate not in groups:
        raise ContractError("allergy-unknown")
    if groups[allergen] != groups[candidate]:
        raise ContractError("allergy-no-cross")
    return "deny"


def age_weight_bound(age_days: int, weight_g: int) -> str:
    """Accept one synthetic age and weight inside the declared bounds."""
    if age_days < 0 or age_days > 36500:
        raise ContractError("age-bound-invalid")
    if weight_g < 500 or weight_g > 300000:
        raise ContractError("weight-bound-invalid")
    return "inside"


def reproductive_rule(state: str, restricted: bool) -> str:
    """Deny a restricted medicine for a declared reproductive state."""
    if state not in {"none", "pregnancy", "lactation"}:
        raise ContractError("reproductive-state-invalid")
    if not isinstance(restricted, bool):
        raise ContractError("reproductive-state-invalid")
    if state != "none" and restricted:
        raise ContractError("reproductive-restricted")
    return "allow"


def critical_lab(value: int, low: int, high: int) -> str:
    """Deny a lab value outside its closed critical interval."""
    if low >= high or value < 0:
        raise ContractError("critical-range-invalid")
    if value < low or value > high:
        raise ContractError("critical-value")
    return "inside"


def evidence_citation(decision: str, digest: str, known: frozenset[str]) -> str:
    """Require a registered citation before a denial can stand."""
    if decision not in {"allow", "deny"}:
        raise ContractError("evidence-decision-invalid")
    if decision == "allow":
        return decision
    if len(digest) != 64 or digest not in known:
        raise ContractError("evidence-citation-missing")
    return digest


def uncertain_rule(state: str) -> str:
    """Allow only a certain rule. Unknown and uncertain both fail closed."""
    if state == "certain":
        return "allow"
    if state in {"unknown", "uncertain"}:
        raise ContractError("rule-uncertain-denied")
    raise ContractError("rule-certainty-invalid")


def model_timeout(rule_decision: str, timed_out: bool) -> str:
    """Return the hard rule even when the model timed out."""
    if rule_decision not in {"allow", "deny"} or not isinstance(timed_out, bool):
        raise ContractError("timeout-input-invalid")
    if timed_out:
        return rule_decision
    return rule_decision
