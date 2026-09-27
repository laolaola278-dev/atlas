"""Regenerate the P1 evidence index from measured gates and artifact digests.

Gates run first, digests are computed afterwards, so an index never records a
stale digest for a file that a gate rewrote. Every gate exit code is recorded; a
non-zero exit makes this tool exit non-zero too.

Usage:
    python -B tools/evidence/p1_index.py
    python -B tools/evidence/p1_index.py --skip-official   # no JRE / no jar here
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from internal.contract.hapi_validator import engine_available  # noqa: E402

_INDEX = _ROOT / "docs" / "evidence" / "p1" / "index.json"

# The Python suite is discovered, not listed: tools/evidence/python_gates.py is
# the single source of truth shared with CI, so the index cannot claim coverage
# that the working tree no longer has.

ARTIFACTS = (
    "docs/evidence/p1/README.md",
    "docs/evidence/p1/fhir-official-validation.json",
    "docs/evidence/p1/fhir-official-validation.log",
    "docs/evidence/p1/fhir-validator-provenance.json",
    "docs/evidence/p1/fhir-vertical-slice.json",
    "docs/evidence/p1/fhir-vertical-slice.log",
    "docs/requirements/fhir-audit-hitl-evidence.md",
    "docs/requirements/fhir-contract-test-plan.md",
    "docs/requirements/traceability-matrix.json",
    "docs/requirements/traceability.md",
    "internal/audit/file.py",
    "internal/contract/digest.py",
    "internal/contract/errors.py",
    "internal/contract/fhir_gate.py",
    "internal/contract/hapi_validator.py",
    "internal/contract/test_hapi_validator.py",
    "internal/contract/validator.py",
    "internal/workflow/slice.py",
    "internal/workflow/test_slice.py",
    "testdata/fhir/r4-examples/README.md",
    "testdata/fhir/r4-examples/bundle-example.json",
    "testdata/fhir/r4-examples/condition-example.json",
    "testdata/fhir/r4-examples/encounter-example.json",
    "testdata/fhir/r4-examples/observation-example.json",
    "testdata/fhir/r4-examples/patient-example.json",
    "testdata/fhir/r4-examples/practitioner-example.json",
    "testdata/fhir/synthetic/r4-observation-invalid-status.json",
    "tools/evidence/fhir_official_validation.py",
    "tools/evidence/fhir_slice_acceptance.py",
    "tools/evidence/p1_index.py",
    "tools/evidence/provision_fhir_validator.py",
    "tools/evidence/python_gates.py",
    "tools/evidence/traceability.py",
    "tools/phi-scan/rules-atlas.json",
    "tools/phi-scan/rules.py",
    "tools/phi-scan/test_scan.py",
    ".github/workflows/ci.yaml",
    "Makefile",
)

UNVERIFIED = (
    "the slice still runs only in Python: no proto stubs or api/gen, no FhirValidationService/HitlService "
    "server, and services/atlas-workflow never consumes audit_event_id",
    "Patient entries are still rejected by ENTRY_TYPES (patient identity belongs to the EMPI slice), so the "
    "transaction bundle references Patient/... without containing it",
    "jar GPG signature not verified: validator_cli.jar.asc is published but no gpg binary exists here",
    "proto service stubs and server implementation (api/gen absent), so FhirValidationService/HitlService have no server",
    "Go-side workflow consumption of audit_event_id (services/atlas-workflow has no reference)",
    "go test -race -cover ./... and gofmt -l (no Go toolchain in this environment)",
    "independent CI runner re-execution: the official-fhir-validator job has not run on GitHub-hosted infrastructure",
    "clinical expert review, property-based testing and regression harness (P3)",
    "P50/P95/P99 performance measurement in the target deployment environment (P8)",
    "security, PHI-leak, authorization, chaos and recovery drills (P6/P8)",
    "version tags, SBOM, signed artifacts, deployment and rollback packages (P8)",
)


def run_gate(command: list[str]) -> dict[str, object]:
    """Run one gate and return its command, exit code and output tail."""
    done = subprocess.run(command, cwd=_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    tail = ((done.stdout or "") + (done.stderr or "")).strip().splitlines()
    return {"command": " ".join(command), "exit_code": done.returncode, "output_tail": tail[-3:]}


def not_run(command: str, reason: str) -> dict[str, object]:
    """Return an explicit not-run row so a skipped gate is never invisible."""
    return {"command": command, "exit_code": None, "not_run_reason": reason, "output_tail": []}


def digest(relative: str) -> dict[str, object]:
    """Return one measured row for an artifact, or a missing-file row."""
    target = _ROOT / relative
    if not target.is_file():
        return {"bytes": 0, "crlf": False, "lines": 0, "path": relative, "sha256": "", "status": "missing"}
    data = target.read_bytes()
    return {
        "bytes": len(data),
        "crlf": b"\r\n" in data,
        "lines": len(data.decode("utf-8", "replace").splitlines()),
        "path": relative,
        "sha256": hashlib.sha256(data).hexdigest(),
        "status": "measured",
    }


def git_revision() -> str:
    """Return the short HEAD revision, or an explicit placeholder."""
    try:
        done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=_ROOT,
                              capture_output=True, text=True)
    except OSError:
        return "git-unavailable"
    return done.stdout.strip() if done.returncode == 0 else "no-commits-yet"


def build(skip_official: bool) -> dict[str, object]:
    """Run every gate, then measure every artifact."""
    engine = engine_available()
    gates: list[dict[str, object]] = [
        run_gate([sys.executable, "-B", "plan/verify_first_round.py"]),
        run_gate([sys.executable, "-B", "tools/phi-scan/scan.py", "--root", ".",
                  "--rules", "tools/phi-scan/rules-atlas.json", "--fail-on", "blocked",
                  "--out", str(_ROOT.parent / "_scratch" / "phi-p1.json")]),
        run_gate([sys.executable, "-B", "tools/evidence/fhir_slice_acceptance.py"]),
        run_gate([sys.executable, "-B", "tools/evidence/traceability.py"]),
        run_gate([sys.executable, "-B", "tools/evidence/python_gates.py"]),
    ]
    if skip_official or not engine:
        reason = "skipped by --skip-official" if skip_official else (
            "official validator engine unavailable (set ATLAS_FHIR_VALIDATOR_JAR and ATLAS_JAVA_HOME)")
        gates.append(not_run("python -B tools/evidence/provision_fhir_validator.py --verify-only", reason))
        gates.append(not_run("python -B tools/evidence/fhir_official_validation.py", reason))
    else:
        gates.append(run_gate([sys.executable, "-B", "tools/evidence/provision_fhir_validator.py", "--verify-only"]))
        gates.append(run_gate([sys.executable, "-B", "tools/evidence/fhir_official_validation.py"]))

    rows = [digest(relative) for relative in ARTIFACTS]
    missing = [row["path"] for row in rows if row["status"] != "measured"]
    return {
        "artifacts": len(rows),
        "artifacts_missing": missing,
        "crlf_artifacts": [row["path"] for row in rows if row["crlf"]],
        "engine_available": engine,
        "environment": {
            "git_revision_at_generation": git_revision(),
            "go_toolchain_available": False,
            "go_toolchain_note": "go is not on PATH here; go test and gofmt were not executed.",
            "python_version": platform.python_version(),
        },
        "gates": gates,
        "gates_failed": sum(1 for gate in gates if gate["exit_code"] not in (0, None)),
        "gates_not_run": sum(1 for gate in gates if gate["exit_code"] is None),
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "index_version": "1.3",
        "phase": "P1",
        "rows": rows,
        "scope": "FHIR vertical slice: Bundle -> Gate -> Validator -> AuditEvent -> Workflow -> HITL Review -> HITL Commit",
        "synthetic": True,
        "unverified": list(UNVERIFIED),
    }


def verify() -> int:
    """Compare the committed index digests against the working tree.

    This is the drift gate: it rewrites nothing, so CI can run it safely. Any
    artifact whose content moved away from the indexed digest fails the check,
    which is what keeps an evidence index from going silently stale.
    """
    if not _INDEX.is_file():
        print(f"MISSING INDEX: {_INDEX.relative_to(_ROOT)}")
        return 1
    committed = json.loads(_INDEX.read_text(encoding="utf-8"))
    indexed = {str(row["path"]): str(row["sha256"]) for row in committed.get("rows", [])}
    drift: list[str] = []
    for relative in ARTIFACTS:
        row = digest(relative)
        if row["status"] != "measured" or indexed.get(relative) != row["sha256"]:
            drift.append(relative)
    unlisted = sorted(set(indexed) - set(ARTIFACTS))
    for path in drift:
        print(f"DRIFT   : {path}")
    for path in unlisted:
        print(f"UNLISTED: {path} (indexed but no longer tracked by this generator)")
    failed_gates = int(committed.get("gates_failed", 0) or 0)
    if failed_gates:
        # An index is evidence. One generated while a gate was failing must not be
        # accepted as committed evidence, even if its digests still match.
        print(f"INDEX RECORDS {failed_gates} FAILED GATE(S); regenerate it before committing")
        for gate in committed.get("gates", []):
            if gate.get("exit_code") not in (0, None):
                print(f"  exit={gate.get('exit_code')} {str(gate.get('command'))[:100]}")
        return 1
    if drift or unlisted:
        print(f"index_version {committed.get('index_version')} does not match the working tree")
        return 1
    print(f"verified {len(ARTIFACTS)} artifact digests against index_version {committed.get('index_version')}")
    return 0


def main() -> int:
    """Write the index and exit non-zero when any executed gate failed."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(_INDEX))
    parser.add_argument("--skip-official", action="store_true",
                        help="record the official validator gates as not-run instead of failing")
    parser.add_argument("--verify", action="store_true",
                        help="only compare the committed index digests against the working tree")
    args = parser.parse_args()
    if args.verify:
        return verify()
    index = build(args.skip_official)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"index_version      : {index['index_version']}")
    print(f"gates_failed       : {index['gates_failed']}    gates_not_run: {index['gates_not_run']}")
    print(f"engine_available   : {index['engine_available']}")
    print(f"artifacts          : {index['artifacts']}    missing: {index['artifacts_missing'] or 'none'}")
    print(f"crlf_artifacts     : {index['crlf_artifacts'] or 'none'}")
    print(f"git_revision       : {index['environment']['git_revision_at_generation']}")
    for gate in index["gates"]:
        print(f"  exit={gate['exit_code']} {str(gate['command'])[:88]}")
    print(f"written            : {out.relative_to(_ROOT)}")
    return 0 if index["gates_failed"] == 0 and not index["artifacts_missing"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
