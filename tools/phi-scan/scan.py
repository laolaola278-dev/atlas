"""Scan files and emit a redacted PHI report."""
import importlib.util
import sys
from pathlib import Path


def _load_sibling(module_name, filename):
    source = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(module_name + "-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_rules = _load_sibling("atlas_phi_rules", "rules.py")
globals().update({name: getattr(_rules, name) for name in dir(_rules) if not name.startswith("__")})

def scan_text(
    text: str,
    path: str = "fixture.txt",
    rules: RuleSet | None = None,
) -> list[dict[str, Any]]:
    """Scan a text string and return only redacted finding dictionaries.

    Invalid JSON is handled by :func:`scan_file`; this helper remains useful for
    tests and for callers that already have decoded text.
    """
    rule_set = rules or load_rules()
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = _normalise_text(text)
    findings: list[Finding] = []
    for line_number, original_line in enumerate(normalized.splitlines(), 1):
        line = original_line
        for rule in rule_set.rules:
            for match in rule.pattern.finditer(line):
                value = match.group(0)
                if _looks_like_regex_example(path, line, match.start(), match.end()):
                    continue
                if rule.check is not None and not _check_rule(rule, value, line):
                    continue
                confidence = _confidence_for(rule, path, line, value)
                if confidence <= 0:
                    continue
                _add_finding(
                    findings,
                    path,
                    line_number,
                    rule.rule_id,
                    value,
                    rule.severity,
                    confidence,
                )
        _scan_key_values(line, path, findings, line_number)
        _scan_entropy_line(line, path, line_number, findings)
    suffix = Path(path).suffix.lower()
    if suffix in {".json", ".jsonl", ".ndjson"}:
        _scan_json_structure(normalized, path, findings)
    _scan_source_literals(normalized, path, findings)
    return [finding.public() for finding in _deduplicate(findings)]


def _is_text_candidate(path: Path) -> bool:
    if path.name in TEXT_BASENAMES:
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower().endswith(
        (".env.example", ".dockerfile")
    )


def _read_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except Exception as exc:
        raise ScanInputError("file-unreadable") from exc
    if b"\x00" in data[:8192]:
        raise BinaryInput()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ScanInputError("file-encoding-invalid") from exc


def _validate_structured_input(path: Path, text: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            json.loads(text)
        except Exception as exc:
            raise ScanInputError("json-invalid") from exc
    elif suffix in {".jsonl", ".ndjson"}:
        for line_number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except Exception as exc:
                raise ScanInputError("jsonl-invalid") from exc


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return path.as_posix()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _allow_match(rule_set: RuleSet, path: str, path_obj: Path) -> AllowEntry | None:
    today = _datetime.date.today()
    for entry in rule_set.allow:
        if entry.path != path:
            continue
        if entry.expires is not None and entry.expires < today:
            continue
        try:
            if _file_digest(path_obj) == entry.sha256:
                return entry
        except OSError:
            continue
    return None


def _error_report(code: str, path: str | None = None) -> dict[str, Any]:
    errors: list[dict[str, str]] = [{"code": code}]
    if path:
        errors[0]["path"] = path
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "error",
        "scanned_files": 0,
        "blocked_findings": 0,
        "review_findings": 0,
        "findings": [],
        "skipped": [],
        "errors": errors,
    }


def scan_root(
    root: str | os.PathLike[str],
    rules_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Scan ``root`` and return a JSON-serializable, redacted report."""
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise ScanInputError("root-missing")
    rules = load_rules(rules_path)
    if root_path.is_file():
        candidates = [root_path]
        root_path = root_path.parent
    else:
        candidates = []
        for directory, dirnames, filenames in os.walk(root_path, topdown=True, followlinks=False):
            current = Path(directory)
            kept_dirs: list[str] = []
            for dirname in sorted(dirnames):
                child = current / dirname
                if dirname in SKIP_DIRS or child.is_symlink():
                    continue
                kept_dirs.append(dirname)
            dirnames[:] = kept_dirs
            for filename in sorted(filenames):
                child = current / filename
                if child.is_symlink():
                    continue
                if _is_text_candidate(child):
                    candidates.append(child)
            # Do not let an inaccessible directory silently disappear.
            if not os.access(current, os.R_OK):
                # The current directory can be a root on some platforms; an
                # actual error is recorded below by attempting its files.
                pass

    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    findings: list[dict[str, Any]] = []
    scanned_files = 0
    for candidate in sorted(set(candidates), key=lambda p: _relative_path(p, root_path)):
        relative = _relative_path(candidate, root_path)
        if not _is_text_candidate(candidate):
            skipped.append({"path": relative, "reason": "unsupported-file-type"})
            continue
        try:
            text = _read_text(candidate)
        except BinaryInput:
            skipped.append({"path": relative, "reason": "binary-file"})
            continue
        except ScanInputError as exc:
            errors.append({"path": relative, "code": str(exc)})
            continue
        except Exception:
            errors.append({"path": relative, "code": "file-unreadable"})
            continue
        try:
            _validate_structured_input(candidate, text)
            scanned_files += 1
            allowed = _allow_match(rules, relative, candidate)
            if allowed is not None:
                skipped.append({"path": relative, "reason": "allowlisted-digest"})
                continue
            findings.extend(scan_text(text, relative, rules))
        except ScanInputError as exc:
            errors.append({"path": relative, "code": str(exc)})
        except RuleConfigError as exc:
            raise
        except Exception:
            errors.append({"path": relative, "code": "scan-failed"})
    findings = sorted(
        findings,
        key=lambda item: (item.get("path", ""), int(item.get("line", 0)), item.get("rule", ""), item.get("fingerprint", "")),
    )
    blocked = sum(1 for item in findings if _is_blocked_finding(item, rules))
    review = len(findings) - blocked
    status = "error" if errors else ("blocked" if blocked else ("review" if review else "pass"))
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "scanned_files": scanned_files,
        "blocked_findings": blocked,
        "review_findings": review,
        "findings": findings,
        "skipped": sorted(skipped, key=lambda item: (item["path"], item["reason"])),
        "errors": sorted(errors, key=lambda item: (item.get("path", ""), item.get("code", ""))),
    }


def _is_blocked_finding(item: Mapping[str, Any], rules: RuleSet) -> bool:
    rule_id = item.get("rule", "")
    # Public findings omit severity by design.  Resolve it from the rule set.
    for rule in rules.rules:
        if rule.rule_id == rule_id:
            return rule.severity == "blocked"
    return rule_id in {
        "structured-identifier",
        "phi-context-combo",
        "high-entropy-sensitive",
    }


def _write_report(report: Mapping[str, Any], output: str | os.PathLike[str] | None) -> None:
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if output is None:
        sys.stdout.write(rendered + "\n")
        return
    path = Path(output)
    try:
        path.write_text(rendered + "\n", encoding="utf-8")
    except Exception as exc:
        raise ScanInputError("output-unwritable") from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phi-scan",
        description="Scan repository text for redacted, deterministic PHI/PII candidates.",
    )
    parser.add_argument("--root", default=".", help="repository root or file to scan")
    parser.add_argument(
        "--rules",
        default=None,
        help="optional JSON rules file; malformed rules fail closed",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "review", "blocked"),
        default="none",
        help="exit 1 for findings at this level (default: none)",
    )
    parser.add_argument("--out", default=None, help="write JSON report to this path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        rules = load_rules(args.rules)
        report = scan_root(args.root, args.rules)
        # A rules file may specify a default; an explicit CLI option wins.
        effective_fail_on = args.fail_on
        if args.fail_on == "none" and rules.configured_fail_on:
            effective_fail_on = rules.configured_fail_on
        _write_report(report, args.out)
    except RuleConfigError as exc:
        report = _error_report(str(exc) if str(exc).startswith("rules-") else "rules-config-error")
        _write_report(report, None)
        return EXIT_ERROR
    except ScanInputError as exc:
        report = _error_report(str(exc))
        _write_report(report, None)
        return EXIT_ERROR
    except OSError:
        report = _error_report("environment-error")
        _write_report(report, None)
        return EXIT_ERROR
    if report.get("errors"):
        return EXIT_ERROR
    level = "review" if effective_fail_on == "review" else "blocked"
    if effective_fail_on == "review" and report.get("review_findings", 0):
        return EXIT_FINDINGS
    if effective_fail_on == "blocked" and report.get("blocked_findings", 0):
        return EXIT_FINDINGS
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover - exercised by subprocess tests
    raise SystemExit(main())
