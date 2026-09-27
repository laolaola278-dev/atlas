"""Official FHIR Validator acceptance runner.

Executes the real HL7 validator_cli.jar against three categories of target and
writes the evidence record. This runner refuses to pass without a working
engine: no engine means exit 1, never a silent skip.

Categories
    must-pass        published HL7 R4 examples that validate cleanly
    known-rejected   a published HL7 R4 example that validator 6.10.4 rejects;
                     the rejection is asserted, so the gate is proven not to
                     rubber-stamp official input
    negative-control an Atlas fixture derived from an official example with one
                     required code broken

Usage:
    python -B tools/evidence/fhir_official_validation.py
    python -B tools/evidence/fhir_official_validation.py --probe-configurations
"""
from __future__ import annotations

import argparse
import json
import platform
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from internal.contract.digest import canonical_digest  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.hapi_validator import (  # noqa: E402
    engine_available,
    engine_config,
    official_record,
    validate_file,
    validator_version,
)
from internal.contract.validator import require_official  # noqa: E402
from internal.workflow.slice import pure_resource  # noqa: E402

_EVIDENCE_DIR = _ROOT / "docs" / "evidence" / "p1"
_CORPUS = _ROOT / "testdata" / "fhir" / "r4-examples"

MUST_PASS = (
    "patient-example.json",
    "observation-example.json",
    "bundle-example.json",
    "condition-example.json",
    "encounter-example.json",
)
KNOWN_REJECTED = {
    "practitioner-example.json": (
        "Practitioner.qualification[0].identifier[0].system",
        "Practitioner.qualification[0].code.coding[0].system",
    ),
}
NEGATIVE_CONTROL = _ROOT / "testdata" / "fhir" / "synthetic" / "r4-observation-invalid-status.json"
ATLAS_FIXTURE = _ROOT / "testdata" / "fhir" / "synthetic" / "observation.json"
PROBE_CONFIGURATIONS = (
    ("online-tx-na", {"ATLAS_FHIR_VALIDATOR_OFFLINE": "", "ATLAS_FHIR_VALIDATOR_TX": "n/a"}),
    ("online-tx-fhir-org", {"ATLAS_FHIR_VALIDATOR_OFFLINE": "", "ATLAS_FHIR_VALIDATOR_TX": "https://tx.fhir.org/r4"}),
    ("offline-tx-na", {"ATLAS_FHIR_VALIDATOR_OFFLINE": "1", "ATLAS_FHIR_VALIDATOR_TX": "n/a"}),
)


def _relative(path: Path) -> str:
    """Return one repository-relative path for the evidence record."""
    try:
        return str(path.relative_to(_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _accepts(record: dict[str, object]) -> str:
    """Return accepted or rejected-with-code for one official record."""
    digest = str(record["contentDigest"])
    try:
        require_official({"contentDigest": digest}, record)
    except ContractError as raised:
        return f"rejected:{raised}"
    return "accepted"


def _row(source: Path, outcome, config, label: str = "") -> dict[str, object]:
    """Return one evidence row for a single official validation."""
    payload = json.loads(source.read_text(encoding="utf-8"))
    record = official_record(payload, outcome, config=config, content_digest=canonical_digest(payload))
    return {
        "content_digest": record["contentDigest"],
        "elapsed_ms": outcome.elapsed_ms,
        "error_count": outcome.error_count,
        "exit_code": outcome.exit_code,
        "fhir_version": outcome.fhir_version,
        "gate": _accepts(record),
        "information_count": outcome.information_count,
        "issue_count": outcome.issue_count,
        "issues": [dict(item) for item in outcome.issues],
        "outcome": outcome.outcome,
        "outcome_id": outcome.outcome_id,
        "path": label or _relative(source),
        "validator_version": outcome.validator_version,
        "warning_count": outcome.warning_count,
    }


def _check(condition: bool, message: str) -> None:
    """Assert one invariant with a readable message."""
    if not condition:
        raise AssertionError(message)


def run(probe: bool = False) -> dict[str, object]:
    """Validate every target with the real engine and return the evidence."""
    _check(engine_available(), "official validator engine unavailable: set ATLAS_FHIR_VALIDATOR_JAR and ATLAS_JAVA_HOME")
    config = engine_config()
    version = validator_version(config)
    lines: list[str] = []

    def note(text: str) -> None:
        lines.append(text)
        print(text)

    note(f"engine java        : {config.java}")
    note(f"engine jar         : {config.jar}")
    note(f"engine jar sha256  : {config.jar_sha256}")
    note(f"validator version  : {version}")
    note(f"fhir version       : 4.0.1    tx server: {config.tx_server}    offline: {config.offline}")

    passed: list[dict[str, object]] = []
    for name in MUST_PASS:
        source = _CORPUS / name
        _check(source.is_file(), f"corpus fixture missing: {_relative(source)}")
        row = _row(source, validate_file(source, config=config), config)
        passed.append(row)
        note(f"[must-pass      ] {row['path']:<50} {row['outcome']:<4} err={row['error_count']} warn={row['warning_count']} info={row['information_count']} exit={row['exit_code']} {row['elapsed_ms']}ms gate={row['gate']}")
        _check(row["outcome"] == "pass", f"official validator rejected a published example: {row['path']} {row['issues']}")
        _check(row["error_count"] == 0 and row["exit_code"] == 0, f"unexpected errors in {row['path']}")
        _check(row["gate"] == "accepted", f"require_official rejected a passing record: {row['path']}")

    rejected: list[dict[str, object]] = []
    for name, expected in sorted(KNOWN_REJECTED.items()):
        source = _CORPUS / name
        _check(source.is_file(), f"corpus fixture missing: {_relative(source)}")
        row = _row(source, validate_file(source, config=config), config)
        rejected.append(row)
        note(f"[known-rejected ] {row['path']:<50} {row['outcome']:<4} err={row['error_count']} exit={row['exit_code']} gate={row['gate']}")
        _check(row["outcome"] == "fail", f"expected validator {version} to reject {name}, it passed")
        _check(row["error_count"] >= 1, f"expected at least one error for {name}")
        _check(row["gate"].startswith("rejected:validator-outcome-failed"), f"gate accepted a failed official outcome for {name}")
        expressions = {str(item["expression"]) for item in row["issues"] if item["severity"] == "error"}
        for wanted in expected:
            _check(wanted in expressions, f"expected error on {wanted} for {name}, got {sorted(expressions)}")
        for issue in row["issues"]:
            note(f"                   {issue['severity']:<11} {issue['code']:<12} {issue['expression'][:66]}")

    negative = _row(NEGATIVE_CONTROL, validate_file(NEGATIVE_CONTROL, config=config), config)
    note(f"[negative-ctrl  ] {negative['path']:<50} {negative['outcome']:<4} err={negative['error_count']} gate={negative['gate']}")
    _check(negative["outcome"] == "fail" and negative["error_count"] >= 1, "official validator accepted a resource with an invalid required code")
    _check(negative["gate"].startswith("rejected:validator-outcome-failed"), "gate accepted the negative control")
    _check(any(str(item["expression"]).startswith("Observation.status") for item in negative["issues"]), "expected an Observation.status issue in the negative control")

    atlas = _row(ATLAS_FIXTURE, validate_file(ATLAS_FIXTURE, config=config), config)
    note(f"[atlas-envelope] {atlas['path']:<50} {atlas['outcome']:<4} err={atlas['error_count']} warn={atlas['warning_count']} gate={atlas['gate']}")
    _check(atlas["outcome"] == "fail" and atlas["error_count"] >= 1,
           "the Atlas envelope unexpectedly validated as FHIR, so the envelope separation would be dead code")
    _check(atlas["gate"].startswith("rejected:validator-outcome-failed"), "gate accepted the Atlas envelope")
    for issue in atlas["issues"][:6]:
        note(f"                   {issue['severity']:<11} {issue['code']:<12} {issue['expression'][:66]}")

    envelope = json.loads(ATLAS_FIXTURE.read_text(encoding="utf-8"))
    projection = pure_resource(envelope)
    note(f"[separation     ] stripped envelope fields: {sorted(set(envelope) - set(projection))}")
    with tempfile.TemporaryDirectory() as directory:
        projection_path = Path(directory) / "observation-projection.json"
        projection_path.write_text(json.dumps(projection, indent=2, sort_keys=True) + "\n",
                                   encoding="utf-8", newline="\n")
        projected = _row(projection_path, validate_file(projection_path, config=config), config,
                         label="testdata/fhir/synthetic/observation.json -> pure FHIR projection")
    note(f"[atlas-project ] {projected['path']:<50} {projected['outcome']:<4} err={projected['error_count']} warn={projected['warning_count']} gate={projected['gate']}")
    _check(projected["outcome"] == "pass" and projected["error_count"] == 0 and projected["exit_code"] == 0,
           f"the derived FHIR projection did not validate: {projected['issues']}")
    _check(projected["gate"] == "accepted", "require_official rejected the projection record")
    _check(projected["content_digest"] == canonical_digest(projection),
           "the evidence digest and the slice digest are not the same bytes")

    probes: list[dict[str, object]] = []
    if probe:
        import os

        for label, overrides in PROBE_CONFIGURATIONS:
            for key, value in overrides.items():
                if value:
                    os.environ[key] = value
                else:
                    os.environ.pop(key, None)
            probed = engine_config()
            target = _CORPUS / next(iter(KNOWN_REJECTED))
            row = _row(target, validate_file(target, config=probed), probed)
            probes.append({"configuration": label, "outcome": row["outcome"], "error_count": row["error_count"],
                           "errors": sorted({str(item["expression"]) for item in row["issues"] if item["severity"] == "error"})})
            note(f"[probe          ] {label:<20} {row['outcome']:<4} err={row['error_count']} {probes[-1]['errors']}")
        outcomes = {str(item["outcome"]) for item in probes}
        _check(outcomes == {"fail"}, f"the known rejection is configuration dependent: {probes}")

    return {
        "atlas_envelope": atlas,
        "atlas_projection": projected,
        "corpus_license": {
            "note": "HL7 permits redistribution of the specification; the document is licensed CC0.",
            "source": "https://hl7.org/fhir/R4/license.html",
        },
        "corpus_source": "https://hl7.org/fhir/R4/",
        "engine": {
            "jar_sha256": config.jar_sha256,
            "java": config.java,
            "offline": config.offline,
            "tx_server": config.tx_server,
            "validator_version": version,
        },
        "environment": {"go_toolchain_available": False, "python_version": platform.python_version()},
        "fhir_version": "4.0.1",
        "separation_note": (
            "The Atlas fixture is an envelope: internal/workflow/slice.py:pure_resource() strips the declared "
            "ATLAS_ENVELOPE_FIELDS (synthetic, purposeCode, actorId, whyCode, consentState, codeSystem, "
            "reviewedAt) and the official engine validates only the projection. Both halves are asserted here: "
            "the envelope must fail as FHIR and the projection must pass, and the projection digest must equal "
            "the digest the audit chain binds. The validator infers the bodyweight profile from LOINC 29463-7, "
            "which is why the projection carries category vital-signs and effectiveDateTime."
        ),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "known_rejected": rejected,
        "log": lines,
        "must_pass": passed,
        "negative_control": negative,
        "official_engine_executed": True,
        "schema_version": "1.1",
        "synthetic": True,
        "totals": {
            "engine_runs": len(passed) + len(rejected) + 3 + len(probes),
            "known_rejected": len(rejected),
            "must_pass": len(passed),
            "must_pass_passed": sum(1 for row in passed if row["outcome"] == "pass"),
            "probed_configurations": len(probes),
        },
    }


def main() -> int:
    """Write the official validation evidence only when every check holds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", default=str(_EVIDENCE_DIR / "fhir-official-validation.json"))
    parser.add_argument("--log", default=str(_EVIDENCE_DIR / "fhir-official-validation.log"))
    parser.add_argument("--probe-configurations", action="store_true",
                        help="also prove the known rejection is not caused by the offline or tx policy")
    args = parser.parse_args()
    try:
        evidence = run(probe=args.probe_configurations)
    except (AssertionError, ContractError) as failure:
        print(f"OFFICIAL VALIDATION FAILED: {failure}")
        return 1
    json_path = Path(args.json)
    log_path = Path(args.log)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    log_path.write_text("\n".join(str(line) for line in evidence["log"]) + "\n", encoding="utf-8", newline="\n")
    print(f"evidence json: {json_path.relative_to(_ROOT)}")
    print(f"evidence log : {log_path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
