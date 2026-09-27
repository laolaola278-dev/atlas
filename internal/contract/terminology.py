"""Synthetic terminology release checks.

A code may be used only when its system has one active release covering the
review time. Unknown and expired releases fail closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier


_MANIFEST = Path(__file__).resolve().parents[2] / "api" / "terminology" / "manifest.json"


def load_releases() -> tuple[dict[str, str], ...]:
    """Return the synthetic release records."""
    try:
        payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("terminology-manifest-corrupt") from exc
    releases = payload.get("releases")
    if payload.get("synthetic") is not True or not isinstance(releases, list) or not releases:
        raise ContractError("terminology-manifest-corrupt")
    loaded: list[dict[str, str]] = []
    for item in releases:
        if not isinstance(item, dict):
            raise ContractError("terminology-manifest-corrupt")
        record = {
            "system_url": str(item.get("system_url", "")),
            "release_id": str(item.get("release_id", "")),
            "effective_from": str(item.get("effective_from", "")),
            "effective_to": str(item.get("effective_to", "")),
        }
        if not all(record.values()):
            raise ContractError("terminology-manifest-corrupt")
        loaded.append(record)
    return tuple(loaded)


def require_active_release(
    system_url: str,
    at_time: str,
    actor_id: str = "actor-synthetic",
    why_code: str = "treatment-review",
) -> str:
    """Return the release covering this time, or reject the code system."""
    if not system_url or not at_time or not actor_id:
        raise ContractError("terminology-release-incomplete")
    if why_code in {"", "unknown", "unspecified"}:
        raise ContractError("terminology-why-missing")
    named = (actor_id, why_code)
    if any(path_has_direct_identifier(value) for value in named):
        raise ContractError("terminology-identifier-forbidden")
    for release in load_releases():
        if release["system_url"] != system_url:
            continue
        if at_time < release["effective_from"] or at_time >= release["effective_to"]:
            raise ContractError("terminology-release-expired")
        return release["release_id"]
    raise ContractError("terminology-release-unknown")


class ReleaseLedger:
    """Remember one code system so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def require(
        self,
        system_url: str,
        at_time: str,
        actor_id: str = "actor-synthetic",
        why_code: str = "treatment-review",
    ) -> str:
        release_id = require_active_release(system_url, at_time, actor_id, why_code)
        recorded = self._records.get(system_url)
        incoming = (actor_id, why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("terminology-responsibility-mismatch")
        self._records.setdefault(system_url, incoming)
        return release_id

    def restore(self, system_url: str, actor_id: str, why_code: str) -> None:
        """Restore one accepted code system without treating it as a new review."""
        missing_actor = not system_url or not actor_id
        if missing_actor:
            raise ContractError("terminology-release-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("terminology-why-missing")
        self._records[system_url] = (actor_id, why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored terminology decisions in stable order."""
        return tuple(sorted(self._records.items()))


def icd_package(payload: dict[str, object]) -> dict[str, str]:
    """Accept an ICD package header. Code tables stay outside this gate."""
    if "codes" in payload or payload.get("synthetic") is not True:
        raise ContractError("icd-package-forbidden")
    family = str(payload.get("family", ""))
    release_id = str(payload.get("release_id", ""))
    digest = str(payload.get("digest", ""))
    if family != "ICD":
        raise ContractError("icd-family-rejected")
    if release_id == "" or path_has_direct_identifier(release_id):
        raise ContractError("icd-release-invalid")
    if len(digest) != 64:
        raise ContractError("icd-digest-invalid")
    return {"digest": digest, "family": family, "release_id": release_id}


_UNITS = frozenset({"mg/dL", "mmol/L", "1"})


def loinc_unit(code_digest: str, unit: str, synthetic: bool) -> dict[str, str]:
    """Map one synthetic code digest to an allowed unit."""
    if synthetic is not True:
        raise ContractError("loinc-not-synthetic")
    if len(code_digest) != 64 or path_has_direct_identifier(code_digest):
        raise ContractError("loinc-digest-invalid")
    if unit not in _UNITS:
        raise ContractError("loinc-unit-unknown")
    return {"digest": code_digest, "unit": unit}


def snomed_subset(name: str, members: tuple[str, ...], synthetic: bool) -> dict[str, object]:
    """Accept a subset of concept digests without storing concept text."""
    if synthetic is not True or "concepts" in name:
        raise ContractError("snomed-not-synthetic")
    if name == "" or path_has_direct_identifier(name):
        raise ContractError("snomed-name-forbidden")
    if not members or len(members) > 100:
        raise ContractError("snomed-subset-invalid")
    if len(set(members)) != len(members):
        raise ContractError("snomed-member-duplicate")
    if any(len(item) != 64 or path_has_direct_identifier(item) for item in members):
        raise ContractError("snomed-member-invalid")
    return {"count": len(members), "members": members, "name": name}


def medication_code(local_digest: str, standard_digest: str, synthetic: bool) -> dict[str, str]:
    """Map one local medication digest to one standard digest."""
    if synthetic is not True:
        raise ContractError("medcode-not-synthetic")
    pair = (local_digest, standard_digest)
    if any(len(item) != 64 or path_has_direct_identifier(item) for item in pair):
        raise ContractError("medcode-digest-invalid")
    if local_digest == standard_digest:
        raise ContractError("medcode-same-digest")
    return {"local": local_digest, "standard": standard_digest}


class LocalExtensionRegistry:
    """Register one synthetic extension id without free text."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def register(self, extension_id: str, digest: str, synthetic: bool) -> int:
        if synthetic is not True:
            raise ContractError("extension-not-synthetic")
        if extension_id == "" or path_has_direct_identifier(extension_id):
            raise ContractError("extension-id-forbidden")
        if len(digest) != 64:
            raise ContractError("extension-digest-invalid")
        if extension_id in self._items:
            raise ContractError("extension-duplicate")
        self._items[extension_id] = digest
        return len(self._items)


def rollback_release(current_from: str, current_to: str, previous_to: str, at_time: str) -> str:
    """Return the previous boundary only after the current release ended."""
    bounds = (current_from, current_to, previous_to, at_time)
    if any(value == "" for value in bounds):
        raise ContractError("rollback-window-incomplete")
    if at_time < current_to:
        raise ContractError("rollback-still-active")
    if previous_to != current_from:
        raise ContractError("rollback-order-invalid")
    return previous_to


def require_known_code(code_digest: str, known: tuple[str, ...]) -> str:
    """Reject a code digest that is absent from the registered set."""
    if len(code_digest) != 64 or path_has_direct_identifier(code_digest):
        raise ContractError("code-digest-invalid")
    if not known or any(len(item) != 64 for item in known):
        raise ContractError("code-registry-invalid")
    if code_digest not in known:
        raise ContractError("code-unknown")
    return code_digest


def version_diff(left: tuple[str, ...], right: tuple[str, ...]) -> dict[str, int]:
    """Count digest additions and removals between two releases."""
    sides = (left, right)
    if any(not side or len(side) > 100 for side in sides):
        raise ContractError("diff-set-invalid")
    if any(len(item) != 64 for side in sides for item in side):
        raise ContractError("code-digest-invalid")
    if set(left) == set(right):
        raise ContractError("diff-unchanged")
    return {"added": len(set(right) - set(left)), "removed": len(set(left) - set(right))}


def reference_integrity(refs: tuple[str, ...], known: tuple[str, ...]) -> int:
    """Count references only when every one is registered."""
    if not refs or len(refs) > 100:
        raise ContractError("reference-set-invalid")
    if len(set(refs)) != len(refs):
        raise ContractError("reference-duplicate")
    for ref in refs:
        require_known_code(ref, known)
    return len(refs)
