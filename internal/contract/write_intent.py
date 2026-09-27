"""Write intents for ordinary and emergency actions.

An approval proof can create an ordinary commit. An emergency grant can only
record an emergency fact. The two credentials are not interchangeable.
"""
from __future__ import annotations

from dataclasses import dataclass

from internal.contract.errors import ContractError
from internal.contract.privacy import path_has_direct_identifier
from internal.contract.version import compatible


@dataclass(frozen=True)
class ApprovalProof:
    proof_id: str
    suggestion_id: str
    suggestion_version: str
    reviewer_id: str
    target_action: str
    content_digest: str
    nonce: str
    issued_at: str
    expires_at: str
    why_code: str = "treatment-review"
    contract_version: str = "1.0"


@dataclass(frozen=True)
class EmergencyGrant:
    grant_id: str
    suggestion_id: str
    suggestion_version: str
    authorized_by: str
    target_action: str
    reason_code: str
    content_digest: str
    nonce: str
    issued_at: str
    expires_at: str
    contract_version: str = "1.0"


def _within(issued_at: str, expires_at: str, at_time: str) -> None:
    if not issued_at or not expires_at or not at_time:
        raise ContractError("write-window-incomplete")
    if at_time < issued_at or at_time >= expires_at:
        raise ContractError("write-window-closed")


def _matches(credential_id: str, version: str, action: str, digest: str, nonce: str) -> None:
    if not all((credential_id, version, action, digest, nonce)):
        raise ContractError("write-credential-incomplete")
    if path_has_direct_identifier(credential_id) or path_has_direct_identifier(action):
        raise ContractError("write-identifier-forbidden")
    if len(digest) != 64:
        raise ContractError("write-digest-invalid")


def ordinary_commit(
    proof: ApprovalProof,
    suggestion_id: str,
    suggestion_version: str,
    target_action: str,
    content_digest: str,
    at_time: str,
    expected_target_version: str,
) -> dict[str, str | bool]:
    """Commit only when the proof matches this exact suggestion."""
    if not isinstance(proof, ApprovalProof):
        raise ContractError("emergency-grant-not-approval")
    if proof.reviewer_id in {"", "system"}:
        raise ContractError("approval-missing")
    if proof.why_code in {"", "unknown", "unspecified"}:
        raise ContractError("write-why-missing")
    if path_has_direct_identifier(proof.why_code):
        raise ContractError("write-identifier-forbidden")
    if not expected_target_version:
        raise ContractError("target-version-missing")
    if not compatible(proof.contract_version):
        raise ContractError("write-version-incompatible")
    _matches(proof.proof_id, proof.suggestion_version, proof.target_action, proof.content_digest, proof.nonce)
    _within(proof.issued_at, proof.expires_at, at_time)
    if (
        proof.suggestion_id != suggestion_id
        or proof.suggestion_version != suggestion_version
        or proof.target_action != target_action
        or proof.content_digest != content_digest
    ):
        raise ContractError("approval-mismatch")
    return {
        "write_kind": "ordinary",
        "committed": True,
        "suggestion_id": suggestion_id,
        "target_version": expected_target_version,
    }


def emergency_record(
    grant: EmergencyGrant,
    suggestion_id: str,
    suggestion_version: str,
    target_action: str,
    content_digest: str,
    at_time: str,
) -> dict[str, str | bool]:
    """Record one emergency fact without creating an ordinary commit."""
    if not isinstance(grant, EmergencyGrant):
        raise ContractError("approval-not-emergency-grant")
    if grant.authorized_by in {"", "system"} or grant.reason_code in {"", "unknown"}:
        raise ContractError("emergency-context-incomplete")
    if not compatible(grant.contract_version):
        raise ContractError("write-version-incompatible")
    _matches(grant.grant_id, grant.suggestion_version, grant.target_action, grant.content_digest, grant.nonce)
    _within(grant.issued_at, grant.expires_at, at_time)
    if (
        grant.suggestion_id != suggestion_id
        or grant.suggestion_version != suggestion_version
        or grant.target_action != target_action
        or grant.content_digest != content_digest
    ):
        raise ContractError("emergency-mismatch")
    return {
        "write_kind": "emergency",
        "committed": False,
        "execution_state": "emergency-recorded",
        "suggestion_id": suggestion_id,
    }


class WriteLedger:
    """Remember one credential so a later actor cannot reuse it silently."""

    def __init__(self) -> None:
        self._records: dict[str, tuple[str, str]] = {}

    def commit(
        self,
        proof: ApprovalProof,
        suggestion_id: str,
        suggestion_version: str,
        target_action: str,
        content_digest: str,
        at_time: str,
        expected_target_version: str,
    ) -> dict[str, str | bool]:
        result = ordinary_commit(
            proof,
            suggestion_id,
            suggestion_version,
            target_action,
            content_digest,
            at_time,
            expected_target_version,
        )
        recorded = self._records.get(proof.proof_id)
        incoming = (proof.reviewer_id, proof.why_code)
        if recorded is not None and recorded != incoming:
            raise ContractError("write-responsibility-mismatch")
        self._records.setdefault(proof.proof_id, incoming)
        return result

    def restore(self, proof_id: str, reviewer_id: str, why_code: str) -> None:
        """Restore one accepted proof without treating it as a new commit."""
        missing_reviewer = not proof_id or not reviewer_id
        if missing_reviewer:
            raise ContractError("write-credential-incomplete")
        if why_code in {"", "unknown", "unspecified"}:
            raise ContractError("write-why-missing")
        self._records[proof_id] = (reviewer_id, why_code)

    def records(self) -> tuple[tuple[str, tuple[str, str]], ...]:
        """Return stored write credentials in stable order."""
        return tuple(sorted(self._records.items()))


def committed_replay(
    ledger: WriteLedger,
    proof: ApprovalProof,
    suggestion_id: str,
    actor_id: str,
    why_code: str,
) -> dict[str, str | bool]:
    """Return the original commit, unless a different reviewer reuses the proof."""
    recorded = ledger._records.get(proof.proof_id, (actor_id, why_code))
    if recorded != (proof.reviewer_id, proof.why_code):
        raise ContractError("write-responsibility-mismatch")
    return {
        "committed": True,
        "execution_state": "writeback-committed",
        "suggestion_id": suggestion_id,
        "write_kind": "ordinary",
    }


def issue_proof(first: str, second: str, digest: str) -> dict[str, str]:
    """Issue one proof only after two distinct reviewers sign one digest."""
    signers = (first, second)
    if any(item == "" or item == "system" for item in signers) or first == second:
        raise ContractError("proof-signers-invalid")
    if len(digest) != 64:
        raise ContractError("proof-digest-invalid")
    return {"state": "issued", "digest": digest, "signers": f"{first}|{second}"}


def bind_proof(proof_ref: str, subject_ref: str, proof_action: str, action: str, proof_version: str, version: str) -> str:
    """Bind a proof to one subject reference, action, and version."""
    bound = (proof_ref, subject_ref, proof_action, action, proof_version, version)
    if any(item == "" for item in bound):
        raise ContractError("proof-binding-incomplete")
    if path_has_direct_identifier(proof_ref) or path_has_direct_identifier(subject_ref):
        raise ContractError("proof-patient-forbidden")
    if proof_ref != subject_ref or proof_action != action or proof_version != version:
        raise ContractError("proof-binding-mismatch")
    return "bound"


class NonceLedger:
    """Accept each nonce once."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def use(self, nonce: str) -> str:
        if len(nonce) != 64:
            raise ContractError("nonce-invalid")
        if nonce in self._seen:
            raise ContractError("nonce-reused")
        self._seen.add(nonce)
        return "used"


def proof_expiry(issued_at: str, expires_at: str, at_time: str) -> str:
    """Accept a proof only before its expiry instant."""
    if issued_at == "" or expires_at == "" or at_time == "":
        raise ContractError("proof-expiry-incomplete")
    if expires_at <= issued_at:
        raise ContractError("proof-expiry-invalid")
    if at_time < issued_at or at_time >= expires_at:
        raise ContractError("proof-expired")
    return "active"


def ordinary_intent(kind: str, proof_kind: str) -> str:
    """Accept only an ordinary proof for an ordinary write intent."""
    if kind not in {"ordinary", "emergency"} or proof_kind not in {"approval", "grant"}:
        raise ContractError("intent-kind-invalid")
    if kind != "ordinary" or proof_kind != "approval":
        raise ContractError("intent-not-ordinary")
    return "ordinary"


def target_version_conflict(proof_version: str, target_version: str) -> str:
    """Accept a write only when the proof names the current target version."""
    if proof_version == "" or target_version == "":
        raise ContractError("target-version-incomplete")
    if proof_version != target_version:
        raise ContractError("target-version-conflict")
    return proof_version


def unknown_receipt(sent: str, receipt: str) -> str:
    """Reconcile only a committed receipt. Unknown stays retryable."""
    if sent not in {"committed", "unknown"} or receipt not in {"committed", "unknown", "rejected"}:
        raise ContractError("receipt-state-invalid")
    if sent == "unknown" or receipt == "unknown":
        raise ContractError("receipt-result-unknown")
    if sent != receipt:
        raise ContractError("receipt-mismatch")
    return receipt
