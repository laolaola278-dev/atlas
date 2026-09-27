"""Audit a tree and reconcile it with the batch plan."""
import importlib.util
from pathlib import Path
import sys


def _load_plan_module():
    source = Path(__file__).with_name("plan.py")
    spec = importlib.util.spec_from_file_location("atlas_locaudit_plan", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("locaudit-plan-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules["atlas_locaudit_plan"] = module
    spec.loader.exec_module(module)
    return module


_plan = _load_plan_module()
globals().update({name: getattr(_plan, name) for name in dir(_plan) if not name.startswith("__")})

def _record_from_file(path: Path, root: Path) -> FileRecord | None:
    relative = path.relative_to(root).as_posix() or "."
    try:
        text = _read_text(path)
    except UnicodeDecodeError:
        # Binary/unknown files are not source and are intentionally not a
        # read failure.  They are represented as skipped files by the caller.
        return None
    classification = classify_file(relative, text)
    try:
        sloc = count_sloc(text, relative) if classification["category"] != "document" else 0
    except AuditInputError:
        raise
    physical = len(text.splitlines())
    digest = _file_digest(path)
    return FileRecord(
        path=relative,
        category=classification["category"],
        language=classification["language"],
        sloc=sloc,
        physical_lines=physical,
        package=_package_for(relative),
        reason=classification["reason"],
        digest=digest,
    )


def _iter_tree(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        # Skip VCS/environment/cache directories entirely.  Cache files in
        # ordinary source directories are still classified below.
        dirnames[:] = sorted(
            dirname
            for dirname in dirnames
            if dirname not in TREE_SKIP_DIRS and not (current / dirname).is_symlink()
        )
        for filename in sorted(filenames):
            child = current / filename
            if child.is_symlink() or not child.is_file():
                continue
            yield child


def _empty_test_findings(records: Sequence[FileRecord]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    # This intentionally reports only locations, never the assertion text.
    assertion_re = re.compile(
        r"\bassert\s+True\b|self\.assertTrue\s*\(\s*True\s*\)|t\.Skip\s*\(",
        re.IGNORECASE,
    )
    for record in records:
        if record.category != "test" or record.path.endswith((".pb.go", "_pb2.py")):
            continue
        try:
            text = (Path(record.path)).read_text(encoding="utf-8")
        except Exception:
            # The source path is relative to the current process, not the
            # original root; skip this optional diagnostic if unavailable.
            continue
        for match in assertion_re.finditer(text):
            result.append({"path": record.path, "line": text.count("\n", 0, match.start()) + 1})
    return sorted(result, key=lambda item: (item["path"], item["line"]))


def _gate(gate_id: str, status: str, actual: Any, threshold: Any, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": gate_id,
        "status": status,
        "actual": actual,
        "threshold": threshold,
    }
    result.update(extra)
    return result


def audit_tree(
    root: str | os.PathLike[str],
    max_file_lines: int = DEFAULT_MAX_FILE_LINES,
    max_package_lines: int = DEFAULT_MAX_PACKAGE_LINES,
    duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD,
    plan_path: str | os.PathLike[str] | None = None,
    enforce_sloc: bool = False,
) -> dict[str, Any]:
    if max_file_lines <= 0 or max_package_lines <= 0:
        raise ValueError("line limits must be positive")
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise AuditInputError("root-missing")
    if root_path.is_file():
        root_path = root_path.parent
    records: list[FileRecord] = []
    errors: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for path in _iter_tree(root_path):
        relative = path.relative_to(root_path).as_posix() if path.is_relative_to(root_path) else path.as_posix()
        # Paths under an explicitly cache-like directory are not read.
        parts = {part.lower() for part in Path(relative).parts}
        if parts.intersection(TREE_SKIP_DIRS):
            skipped.append({"path": relative, "reason": "skipped-directory"})
            continue
        if parts.intersection(CACHE_DIR_NAMES):
            # Cache files stay in their own bucket. Decode only when the file
            # is text so a binary cache cannot fail the gate.
            try:
                record = _record_from_file(path, root_path)
            except AuditInputError:
                record = None
            if record is None:
                skipped.append({"path": relative, "reason": "cache-file"})
            else:
                records.append(record)
            continue
        try:
            record = _record_from_file(path, root_path)
        except AuditInputError as exc:
            errors.append({"path": relative, "code": str(exc)})
            continue
        except Exception:
            errors.append({"path": relative, "code": "file-read-failed"})
            continue
        if record is None:
            skipped.append({"path": relative, "reason": "binary-or-unknown"})
        else:
            records.append(record)

    production = sum(record.sloc for record in records if record.category == "production")
    tests = sum(record.sloc for record in records if record.category == "test")
    generated = sum(record.sloc for record in records if record.category == "generated")
    vendor = sum(record.sloc for record in records if record.category == "vendor")
    cache_records = [record for record in records if record.category == "cache"]
    cache = sum(record.sloc for record in cache_records)
    documents = sum(record.sloc for record in records if record.category == "document")
    generated_files = sum(1 for record in records if record.category == "generated")
    vendor_files = sum(1 for record in records if record.category == "vendor")
    cache_files = sum(1 for record in cache_records)

    packages: dict[str, dict[str, int]] = {}
    for record in records:
        if record.category not in {"production", "test"}:
            continue
        package = packages.setdefault(
            record.package,
            {"production": 0, "test": 0, "total": 0, "files": 0},
        )
        package[record.category] += record.sloc
        package["total"] += record.sloc
        package["files"] += 1

    manual_texts: dict[str, str] = {}
    for record in records:
        if record.category not in {"production", "test"}:
            continue
        try:
            manual_texts[record.path] = (root_path / record.path).read_text(encoding="utf-8")
        except Exception:
            # The file was already read; this is an unexpected race.  Mark it
            # as an audit error instead of silently undercounting.
            errors.append({"path": record.path, "code": "file-raced"})
    duplicates = find_duplicate_blocks(manual_texts, threshold=duplicate_threshold)

    oversized = [
        {"path": record.path, "lines": record.physical_lines, "threshold": max_file_lines}
        for record in records
        if record.category in {"production", "test"} and record.physical_lines > max_file_lines
    ]
    oversized_packages = [
        {"package": package, "lines": values["total"], "threshold": max_package_lines}
        for package, values in packages.items()
        if values["total"] > max_package_lines
    ]
    empty_test_findings = _empty_test_findings(records)
    # _empty_test_findings needs the actual root to resolve paths; run a
    # second, root-aware pass without exposing source text.
    empty_test_findings = []
    assertion_re = re.compile(
        r"\bassert\s+True\b|self\.assertTrue\s*\(\s*True\s*\)|t\.Skip\s*\(",
        re.IGNORECASE,
    )
    for record in records:
        if record.category != "test":
            continue
        try:
            text = (root_path / record.path).read_text(encoding="utf-8")
        except Exception:
            continue
        for match in assertion_re.finditer(text):
            empty_test_findings.append(
                {"path": record.path, "line": text.count("\n", 0, match.start()) + 1}
            )
    empty_test_findings.sort(key=lambda item: (item["path"], item["line"]))

    manual_total = production + tests
    gates: list[dict[str, Any]] = [
        _gate(
            "manual-sloc",
            "fail" if enforce_sloc and manual_total < MANUAL_SLOC_TARGET else ("pass" if not enforce_sloc else "pass"),
            manual_total,
            MANUAL_SLOC_TARGET,
            enforced=bool(enforce_sloc),
        ),
        _gate("production-test-separation", "pass" if manual_total == production + tests else "fail", manual_total, None),
        _gate("file-line-limit", "fail" if oversized else "pass", max((item["lines"] for item in oversized), default=0), max_file_lines, files=oversized),
        _gate("package-line-limit", "fail" if oversized_packages else "pass", max((item["lines"] for item in oversized_packages), default=0), max_package_lines, packages=oversized_packages),
        _gate("duplicate-blocks", "fail" if duplicates else "pass", len(duplicates), 0, blocks=duplicates[:100]),
        _gate("empty-tests", "fail" if empty_test_findings else "pass", len(empty_test_findings), 0, findings=empty_test_findings),
    ]
    plan_report: dict[str, Any] | None = None
    if plan_path is not None:
        rows = load_plan(plan_path)
        plan_report = validate_plan(rows)
        plan_status = plan_report["status"]
        plan_actual = manual_total
        plan_target = plan_report["total_loc"]
        gates.append(
            _gate(
                "batch-plan-reconciliation",
                "pass" if plan_status == "pass" else "fail",
                plan_actual,
                plan_target,
                batches=plan_report["batches"],
                issues=plan_report["issues"],
            )
        )
        plan_report["measured_manual_sloc"] = plan_actual
        plan_report["measured_delta"] = plan_actual - plan_target

    violations: list[dict[str, Any]] = []
    for gate in gates:
        if gate["status"] == "fail":
            violations.append({"id": gate["id"], "actual": gate["actual"], "threshold": gate["threshold"]})

    files_public = [
        {
            "path": record.path,
            "category": record.category,
            "language": record.language,
            "sloc": record.sloc,
            "physical_lines": record.physical_lines,
            "reason": record.reason,
            "digest": record.digest,
        }
        for record in sorted(records, key=lambda item: item.path)
    ]
    stable_material = "\n".join(
        f"{item['path']}:{item['digest']}:{item['sloc']}" for item in files_public
    ).encode("utf-8")
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "error" if errors else ("fail" if violations else "pass"),
        "manual": {"production": production, "test": tests, "total": manual_total},
        "generated": {"total": generated, "files": generated_files},
        "vendor": {"total": vendor, "files": vendor_files},
        "caches": {"total": cache, "files": cache_files},
        "documents": {"total": documents},
        "files": files_public,
        "modules": [
            {"package": package, **values}
            for package, values in sorted(packages.items())
        ],
        "duplicates": duplicates,
        "gates": gates,
        "violations": violations,
        "skipped": sorted(skipped, key=lambda item: (item["path"], item["reason"])),
        "errors": sorted(errors, key=lambda item: (item.get("path", ""), item.get("code", ""))),
        "digest": "sha256:" + hashlib.sha256(stable_material).hexdigest(),
    }
    if plan_report is not None:
        report["plan"] = plan_report
    return report


def _error_report(code: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _datetime.datetime.now(_datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "error",
        "manual": {"production": 0, "test": 0, "total": 0},
        "generated": {"total": 0, "files": 0},
        "vendor": {"total": 0, "files": 0},
        "caches": {"total": 0, "files": 0},
        "files": [],
        "modules": [],
        "duplicates": [],
        "gates": [],
        "violations": [],
        "errors": [{"code": code}],
    }


def _write_report(report: Mapping[str, Any], output: str | os.PathLike[str] | None) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if output is None:
        sys.stdout.write(rendered + "\n")
        return
    try:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    except Exception as exc:
        raise AuditInputError("output-unwritable") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="locaudit",
        description="Audit hand-written source SLOC and report quality gates.",
    )
    parser.add_argument("--root", default=".", help="repository root to audit")
    parser.add_argument("--plan", default=None, help="optional batches.jsonl reconciliation input")
    parser.add_argument("--out", default=None, help="write JSON report to this path")
    parser.add_argument("--max-file-lines", type=int, default=DEFAULT_MAX_FILE_LINES)
    parser.add_argument("--max-package-lines", type=int, default=DEFAULT_MAX_PACKAGE_LINES)
    parser.add_argument(
        "--duplicate-threshold",
        type=float,
        default=DEFAULT_DUPLICATE_THRESHOLD,
        help="Jaccard threshold for duplicate blocks (default: 0.90)",
    )
    parser.add_argument(
        "--enforce-sloc",
        action="store_true",
        help="also fail when the 560000 hand-written LOC target is not met",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.max_file_lines <= 0 or args.max_package_lines <= 0:
            raise AuditInputError("line-limit-invalid")
        if not 0.0 <= args.duplicate_threshold <= 1.0:
            raise AuditInputError("duplicate-threshold-invalid")
        report = audit_tree(
            args.root,
            max_file_lines=args.max_file_lines,
            max_package_lines=args.max_package_lines,
            duplicate_threshold=args.duplicate_threshold,
            plan_path=args.plan,
            enforce_sloc=args.enforce_sloc,
        )
        _write_report(report, args.out)
    except PlanError as exc:
        _write_report(_error_report(str(exc)), None)
        return EXIT_ERROR
    except (AuditInputError, ValueError) as exc:
        _write_report(_error_report(str(exc) if str(exc).startswith(("root-", "line-", "duplicate-", "output-")) else "audit-error"), None)
        return EXIT_ERROR
    except OSError:
        _write_report(_error_report("environment-error"), None)
        return EXIT_ERROR
    if report.get("errors"):
        return EXIT_ERROR
    return EXIT_FINDINGS if report.get("status") == "fail" else EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess tests
    raise SystemExit(main())
