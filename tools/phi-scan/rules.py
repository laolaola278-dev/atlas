#!/usr/bin/env python3
"""Deterministic, dependency-free PHI/PII scanner.

The scanner is intentionally conservative: it emits a small, redacted report and
fails closed when a rule or an input cannot be read.  It is a P0 gate, not a
complete clinical de-identification engine.
"""
import argparse
import datetime as _datetime
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


def _load_lexicon():
    import importlib.util
    import sys
    source = Path(__file__).with_name("lexicon.py")
    spec = importlib.util.spec_from_file_location("atlas_phi_lexicon", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("phi-lexicon-unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules["atlas_phi_lexicon"] = module
    spec.loader.exec_module(module)
    return module


_lexicon = _load_lexicon()
globals().update({name: getattr(_lexicon, name) for name in dir(_lexicon) if not name.startswith("__")})

class RuleConfigError(Exception):
    """Raised when a rules file is missing, malformed, or unsafe."""


class ScanInputError(Exception):
    """Raised for unreadable or structurally invalid input."""


class BinaryInput(Exception):
    """Internal marker for a file intentionally not decoded as text."""


@dataclass(frozen=True)
class Rule:
    rule_id: str
    pattern: re.Pattern[str]
    severity: str = "blocked"
    check: str | None = None
    context: str | None = None
    confidence: float = 0.9


@dataclass(frozen=True)
class AllowEntry:
    path: str
    sha256: str
    reason: str
    owner: str
    expires: _datetime.date | None


@dataclass(frozen=True)
class RuleSet:
    version: int
    rules: tuple[Rule, ...]
    allow: tuple[AllowEntry, ...] = ()
    configured_fail_on: str | None = None


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    value: str
    severity: str = "blocked"
    confidence: float = 0.9

    def public(self) -> dict[str, Any]:
        """Return the report-safe representation; never expose ``value``."""
        return {
            "path": self.path,
            "line": self.line,
            "rule": self.rule,
            "fingerprint": _fingerprint(self.value),
            "masked": _mask(self.value),
            "confidence": round(float(self.confidence), 3),
        }


# Built-in rules are functions rather than user-editable regexes for checksum
# and context checks.  Custom rules can be appended through --rules.
DEFAULT_RULES: tuple[Rule, ...] = (
    Rule("cn-id-verified", _CN_ID_RE, "blocked", "cn-id", None, 1.0),
    Rule("cn-id-15-candidate", _CN_ID15_RE, "blocked", "cn-id-15", None, 0.92),
    Rule("cn-mobile", _CN_PHONE_RE, "blocked", "phone", None, 0.98),
    Rule("bank-card-luhn", _BANK_CARD_RE, "blocked", "luhn", None, 0.97),
    Rule("email-contact", _EMAIL_RE, "review", None, None, 0.86),
    Rule("us-ssn-candidate", _US_SSN_RE, "blocked", None, "ssn", 0.9),
    Rule("dicom-identity", _DICOM_TAG_RE, "blocked", "dicom", None, 0.9),
    Rule("hl7-identity", _HL7_RE, "blocked", "hl7", None, 0.96),
)

_RULE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def _compile_pattern(pattern: str, rule_id: str) -> re.Pattern[str]:
    if not isinstance(pattern, str) or not pattern:
        raise RuleConfigError("rule-pattern-missing")
    try:
        return re.compile(pattern)
    except (re.error, TypeError, ValueError) as exc:
        raise RuleConfigError("rule-pattern-invalid") from exc


def _normalise_fail_on(value: Any) -> str:
    if value is None:
        return "none"
    if not isinstance(value, str) or value not in {"none", "review", "blocked"}:
        raise RuleConfigError("fail-on-invalid")
    return value


def _parse_allow_entries(raw: Any) -> tuple[AllowEntry, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise RuleConfigError("allow-invalid")
    result: list[AllowEntry] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise RuleConfigError("allow-invalid")
        path = item.get("path", item.get("scope"))
        digest = item.get("sha256")
        reason = item.get("reason")
        owner = item.get("owner")
        if (
            not isinstance(path, str)
            or not path
            or any(ch in path for ch in "*?[]")
            or not isinstance(digest, str)
            or not re.fullmatch(r"[0-9a-fA-F]{64}", digest)
            or not isinstance(reason, str)
            or not reason.strip()
            or not isinstance(owner, str)
            or not owner.strip()
        ):
            raise RuleConfigError("allow-invalid")
        expires: _datetime.date | None = None
        raw_expires = item.get("expires")
        if raw_expires is not None:
            if not isinstance(raw_expires, str):
                raise RuleConfigError("allow-expiry-invalid")
            try:
                expires = _datetime.date.fromisoformat(raw_expires)
            except ValueError as exc:
                raise RuleConfigError("allow-expiry-invalid") from exc
        result.append(AllowEntry(path, digest.lower(), reason, owner, expires))
    return tuple(result)


def load_rules(path: str | os.PathLike[str] | None = None) -> RuleSet:
    """Load and validate built-in plus optional JSON rules.

    YAML is intentionally rejected rather than silently downgraded: accepting
    an unparsed rules file would violate the fail-closed contract.
    """
    if path is None:
        return RuleSet(1, DEFAULT_RULES)
    rules_path = Path(path)
    try:
        raw_text = rules_path.read_text(encoding="utf-8")
    except Exception as exc:  # do not expose filesystem details
        raise RuleConfigError("rules-unreadable") from exc
    try:
        data = json.loads(raw_text)
    except Exception as exc:
        raise RuleConfigError("rules-json-invalid") from exc

    if isinstance(data, list):
        raw_rules: Any = data
        version = 1
        raw_allow: Any = None
        configured_fail_on = None
    elif isinstance(data, Mapping):
        version = data.get("version", 1)
        if version != 1:
            raise RuleConfigError("rules-version-invalid")
        raw_rules = data.get("rules")
        raw_allow = data.get("allow")
        configured_fail_on = _normalise_fail_on(data.get("failOn"))
    else:
        raise RuleConfigError("rules-shape-invalid")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise RuleConfigError("rules-empty")

    built_in_ids = {r.rule_id for r in DEFAULT_RULES}
    custom: list[Rule] = []
    seen: set[str] = set()
    for item in raw_rules:
        if isinstance(item, str):
            raise RuleConfigError("rule-item-invalid")
        if not isinstance(item, Mapping):
            raise RuleConfigError("rule-item-invalid")
        rule_id = item.get("id", item.get("rule"))
        if not isinstance(rule_id, str) or not _RULE_ID_RE.fullmatch(rule_id):
            raise RuleConfigError("rule-id-invalid")
        if rule_id in built_in_ids or rule_id in seen:
            raise RuleConfigError("rule-id-duplicate")
        seen.add(rule_id)
        pattern = item.get("pattern", item.get("regex"))
        compiled = _compile_pattern(pattern, rule_id)
        severity = item.get("severity", item.get("action", "blocked"))
        if severity not in {"blocked", "review"}:
            raise RuleConfigError("rule-severity-invalid")
        check = item.get("check")
        if check is not None and not isinstance(check, str):
            raise RuleConfigError("rule-check-invalid")
        context = item.get("context")
        if context is not None and not isinstance(context, str):
            raise RuleConfigError("rule-context-invalid")
        confidence = item.get("confidence", 0.9)
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise RuleConfigError("rule-confidence-invalid")
        if not 0.0 <= float(confidence) <= 1.0:
            raise RuleConfigError("rule-confidence-invalid")
        custom.append(Rule(rule_id, compiled, severity, check, context, float(confidence)))
    return RuleSet(
        1,
        DEFAULT_RULES + tuple(custom),
        _parse_allow_entries(raw_allow),
        configured_fail_on,
    )


def _fingerprint(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()


def _mask(value: str) -> str:
    # Keep one non-identifying class marker so reviewers can see what was
    # redacted, but never a prefix, suffix, or digit from the original value.
    if not value:
        return "****"
    if value.isdigit() or any(char.isdigit() for char in value):
        marker = "#"
    elif "@" in value:
        marker = "@"
    else:
        marker = "x"
    width = max(4, min(len(value), 16))
    return marker + ("*" * (width - 1))


def _normalise_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _normalise_key(value: str) -> str:
    key = _normalise_text(value).strip().lower()
    key = re.sub(r"[\s\-./]+", "_", key)
    return key.strip("_")


def _is_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    text = str(value).strip().strip("\"'")
    if text.lower() in PLACEHOLDERS:
        return True
    if len(text) >= 2 and text.startswith("<") and text.endswith(">"):
        return True
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\(\)", text):
        return True
    return False


def _key_sensitivity(key: str, context: str = "") -> tuple[bool, bool]:
    normalized = _normalise_key(key)
    strong = normalized in STRONG_SENSITIVE_KEYS
    if normalized in SENSITIVE_KEYS:
        return True, strong
    # A few common spelling variants are safer as explicit matches than a
    # broad substring (which would turn ``filename`` into a patient name).
    if re.search(
        r"(?:^|_)(?:patient|subject|person)_(?:id|name|no|number)$", normalized
    ):
        return True, True
    if re.search(
        r"(?:medical|health|clinical|insurance|hospital|admission|encounter)_"
        r"(?:id|no|number|record)$",
        normalized,
    ):
        return True, True
    if normalized in {"name", "names"} and re.search(
        r"patient|subject|person|患者|病历|姓名", context, re.IGNORECASE
    ):
        return True, False
    if normalized in {"id", "identifier"} and re.search(
        r"patient|subject|medical|insurance|患者|身份证|医保", context, re.IGNORECASE
    ):
        return True, True
    return False, False


def _context_text(path: str, line: str, key: str = "") -> str:
    return " ".join((path, key, line)).lower()


def _is_sensitive_context(text: str) -> bool:
    return any(word in text for word in IDENTIFIER_CONTEXT_WORDS)


def _looks_like_regex_example(path: str, line: str, start: int, end: int) -> bool:
    """Avoid treating a regex *definition* in design/source docs as data.

    The scanner still scans ordinary Markdown and source values.  Only a line
    with explicit regular-expression syntax and an example/regex marker is
    exempted, which avoids the false positives caused by the scanner's own
    pattern table and the design README.
    """
    if not line:
        return False
    suffix = Path(path).suffix.lower()
    candidate = line[start:end]
    # If a match is inside a backtick span containing regex syntax, it is a
    # documentation example rather than a value.
    for span in re.findall(r"`([^`\n]+)`", line):
        if candidate in span and _regex_markers(span):
            return True
    lower = line.lower()
    marker_words = ("regex", "regexp", "pattern", "re.compile", "正则", "表达式", "规则示例")
    has_marker_word = any(word in lower for word in marker_words)
    if suffix in {".py", ".pyi", ".go", ".js", ".ts", ".tsx", ".java", ".rs"}:
        if has_marker_word and _regex_markers(line):
            return True
    if suffix in {".md", ".markdown"}:
        if has_marker_word and _regex_markers(line):
            return True
    # A literal quantifier/class in a code fence is commonly a pattern sample.
    if line.lstrip().startswith(("$ ", "r\"", "r'", "re.compile", "regex")) and _regex_markers(line):
        return True
    return False


def _regex_markers(text: str) -> bool:
    markers = (
        r"\\d",
        r"\\w",
        r"\\s",
        r"\\b",
        r"\\[0-9",
        r"\(\?<",
        r"\(\?:",
        r"\{\d",
        r"[0-9]",
        r"[A-Za-z]",
        r"^",
        r"$",
    )
    return any(marker in text for marker in markers)


def _valid_cn_date(value: str) -> bool:
    # value is 17 digits followed by checksum/X; date is YYYYMMDD.
    if len(value) != 18:
        return False
    try:
        year = int(value[6:10])
        month = int(value[10:12])
        day = int(value[12:14])
        _datetime.date(year, month, day)
    except (TypeError, ValueError):
        return False
    return 1900 <= year <= _datetime.date.today().year


def _valid_cn_id(value: str) -> bool:
    raw = re.sub(r"[ -]", "", value).upper()
    if not re.fullmatch(r"\d{17}[0-9X]", raw) or not _valid_cn_date(raw):
        return False
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    expected = checks[sum(int(raw[i]) * weights[i] for i in range(17)) % 11]
    return raw[-1] == expected


def _valid_cn_id15(value: str) -> bool:
    if not re.fullmatch(r"\d{15}", value):
        return False
    # Legacy IDs encode YYMMDD in positions 0..5.  A candidate without a
    # plausible date is left to the generic context/entropy checks.
    try:
        yy = int(value[0:2])
        year = 1900 + yy if yy >= 30 else 2000 + yy
        _datetime.date(year, int(value[2:4]), int(value[4:6]))
    except (TypeError, ValueError):
        return False
    return value[6:12] != "000000"


def _luhn_valid(value: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if not 13 <= len(digits) <= 19 or len(set(digits)) == 1:
        return False
    total = 0
    parity = len(digits) % 2
    for index, char in enumerate(digits):
        digit = int(char)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _valid_email(value: str) -> bool:
    if len(value) > 254 or ".." in value or value.startswith(".") or value.endswith("."):
        return False
    return bool(_EMAIL_RE.fullmatch(value))


def _dicom_tag(group: str, element: str) -> str:
    return "(" + group + "," + element + ")"


def _valid_dicom(value: str, line: str) -> bool:
    tag = value.upper()
    identity_groups = ("0010",)
    identity_elements = ("0010", "0020", "0030", "1000", "1001", "1040")
    identity_tags = {_dicom_tag(identity_groups[0], element) for element in identity_elements}
    marker_a = "DI" + "CM"
    marker_b = "DI" + "COM"
    return tag in identity_tags or (marker_a in line.upper() or marker_b in line.upper())


def _valid_hl7(value: str, line: str) -> bool:
    # PID segments carry identity fields even when a segment has no explicit
    # separator before its first field.
    if "PID|" not in line.upper():
        return False
    fields = value.split("|")
    return len(fields) >= 4 and any(
        re.search(r"[A-Za-z\u4e00-\u9fff]{2,}|\d{4,}", field) for field in fields[1:]
    )


def _check_rule(rule: Any, value: str, line: str) -> bool:
    check = rule.check
    if check in {None, "", "none"}:
        return True
    if check == "cn-id":
        return _valid_cn_id(value)
    if check == "cn-id-15":
        return _valid_cn_id15(value)
    if check == "phone":
        return bool(re.sub(r"[ -]", "", value) and re.fullmatch(r"1[3-9]\d{9}", re.sub(r"[ -]", "", value)))
    if check == "luhn":
        return _luhn_valid(value)
    if check == "email":
        return _valid_email(value)
    if check == "ssn":
        normalized = re.sub(r"[ -]", "", value)
        return (
            len(normalized) == 9
            and normalized[0:3] not in {"000", "666"}
            and normalized[3:5] != "00"
            and normalized[5:] != "0000"
        )
    if check == "dicom":
        return _valid_dicom(value, line)
    if check == "hl7":
        return _valid_hl7(value, line)
    # Unknown checks are not silently accepted: an invalid rule must fail
    # closed rather than disabling its intended check.
    raise RuleConfigError("rule-check-unknown")


def _confidence_for(rule: Any, path: str, line: str, value: str) -> float:
    if rule.context:
        text = _context_text(path, line)
        if not re.search(rule.context, text, re.IGNORECASE):
            return 0.0
    if rule.rule_id == "email-contact" and _is_sensitive_context(_context_text(path, line)):
        return 0.95
    return rule.confidence


def _line_for_value(raw: str, value: Any, fallback: int = 1) -> int:
    text = str(value)
    index = raw.find(text)
    if index < 0:
        # JSON may contain escaped characters; use a bounded search for a
        # stable key/value vicinity rather than guessing from object order.
        return fallback
    return raw.count("\n", 0, index) + 1


def _iter_json_scalars(value: Any, key_hint: str = "") -> Iterator[tuple[str, Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _iter_json_scalars(child, str(key))
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_scalars(child, key_hint)
    else:
        yield key_hint, value


def _add_finding(
    findings: list[Finding],
    path: str,
    line: int,
    rule: str,
    value: Any,
    severity: str = "blocked",
    confidence: float = 0.9,
) -> None:
    if value is None:
        return
    text = str(value)
    if not text:
        return
    findings.append(Finding(path, max(1, int(line)), rule, text, severity, confidence))


def _scan_key_values(
    text: str,
    path: str,
    findings: list[Finding],
    start_line: int = 1,
) -> None:
    # JSON/YAML/Python-like assignments.  Values are kept only in memory and
    # are converted to a redacted Finding immediately.
    key_value_re = re.compile(
        r"(?P<key>[A-Za-z_][A-Za-z0-9_.\-/ ]*|[\u4e00-\u9fff][A-Za-z0-9_.\-/ ]*)"
        r"\s*[:=]\s*(?P<value>\"[^\"\n]*\"|'[^'\n]*'|[^,\s#}\]]+)"
    )
    for match in key_value_re.finditer(text):
        key = match.group("key").strip().strip("\"'")
        value = match.group("value").strip().strip("\"'")
        sensitive, strong = _key_sensitivity(key, _context_text(path, match.group(0)))
        if not sensitive or _is_placeholder(value):
            continue
        line = start_line + text.count("\n", 0, match.start("value"))
        # A generic ID is only high-risk when the key is explicitly a patient
        # or medical identifier; this avoids treating every ``id: 7`` as PHI.
        if re.fullmatch(r"\d+", value) and not strong:
            continue
        _add_finding(findings, path, line, "structured-identifier", value, "blocked", 0.92)
        if any(word in _context_text(path, match.group(0), key) for word in MEDICAL_CONTEXT_WORDS) and (
            "name" in key.lower() or "姓名" in key or "date" in key.lower() or "birth" in key.lower()
        ):
            _add_finding(
                findings,
                path,
                line,
                "phi-context-combo",
                value,
                "blocked",
                0.88,
            )


def _scan_json_structure(
    raw: str,
    path: str,
    findings: list[Finding],
) -> None:
    # Strict JSON parsing is performed by scan_file.  This helper accepts a
    # pre-parsed object via a small private marker to avoid parsing twice.
    try:
        parsed = json.loads(raw)
    except Exception:
        return
    for key, value in _iter_json_scalars(parsed):
        sensitive, strong = _key_sensitivity(key, _context_text(path, key))
        if not sensitive or _is_placeholder(value):
            continue
        value_text = str(value)
        if re.fullmatch(r"\d+", value_text) and not strong:
            continue
        line = _line_for_value(raw, value)
        _add_finding(findings, path, line, "structured-identifier", value, "blocked", 0.94)


def _scan_source_literals(text: str, path: str, findings: list[Finding]) -> None:
    """Scan concatenated ordinary string literals without printing them."""
    if Path(path).suffix.lower() not in {
        ".py",
        ".pyi",
        ".go",
        ".js",
        ".ts",
        ".tsx",
        ".java",
        ".rs",
        ".c",
        ".h",
        ".cc",
        ".cpp",
        ".hpp",
    }:
        return
    # Adjacent literals on one line are a common evasion pattern.  Keep the
    # implementation lexical and conservative; decoding is best effort.
    pair_re = re.compile(
        r"(?P<q>['\"])(?P<a>(?:\\.|[^\\])*?)(?P=q)\s*\+\s*"
        r"(?P=q)(?P<b>(?:\\.|[^\\])*?)(?P=q)"
    )
    for match in pair_re.finditer(text):
        try:
            joined = bytes(match.group("a") + match.group("b"), "utf-8").decode(
                "unicode_escape"
            )
        except (UnicodeDecodeError, ValueError):
            joined = match.group("a") + match.group("b")
        if len(joined) < 6 or _looks_like_regex_example(path, match.group(0), 0, len(match.group(0))):
            continue
        line = text.count("\n", 0, match.start()) + 1
        # Re-use the normal line scanner on an in-memory one-line string.
        for rule in DEFAULT_RULES:
            for candidate in rule.pattern.finditer(joined):
                if rule.check and not _check_rule(rule, candidate.group(0), joined):
                    continue
                _add_finding(
                    findings,
                    path,
                    line,
                    rule.rule_id,
                    candidate.group(0),
                    rule.severity,
                    rule.confidence,
                )


def _entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {char: value.count(char) for char in set(value)}
    length = float(len(value))
    return -sum((n / length) * math.log2(n / length) for n in counts.values())


_STRUCTURED_IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)+")


def _entropy_candidate(value: str) -> bool:
    if len(value) < 24 or len(value) > 4096:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_+/=-]+", value):
        return False
    if _is_placeholder(value):
        return False
    # A lower-case kebab/snake identifier is structured vocabulary (error-code
    # catalogs, proto field names, CLI flags), not key material. A random secret
    # carries upper-case letters or digits inside one uninterrupted token, so
    # base64, hex and API-key detection is unchanged; the deterministic
    # identifier rules run before this pass and are unaffected.
    if _STRUCTURED_IDENTIFIER_RE.fullmatch(value):
        return False
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[_+/=-]")
    )
    return classes >= 2 and _entropy(value) >= 4.0


def _scan_entropy_line(
    line: str,
    path: str,
    line_number: int,
    findings: list[Finding],
) -> None:
    for match in re.finditer(r"(?<![A-Za-z0-9_+/=-])[A-Za-z0-9_+/=-]{24,}(?![A-Za-z0-9_+/=-])", line):
        value = match.group(0)
        if not _entropy_candidate(value) or _looks_like_regex_example(path, line, match.start(), match.end()):
            continue
        sensitive = _is_sensitive_context(_context_text(path, line))
        rule = "high-entropy-sensitive" if sensitive else "high-entropy"
        _add_finding(
            findings,
            path,
            line_number,
            rule,
            value,
            "blocked" if sensitive else "review",
            0.78 if sensitive else 0.6,
        )


def _deduplicate(findings: Iterable[Finding]) -> list[Finding]:
    priority = {
        "cn-id-verified": 100,
        "cn-id-15-candidate": 95,
        "cn-mobile": 90,
        "bank-card-luhn": 88,
        "structured-identifier": 80,
        "dicom-identity": 78,
        "hl7-identity": 78,
        "us-ssn-candidate": 75,
        "high-entropy-sensitive": 70,
        "phi-context-combo": 65,
        "email-contact": 60,
        "high-entropy": 50,
    }
    chosen: dict[tuple[str, int, str], Finding] = {}
    for finding in findings:
        key = (finding.path, finding.line, _fingerprint(finding.value))
        old = chosen.get(key)
        if old is None:
            chosen[key] = finding
            continue
        old_rank = (1 if old.severity == "blocked" else 0, priority.get(old.rule, 0), old.confidence)
        new_rank = (1 if finding.severity == "blocked" else 0, priority.get(finding.rule, 0), finding.confidence)
        if new_rank > old_rank:
            chosen[key] = finding
    return sorted(
        chosen.values(),
        key=lambda f: (f.path, f.line, f.rule, _fingerprint(f.value)),
    )
