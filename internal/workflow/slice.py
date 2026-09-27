"""FHIR vertical-slice workflow stage.

The workflow stage is the consumer that sits between the append-only audit
chain and HITL review. It refuses to open a review task unless the caller
presents the audit_event_id that the FHIR validation stage generated, it
re-verifies the hash chain, and it propagates that same id into the review
receipt and the commit response. That makes the wire contract executable
instead of only declared:

    api/proto/atlas/v1/fhir.proto  FhirResourceResponse.audit_event_id (3)
    api/proto/atlas/v1/hitl.proto  ReviewReceipt.audit_event_id        (7)
    api/proto/atlas/v1/hitl.proto  CommitResponse.audit_event_id       (5)

This module composes the existing gates and adds no clinical rule of its own.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from internal.audit.chain import AuditEvent, AuditLog, to_fhir_audit_event
from internal.contract.bundle import require_bundle
from internal.contract.errors import ContractError
from internal.contract.digest import canonical_digest
from internal.contract.fhir_gate import patient_reference, validate_resource
from internal.contract.hapi_validator import validate_payload
from internal.contract.validator import require_official
from internal.contract.write_intent import ApprovalProof

_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES = _ROOT / "testdata" / "fhir" / "synthetic"

STAGES = (
    "bundle",
    "gate",
    "validator",
    "audit",
    "workflow",
    "hitl-review",
    "hitl-commit",
)


def load_fixture(name: str) -> dict[str, object]:
    """Load one synthetic fixture from the P1 regression set."""
    path = _FIXTURES / f"{name}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("profile-fixture-corrupt") from exc
    if not isinstance(payload, dict):
        raise ContractError("profile-fixture-corrupt")
    return payload


# Atlas provenance fields live on the review envelope, never inside the FHIR
# payload that the official validator sees. Keeping them in one declared set is
# what makes the separation auditable instead of incidental.
ATLAS_ENVELOPE_FIELDS = frozenset({
    "actorId",
    "codeSystem",
    "consentState",
    "purposeCode",
    "reviewedAt",
    "synthetic",
    "whyCode",
})


def pure_resource(envelope: dict[str, object]) -> dict[str, object]:
    """Return the FHIR payload with every Atlas provenance field removed.

    The gate consumes the envelope, the official validator consumes this
    projection, and the digest that binds the audit event, the workflow task and
    the HITL receipt is computed over the projection only. That way the record
    the audit chain carries is exactly the bytes the official engine judged.
    """
    payload = {key: value for key, value in envelope.items() if key not in ATLAS_ENVELOPE_FIELDS}
    if len(payload) == len(envelope):
        raise ContractError("validator-envelope-invalid")
    if not str(payload.get("resourceType", "")) or not str(payload.get("id", "")):
        raise ContractError("validator-envelope-invalid")
    leaked = sorted(ATLAS_ENVELOPE_FIELDS.intersection(payload))
    if leaked:
        raise ContractError("validator-envelope-invalid")
    return payload


def stage_bundle(bundle: dict[str, object]) -> tuple[str, ...]:
    """Stage 1: accept only a transaction bundle with allowed entries."""
    require_bundle(bundle)
    entries = bundle.get("entry")
    if not isinstance(entries, list):
        raise ContractError("bundle-empty")
    return tuple(str(item.get("reference", "")) for item in entries if isinstance(item, dict))


def stage_gate(resource: dict[str, object]) -> tuple[object, ...]:
    """Stage 2: fail closed on the first structural issue."""
    issues = validate_resource(resource)
    if issues:
        raise ContractError(issues[0].code)
    return issues


def official_record(digest: str, outcome_id: str, outcome: str = "pass") -> dict[str, object]:
    """Build one HAPI-shaped outcome record.

    The record is synthetic evidence. require_official() accepts it only
    because it names the engine, the official flag and this exact digest. No
    HAPI binary is executed anywhere in this repository; that gap is recorded
    in docs/evidence/p1/fhir-vertical-slice.md.
    """
    return {
        "engine": "hapi",
        "official": True,
        "contentDigest": digest,
        "outcome": outcome,
        "outcomeId": outcome_id,
    }


def stage_validator(envelope: dict[str, object], record: dict[str, object] | None) -> tuple[str, str]:
    """Stage 3: bind the digest of the pure FHIR payload to one outcome id."""
    payload = pure_resource(envelope)
    digest = canonical_digest(payload)
    return digest, require_official({**payload, "contentDigest": digest}, record)


def stage_audit(
    log: AuditLog,
    *,
    actor: dict[str, object],
    resource: dict[str, object],
    digest: str,
    outcome_id: str,
) -> AuditEvent:
    """Stage 4: append the FHIR validation event. This generates audit_event_id."""
    resource_id = str(resource.get("id", ""))
    resource_type = str(resource.get("resourceType", ""))
    if not resource_id or not resource_type or not digest or not outcome_id:
        raise ContractError("workflow-slice-stage-missing")
    payload = "|".join((resource_type, resource_id, digest, outcome_id))
    event = log.append({
        "event_id": f"fhir-validate-{resource_id}-{len(log.events) + 1}",
        "stream_id": log.stream_id,
        "sequence": len(log.events) + 1,
        "tenant_id": actor.get("tenant_id", ""),
        "campus_id": actor.get("campus_id", ""),
        "actor_id": actor.get("actor_id", ""),
        "actor_role": actor.get("actor_role", ""),
        "operation": "fhir-validate",
        "resource_type": resource_type,
        "resource_id": resource_id,
        "purpose_code": actor.get("purpose_code", ""),
        "why_code": actor.get("why_code", ""),
        "policy_version": "1.0.0",
        "occurred_at": actor.get("occurred_at", ""),
        "payload_digest": digest,
        "clock_quality": "synchronized",
        "consent_decision": "active",
    })
    log.verify()
    return event


def fhir_validation_result(
    resource: dict[str, object],
    digest: str,
    validator_version: str,
    issues: tuple[object, ...] = (),
) -> dict[str, object]:
    """Mirror api/proto/atlas/v1/fhir.proto FhirValidationResult."""
    meta = resource.get("meta", {})
    declared = meta.get("profile", []) if isinstance(meta, dict) else []
    return {
        "valid": not issues,
        "issues": [
            {
                "path": str(getattr(item, "path", "")),
                "code": str(getattr(item, "code", "")),
                "severity": "error",
                "message": str(getattr(item, "code", "")),
                "source_version": validator_version,
            }
            for item in issues
        ],
        "validator_version": validator_version,
        "profile_digest": canonical_digest({"profile": list(declared)}),
        "resource_digest": digest,
    }


def fhir_resource_response(
    resource: dict[str, object],
    validation: dict[str, object],
    audit_event_id: str,
) -> dict[str, object]:
    """Mirror api/proto/atlas/v1/fhir.proto FhirResourceResponse."""
    if not audit_event_id:
        raise ContractError("workflow-audit-event-missing")
    meta = resource.get("meta", {})
    declared = meta.get("profile", []) if isinstance(meta, dict) else []
    return {
        "resource": {
            "resource_type": str(resource.get("resourceType", "")),
            "logical_id": str(resource.get("id", "")),
            "version_id": str(meta.get("versionId", "")) if isinstance(meta, dict) else "",
            "profile_url": str(declared[0]) if declared else "",
        },
        "validation": validation,
        "audit_event_id": audit_event_id,
    }


@dataclass
class WorkflowTask:
    """One workflow task bound to exactly one audit_event_id."""

    task_id: str
    audit_event_id: str
    resource_id: str
    patient_ref: str
    resource_digest: str
    state: str
    suggestion: object | None = None


class SliceWorkflow:
    """Consume one audit_event_id, then drive HITL review and commit."""

    def __init__(self, service: object) -> None:
        self.service = service
        self._tasks: dict[str, WorkflowTask] = {}

    @property
    def log(self) -> AuditLog:
        return self.service.log  # type: ignore[attr-defined,no-any-return]

    def locate(self, audit_event_id: str) -> AuditEvent:
        """Return the chained event named by one audit_event_id."""
        for event in self.log.events:
            if event.event_id == audit_event_id:
                return event
        raise ContractError("workflow-audit-event-unknown")

    def open_task(
        self,
        audit_event_id: str,
        *,
        resource_id: str,
        patient_ref: str,
        resource_digest: str,
    ) -> WorkflowTask:
        """Stage 5: refuse a task that cannot present a verifiable audit_event_id."""
        if not audit_event_id:
            raise ContractError("workflow-audit-event-missing")
        if not resource_id or not patient_ref or not resource_digest:
            raise ContractError("workflow-slice-stage-missing")
        event = self.locate(audit_event_id)
        if event.resource_id != resource_id or event.payload_digest != resource_digest:
            raise ContractError("workflow-audit-event-mismatch")
        if event.operation != "fhir-validate":
            raise ContractError("workflow-audit-event-mismatch")
        self.log.verify()
        task = WorkflowTask(
            f"task-{audit_event_id}",
            audit_event_id,
            resource_id,
            patient_ref,
            resource_digest,
            "OPEN",
        )
        self._tasks[task.task_id] = task
        return task

    def task(self, task_id: str) -> WorkflowTask:
        """Return one stored task or fail closed."""
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise ContractError("workflow-task-unknown") from exc

    def review(
        self,
        task: WorkflowTask,
        draft: object,
        resource: dict[str, object],
        second_reviewer_id: str,
    ) -> dict[str, str]:
        """Stage 6: HITL Review. Dual approval, receipt carries audit_event_id."""
        self._require_state(task, "OPEN")
        if patient_reference(resource) != task.patient_ref:
            raise ContractError("patient-reference-mismatch")
        service = self.service
        suggestion = service.approve(draft, resource)  # type: ignore[attr-defined]
        approved = service.approve_independent(suggestion, draft, second_reviewer_id)  # type: ignore[attr-defined]
        review_event = self.log.events[-1]
        task.suggestion = approved
        task.state = "REVIEWED"
        return {
            "audit_event_id": task.audit_event_id,
            "content_digest": approved.content_digest,
            "review_event_id": review_event.event_id,
            "state": approved.state,
            "state_version": str(approved.version),
            "suggestion_id": approved.suggestion_id,
            "suggestion_version": str(approved.version),
        }

    def commit(
        self,
        task: WorkflowTask,
        proof: ApprovalProof,
        at_time: str,
        expected_target_version: str,
    ) -> dict[str, object]:
        """Stage 7: HITL Commit. Response carries the same audit_event_id."""
        self._require_state(task, "REVIEWED")
        if task.suggestion is None:
            raise ContractError("workflow-task-state-invalid")
        result = self.service.commit_ordinary(  # type: ignore[attr-defined]
            task.suggestion, proof, at_time, expected_target_version,
        )
        commit_event = self.log.events[-1]
        task.state = "COMMITTED"
        return {
            "audit_event_id": task.audit_event_id,
            "commit_audit_event_id": commit_event.event_id,
            "committed": bool(result.get("committed", False)),
            "target_version": str(result.get("target_version", "")),
            "write_intent_id": proof.proof_id,
            "write_kind": str(result.get("write_kind", "")),
        }

    def fhir_audit_event(self, task: WorkflowTask) -> dict[str, object]:
        """Return the FHIR AuditEvent projection named by one task."""
        return to_fhir_audit_event(self.locate(task.audit_event_id))

    def _require_state(self, task: WorkflowTask, expected: str) -> None:
        if task.state != expected:
            raise ContractError("workflow-task-state-invalid")


def run_vertical_slice(
    service: object,
    draft: object,
    *,
    bundle_name: str = "valid-patient-bundle",
    resource_name: str = "observation",
    second_reviewer_id: str = "reviewer-second",
    proof_id: str = "proof-slice",
    nonce: str = "nonce-slice",
    at_time: str = "2026-09-24T00:30:00Z",
    target_version: str = "target-slice",
    validator_record: dict[str, object] | None = None,
    validator_version: str = "hapi-unexecuted",
    official_engine: bool = False,
    validator_engine: str = "",
) -> dict[str, object]:
    """Run Bundle -> Gate -> Validator -> Audit -> Workflow -> Review -> Commit."""
    stages: list[dict[str, object]] = []
    bundle = load_fixture(bundle_name)
    entries = stage_bundle(bundle)
    stages.append({"entries": list(entries), "stage": "bundle"})

    resource = load_fixture(resource_name)
    reference = f"{resource.get('resourceType', '')}/{resource.get('id', '')}"
    if reference not in entries:
        raise ContractError("workflow-slice-stage-missing")
    issues = stage_gate(resource)
    stages.append({"issues": list(issues), "resource": reference, "stage": "gate"})

    record = validator_record
    engine = validator_engine or "supplied-record"
    if record is None and official_engine:
        # Real engine execution: validator_cli.jar runs and its OperationOutcome
        # becomes the official record. Without an engine this fails closed.
        record = validate_payload(pure_resource(resource))
        engine = "official-engine"
        validator_version = str(record.get("validatorVersion", validator_version))
    if engine == "official-engine":
        # The label is not a claim, it is checked: only a record produced by the
        # real engine carries a jar digest and a resolved validator version.
        if not isinstance(record, dict) or not str(record.get("jarSha256", "")) or not str(record.get("validatorVersion", "")):
            raise ContractError("validator-not-official")
        validator_version = str(record.get("validatorVersion", validator_version))
    digest, outcome_id = stage_validator(resource, record)
    stages.append({
        "engine": engine,
        "official": bool(isinstance(record, dict) and record.get("official") is True),
        "outcome_id": outcome_id,
        "resource_digest": digest,
        "stage": "validator",
        "validator_version": (
            str(record.get("validatorVersion") or validator_version) if isinstance(record, dict) else validator_version
        ),
    })

    event = stage_audit(
        service.log,  # type: ignore[attr-defined]
        actor=draft.actor,  # type: ignore[attr-defined]
        resource=resource,
        digest=digest,
        outcome_id=outcome_id,
    )
    validation = fhir_validation_result(resource, digest, validator_version)
    response = fhir_resource_response(resource, validation, event.event_id)
    stages.append({
        "audit_event_id": event.event_id,
        "event_hash": event.event_hash,
        "previous_hash": event.previous_hash,
        "sequence": event.sequence,
        "stage": "audit",
    })

    workflow = SliceWorkflow(service)
    task = workflow.open_task(
        str(response["audit_event_id"]),
        resource_id=str(resource.get("id", "")),
        patient_ref=str(draft.patient_ref),  # type: ignore[attr-defined]
        resource_digest=digest,
    )
    stages.append({
        "audit_event_id": task.audit_event_id,
        "stage": "workflow",
        "task_id": task.task_id,
        "task_state": task.state,
    })

    receipt = workflow.review(task, draft, resource, second_reviewer_id)
    stages.append({"stage": "hitl-review", **receipt})

    proof = ApprovalProof(
        proof_id,
        receipt["suggestion_id"],
        receipt["suggestion_version"],
        second_reviewer_id,
        str(draft.action),  # type: ignore[attr-defined]
        receipt["content_digest"],
        nonce,
        "2026-09-24T00:00:00Z",
        "2026-09-24T01:00:00Z",
    )
    committed = workflow.commit(task, proof, at_time, target_version)
    stages.append({"stage": "hitl-commit", **committed})

    service.log.verify()  # type: ignore[attr-defined]
    return {
        "audit_chain_verified": True,
        "audit_event_ids": {
            "commit_response": committed["audit_event_id"],
            "fhir_resource_response": response["audit_event_id"],
            "review_receipt": receipt["audit_event_id"],
            "workflow_task": task.audit_event_id,
        },
        "commit_response": committed,
        "fhir_audit_event": workflow.fhir_audit_event(task),
        "fhir_resource_response": response,
        "review_receipt": receipt,
        "stages": stages,
        "task_state": task.state,
    }
