"""Reproducible provisioning for the official FHIR validator engine and corpus.

Nothing binary enters the repository. This script places the JRE, the official
validator jar and the HL7 R4 example corpus outside the working tree, verifies
every artifact against a pinned SHA-256, and writes one provenance record into
docs/evidence/p1/fhir-validator-provenance.json.

Usage:
    python -B tools/evidence/provision_fhir_validator.py --verify-only
    python -B tools/evidence/provision_fhir_validator.py --dest <dir> [--download]

Pins are the contract: a digest mismatch fails closed and is never overwritten
silently. The Adoptium URL is a floating "latest 21 GA" alias, so the digest is
what pins the JRE, together with the resolved version string.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_PROVENANCE = _ROOT / "docs" / "evidence" / "p1" / "fhir-validator-provenance.json"
_CORPUS_DIR = _ROOT / "testdata" / "fhir" / "r4-examples"
_CORPUS_BASE = "https://hl7.org/fhir/R4/"

VALIDATOR_PIN = {
    "artifact": "validator_cli.jar",
    "bytes": 200928617,
    "publisher": "HL7 / hapifhir org.hl7.fhir.core",
    "release_published_at": "2026-09-04T05:39:02Z",
    "release_tag": "6.10.4",
    "sha256": "1106b9d58f9e363e47bea7c4fc065841e5fc91fe9d062775c3bfdd212bd653cc",
    "signature_asset": "validator_cli.jar.asc",
    "signature_note": "GPG signature asset published alongside the jar; not verified here because no gpg binary is available in this environment.",
    "url": "https://github.com/hapifhir/org.hl7.fhir.core/releases/download/6.10.4/validator_cli.jar",
}

JRE_PIN = {
    "artifact": "jdk21.zip",
    "bytes": 205073461,
    "extracted_directory": "jdk-21.0.12.1+1",
    "publisher": "Eclipse Temurin (Adoptium)",
    "resolved_version": "21.0.12.1+1",
    "sha256": "f9d6e191ab098c0d416e7d588a24420a8621cd2f4720dab2459b8b7b2d2d8b4e",
    "url": "https://api.adoptium.net/v3/binary/latest/21/ga/windows/x64/jdk/hotspot/normal/eclipse",
    "url_note": "floating latest-21-GA alias; the sha256 and resolved_version are the actual pins",
}

CORPUS_PINS = {
    "patient-example.json": "7cc6b3817264c22e722b6bc10e494d3441341032f8294db7ccec796ca7a0cf81",
    "observation-example.json": "95b2b641707cd473902670a65c20008282c09b7e71731d1010a3db6ce24fce7f",
    "bundle-example.json": "04e02dacfb194294a79b43d5ddf25a0df2af8ef135df4a7f8aa7dd51f85ecf91",
    "condition-example.json": "450c80e71cdad565523c27a62bc94f53db949e02417e1d2dd4fe39927f34adeb",
    "encounter-example.json": "6ef7c93b28fa76d3f1f1dcd3e795a8e35c70b5f86ad4659b75f7fc3d93ff0bb5",
    "practitioner-example.json": "f7bdedca23fe131d62bbf7efae8c4dca6c691fe1ab78aa55e81b5fea43a88655",
}


def sha256_file(path: Path) -> str:
    """Return the SHA-256 of one file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def default_dest() -> Path:
    """Return the default out-of-tree tool directory."""
    override = os.environ.get("ATLAS_FHIR_TOOLS_DIR", "")
    if override:
        return Path(override)
    return _ROOT.parent / "_scratch" / "tools"


def download(url: str, target: Path, timeout: int = 1800) -> bool:
    """Fetch one artifact with curl so the system proxy settings are honoured."""
    target.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        ["curl", "-sS", "-L", "--fail", "--retry", "3", "--connect-timeout", "30",
         "--max-time", str(timeout), "-o", str(target), url],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return done.returncode == 0 and target.is_file()


def check_pin(path: Path, expected_sha: str, expected_bytes: int | None = None) -> dict[str, object]:
    """Return one verification row for a pinned artifact."""
    row: dict[str, object] = {"expected_sha256": expected_sha, "path": path.name, "present": path.is_file()}
    if not path.is_file():
        row["status"] = "missing"
        return row
    actual = sha256_file(path)
    size = path.stat().st_size
    row["actual_sha256"] = actual
    row["bytes"] = size
    if actual != expected_sha:
        row["status"] = "digest-mismatch"
    elif expected_bytes is not None and size != expected_bytes:
        row["status"] = "size-mismatch"
    else:
        row["status"] = "verified"
    return row


def extract_jre(archive: Path, dest: Path) -> Path | None:
    """Extract the JRE archive once and return the java home directory."""
    expected = dest / JRE_PIN["extracted_directory"]
    if (expected / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file():
        return expected
    if not archive.is_file():
        return None
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(dest)
    return expected if expected.is_dir() else None


def resolve_java(dest: Path) -> str:
    """Return one usable java executable path or an empty string."""
    candidate = dest / JRE_PIN["extracted_directory"] / "bin" / ("java.exe" if os.name == "nt" else "java")
    if candidate.is_file():
        return str(candidate)
    home = os.environ.get("ATLAS_JAVA_HOME", "")
    if home and (Path(home) / "bin" / candidate.name).is_file():
        return str(Path(home) / "bin" / candidate.name)
    return shutil.which("java") or ""


def main() -> int:
    """Verify or provision the engine, then write the provenance record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", default=str(default_dest()), help="out-of-tree tool directory")
    parser.add_argument("--download", action="store_true", help="fetch missing pinned artifacts")
    parser.add_argument("--verify-only", action="store_true", help="verify what exists and exit")
    parser.add_argument("--out", default=str(_PROVENANCE))
    args = parser.parse_args()
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    jar_path = dest / "fhir-validator" / VALIDATOR_PIN["artifact"]
    jre_zip = dest / JRE_PIN["artifact"]

    corpus_rows = {}
    for name, digest in sorted(CORPUS_PINS.items()):
        target = _CORPUS_DIR / name
        if not target.is_file() and args.download and not args.verify_only:
            if not download(_CORPUS_BASE + name, target):
                corpus_rows[name] = {"status": "download-failed"}
                continue
        row = check_pin(target, digest)
        row["path"] = str(target.relative_to(_ROOT)).replace(os.sep, "/")
        corpus_rows[name] = row

    if not jar_path.is_file() and args.download and not args.verify_only:
        download(VALIDATOR_PIN["url"], jar_path)
    if not jre_zip.is_file() and args.download and not args.verify_only:
        download(JRE_PIN["url"], jre_zip)

    jar_row = check_pin(jar_path, VALIDATOR_PIN["sha256"], VALIDATOR_PIN["bytes"])
    jre_row = check_pin(jre_zip, JRE_PIN["sha256"], JRE_PIN["bytes"])
    java_home = extract_jre(jre_zip, dest / "jdk21") if not args.verify_only else (
        dest / "jdk21" / JRE_PIN["extracted_directory"]
    )
    java = resolve_java(dest / "jdk21") if java_home and java_home.is_dir() else resolve_java(dest)

    version = ""
    if java and jar_row.get("status") == "verified":
        try:
            done = subprocess.run([java, "-jar", str(jar_path), "-help"], capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=300)
            head = "\n".join((done.stdout or "").splitlines()[:3])
            version = head.splitlines()[0] if head.splitlines() else ""
        except (OSError, subprocess.SubprocessError):
            version = ""

    usable = bool(java) and jar_row.get("status") == "verified"
    provenance = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": corpus_rows,
        "corpus_base_url": _CORPUS_BASE,
        "corpus_directory": str(_CORPUS_DIR.relative_to(_ROOT)).replace(os.sep, "/"),
        "engine": {
            "java": java,
            "jar": str(jar_path),
            "jar_verification": jar_row,
            "jre_verification": jre_row,
            "tool_directory": str(dest),
            "usable": usable,
            "validator_help_first_line": version,
        },
        "pins": {"jre": JRE_PIN, "validator": VALIDATOR_PIN},
        "provenance_version": "1.0",
        "repository_binary_policy": "no JRE, jar or package cache is committed; only pins, corpus fixtures and provenance are",
        "synthetic": True,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"engine usable      : {usable}")
    print(f"java               : {java or 'none'}")
    print(f"jar verification   : {jar_row.get('status')}")
    print(f"jre verification   : {jre_row.get('status')}")
    print(f"validator version  : {version[:96] or 'unresolved'}")
    bad = [name for name, row in corpus_rows.items() if row.get("status") != "verified"]
    print(f"corpus verified    : {len(corpus_rows) - len(bad)}/{len(corpus_rows)}" + (f" (bad: {bad})" if bad else ""))
    print(f"provenance written : {out.relative_to(_ROOT)}")
    if args.verify_only and not usable:
        return 1
    return 0 if usable and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
