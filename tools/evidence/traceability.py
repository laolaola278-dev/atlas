"""P0-P8 requirements traceability matrix, generated from measured facts.

Every planned batch is linked to the code, tests and acceptance evidence that
actually exists on disk. Nothing is inferred from a status flag: a batch counts
as evidence-complete only when all of its declared output files exist, and its
declared line counts are compared against the measured ones.

Usage:
    python -B tools/evidence/traceability.py            # print the summary
    python -B tools/evidence/traceability.py --write    # also write the JSON matrix
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PLAN = _ROOT / "plan" / "batches.jsonl"
_MATRIX = _ROOT / "docs" / "requirements" / "traceability-matrix.json"
_PHASES = ("P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8")


class TraceabilityError(RuntimeError):
    """Raised when the plan cannot support an honest matrix."""


def load_rows() -> tuple[dict[str, object], ...]:
    """Return every planned batch row, failing closed on a corrupt plan."""
    try:
        lines = _PLAN.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise TraceabilityError(f"plan unreadable: {exc}") from exc
    rows: list[dict[str, object]] = []
    for number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TraceabilityError(f"plan line {number} is not JSON: {exc}") from exc
        if not isinstance(item, dict) or not item.get("id") or not item.get("phase"):
            raise TraceabilityError(f"plan line {number} is missing id or phase")
        rows.append(item)
    if not rows:
        raise TraceabilityError("plan contains no batch rows")
    return tuple(rows)


def measure(path: str) -> int | None:
    """Return the line count of one declared output, or None when absent.

    A declared output ending in "/" is a directory: it counts as present when it
    exists and holds at least one file, and its measured size is the combined
    line count of the files it holds.
    """
    target = _ROOT / path
    if path.endswith("/"):
        if not target.is_dir():
            return None
        files = sorted(item for item in target.rglob("*") if item.is_file())
        if not files:
            return None
        total = 0
        for item in files:
            try:
                total += len(item.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                return None
        return total
    if not target.is_file():
        return None
    try:
        return len(target.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return None


def is_test_output(path: str) -> bool:
    """Return True when one declared output is a test artifact."""
    name = Path(path).name
    return name.endswith("_test.go") or (name.startswith("test_") and name.endswith(".py"))


def classify(row: dict[str, object]) -> dict[str, object]:
    """Return one measured traceability record for a planned batch."""
    outputs = [str(item) for item in row.get("outputs", []) if isinstance(item, str)]
    measured: dict[str, int | None] = {path: measure(path) for path in outputs}
    present = {path: value for path, value in measured.items() if value is not None}
    missing = sorted(path for path, value in measured.items() if value is None)
    production = sum(value for path, value in present.items() if not is_test_output(path))
    tests = sum(value for path, value in present.items() if is_test_output(path))
    declared_production = row.get("production_loc")
    declared_test = row.get("test_loc")
    declared_sum = (
        declared_production + declared_test
        if isinstance(declared_production, int) and isinstance(declared_test, int)
        else None
    )
    loc_target = row.get("loc_target")
    if not outputs:
        state = "no-outputs-declared"
    elif not present:
        state = "absent"
    elif missing:
        state = "partial"
    else:
        state = "files-present"
    return {
        "acceptance_criteria": len(row.get("acceptance", []) or []),
        "declared_production_loc": declared_production,
        "declared_sum": declared_sum,
        "declared_test_loc": declared_test,
        "declared_vs_target": (
            "reconciled" if declared_sum == loc_target else "mismatch"
        ) if declared_sum is not None else "undeclared",
        "evidence_state": state,
        "id": str(row.get("id", "")),
        "loc_target": loc_target,
        "measured_production_loc": production,
        "measured_test_loc": tests,
        "measured_total_loc": production + tests,
        "missing_outputs": missing,
        "module": str(row.get("module", "")),
        "phase": str(row.get("phase", "")),
        "present_outputs": sorted(present),
        "row_status": str(row.get("status", "")),
        "row_verified": bool(row.get("verified", False)),
        "row_completed": bool(row.get("completed", False)),
        "title": str(row.get("title", "")),
    }


def phase_summary(records: tuple[dict[str, object], ...]) -> tuple[dict[str, object], ...]:
    """Aggregate the measured records per phase."""
    summary: list[dict[str, object]] = []
    for phase in _PHASES:
        rows = [item for item in records if item["phase"] == phase]
        if not rows:
            continue
        states = Counter(str(item["evidence_state"]) for item in rows)
        summary.append({
            "batches": len(rows),
            "declared_loc_target": sum(int(item["loc_target"] or 0) for item in rows),
            "declared_loc_sum": sum(int(item["declared_sum"] or 0) for item in rows),
            "evidence_states": dict(sorted(states.items())),
            "files_present": states.get("files-present", 0),
            "loc_reconciled": sum(1 for item in rows if item["declared_vs_target"] == "reconciled"),
            "measured_loc": sum(int(item["measured_total_loc"]) for item in rows),
            "missing_output_files": sum(len(list(item["missing_outputs"])) for item in rows),
            "partial": states.get("partial", 0),
            "absent": states.get("absent", 0),
            "phase": phase,
        })
    return tuple(summary)


def build_matrix() -> dict[str, object]:
    """Return the complete machine-readable matrix."""
    rows = load_rows()
    records = tuple(classify(row) for row in rows)
    summary = phase_summary(records)
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "matrix_version": "1.0",
        "phases": summary,
        "plan_source": "plan/batches.jsonl",
        "records": list(records),
        "synthetic": True,
        "totals": {
            "batches": len(records),
            "declared_loc_target": sum(int(item["loc_target"] or 0) for item in records),
            "files_present": sum(1 for item in records if item["evidence_state"] == "files-present"),
            "loc_reconciled": sum(1 for item in records if item["declared_vs_target"] == "reconciled"),
            "measured_loc": sum(int(item["measured_total_loc"]) for item in records),
            "missing_output_files": sum(len(list(item["missing_outputs"])) for item in records),
            "partial": sum(1 for item in records if item["evidence_state"] == "partial"),
            "absent": sum(1 for item in records if item["evidence_state"] == "absent"),
        },
    }


def render(matrix: dict[str, object]) -> str:
    """Return the human-readable summary table."""
    lines = [
        "phase  batches  files-present  partial  absent  missing-files  measured-loc  declared-loc  target-loc  loc-reconciled",
    ]
    for phase in matrix["phases"]:  # type: ignore[index]
        lines.append(
            "{phase:<6} {batches:>7}  {files_present:>13}  {partial:>7}  {absent:>6}  {missing:>13}"
            "  {measured:>12}  {declared:>12}  {target:>10}  {reconciled:>14}".format(
                phase=phase["phase"],
                batches=phase["batches"],
                files_present=phase["files_present"],
                partial=phase["partial"],
                absent=phase["absent"],
                missing=phase["missing_output_files"],
                measured=phase["measured_loc"],
                declared=phase["declared_loc_sum"],
                target=phase["declared_loc_target"],
                reconciled=phase["loc_reconciled"],
            )
        )
    totals = matrix["totals"]  # type: ignore[index]
    lines.append("-" * 118)
    lines.append(
        "TOTAL  {batches:>7}  {files_present:>13}  {partial:>7}  {absent:>6}  {missing:>13}"
        "  {measured:>12}  {declared:>12}  {target:>10}  {reconciled:>14}".format(
            batches=totals["batches"],
            files_present=totals["files_present"],
            partial=totals["partial"],
            absent=totals["absent"],
            missing=totals["missing_output_files"],
            measured=totals["measured_loc"],
            declared=totals["declared_loc_target"],
            target=totals["declared_loc_target"],
            reconciled=totals["loc_reconciled"],
        )
    )
    mismatches = [
        str(item["id"]) for item in matrix["records"]  # type: ignore[index]
        if item["declared_vs_target"] == "mismatch"
    ]
    lines.append(f"declared-vs-target mismatches ({len(mismatches)}): {', '.join(mismatches) or 'none'}")
    claimed = [
        f"{item['id']}({item['evidence_state']})"
        for item in matrix["records"]  # type: ignore[index]
        if (item["row_status"] == "complete" or item["row_verified"] or item["row_completed"])
        and item["evidence_state"] != "files-present"
    ]
    lines.append(f"completion claims without full file evidence ({len(claimed)}): {', '.join(claimed) or 'none'}")
    return "\n".join(lines)


def main() -> int:
    """Print the matrix and optionally persist it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write docs/requirements/traceability-matrix.json")
    parser.add_argument("--out", default=str(_MATRIX))
    args = parser.parse_args()
    try:
        matrix = build_matrix()
    except TraceabilityError as failure:
        print(f"FAIL: {failure}")
        return 1
    print(render(matrix))
    if args.write:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"matrix written: {path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
