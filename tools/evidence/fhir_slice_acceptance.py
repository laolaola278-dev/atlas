"""P1 FHIR vertical-slice acceptance runner.

This script is a gate, not a report generator. It executes the seven stages

    Bundle -> Gate -> Validator -> Audit -> Workflow -> HITL Review -> HITL Commit

against the synthetic fixtures, re-checks every invariant, exercises the
fail-closed branches, and only then writes the evidence record. Any failed
invariant exits non-zero and writes nothing.

Usage:
    python -B tools/evidence/fhir_slice_acceptance.py
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from internal.audit.file import AuditFile  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.hapi_validator import engine_available, validate_payload  # noqa: E402
from internal.hitl.fixtures import review_draft  # noqa: E402
from internal.hitl.service import ReviewService  # noqa: E402
from internal.workflow.slice import (  # noqa: E402
    STAGES,
    SliceWorkflow,
    canonical_digest,
    load_fixture,
    official_record,
    pure_resource,
    run_vertical_slice,
    stage_audit,
    stage_bundle,
    stage_gate,
    stage_validator,
)

_EVIDENCE_DIR = _ROOT / "docs" / "evidence" / "p1"
_CONFIG = {
    "tenant_id": "tenant-synthetic",
    "campus_id": "campus-synthetic",
    "policy_version": "1.0.0",
    "audit_stream": "review-service",
    "secret_ref": "secret://atlas/signing-key",
}
_OBSERVATION = "observation"
_BUNDLE = "valid-patient-bundle"
_OUTCOME = "hapi-outcome-acceptance"


def _service(directory: str) -> ReviewService:
    """Build one durable review service inside a temporary directory."""
    return ReviewService(
        _CONFIG,
        Path(directory) / "slice-audit.jsonl",
        Path(directory) / "slice-store.json",
    )


def _git_revision() -> str:
    """Return the current commit or an explicit uncommitted marker."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return "git-unavailable"
    if done.returncode != 0:
        return "no-commits-yet"
    return done.stdout.strip()


def _expect_code(action, expected: str) -> str:
    """Run one fail-closed branch and return the code it raised."""
    try:
        action()
    except ContractError as raised:
        if str(raised) != expected:
            raise AssertionError(f"expected {expected}, got {raised}") from raised
        return str(raised)
    raise AssertionError(f"expected {expected}, but nothing was rejected")


def run_acceptance() -> dict[str, object]:
    """Execute every stage and return the evidence record."""
    lines: list[str] = []

    def note(text: str) -> None:
        lines.append(text)
        print(text)

    envelope = load_fixture(_OBSERVATION)
    projection = pure_resource(envelope)
    digest = canonical_digest(projection)
    note(f"[stage 0] synthetic fixtures loaded: {_BUNDLE}.json, {_OBSERVATION}.json")
    note(f"[stage 0] envelope fields stripped before validation: "
         f"{sorted(set(envelope) - set(projection))}")
    note(f"[stage 0] canonical resource digest (projection only): {digest}")

    engine_used = engine_available()
    if engine_used:
        # The real official engine judges exactly the bytes this digest names.
        record = validate_payload(projection)
        validator_version = str(record.get("validatorVersion", ""))
        validator_engine = "official-engine"
        if record.get("outcome") != "pass" or record.get("errorCount"):
            raise AssertionError(f"official validator rejected the projection: {record.get('issues')}")
        note(f"[stage 0] official validator {validator_version} outcome={record.get('outcome')} "
             f"errors={record.get('errorCount')} warnings={record.get('warningCount')} "
             f"info={record.get('informationCount')} elapsedMs={record.get('elapsedMs')}")
    else:
        if os.environ.get("ATLAS_FHIR_VALIDATOR_REQUIRE_OFFICIAL") == "1":
            raise AssertionError("official engine required but unavailable")
        record = official_record(digest, _OUTCOME)
        validator_version = "hapi-unexecuted"
        validator_engine = "synthetic-record"
        note("[stage 0] official engine unavailable; using an official-shaped synthetic record "
             "(CI job official-fhir-validator runs the real engine)")

    with tempfile.TemporaryDirectory() as directory:
        service = _service(directory)
        trace = run_vertical_slice(
            service,
            review_draft(),
            validator_record=record,
            validator_version=validator_version,
            validator_engine="official-engine" if engine_used else "",
        )
        for stage in trace["stages"]:
            name = str(stage["stage"])
            detail = {key: value for key, value in stage.items() if key != "stage"}
            note(f"[stage {list(STAGES).index(name) + 1}] {name}: {json.dumps(detail, sort_keys=True, default=str)}")

        ids = trace["audit_event_ids"]
        unique = set(ids.values())
        if len(unique) != 1:
            raise AssertionError(f"audit_event_id did not propagate: {ids}")
        audit_event_id = str(next(iter(unique)))
        note(f"[check] one audit_event_id propagated across {len(ids)} surfaces: {audit_event_id}")
        for surface, value in sorted(ids.items()):
            if value != audit_event_id:
                raise AssertionError(f"{surface} carries {value}")

        if [str(stage["stage"]) for stage in trace["stages"]] != list(STAGES):
            raise AssertionError("stage order changed")
        note(f"[check] stage order matches contract: {' -> '.join(STAGES)}")

        if trace["task_state"] != "COMMITTED" or not trace["commit_response"]["committed"]:
            raise AssertionError("slice did not reach COMMITTED")
        note(f"[check] workflow task state: {trace['task_state']}")
        note(f"[check] commit response: {json.dumps(trace['commit_response'], sort_keys=True)}")

        operations = [event.operation for event in service.log.events]
        expected_operations = ["fhir-validate", "queue-review", "approve-one", "approve-second", "ordinary-commit"]
        if operations != expected_operations:
            raise AssertionError(f"unexpected audit operations: {operations}")
        note(f"[check] audit chain operations: {' -> '.join(operations)}")
        service.log.verify()
        note(f"[check] hash chain verified over {len(service.log.events)} events")

        projected = trace["fhir_audit_event"]
        if projected["resourceType"] != "AuditEvent" or projected["entityDigest"] != digest:
            raise AssertionError("FHIR AuditEvent projection is wrong")
        note(f"[check] to_fhir_audit_event projection: id={projected['id']} action={projected['action']}")

        audit_path = Path(directory) / "slice-audit.jsonl"
        written = len(audit_path.read_text(encoding="utf-8").splitlines())
        first = AuditFile(audit_path, _CONFIG["audit_stream"])
        after_first = len(audit_path.read_text(encoding="utf-8").splitlines())
        second = AuditFile(audit_path, _CONFIG["audit_stream"])
        after_second = len(audit_path.read_text(encoding="utf-8").splitlines())
        if not written == after_first == after_second:
            raise AssertionError(f"reload rewrote history: {written} -> {after_first} -> {after_second}")
        if len(second.log.events) != len(first.log.events) != written:
            raise AssertionError("reloaded chain length changed")
        second.log.verify()
        note(f"[check] durable reload is idempotent: {written} lines before and after two reloads")

        restored = ReviewService(_CONFIG, audit_path, Path(directory) / "slice-store.json")
        suggestion_id = str(trace["review_receipt"]["suggestion_id"])
        state = restored._suggestions[suggestion_id].state
        if state != "WRITEBACK_COMMITTED":
            raise AssertionError(f"restored suggestion state is {state}")
        note(f"[check] restarted service restores {suggestion_id} as {state}")

        # Fail-closed branches: each one must reject and append nothing new.
        baseline = len(service.log.events)
        negatives: dict[str, str] = {}
        workflow = SliceWorkflow(service)
        stage_bundle(load_fixture(_BUNDLE))
        resource = load_fixture(_OBSERVATION)
        stage_gate(resource)
        stage_validator(resource, record)
        event = stage_audit(
            service.log,
            actor=review_draft().actor,
            resource=resource,
            digest=digest,
            outcome_id=_OUTCOME,
        )
        negatives["validator-record-absent"] = _expect_code(
            lambda: stage_validator(resource, None), "validator-result-unknown",
        )
        negatives["validator-not-official"] = _expect_code(
            lambda: stage_validator(resource, {**record, "engine": "local"}), "validator-not-official",
        )
        negatives["validator-digest-mismatch"] = _expect_code(
            lambda: stage_validator(resource, official_record("0" * 64, _OUTCOME)), "validator-digest-mismatch",
        )
        negatives["validator-envelope-invalid"] = _expect_code(
            lambda: stage_validator(pure_resource(resource), record), "validator-envelope-invalid",
        )
        negatives["bundle-type-invalid"] = _expect_code(
            lambda: stage_bundle({**load_fixture(_BUNDLE), "type": "document"}), "bundle-type-invalid",
        )
        negatives["gate-purpose-missing"] = _expect_code(
            lambda: stage_gate({**resource, "purposeCode": ""}), "purpose-missing",
        )
        negatives["workflow-audit-event-missing"] = _expect_code(
            lambda: workflow.open_task(
                "", resource_id="observation-synthetic", patient_ref="patient-ref-synthetic", resource_digest=digest,
            ),
            "workflow-audit-event-missing",
        )
        negatives["workflow-audit-event-unknown"] = _expect_code(
            lambda: workflow.open_task(
                "fhir-validate-observation-synthetic-99",
                resource_id="observation-synthetic",
                patient_ref="patient-ref-synthetic",
                resource_digest=digest,
            ),
            "workflow-audit-event-unknown",
        )
        negatives["workflow-audit-event-mismatch"] = _expect_code(
            lambda: workflow.open_task(
                event.event_id,
                resource_id="observation-synthetic",
                patient_ref="patient-ref-synthetic",
                resource_digest="0" * 64,
            ),
            "workflow-audit-event-mismatch",
        )
        task = workflow.open_task(
            event.event_id,
            resource_id="observation-synthetic",
            patient_ref="patient-ref-synthetic",
            resource_digest=digest,
        )
        from internal.contract.write_intent import ApprovalProof

        early_proof = ApprovalProof(
            "proof-early", "suggestion-synthetic", "3", "reviewer-second", "review-order",
            "d" * 64, "nonce-early", "2026-09-24T00:00:00Z", "2026-09-24T01:00:00Z",
        )
        negatives["workflow-commit-before-review"] = _expect_code(
            lambda: workflow.commit(task, early_proof, "2026-09-24T00:30:00Z", "target-early"),
            "workflow-task-state-invalid",
        )
        for name, code in sorted(negatives.items()):
            note(f"[fail-closed] {name} -> {code}")
        if len(service.log.events) != baseline + 1:
            raise AssertionError("a rejected branch appended an audit event")
        note("[check] no rejected branch appended a success event")

    return {
        "acceptance": "pass",
        "audit_event_id": audit_event_id,
        "audit_event_id_surfaces": ids,
        "bundle_fixture": f"testdata/fhir/synthetic/{_BUNDLE}.json",
        "commit_response": trace["commit_response"],
        "fhir_audit_event": projected,
        "fhir_resource_response": trace["fhir_resource_response"],
        "fail_closed_checks": negatives,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_revision": _git_revision(),
        "hapi_validator_executed": engine_used,
        "hapi_validator_note": (
            "validator_cli.jar runs as a subprocess when ATLAS_FHIR_VALIDATOR_JAR and a JRE are "
            "configured, and its OperationOutcome becomes the official record. Without an engine "
            "this runner records an official-shaped synthetic record and says so explicitly."
        ),
        "official_error_count": record.get("errorCount", 0),
        "official_information_count": record.get("informationCount", 0),
        "official_issue_count": record.get("issueCount", 0),
        "official_outcome": str(record.get("outcome", "")),
        "official_outcome_id": str(record.get("outcomeId", _OUTCOME)),
        "official_warning_count": record.get("warningCount", 0),
        "validator_engine": validator_engine,
        "validator_version": validator_version,
        "log": lines,
        "python_version": platform.python_version(),
        "resource_digest": digest,
        "resource_fixture": f"testdata/fhir/synthetic/{_OBSERVATION}.json",
        "review_receipt": trace["review_receipt"],
        "stages": list(STAGES),
        "synthetic": True,
        "test_command": "python -B -m unittest internal.workflow.test_slice",
    }


def main() -> int:
    """Write the evidence record only when every invariant holds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default=str(_EVIDENCE_DIR / "fhir-vertical-slice.json"))
    parser.add_argument("--log", default=str(_EVIDENCE_DIR / "fhir-vertical-slice.log"))
    args = parser.parse_args()
    try:
        evidence = run_acceptance()
    except (AssertionError, ContractError) as failure:
        print(f"ACCEPTANCE FAILED: {failure}")
        return 1
    json_path = Path(args.json)
    log_path = Path(args.log)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n" keeps the artifacts byte-identical across platforms and
    # across a Git commit/checkout round trip, so the recorded SHA-256 in
    # docs/evidence/p1/index.json stays verifiable.
    json_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    log_path.write_text("\n".join(str(line) for line in evidence["log"]) + "\n", encoding="utf-8", newline="\n")
    print(f"evidence json: {json_path.relative_to(_ROOT)}")
    print(f"evidence log : {log_path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
