"""Tests for the official HL7 FHIR Validator integration.

Two groups:

1. Engine-independent tests always run. They prove the integration fails closed
   when no official engine can be resolved, that a pinned jar digest mismatch is
   rejected, and that a real-shaped record is what require_official() accepts.
2. Engine-dependent tests run only when the environment names a real
   validator_cli.jar plus a JRE. When the engine is absent they are reported as
   skipped, never as passed; tools/evidence/fhir_official_validation.py is the
   runner that records which group actually executed.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from internal.contract._path import install_contract_path

install_contract_path()
from internal.contract.digest import canonical_digest  # noqa: E402
from internal.contract.errors import ContractError  # noqa: E402
from internal.contract.hapi_validator import (  # noqa: E402
    EngineConfig,
    OperationOutcome,
    engine_available,
    engine_config,
    official_record,
    validate_file,
    validate_payload,
    validator_version,
)
from internal.contract.validator import require_official  # noqa: E402

_ROOT = Path(__file__).resolve().parents[2]
_CORPUS = _ROOT / "testdata" / "fhir" / "r4-examples"
_NEGATIVE = _ROOT / "testdata" / "fhir" / "synthetic" / "r4-observation-invalid-status.json"
_JAR = os.environ.get("ATLAS_FHIR_VALIDATOR_JAR", "")
_ENGINE = bool(_JAR) and Path(_JAR).is_file() and _CORPUS.is_dir()
_SKIP = "official validator engine not configured (set ATLAS_FHIR_VALIDATOR_JAR, ATLAS_JAVA_HOME and testdata/fhir/r4-examples)"


def dummy_config() -> EngineConfig:
    """Return one engine configuration without touching the environment."""
    return EngineConfig(
        java="java",
        jar="validator_cli.jar",
        jar_sha256="1" * 64,
        extra_args=(),
        timeout=600.0,
        proxy="",
        offline=False,
        tx_server="n/a",
    )


def fake_outcome(outcome: str = "pass", errors: int = 0) -> OperationOutcome:
    """Return one engine-shaped outcome without running a JVM."""
    return OperationOutcome(
        outcome=outcome,
        outcome_id="a" * 64,
        issue_count=errors + 1,
        error_count=errors,
        warning_count=0,
        information_count=1,
        issues=({"code": "invalid", "diagnostics_sha256": "b" * 64, "expression": "Observation.status", "severity": "error"},) * errors
        + ({"code": "informational", "diagnostics_sha256": "c" * 64, "expression": "", "severity": "information"},),
        exit_code=0,
        elapsed_ms=1,
        command=("java", "-jar", "validator_cli.jar", "resource.json"),
        fhir_version="4.0.1",
        validator_version="6.10.4+git.1b90fb13f77b",
        resource_path="resource.json",
    )


class EngineIndependentTests(unittest.TestCase):
    def test_engine_config_fails_closed_without_a_jar(self) -> None:
        self.assertFalse(engine_available({}))
        with self.assertRaises(ContractError) as raised:
            engine_config({})
        self.assertEqual(str(raised.exception), "validator-engine-unavailable")

    def test_engine_config_fails_closed_when_the_jar_path_is_absent(self) -> None:
        env = {"ATLAS_FHIR_VALIDATOR_JAR": str(_ROOT / "no-such-validator.jar"), "ATLAS_JAVA_HOME": str(_ROOT)}
        with self.assertRaises(ContractError) as raised:
            engine_config(env)
        self.assertEqual(str(raised.exception), "validator-engine-unavailable")

    def test_engine_config_fails_closed_without_a_java_runtime(self) -> None:
        env = {"ATLAS_FHIR_VALIDATOR_JAR": str(_CORPUS / "patient-example.json"), "ATLAS_JAVA_HOME": str(_ROOT / "no-jdk")}
        with self.assertRaises(ContractError) as raised:
            engine_config({**env, "PATH": ""})
        self.assertEqual(str(raised.exception), "validator-engine-unavailable")

    def test_pinned_jar_digest_mismatch_is_rejected(self) -> None:
        # A fake JAVA_HOME with a bin/java placeholder is enough: engine_config
        # only resolves paths and digests, it never starts a JVM.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            (root / "bin" / ("java.exe" if os.name == "nt" else "java")).write_text("placeholder", encoding="utf-8")
            jar = root / "validator_cli.jar"
            jar.write_text("not-a-real-jar", encoding="utf-8")
            env = {
                "ATLAS_FHIR_VALIDATOR_JAR": str(jar),
                "ATLAS_JAVA_HOME": str(root),
                "ATLAS_FHIR_VALIDATOR_JAR_SHA256": "0" * 64,
            }
            with self.assertRaises(ContractError) as raised:
                engine_config(env)
            self.assertEqual(str(raised.exception), "validator-jar-digest-mismatch")
            resolved = engine_config({k: v for k, v in env.items() if not k.endswith("JAR_SHA256")})
            self.assertEqual(len(resolved.jar_sha256), 64)
            self.assertEqual(resolved.timeout, 600.0)
            self.assertEqual(resolved.tx_server, "n/a")

    def test_invalid_timeout_is_rejected(self) -> None:
        env = {
            "ATLAS_FHIR_VALIDATOR_JAR": str(_CORPUS / "patient-example.json"),
            "ATLAS_FHIR_VALIDATOR_TIMEOUT": "not-a-number",
        }
        with self.assertRaises(ContractError) as raised:
            engine_config(env)
        self.assertIn(str(raised.exception), {"validator-engine-unavailable"})

    def test_missing_input_file_and_empty_payload_are_rejected_without_an_engine(self) -> None:
        # Input validation happens before engine resolution, so a caller error is
        # reported even on a machine with no JRE and no jar.
        with self.assertRaises(ContractError) as absent:
            validate_file(_ROOT / "no-such-resource.json")
        self.assertEqual(str(absent.exception), "validator-input-invalid")
        with self.assertRaises(ContractError) as empty:
            validate_payload({})
        self.assertEqual(str(empty.exception), "validator-input-invalid")
        if not engine_available():
            # With no engine configured, resolution itself must fail closed
            # instead of silently skipping the official validation.
            with self.assertRaises(ContractError) as absent_engine:
                validate_payload({"resourceType": "Observation"})
            self.assertEqual(str(absent_engine.exception), "validator-engine-unavailable")

    def test_official_record_shape_is_what_require_official_accepts(self) -> None:
        payload = {"resourceType": "Observation", "id": "example", "status": "final"}
        config = dummy_config()
        digest = canonical_digest(payload)
        passed = official_record(payload, fake_outcome("pass"), config=config, content_digest=digest)
        self.assertEqual(passed["engine"], "hapi")
        self.assertIs(passed["official"], True)
        self.assertEqual(passed["contentDigest"], digest)
        self.assertEqual(require_official({**payload, "contentDigest": digest}, passed), "a" * 64)
        failed = official_record(payload, fake_outcome("fail", errors=2), config=config, content_digest=digest)
        with self.assertRaises(ContractError) as rejected:
            require_official({**payload, "contentDigest": digest}, failed)
        self.assertEqual(str(rejected.exception), "validator-outcome-failed")
        with self.assertRaises(ContractError) as stale:
            require_official({**payload, "contentDigest": "f" * 64}, passed)
        self.assertEqual(str(stale.exception), "validator-digest-mismatch")


@unittest.skipUnless(_ENGINE, _SKIP)
class OfficialEngineTests(unittest.TestCase):
    config = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = engine_config()
        cls.version = validator_version(cls.config)

    def test_version_is_recorded(self) -> None:
        self.assertRegex(self.version, r"^\d+\.\d+\.\d+")
        self.assertNotEqual(self.version, "")

    def test_official_validator_passes_the_hl7_r4_example_corpus(self) -> None:
        for name in ("patient-example.json", "observation-example.json", "bundle-example.json"):
            source = _CORPUS / name
            payload = __import__("json").loads(source.read_text(encoding="utf-8"))
            outcome = validate_file(source, config=self.config)
            record = official_record(payload, outcome, config=self.config)
            self.assertEqual(outcome.outcome, "pass", f"{name}: {outcome.issues}")
            self.assertEqual(outcome.error_count, 0, name)
            self.assertEqual(outcome.exit_code, 0, name)
            self.assertEqual(outcome.fhir_version, "4.0.1", name)
            self.assertEqual(outcome.validator_version, self.version, name)
            self.assertEqual(
                require_official({**payload, "contentDigest": record["contentDigest"]}, record),
                outcome.outcome_id,
                name,
            )

    def test_official_validator_rejects_an_invalid_required_code(self) -> None:
        import json

        payload = json.loads(_NEGATIVE.read_text(encoding="utf-8"))
        outcome = validate_file(_NEGATIVE, config=self.config)
        record = official_record(payload, outcome, config=self.config)
        self.assertEqual(outcome.outcome, "fail", outcome.issues)
        self.assertGreaterEqual(outcome.error_count, 1)
        self.assertTrue(
            any(item["expression"].startswith("Observation.status") for item in outcome.issues),
            outcome.issues,
        )
        with self.assertRaises(ContractError) as rejected:
            require_official({**payload, "contentDigest": record["contentDigest"]}, record)
        self.assertEqual(str(rejected.exception), "validator-outcome-failed")


if __name__ == "__main__":
    unittest.main()
