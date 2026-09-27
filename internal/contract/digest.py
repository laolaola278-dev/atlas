"""Canonical payload digest.

One definition is shared by the FHIR gate, the workflow slice, the audit stage
and the official validator integration so that a digest computed anywhere can be
compared everywhere. The encoding is fixed: sorted keys, no insignificant
whitespace, UTF-8.
"""
from __future__ import annotations

import hashlib
import json


def canonical_json(payload: object) -> str:
    """Return the canonical JSON text of one payload."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_digest(payload: object) -> str:
    """Return the SHA-256 digest that binds a resource to its evidence."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def file_digest(path) -> str:
    """Return the SHA-256 digest of one file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
