"""Minimal FHIR resource gate.

This is not the official HAPI validator. It blocks structurally incomplete
resources before they can reach review. Profile validation remains a later
integration step.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import find_direct_identifier, path_has_direct_identifier
from internal.contract.profiles import ProfileLedger, require_declared_profile
from internal.contract.terminology import ReleaseLedger, require_active_release
from internal.contract.version import compatible


ALLOWED_TYPES = frozenset({
    "Patient",
    "Encounter",
    "Observation",
    "Condition",
    "AllergyIntolerance",
    "MedicationRequest",
    "DiagnosticReport",
    "DocumentReference",
    "Procedure",
    "Provenance",
    "ServiceRequest",
})
PATIENT_DEMOGRAPHICS = frozenset({
    "address",
    "birthDate",
    "contact",
    "identifier",
    "name",
    "photo",
    "telecom",
})
ENCOUNTER_STATUSES = frozenset({
    "arrived",
    "cancelled",
    "finished",
    "in-progress",
    "onleave",
    "planned",
    "triaged",
})
CONDITION_CLINICAL = frozenset({
    "active",
    "inactive",
    "recurrence",
    "relapse",
    "remission",
    "resolved",
})
ALLERGY_SEVERITY = frozenset({"mild", "moderate", "severe"})
PROCEDURE_STATUSES = frozenset({
    "completed",
    "in-progress",
    "not-done",
    "on-hold",
    "preparation",
    "stopped",
})
REPORT_STATUSES = frozenset({
    "amended",
    "appended",
    "cancelled",
    "corrected",
    "final",
    "partial",
    "preliminary",
    "registered",
})
REQUEST_PRIORITIES = frozenset({"asap", "routine", "stat", "urgent"})


@dataclass(frozen=True)
class FhirIssue:
    path: str
    code: str


def _require_release(
    releases: ReleaseLedger | None,
    system_url: str,
    reviewed_at: str,
    payload: dict[str, object],
) -> None:
    """Use the ledger when the FHIR gate owns one."""
    actor_id = str(payload.get("actorId", "actor-synthetic"))
    why_code = str(payload.get("whyCode", "treatment-review"))
    if releases is None:
        require_active_release(system_url, reviewed_at, actor_id, why_code)
        return
    releases.require(system_url, reviewed_at, actor_id, why_code)


def _require_profile(profiles: ProfileLedger | None, payload: dict[str, object]) -> None:
    """Use the ledger when the FHIR gate owns one."""
    if profiles is None:
        require_declared_profile(payload)
        return
    profiles.require(payload)


def validate_resource(
    payload: dict[str, object],
    releases: ReleaseLedger | None = None,
    profiles: ProfileLedger | None = None,
) -> tuple[FhirIssue, ...]:
    """Return structural issues. Callers must treat any issue as invalid."""
    issues: list[FhirIssue] = []
    resource_type = str(payload.get("resourceType", ""))
    if resource_type not in ALLOWED_TYPES:
        issues.append(FhirIssue("resourceType", "resource-type-rejected"))
    if not str(payload.get("id", "")):
        issues.append(FhirIssue("id", "resource-id-missing"))
    meta = payload.get("meta", {})
    version_id = str(meta.get("versionId", "")) if isinstance(meta, dict) else ""
    if not version_id:
        issues.append(FhirIssue("meta.versionId", "resource-version-missing"))
    elif not compatible(version_id):
        issues.append(FhirIssue("meta.versionId", "resource-version-incompatible"))
    declared = meta.get("profile", []) if isinstance(meta, dict) else []
    if not isinstance(declared, list) or not declared:
        issues.append(FhirIssue("meta.profile", "profile-missing"))
    if not str(payload.get("purposeCode", "")):
        issues.append(FhirIssue("purposeCode", "purpose-missing"))
    actor_id = str(payload.get("actorId", "actor-synthetic"))
    why_code = str(payload.get("whyCode", "treatment-review"))
    if not actor_id:
        issues.append(FhirIssue("actorId", "actor-context-incomplete"))
    if why_code in {"", "unknown", "unspecified"}:
        issues.append(FhirIssue("whyCode", "actor-why-missing"))
    named = (actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in named):
        issues.append(FhirIssue("whyCode", "direct-identifier-forbidden"))
    consent_state = str(payload.get("consentState", "active"))
    if consent_state != "active":
        issues.append(FhirIssue("consentState", "consent-not-active"))
    if resource_type != "Patient" and not _patient_reference(payload.get("subject", payload.get("patient"))):
        issues.append(FhirIssue("subject", "patient-reference-missing"))
    demographic = _patient_demographic(payload)
    if demographic:
        issues.append(FhirIssue(demographic, "patient-identifier-forbidden"))
    issues.extend(_encounter_window(payload))
    issues.extend(_observation_quantity(payload))
    issues.extend(_condition_status(payload))
    issues.extend(_medication_dose(payload))
    issues.extend(_allergy_severity(payload))
    issues.extend(_procedure_timing(payload))
    issues.extend(_report_status(payload))
    issues.extend(_document_digest(payload))
    issues.extend(_request_priority(payload))
    issues.extend(_provenance_chain(payload))
    system_url = str(payload.get("codeSystem", ""))
    reviewed_at = str(payload.get("reviewedAt", ""))
    if system_url or reviewed_at:
        try:
            _require_release(releases, system_url, reviewed_at, payload)
        except ContractError as exc:
            issues.append(FhirIssue("codeSystem", str(exc)))
    if payload.get("synthetic") is True:
        try:
            _require_profile(profiles, payload)
        except ContractError as exc:
            issues.append(FhirIssue("meta.profile", str(exc)))
    forbidden = find_direct_identifier(payload)
    if forbidden:
        issues.append(FhirIssue(forbidden, "direct-identifier-forbidden"))
    return tuple(issues)


def patient_reference(payload: dict[str, object]) -> str:
    """Return the referenced patient identifier, or an empty string."""
    value = payload.get("subject", payload.get("patient"))
    if not isinstance(value, dict):
        return ""
    reference = str(value.get("reference", ""))
    prefix = "Patient/"
    if not reference.startswith(prefix) or reference == prefix:
        return ""
    token = reference[len(prefix):]
    if path_has_direct_identifier(token):
        return ""
    return token


def _patient_reference(value: object) -> bool:
    return bool(patient_reference({"subject": value}) if isinstance(value, dict) else {})


def _provenance_chain(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return source-chain issues for one Provenance resource."""
    if payload.get("resourceType") != "Provenance":
        return ()
    found: list[FhirIssue] = []
    target = payload.get("target")
    reference = str(target.get("reference", "")) if isinstance(target, dict) else ""
    slash = reference.find("/")
    kind, _, token = reference.partition("/")
    linked = kind in ALLOWED_TYPES and kind not in {"Patient", "Provenance"}
    if slash < 1 or not linked or token == "" or path_has_direct_identifier(token):
        found.append(FhirIssue("target", "provenance-target-missing"))
    recorded = str(payload.get("recorded", ""))
    if "T" not in recorded or recorded.endswith("T"):
        found.append(FhirIssue("recorded", "provenance-recorded-missing"))
    agent = payload.get("agent")
    who = str(agent.get("reference", "")) if isinstance(agent, dict) else ""
    if not who.startswith("Practitioner/") or path_has_direct_identifier(who):
        found.append(FhirIssue("agent", "provenance-agent-missing"))
    return tuple(found)


def _request_priority(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when a service request has no known priority."""
    if payload.get("resourceType") != "ServiceRequest":
        return ()
    priority = payload.get("priority")
    if isinstance(priority, str) and priority in REQUEST_PRIORITIES:
        return ()
    missing = priority in {None, ""}
    code = "request-priority-missing" if missing else "request-priority-invalid"
    return (FhirIssue("priority", code),)


def _document_digest(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when a document has no 64-character content digest."""
    if payload.get("resourceType") != "DocumentReference":
        return ()
    digest = payload.get("contentDigest")
    text = digest if isinstance(digest, str) else ""
    if len(text) == 0:
        return (FhirIssue("contentDigest", "document-hash-missing"),)
    hex_chars = set("0123456789abcdef")
    valid = len(text) == 64 and set(text).issubset(hex_chars)
    if valid:
        return ()
    return (FhirIssue("contentDigest", "document-hash-invalid"),)


def _report_status(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when a report has no known conclusion status."""
    if str(payload.get("resourceType", "")) != "DiagnosticReport":
        return ()
    status = str(payload.get("status", ""))
    if status in REPORT_STATUSES:
        return ()
    code = "report-status-missing" if status == "" else "report-status-invalid"
    return (FhirIssue("status", code),)


def _procedure_timing(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return status and performed-window issues for one Procedure."""
    if str(payload.get("resourceType", "")) != "Procedure":
        return ()
    found: list[FhirIssue] = []
    status = str(payload.get("status", ""))
    if status not in PROCEDURE_STATUSES:
        code = "procedure-status-missing" if status == "" else "procedure-status-invalid"
        found.append(FhirIssue("status", code))
    performed = payload.get("performed")
    start = str(performed.get("start", "")) if isinstance(performed, dict) else ""
    end = str(performed.get("end", "")) if isinstance(performed, dict) else ""
    if not start:
        found.append(FhirIssue("performed.start", "procedure-time-missing"))
    elif end and start > end:
        found.append(FhirIssue("performed.end", "procedure-time-inverted"))
    return tuple(found)


def _allergy_severity(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when an allergy has no known severity."""
    if str(payload.get("resourceType", "")) != "AllergyIntolerance":
        return ()
    severity = str(payload.get("severity", ""))
    if severity in ALLERGY_SEVERITY:
        return ()
    code = "allergy-severity-missing" if not severity else "allergy-severity-invalid"
    return (FhirIssue("severity", code),)


def _medication_dose(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when a MedicationRequest dose is incomplete."""
    if str(payload.get("resourceType", "")) != "MedicationRequest":
        return ()
    dose = payload.get("dose")
    if dose is None:
        return ()
    amount = dose.get("value") if isinstance(dose, dict) else None
    unit = str(dose.get("unit", "")) if isinstance(dose, dict) else ""
    route = str(dose.get("route", "")) if isinstance(dose, dict) else ""
    positive = isinstance(amount, (int, float)) and not isinstance(amount, bool) and amount > 0
    if positive and unit and route:
        return ()
    return (FhirIssue("dose", "medication-dose-invalid"),)


def _condition_status(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return one issue when a Condition has no known clinical status."""
    if str(payload.get("resourceType", "")) != "Condition":
        return ()
    status = str(payload.get("clinicalStatus", ""))
    if status in CONDITION_CLINICAL:
        return ()
    code = "condition-status-missing" if status == "" else "condition-status-invalid"
    return (FhirIssue("clinicalStatus", code),)


def _observation_quantity(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return unit and reference-range issues for one Observation."""
    if str(payload.get("resourceType", "")) != "Observation":
        return ()
    found: list[FhirIssue] = []
    quantity = payload.get("valueQuantity")
    if quantity is not None:
        value = quantity.get("value") if isinstance(quantity, dict) else None
        unit = str(quantity.get("unit", "")) if isinstance(quantity, dict) else ""
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not unit:
            found.append(FhirIssue("valueQuantity", "observation-quantity-invalid"))
    bounds = payload.get("referenceRange")
    if isinstance(bounds, dict):
        low = bounds.get("low")
        high = bounds.get("high")
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)) or isinstance(low, bool) or isinstance(high, bool):
            found.append(FhirIssue("referenceRange", "observation-range-invalid"))
        elif low > high:
            found.append(FhirIssue("referenceRange", "observation-range-inverted"))
    return tuple(found)


def _encounter_window(payload: dict[str, object]) -> tuple[FhirIssue, ...]:
    """Return status and period issues for one Encounter."""
    if str(payload.get("resourceType", "")) != "Encounter":
        return ()
    found: list[FhirIssue] = []
    status = str(payload.get("status", ""))
    if not status:
        found.append(FhirIssue("status", "encounter-status-missing"))
    elif status not in ENCOUNTER_STATUSES:
        found.append(FhirIssue("status", "encounter-status-invalid"))
    period = payload.get("period")
    start = str(period.get("start", "")) if isinstance(period, dict) else ""
    end = str(period.get("end", "")) if isinstance(period, dict) else ""
    if not start:
        found.append(FhirIssue("period.start", "encounter-period-missing"))
    elif end and end < start:
        found.append(FhirIssue("period.end", "encounter-period-inverted"))
    return tuple(found)


def _patient_demographic(payload: dict[str, object]) -> str:
    """Return the first direct demographic field carried by a Patient."""
    if str(payload.get("resourceType", "")) != "Patient":
        return ""
    present = PATIENT_DEMOGRAPHICS.intersection(payload)
    if not present:
        return ""
    return sorted(present)[0]


def require_valid(
    payload: dict[str, object],
    emergency: bool = False,
    releases: ReleaseLedger | None = None,
    profiles: ProfileLedger | None = None,
) -> None:
    """Raise on the first structural issue."""
    issues = validate_resource(payload, releases, profiles)
    if emergency:
        issues = tuple(issue for issue in issues if issue.code != "consent-not-active")
    if issues:
        raise ContractError(issues[0].code)


class FhirLedger:
    """Remember one resource so a later actor cannot validate it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}
        self.releases = ReleaseLedger()
        self.profiles = ProfileLedger()

    def require(self, payload: dict[str, object], emergency: bool = False) -> None:
        require_valid(payload, emergency, self.releases, self.profiles)
        resource_id = str(payload.get("id", ""))
        actor_id = str(payload.get("actorId", "actor-synthetic"))
        why_code = str(payload.get("whyCode", "treatment-review"))
        recorded = self._records.get(resource_id)
        if recorded is None:
            self._records[resource_id] = (actor_id, why_code)
            return
        if recorded != (actor_id, why_code):
            raise ContractError("fhir-responsibility-mismatch")

    def restore(self, resource_id: str, actor_id: str, why_code: str) -> None:
        """Restore one accepted resource without treating it as a new review."""
        blank_reason = why_code in {"", "unknown", "unspecified"}
        if blank_reason:
            raise ContractError("actor-why-missing")
        pair = (resource_id, actor_id)
        if "" in pair:
            raise ContractError("actor-context-incomplete")
        stored = self._records
        stored[pair[0]] = (pair[1], why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored resource decisions in stable order."""
        return tuple(sorted(self._records.items()))
