"""Registered bypass paths.

A catalogued path can be counted. Using it is still forbidden.
"""
from __future__ import annotations

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_CATALOG = frozenset(
    {
        "direct-write",
        "emergency-as-approval",
        "expired-proof",
        "missing-signoff",
        "wrong-subject",
    }
)


def bypass_catalog(name: str, use: bool) -> int:
    """Return the catalog size. Never allow the named path to be used."""
    if name == "" or not isinstance(use, bool):
        raise ContractError("bypass-catalog-invalid")
    if path_has_direct_identifier(name):
        raise ContractError("bypass-catalog-forbidden")
    if name not in _CATALOG:
        raise ContractError("bypass-catalog-unknown")
    if use:
        raise ContractError("bypass-catalog-forbidden")
    return len(_CATALOG)


_KINDS = frozenset({"check", "required", "unique"})
_STATES = frozenset({"draft", "submitted"})


def db_constraint(kind: str, value: str, seen: frozenset[str]) -> str:
    """Accept one holding constraint. No statement is executed."""
    if kind not in _KINDS:
        raise ContractError("constraint-kind-invalid")
    if path_has_direct_identifier(value):
        raise ContractError("constraint-identifier-forbidden")
    if kind == "required" and value == "":
        raise ContractError("constraint-required-missing")
    if kind == "unique" and value in seen:
        raise ContractError("constraint-duplicate")
    if kind == "check" and value not in _STATES:
        raise ContractError("constraint-check-failed")
    return kind


def service_reject(signed: bool, same_subject: bool, expired: bool, proof: str, direct: bool) -> str:
    """Accept one ordinary signed write. Every other service call stops."""
    flags = (signed, same_subject, expired, direct)
    if any(not isinstance(item, bool) for item in flags) or proof not in {"approval", "grant", ""}:
        raise ContractError("service-input-invalid")
    if direct:
        raise ContractError("service-direct-write-forbidden")
    if not signed:
        raise ContractError("service-unsigned")
    if expired:
        raise ContractError("service-proof-expired")
    if not same_subject:
        raise ContractError("service-subject-mismatch")
    if proof != "approval":
        raise ContractError("service-grant-rejected")
    return "accepted"


_METHODS = frozenset({"GET", "POST"})
_ROUTES = frozenset({"orders", "reviews"})


def api_reject(method: str, content_type: str, route: str) -> str:
    """Accept one FHIR JSON write on a registered route."""
    if method not in _METHODS or content_type == "" or route == "":
        raise ContractError("api-input-invalid")
    if path_has_direct_identifier(route):
        raise ContractError("api-route-forbidden")
    if route not in _ROUTES:
        raise ContractError("api-route-unknown")
    if method != "POST":
        raise ContractError("api-method-forbidden")
    if content_type != "application/fhir+json":
        raise ContractError("api-content-type-rejected")
    return "accepted"


_SAFE_MIGRATIONS = frozenset({"add-column", "backfill"})
_DESTRUCTIVE = frozenset({"drop", "truncate"})


def migration_reject(action: str, reviewed: bool, synthetic: bool) -> str:
    """Accept one reviewed synthetic migration. Destructive actions stop."""
    flags = (reviewed, synthetic)
    if any(not isinstance(item, bool) for item in flags):
        raise ContractError("migration-input-invalid")
    if path_has_direct_identifier(action):
        raise ContractError("migration-identifier-forbidden")
    if action in _DESTRUCTIVE:
        raise ContractError("migration-destructive-forbidden")
    if action not in _SAFE_MIGRATIONS:
        raise ContractError("migration-action-unknown")
    if synthetic is not True:
        raise ContractError("migration-not-synthetic")
    if reviewed is not True:
        raise ContractError("migration-unreviewed")
    return action


_PRIVILEGED = frozenset({"admin", "dba", "root", "system"})


def privilege_reject(account: str, action: str) -> str:
    """Let an ordinary reviewer act. High-privilege accounts stop."""
    named = account.strip()
    if named == "" or action == "":
        raise ContractError("privilege-input-invalid")
    if path_has_direct_identifier(named):
        raise ContractError("privilege-identifier-forbidden")
    if named in _PRIVILEGED:
        raise ContractError("privilege-account-forbidden")
    if action not in {"review", "sign"}:
        raise ContractError("privilege-action-invalid")
    return action


def skip_switch(requested: str) -> str:
    """Report that no emergency-skip switch exists."""
    if requested not in {"query", "enable"}:
        raise ContractError("skip-switch-invalid")
    if requested == "enable":
        raise ContractError("skip-switch-absent")
    return "absent"


_SLICES = (1, 5, 10)


def canary_safety(percent: int, gate: str) -> str:
    """Keep the safety gate closed during a small canary slice."""
    if type(percent) is not int or percent not in _SLICES:
        raise ContractError("canary-slice-invalid")
    if gate != "closed":
        raise ContractError("canary-gate-open")
    return gate


_GRADES = ("blocker", "critical", "major", "minor")
_HOLD = frozenset({"blocker", "critical"})


def defect_grade(grade: str, disposition: str) -> str:
    """Classify a defect. Blocker and critical grades cannot be deferred."""
    if grade not in _GRADES or disposition not in {"defer", "fix"}:
        raise ContractError("defect-grade-invalid")
    if grade in _HOLD and disposition == "defer":
        raise ContractError("defect-defer-forbidden")
    return grade


def safety_signoff(signers: tuple[str, str], digest: str) -> int:
    """Record two distinct human signers for one safety digest."""
    if len(digest) != 64:
        raise ContractError("safety-digest-invalid")
    left, right = (item.strip() for item in signers)
    banned = left == "system" or right == "system"
    if banned or path_has_direct_identifier(left) or path_has_direct_identifier(right):
        raise ContractError("safety-signer-forbidden")
    if left == "" or right == "" or left == right:
        raise ContractError("safety-signers-invalid")
    return 2
