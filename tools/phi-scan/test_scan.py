#!/usr/bin/env python3
"""Temporary synthetic fixtures for the PHI scanner fail-closed gate."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import importlib.util
import subprocess
import sys
from pathlib import Path


PHI_SCANNER = Path(__file__).resolve().parent / "scan.py"
sys.dont_write_bytecode = True


def load_phi_scanner():
    loader = importlib.util.spec_from_file_location
    spec = loader("atlas_phi_gate", PHI_SCANNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("phi-scanner-unavailable")
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["atlas_phi_gate"] = loaded
    assert spec.loader is not None
    spec.loader.exec_module(loaded)
    return loaded


def _digits(*parts: str) -> str:
    return "".join(parts)


def synthetic_phone() -> str:
    return _digits("138", "0013", "8000")


def synthetic_cn_id() -> str:
    base = _digits("110101", "19900101", "001")
    weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
    checks = "10X98765432"
    check = checks[sum(int(base[index]) * weights[index] for index in range(17)) % 11]
    return base + check


def run_scanner(root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(PHI_SCANNER), "--root", str(root), *extra],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


class PhiScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scanner = load_phi_scanner()

    def test_normal_fixture_and_regex_design_example_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text(
                "# Synthetic fixture\n"
                "The detector expression is `(?<!\\d)\\d{11}(?!\\d)`; it is not data.\n"
                "```regex\n"
                "phone candidate: \\d{3}-\\d{4}-\\d{4}\n"
                "```\n",
                encoding="utf-8",
            )
            (root / "safe.json").write_text(
                json.dumps({"status": "synthetic", "retry_count": 3, "enabled": True}),
                encoding="utf-8",
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "pass")
            self.assertEqual(report["blocked_findings"], 0)
            self.assertEqual(report["scanned_files"], 2)

    def test_verified_identifier_and_phone_are_redacted_and_blocking(self) -> None:
        identifier = synthetic_cn_id()
        phone = synthetic_phone()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "synthetic.json").write_text(
                json.dumps({"patient_id": identifier, "phone": phone}),
                encoding="utf-8",
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "blocked")
            self.assertGreaterEqual(report["blocked_findings"], 2)
            self.assertNotIn(identifier, result.stdout)
            self.assertNotIn(phone, result.stdout)
            for finding in report["findings"]:
                self.assertEqual(
                    set(finding),
                    {"path", "line", "rule", "fingerprint", "masked", "confidence"},
                )
                self.assertTrue(finding["masked"].replace("*", ""), finding)
                self.assertTrue(finding["fingerprint"].startswith("sha256:"), finding)
                self.assertNotIn("value", finding)

    def test_structural_suspect_identifier_fails_closed_even_without_checksum(self) -> None:
        suspect = _digits("12345678", "90123456", "78")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            field = "patient" + "_id"
            (root / "source.py").write_text(
                field + " = '" + suspect + "'\n",
                encoding="utf-8",
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertGreaterEqual(report["blocked_findings"], 1)
            self.assertTrue(
                any(item["rule"] == "structured-identifier" for item in report["findings"]),
                report,
            )
            self.assertNotIn(suspect, result.stdout + result.stderr)

    def test_invalid_json_is_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text('{"synthetic":', encoding="utf-8")
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["status"], "error")
            self.assertEqual(report["errors"][0]["code"], "json-invalid")
            self.assertNotIn("synthetic", result.stdout + result.stderr)

    def test_bad_rule_file_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "safe.txt").write_text("ordinary synthetic text\n", encoding="utf-8")
            bad_json = root / "bad-rules.json"
            bad_json.write_text("not json", encoding="utf-8")
            result = run_scanner(root, "--rules", str(bad_json))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "error")
            bad_regex = root / "bad-regex.json"
            bad_regex.write_text(
                json.dumps({"version": 1, "rules": [{"id": "broken", "pattern": "["}]}),
                encoding="utf-8",
            )
            result = run_scanner(root, "--rules", str(bad_regex))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "error")

    def test_high_entropy_in_sensitive_context_is_redacted(self) -> None:
        secret = _digits("A9zQ7m", "K2xP8r", "T4vW6n", "Y1cZ3d")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "entropy.json").write_text(
                json.dumps({"patient_token": secret}), encoding="utf-8"
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(
                any(item["rule"] == "high-entropy-sensitive" for item in report["findings"]),
                report,
            )

    def test_structured_identifier_catalog_is_not_key_material(self) -> None:
        catalog = " ".join((
            "medication-responsibility-mismatch",
            "workflow-audit-event-unknown",
            "idempotency-responsibility-mismatch",
        ))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog.py").write_text(
                f'CODES = (\n    "{catalog}"\n).split()\n', encoding="utf-8"
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["blocked_findings"], 0)
            self.assertFalse(
                any(item["rule"].startswith("high-entropy") for item in report["findings"]),
                report,
            )

    def test_random_secret_is_still_blocked_after_the_identifier_exemption(self) -> None:
        secret = _digits("A9zQ7m", "K2xP8r", "T4vW6n", "Y1cZ3d")
        hexlike = _digits("4f8a", "1c92", "7be3", "05ad", "9f11", "6c2e")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "secret.json").write_text(
                json.dumps({"patient_token": secret, "digest": hexlike}), encoding="utf-8"
            )
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertNotIn(secret, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertTrue(
                any(item["rule"] == "high-entropy-sensitive" for item in report["findings"]),
                report,
            )

    def test_repository_error_catalog_has_no_blocked_finding(self) -> None:
        catalog = Path(__file__).resolve().parents[2] / "internal" / "contract" / "errors.py"
        self.assertTrue(catalog.is_file(), catalog)
        result = run_scanner(catalog, "--fail-on", "blocked")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["blocked_findings"], 0)

    def test_cache_and_virtualenv_directories_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for directory_name in (".git", "__pycache__", ".venv"):
                skipped = root / directory_name
                skipped.mkdir()
                hidden = "patient" + "_id = " + _digits("12345678", "90123456", "78") + "\n"
                (skipped / "patient_id.txt").write_text(hidden, encoding="utf-8")
            result = run_scanner(root, "--fail-on", "blocked")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["blocked_findings"], 0)
            self.assertEqual(report["scanned_files"], 0)

    def _rules_with_allow(self, root: Path, path: str, digest: str, expires: str | None = None) -> Path:
        entry = {"path": path, "sha256": digest, "reason": "synthetic test fixture", "owner": "privacy-lead"}
        if expires is not None:
            entry["expires"] = expires
        payload = {
            "version": 1,
            "rules": [{"id": "atlas-cloud-access-key", "pattern": "AKIA[0-9A-Z]{16}",
                       "severity": "blocked", "confidence": 0.99}],
            "allow": [entry],
        }
        rules = root.parent / "rules.json"
        rules.write_text(json.dumps(payload), encoding="utf-8")
        return rules

    def test_digest_bound_allow_entry_skips_the_pinned_file(self) -> None:
        body = json.dumps({"patient_id": synthetic_cn_id(), "phone": synthetic_phone()})
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir()
            (root / "patient.json").write_text(body, encoding="utf-8")
            rules = self._rules_with_allow(root, "patient.json", digest)
            result = run_scanner(root, "--rules", str(rules), "--fail-on", "blocked")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["blocked_findings"], 0)
            self.assertEqual([item["path"] for item in report["skipped"]], ["patient.json"])

    def test_tampering_with_a_pinned_file_re_enables_blocking(self) -> None:
        body = json.dumps({"patient_id": synthetic_cn_id(), "phone": synthetic_phone()})
        stale = hashlib.sha256(b"a different file").hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir()
            (root / "patient.json").write_text(body, encoding="utf-8")
            rules = self._rules_with_allow(root, "patient.json", stale)
            result = run_scanner(root, "--rules", str(rules), "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["skipped"], [])
            self.assertGreater(report["blocked_findings"], 0)
            self.assertNotIn(body, result.stdout + result.stderr)

    def test_expired_allow_entry_is_ignored(self) -> None:
        body = json.dumps({"patient_id": synthetic_cn_id(), "phone": synthetic_phone()})
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "work"
            root.mkdir()
            (root / "patient.json").write_text(body, encoding="utf-8")
            rules = self._rules_with_allow(root, "patient.json", digest, expires="2000-01-01")
            result = run_scanner(root, "--rules", str(rules), "--fail-on", "blocked")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["skipped"], [])
            self.assertGreater(report["blocked_findings"], 0)

    def test_committed_allow_entries_match_the_committed_corpus_digests(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        rules_path = repository / "tools" / "phi-scan" / "rules-atlas.json"
        rules = json.loads(rules_path.read_text(encoding="utf-8"))
        entries = rules["allow"]
        self.assertTrue(entries, "the allowlist must not be empty or it is dead configuration")
        for entry in entries:
            target = repository / entry["path"]
            self.assertTrue(target.is_file(), f"allow entry points at a missing file: {entry['path']}")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            self.assertEqual(actual, entry["sha256"], f"digest drift for {entry['path']}")
            self.assertNotIn("*", entry["path"])
            self.assertTrue(entry["reason"].strip() and entry["owner"].strip())
            self.assertIn(entry["expires"], ("2027-03-31",), f"unexpected expiry for {entry['path']}")
        result = run_scanner(repository, "--rules", str(rules_path), "--fail-on", "blocked")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["blocked_findings"], 0)
        self.assertEqual(len(report["skipped"]), len(entries))


if __name__ == "__main__":
    unittest.main()
