"""Official HL7 FHIR Validator (HAPI) execution.

This module runs the real `validator_cli.jar` as a subprocess and turns its
OperationOutcome into the official record that
`internal.contract.validator.require_official()` accepts. It never fabricates a
result: when the engine is missing, times out, or writes no parsable
OperationOutcome, the caller gets a stable error code and the pipeline stops.

The engine is located through the environment so that no binary ever enters the
repository:

    ATLAS_FHIR_VALIDATOR_JAR        absolute path to validator_cli.jar (required)
    ATLAS_JAVA_HOME                 directory holding bin/java (falls back to PATH)
    ATLAS_FHIR_VALIDATOR_JAR_SHA256 optional pinned jar digest; mismatch fails closed
    ATLAS_FHIR_VALIDATOR_ARGS       extra CLI arguments, whitespace separated
    ATLAS_FHIR_VALIDATOR_TIMEOUT    seconds, default 600
    ATLAS_FHIR_VALIDATOR_PROXY      host:port for the JVM proxy properties
    ATLAS_FHIR_VALIDATOR_OFFLINE    "1" adds -no-http-access once the cache is warm
    ATLAS_FHIR_VALIDATOR_TX         terminology server, default "n/a" (disabled)

Provisioning is reproducible: see tools/evidence/provision_fhir_validator.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from internal.contract.digest import canonical_digest, file_digest
from internal.contract.errors import ContractError

_JAR_ENV = "ATLAS_FHIR_VALIDATOR_JAR"
_JAVA_HOME_ENV = "ATLAS_JAVA_HOME"
_JAR_SHA_ENV = "ATLAS_FHIR_VALIDATOR_JAR_SHA256"
_ARGS_ENV = "ATLAS_FHIR_VALIDATOR_ARGS"
_TIMEOUT_ENV = "ATLAS_FHIR_VALIDATOR_TIMEOUT"
_PROXY_ENV = "ATLAS_FHIR_VALIDATOR_PROXY"
_OFFLINE_ENV = "ATLAS_FHIR_VALIDATOR_OFFLINE"
_TX_ENV = "ATLAS_FHIR_VALIDATOR_TX"

DEFAULT_TIMEOUT = 600.0
DEFAULT_FHIR_VERSION = "4.0.1"
DEFAULT_TX = "n/a"
BLOCKING_SEVERITIES = frozenset({"error", "fatal"})
_VERSION_RE = re.compile(r"FHIR Validation tool Version (\S+)(?: \(Git# ([0-9a-f]+)\))?")
_VERSION_CACHE: dict[str, str] = {}


@dataclass(frozen=True)
class EngineConfig:
    """One resolved official validator engine."""

    java: str
    jar: str
    jar_sha256: str
    extra_args: tuple[str, ...]
    timeout: float
    proxy: str
    offline: bool
    tx_server: str


@dataclass(frozen=True)
class OperationOutcome:
    """One parsed official validation result."""

    outcome: str
    outcome_id: str
    issue_count: int
    error_count: int
    warning_count: int
    information_count: int
    issues: tuple[dict[str, str], ...]
    exit_code: int
    elapsed_ms: int
    command: tuple[str, ...]
    fhir_version: str
    validator_version: str
    resource_path: str


def _java_binary(java_home: str) -> str:
    """Return one java executable path or an empty string."""
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        return str(candidate) if candidate.is_file() else ""
    return shutil.which("java") or ""


def engine_config(env: Mapping[str, str] | None = None) -> EngineConfig:
    """Resolve the official engine from the environment, or fail closed."""
    environ: Mapping[str, str] = os.environ if env is None else env
    jar = str(environ.get(_JAR_ENV, "") or "")
    if not jar:
        raise ContractError("validator-engine-unavailable")
    jar_path = Path(jar)
    if not jar_path.is_file():
        raise ContractError("validator-engine-unavailable")
    java = _java_binary(str(environ.get(_JAVA_HOME_ENV, "") or ""))
    if not java:
        raise ContractError("validator-engine-unavailable")
    digest = file_digest(jar_path)
    pinned = str(environ.get(_JAR_SHA_ENV, "") or "").strip().lower()
    if pinned and pinned != digest:
        raise ContractError("validator-jar-digest-mismatch")
    raw_timeout = str(environ.get(_TIMEOUT_ENV, "") or "").strip()
    try:
        timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT
    except ValueError as exc:
        raise ContractError("validator-engine-unavailable") from exc
    if timeout <= 0:
        raise ContractError("validator-engine-unavailable")
    return EngineConfig(
        java=java,
        jar=str(jar_path),
        jar_sha256=digest,
        extra_args=tuple(str(environ.get(_ARGS_ENV, "") or "").split()),
        timeout=timeout,
        proxy=str(environ.get(_PROXY_ENV, "") or "").strip(),
        offline=str(environ.get(_OFFLINE_ENV, "") or "").strip() == "1",
        tx_server=str(environ.get(_TX_ENV, "") or "").strip() or DEFAULT_TX,
    )


def engine_available(env: Mapping[str, str] | None = None) -> bool:
    """Return True only when a real official engine is resolvable."""
    try:
        engine_config(env)
    except ContractError:
        return False
    return True


def validator_version(config: EngineConfig) -> str:
    """Return the official validator version string, cached per jar."""
    cached = _VERSION_CACHE.get(config.jar)
    if cached:
        return cached
    argv = [config.java, "-jar", config.jar, "-help"]
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=min(config.timeout, 300.0),
        )
    except subprocess.TimeoutExpired as exc:
        raise ContractError("validator-engine-timeout") from exc
    except OSError as exc:
        raise ContractError("validator-engine-unavailable") from exc
    head = "\n".join((done.stdout or "").splitlines()[:4] + (done.stderr or "").splitlines()[:4])
    match = _VERSION_RE.search(head)
    if match is None:
        raise ContractError("validator-engine-unavailable")
    version = match.group(1)
    git = match.group(2) or ""
    resolved = f"{version}+git.{git}" if git else version
    _VERSION_CACHE[config.jar] = resolved
    return resolved


def _jvm_properties(config: EngineConfig) -> list[str]:
    """Return JVM flags that keep output UTF-8 and route the proxy."""
    flags = ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]
    host, _, port = config.proxy.partition(":")
    if host and port:
        flags += [
            f"-Dhttps.proxyHost={host}",
            f"-Dhttps.proxyPort={port}",
            f"-Dhttp.proxyHost={host}",
            f"-Dhttp.proxyPort={port}",
        ]
    return flags


def _command(config: EngineConfig, target: Path, output: Path, fhir_version: str,
             profiles: tuple[str, ...], igs: tuple[str, ...]) -> list[str]:
    """Return the exact argv used for one official validation."""
    argv = [config.java, *_jvm_properties(config), "-jar", config.jar, str(target),
            "-version", fhir_version, "-tx", config.tx_server, "-locale", "en",
            "-output", str(output)]
    for profile in profiles:
        argv += ["-profile", profile]
    for ig in igs:
        argv += ["-ig", ig]
    if config.offline:
        argv.append("-no-http-access")
    argv += list(config.extra_args)
    return argv


def _parse_issues(payload: dict[str, object]) -> tuple[dict[str, str], ...]:
    """Return severity/code/expression rows, never the diagnostic text."""
    raw = payload.get("issue")
    issues = raw if isinstance(raw, list) else []
    parsed: list[dict[str, str]] = []
    for item in issues:
        if not isinstance(item, dict):
            raise ContractError("validator-output-corrupt")
        details = item.get("details")
        text = ""
        if isinstance(details, dict):
            text = str(details.get("text", ""))
        expression = item.get("expression")
        location = expression if isinstance(expression, list) else ([expression] if expression else [])
        parsed.append({
            "code": str(item.get("code", "")),
            "diagnostics_sha256": canonical_digest({"text": text}),
            "expression": ",".join(str(part) for part in location),
            "severity": str(item.get("severity", "")),
        })
    return tuple(parsed)


def validate_file(
    resource_path: Path | str,
    *,
    config: EngineConfig | None = None,
    fhir_version: str = DEFAULT_FHIR_VERSION,
    profiles: tuple[str, ...] = (),
    igs: tuple[str, ...] = (),
    output_path: Path | None = None,
) -> OperationOutcome:
    """Run the official validator against one file and parse its outcome."""
    # Cheap input validation first, so a caller error is reported even where no
    # engine is configured at all.
    target = Path(resource_path)
    if not target.is_file():
        raise ContractError("validator-input-invalid")
    cfg = config or engine_config()
    temporary = tempfile.TemporaryDirectory() if output_path is None else None
    try:
        output = Path(output_path) if output_path is not None else Path(temporary.name) / "operation-outcome.json"
        argv = _command(cfg, target, output, fhir_version, tuple(profiles), tuple(igs))
        started = time.monotonic()
        try:
            done = subprocess.run(
                argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=cfg.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise ContractError("validator-engine-timeout") from exc
        except OSError as exc:
            raise ContractError("validator-engine-unavailable") from exc
        elapsed_ms = int((time.monotonic() - started) * 1000)
        if not output.is_file():
            raise ContractError("validator-output-missing")
        raw = output.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractError("validator-output-corrupt") from exc
        if not isinstance(payload, dict) or payload.get("resourceType") != "OperationOutcome":
            raise ContractError("validator-output-corrupt")
        issues = _parse_issues(payload)
        counts = {severity: sum(1 for item in issues if item["severity"] == severity)
                  for severity in ("error", "fatal", "warning", "information")}
        blocking = counts["error"] + counts["fatal"]
        return OperationOutcome(
            outcome="pass" if blocking == 0 else "fail",
            outcome_id=hashlib.sha256(raw).hexdigest(),
            issue_count=len(issues),
            error_count=counts["error"] + counts["fatal"],
            warning_count=counts["warning"],
            information_count=counts["information"],
            issues=issues,
            exit_code=int(done.returncode),
            elapsed_ms=elapsed_ms,
            command=tuple(argv),
            fhir_version=fhir_version,
            validator_version=validator_version(cfg),
            resource_path=str(target),
        )
    finally:
        if temporary is not None:
            temporary.cleanup()


def official_record(
    payload: dict[str, object],
    outcome: OperationOutcome,
    *,
    config: EngineConfig,
    content_digest: str = "",
) -> dict[str, object]:
    """Return the record require_official() accepts, plus real provenance."""
    digest = content_digest or canonical_digest(payload)
    return {
        "command": list(outcome.command),
        "contentDigest": digest,
        "elapsedMs": outcome.elapsed_ms,
        "engine": "hapi",
        "errorCount": outcome.error_count,
        "executedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exitCode": outcome.exit_code,
        "fhirVersion": outcome.fhir_version,
        "informationCount": outcome.information_count,
        "issueCount": outcome.issue_count,
        "issues": [dict(item) for item in outcome.issues],
        "jarSha256": config.jar_sha256,
        "official": True,
        "outcome": outcome.outcome,
        "outcomeId": outcome.outcome_id,
        "resourcePath": outcome.resource_path,
        "validatorVersion": outcome.validator_version,
        "warningCount": outcome.warning_count,
    }


def validate_payload(
    payload: dict[str, object],
    *,
    config: EngineConfig | None = None,
    fhir_version: str = DEFAULT_FHIR_VERSION,
    profiles: tuple[str, ...] = (),
    igs: tuple[str, ...] = (),
    suffix: str = "resource",
) -> dict[str, object]:
    """Validate one in-memory resource with the official engine."""
    if not isinstance(payload, dict) or not payload:
        raise ContractError("validator-input-invalid")
    cfg = config or engine_config()
    version = validator_version(cfg)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / f"{suffix}.json"
        source.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        keep = Path(directory) / "operation-outcome.json"
        outcome = validate_file(
            source, config=cfg, fhir_version=fhir_version, profiles=profiles, igs=igs, output_path=keep,
        )
        if outcome.validator_version != version:
            raise ContractError("validator-engine-unavailable")
        return official_record(payload, outcome, config=cfg)
