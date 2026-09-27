"""DICOM metadata index.

The index stores study, series, and instance digests. Pixel fields never
enter it.
"""
from __future__ import annotations

from internal.contract.errors import ContractError


_PIXEL_FIELDS = frozenset({"pixeldata", "pixels", "image"})


def dicom_index(study: str, series: str, instance: str, fields: tuple[str, ...]) -> dict[str, str]:
    """Return one metadata index entry without pixel content."""
    digests = (study, series, instance)
    if any(len(item) != 64 for item in digests):
        raise ContractError("dicom-digest-invalid")
    if len(set(digests)) != 3:
        raise ContractError("dicom-digest-reused")
    if any(field.lower() in _PIXEL_FIELDS for field in fields):
        raise ContractError("dicom-pixel-forbidden")
    if not fields:
        raise ContractError("dicom-fields-missing")
    return {"instance": instance, "series": series, "study": study}


def model_input(fields: tuple[str, ...], digest: str) -> str:
    """Allow a model to see a metadata digest, never pixel content."""
    if not fields or any(field.lower() in _PIXEL_FIELDS for field in fields):
        raise ContractError("model-pixel-forbidden")
    if len(digest) != 64:
        raise ContractError("model-digest-invalid")
    return digest


def object_checksum(declared: str, stored: str, body: str) -> str:
    """Accept an object only when both digests match and no body is kept."""
    pair = (declared, stored)
    if any(len(item) != 64 for item in pair):
        raise ContractError("object-digest-invalid")
    if declared != stored:
        raise ContractError("object-digest-mismatch")
    if body != "":
        raise ContractError("object-body-forbidden")
    return stored


def study_token(accession: str, digest: str) -> dict[str, str]:
    """Replace an accession with a digest token."""
    if accession == "" or accession == digest:
        raise ContractError("study-accession-forbidden")
    if len(digest) != 64:
        raise ContractError("study-token-invalid")
    if any(char.isdigit() for char in accession):
        raise ContractError("study-accession-forbidden")
    return {"accession_kept": "false", "token": digest}


_SYNTAXES = frozenset({"1.2.840.10008.1.2.1", "1.2.840.10008.1.2.4.90"})


def transfer_syntax(uid: str) -> str:
    """Accept one declared transfer syntax and reject every other UID."""
    if uid not in _SYNTAXES:
        raise ContractError("syntax-not-allowed")
    return uid


def image_access(role: str, action: str, digest: str) -> dict[str, str]:
    """Record one image access without study text or pixels."""
    if role not in {"reviewer", "ingest"} or action not in {"view", "deny"}:
        raise ContractError("image-access-invalid")
    if len(digest) != 64:
        raise ContractError("image-access-digest-invalid")
    return {"action": action, "digest": digest, "role": role}


def cross_campus_object(size_bytes: int, same_campus: bool) -> str:
    """Reject a large object before it can leave its campus."""
    if size_bytes < 1:
        raise ContractError("object-size-invalid")
    if not isinstance(same_campus, bool):
        raise ContractError("object-size-invalid")
    if size_bytes > 1_000_000 and not same_campus:
        raise ContractError("object-cross-campus-forbidden")
    return "local" if same_campus else "metadata-only"


def synthetic_fixture(synthetic: bool, fields: tuple[str, ...], digest: str) -> dict[str, object]:
    """Accept one synthetic fixture header and reject pixel content."""
    if synthetic is not True:
        raise ContractError("fixture-not-synthetic")
    if not fields or any(field.lower() in _PIXEL_FIELDS for field in fields):
        raise ContractError("fixture-pixel-forbidden")
    if len(digest) != 64:
        raise ContractError("fixture-digest-invalid")
    return {"digest": digest, "fields": fields, "synthetic": True}


def storage_watermark(used: int, incoming: int, capacity: int) -> int:
    """Return the next used total, or reject an object that would overflow."""
    if used < 0 or incoming < 1 or capacity < 1:
        raise ContractError("storage-input-invalid")
    if used > capacity:
        raise ContractError("storage-watermark-corrupt")
    nxt = used + incoming
    if nxt > capacity:
        raise ContractError("storage-watermark-full")
    return nxt


def integrity_sample(declared: tuple[str, ...], sampled: tuple[str, ...]) -> int:
    """Check one sample without reading object bodies."""
    if not sampled or len(sampled) > len(declared) or len(declared) > 100:
        raise ContractError("sample-set-invalid")
    if any(len(item) != 64 for item in (*declared, *sampled)):
        raise ContractError("sample-digest-invalid")
    if any(item not in declared for item in sampled):
        raise ContractError("sample-mismatch")
    return len(sampled)
