"""In-process review service.

This is not a deployed clinical service. It composes the existing gates:
configuration, resource structure, access policy, review, and audit. Any
failed gate returns before an approval event is appended.
"""
from __future__ import annotations

from pathlib import Path

from dataclasses import replace

from internal.audit.chain import AuditLog
from internal.audit.file import AuditFile
from internal.contract.config import RuntimeConfig, load_config
from internal.contract.domain import SuggestionDraft, ready_for_review
from internal.contract.errors import ContractError
from internal.contract.evidence import require_locatable
from internal.contract.fhir_gate import patient_reference
from internal.contract.idempotency import IdempotencyLog
from internal.contract.identity import require_context
from internal.contract.replay import ReplayGuard
from internal.contract.transaction import TransactionWatermark
from internal.contract.version import compatible
from internal.contract.write_intent import (
    ApprovalProof,
    EmergencyGrant,
    committed_replay,
    emergency_record,
)
from internal.hitl.audited import (
    append_actor_event,
    append_review_event,
    approve_and_audit,
    queue_and_audit,
)
from internal.hitl.review import approve_second
from internal.hitl.state.machine import Suggestion, TransitionError, transition
from internal.hitl.store import (
    ReviewStore,
    bind_review_ledgers,
    export_saved,
    observe_saved,
    project_commit,
    probe_startup,
    query_saved,
    replay_snapshot,
    restore_replays,
    store_records,
)


class ReviewService:
    """One tenant-scoped review process with one audit stream."""

    def __init__(self, config_payload: dict[str, object], audit_path: Path | None = None, store_path: Path | None = None) -> None:
        self.config: RuntimeConfig = load_config(config_payload)
        self.audit_file = None if audit_path is None else AuditFile(audit_path, str(config_payload["audit_stream"]))
        self.log = AuditLog(self.config.audit_stream) if self.audit_file is None else self.audit_file.log
        self.store = None if store_path is None else ReviewStore(
            store_path, self.config.tenant_id, self.config.campus_id, self.config.audit_stream,
        )
        if self.store is None:
            self.writes = IdempotencyLog()
            self._suggestions: dict[str, Suggestion] = {}
            self._emergencies: dict[str, Suggestion] = {}
            self._drafts: dict[str, SuggestionDraft] = {}
        else:
            self.writes = self.store.writes
            self._suggestions = self.store.suggestions
            self._emergencies = self.store.emergencies
            self._drafts = self.store.drafts
        self.replays = ReplayGuard()
        self._commit_sequences: dict[str, int] = {}
        self.transactions = TransactionWatermark(self.config.audit_stream)
        bind_review_ledgers(self, self.store)
        if self.store is not None:
            restore_replays(self.replays, self.store.replays, self._commit_sequences)
        records = store_records(self.store)
        self._consent_states = records["consents"]
        self._rule_states = records["rules"]
        self._rule_digests = records["rule_digests"]
        self._evidence_digests = records["evidence_digests"]
        self._actors = records["actors"]
        probe_startup(self, config_payload)

    def approve(self, draft: SuggestionDraft, resource: dict[str, object]) -> Suggestion:
        """Queue and approve one suggestion when every gate accepts it."""
        self._check_scope(draft)
        self._check_patient(draft, resource)
        self._check_resource_consent(draft, resource)
        decision = self.policies.evaluate({
            "tenant_id": self.config.tenant_id,
            "campus_id": self.config.campus_id,
            "purpose_code": str(draft.actor.get("purpose_code", "")),
            "policy_version": self.config.policy_version,
            "action": "review",
            "resource_id": str(resource.get("id", "")),
            "actor_id": str(draft.actor.get("actor_id", "")),
            "why_code": str(draft.actor.get("why_code", "")),
            "emergency": False,
            "fields": frozenset(),
            "consent_state": self._consent_states.get(draft.consent.consent_id, draft.consent.state),
        })
        if not decision.allowed:
            raise ContractError(decision.reason_codes[0])
        self.resources.require(self._resource_with_actor(resource, draft.actor))
        self._review_current(draft, draft.at_time)
        before = len(self.log.events)
        suggestion = queue_and_audit(
            draft, self.log, self.evidence, self.rules, self.consents, self.medications,
        )
        try:
            approved = approve_and_audit(
                suggestion, draft, self.log, self.evidence, self.rules, self.consents, self.medications,
            )
        except ContractError:
            if len(self.log.events) != before + 1:
                raise ContractError("review-audit-partial")
            raise
        self._suggestions[approved.suggestion_id] = approved
        self._drafts[approved.suggestion_id] = draft
        self._actors[str(draft.actor.get("actor_id", ""))] = {
            "actor_role": str(draft.actor.get("actor_role", "")),
            "purpose_code": str(draft.actor.get("purpose_code", "")),
        }
        approved.reviewer_roles[str(draft.actor.get("actor_id", ""))] = str(draft.actor.get("actor_role", ""))
        self._remember_state(self._consent_states, draft.consent.consent_id, draft.consent.state)
        self._remember_state(self._rule_states, draft.rule_pack.pack_id, draft.rule_pack.state)
        self._rule_digests.setdefault(draft.rule_pack.pack_id, draft.rule_pack.digest)
        for ref in draft.evidence:
            self._evidence_digests.setdefault(ref.evidence_id, ref.value_digest)
        self._flush()
        return approved

    def approve_independent(
        self,
        suggestion: Suggestion,
        draft: SuggestionDraft,
        second_actor_id: str,
        second_actor: dict[str, object] | None = None,
    ) -> Suggestion:
        """Complete dual review. The first reviewer cannot sign both steps."""
        actor = dict(draft.actor if second_actor is None else second_actor)
        actor["actor_id"] = second_actor_id
        require_context(actor)
        self._check_scope(draft)
        decision = self.policies.evaluate({
            "action": "second-review",
            "actor_id": str(actor.get("actor_id", "")),
            "campus_id": self.config.campus_id,
            "consent_state": self._consent_states.get(draft.consent.consent_id, draft.consent.state),
            "emergency": False,
            "fields": frozenset(),
            "policy_version": self.config.policy_version,
            "purpose_code": str(actor.get("purpose_code", "")),
            "resource_id": draft.suggestion_id,
            "tenant_id": self.config.tenant_id,
            "why_code": str(actor.get("why_code", "")),
        })
        if not decision.allowed:
            raise ContractError(decision.reason_codes[0])
        self._review_current(draft, draft.at_time)
        tracked = self._suggestion_for(suggestion.suggestion_id)
        if tracked.suggestion_id != draft.suggestion_id or tracked.content_digest != draft.content_digest:
            raise ContractError("review-digest-mismatch")
        approved = approve_second(
            tracked, draft, second_actor_id, self.evidence, self.rules, self.consents, self.medications,
        )
        self._actors[second_actor_id] = {
            "actor_role": str(actor["actor_role"]),
            "purpose_code": str(actor["purpose_code"]),
        }
        approved.reviewer_roles[second_actor_id] = str(actor["actor_role"])
        append_actor_event(
            self.log,
            suggestion_id=approved.suggestion_id,
            operation="approve-second",
            actor_id=second_actor_id,
            actor_role=str(actor["actor_role"]),
            purpose_code=str(actor["purpose_code"]),
            occurred_at=str(actor["occurred_at"]),
            why_code="second-review",
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=tracked.content_digest,
            consent_decision=self._consent_decision(approved.suggestion_id),
        )
        self._flush()
        return approved

    def commit_ordinary(
        self,
        suggestion: Suggestion,
        proof: ApprovalProof,
        at_time: str,
        expected_target_version: str,
    ) -> dict[str, str | bool]:
        """Commit only a fully approved suggestion with a matching proof."""
        if not isinstance(proof, ApprovalProof):
            raise ContractError("emergency-grant-not-approval")
        suggestion = self._suggestion_for(proof.suggestion_id)
        existing = self.writes.get(proof.proof_id)
        if existing is not None and existing.payload_digest != proof.content_digest:
            raise ContractError("idempotency-conflict")
        if existing is not None and existing.state == "committed":
            return committed_replay(
                self.credentials, proof, suggestion.suggestion_id, existing.actor_id, existing.why_code,
            )
        if existing is not None and existing.state == "unknown":
            raise ContractError("result-unknown")
        if suggestion.state != "APPROVED" or suggestion.submitted:
            raise ContractError("commit-state-invalid")
        if proof.content_digest != suggestion.content_digest:
            raise ContractError("approval-mismatch")
        if proof.suggestion_version != str(suggestion.version):
            raise ContractError("approval-mismatch")
        if proof.reviewer_id not in suggestion.reviewers:
            raise ContractError("approval-reviewer-not-recorded")
        actor = self._actors.get(proof.reviewer_id)
        recorded_role = suggestion.reviewer_roles.get(proof.reviewer_id, "")
        if actor is None or not recorded_role or recorded_role != actor.get("actor_role", ""):
            raise ContractError("approval-role-mismatch")
        draft = self._drafts.get(suggestion.suggestion_id)
        if draft is None:
            raise ContractError("review-draft-missing")
        if not compatible(draft.contract_version):
            raise ContractError("contract-version-incompatible")
        decision = self.policies.evaluate({
            "tenant_id": self.config.tenant_id,
            "campus_id": self.config.campus_id,
            "purpose_code": str(draft.actor.get("purpose_code", "")),
            "policy_version": self.config.policy_version,
            "action": "commit",
            "resource_id": suggestion.suggestion_id,
            "actor_id": str(draft.actor.get("actor_id", "")),
            "why_code": str(draft.actor.get("why_code", "")),
            "emergency": False,
            "fields": frozenset(),
            "consent_state": self._consent_states.get(draft.consent.consent_id, draft.consent.state),
        })
        if not decision.allowed:
            raise ContractError(decision.reason_codes[0])
        self._accept_once(suggestion.suggestion_id, proof.nonce)
        self._review_current(draft, at_time)
        result = self.credentials.commit(
            proof,
            suggestion.suggestion_id,
            proof.suggestion_version,
            suggestion.action,
            suggestion.content_digest,
            at_time,
            expected_target_version,
        )
        suggestion.write_intent_id = proof.proof_id
        try:
            transition(suggestion, "WRITEBACK_PENDING", proof.reviewer_id, reason="ordinary-commit")
            transition(suggestion, "WRITEBACK_COMMITTED", proof.reviewer_id, reason="ordinary-commit")
        except TransitionError as exc:
            suggestion.write_intent_id = None
            raise ContractError(str(exc)) from exc
        self.writes.begin(
            proof.proof_id,
            suggestion.content_digest,
            expected_target_version,
            proof.reviewer_id,
            proof.why_code,
        )
        self.transactions.begin(
            proof.proof_id,
            suggestion.content_digest,
            proof.reviewer_id,
            proof.why_code,
        )
        self.transactions.commit(proof.proof_id)
        self.writes.mark_committed(proof.proof_id)
        project_commit(self, draft, proof.reviewer_id, proof.why_code)
        append_actor_event(
            self.log,
            suggestion_id=suggestion.suggestion_id,
            operation="ordinary-commit",
            actor_id=proof.reviewer_id,
            actor_role=actor["actor_role"],
            purpose_code=actor["purpose_code"],
            occurred_at=at_time,
            why_code="ordinary-commit",
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=proof.content_digest,
            consent_decision=self._consent_decision(suggestion.suggestion_id),
        )
        self._flush()
        return result

    def record_emergency(
        self,
        draft: SuggestionDraft,
        resource: dict[str, object],
        grant: EmergencyGrant,
        at_time: str,
    ) -> dict[str, str | bool]:
        """Issue one emergency action and wait for a target receipt."""
        self._check_scope(draft)
        self._check_patient(draft, resource)
        self._check_resource_consent(draft, resource)
        self.resources.require(self._resource_with_actor(resource, draft.actor), emergency=True)
        if not isinstance(grant, EmergencyGrant):
            raise ContractError("approval-not-emergency-grant")
        self._emergency_policy(grant, "review")
        existing = self.writes.get(grant.grant_id)
        if existing is not None:
            raise ContractError("idempotency-conflict" if existing.state != "unknown" else "result-unknown")
        if grant.authorized_by != str(draft.actor.get("actor_id", "")):
            raise ContractError("emergency-authorizer-mismatch")
        if grant.content_digest != draft.content_digest:
            raise ContractError("emergency-mismatch")
        if not compatible(draft.contract_version):
            raise ContractError("contract-version-incompatible")
        self._accept_once(draft.suggestion_id, grant.nonce)
        self._review_current(draft, at_time, emergency=True)
        queued_version = "3"
        if grant.suggestion_version != queued_version:
            raise ContractError("emergency-version-mismatch")
        suggestion = queue_and_audit(
            draft, self.log, self.evidence, self.rules, self.consents, self.medications,
        )
        if str(suggestion.version) != queued_version:
            raise ContractError("emergency-version-mismatch")
        result = emergency_record(
            grant,
            draft.suggestion_id,
            grant.suggestion_version,
            draft.action,
            draft.content_digest,
            at_time,
        )
        self.writes.begin(
            grant.grant_id,
            grant.content_digest,
            "",
            grant.authorized_by,
            grant.reason_code,
        )
        self.transactions.begin(
            grant.grant_id,
            grant.content_digest,
            grant.authorized_by,
            grant.reason_code,
        )
        try:
            transition(
                suggestion,
                "EMERGENCY_OVERRIDE",
                grant.authorized_by,
                reason=grant.reason_code,
            )
            transition(
                suggestion,
                "EMERGENCY_PENDING_CONFIRMATION",
                grant.authorized_by,
                reason=grant.reason_code,
                emergency_nonce=grant.nonce,
            )
        except TransitionError as exc:
            raise ContractError(str(exc)) from exc
        append_review_event(self.log, draft, "emergency-pending", suggestion.suggestion_id)
        consent_state = self._consent_states.get(draft.consent.consent_id, draft.consent.state)
        append_actor_event(
            self.log,
            suggestion_id=suggestion.suggestion_id,
            operation="emergency-consent",
            actor_id=grant.authorized_by,
            actor_role=str(draft.actor.get("actor_role", "")),
            purpose_code=str(draft.actor.get("purpose_code", "")),
            occurred_at=at_time,
            why_code=grant.reason_code,
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=grant.content_digest,
            consent_decision=consent_state,
        )
        suggestion.emergency_grant_id = grant.grant_id
        self._emergencies[suggestion.suggestion_id] = suggestion
        self._drafts[suggestion.suggestion_id] = draft
        if suggestion.submitted or suggestion.state == "EMERGENCY_RECORDED":
            raise ContractError("emergency-cannot-enter-ordinary-commit")
        self._flush()
        return {
            "write_kind": "emergency",
            "committed": False,
            "execution_state": "emergency-pending-confirmation",
            "suggestion_id": result["suggestion_id"],
        }

    def confirm_emergency(self, grant: EmergencyGrant, receipt: str) -> dict[str, str | bool]:
        """Confirm an issued emergency action from an explicit target receipt."""
        tracked = self._emergencies.get(grant.suggestion_id)
        if tracked is not None and tracked.state == "POST_REVIEW_REQUIRED":
            if tracked.emergency_grant_id != grant.grant_id or tracked.emergency_nonce != grant.nonce:
                raise ContractError("emergency-grant-mismatch")
            return {
                "write_kind": "emergency",
                "committed": False,
                "execution_state": "post-review-required",
                "suggestion_id": tracked.suggestion_id,
            }
        suggestion = self._emergency_for(grant.suggestion_id, "EMERGENCY_PENDING_CONFIRMATION")
        if suggestion.emergency_grant_id != grant.grant_id or suggestion.emergency_nonce != grant.nonce:
            raise ContractError("emergency-grant-mismatch")
        draft = self._drafts.get(suggestion.suggestion_id)
        if draft is None:
            raise ContractError("review-draft-missing")
        self._emergency_policy(grant, "confirm")
        if receipt == "unknown":
            self.transactions.begin(
                grant.grant_id,
                grant.content_digest,
                grant.authorized_by,
                grant.reason_code,
            )
            self.writes.mark_unknown(grant.grant_id)
            self.transactions.mark_unknown(grant.grant_id)
            try:
                transition(suggestion, "EMERGENCY_UNKNOWN", grant.authorized_by, reason=grant.reason_code)
            except TransitionError as exc:
                raise ContractError(str(exc)) from exc
            append_actor_event(
                self.log,
                suggestion_id=suggestion.suggestion_id,
                operation="emergency-unknown",
                actor_id=grant.authorized_by,
                actor_role=str(draft.actor.get("actor_role", "")),
                purpose_code=str(draft.actor.get("purpose_code", "")),
                occurred_at=grant.expires_at,
                why_code=grant.reason_code,
                tenant_id=self.config.tenant_id,
                campus_id=self.config.campus_id,
                payload_digest=grant.content_digest,
                consent_decision=self._consent_decision(suggestion.suggestion_id),
            )
            self._flush()
            raise ContractError("result-unknown")
        if receipt != "executed":
            raise ContractError("emergency-receipt-invalid")
        try:
            transition(suggestion, "EMERGENCY_RECORDED", grant.authorized_by, reason=grant.reason_code)
            transition(suggestion, "POST_REVIEW_REQUIRED", grant.authorized_by, reason=grant.reason_code)
        except TransitionError as exc:
            raise ContractError(str(exc)) from exc
        self.transactions.begin(
            grant.grant_id,
            grant.content_digest,
            grant.authorized_by,
            grant.reason_code,
        )
        self.transactions.commit(grant.grant_id)
        self.writes.mark_committed(grant.grant_id)
        if suggestion.submitted:
            raise ContractError("emergency-cannot-enter-ordinary-commit")
        append_actor_event(
            self.log,
            suggestion_id=suggestion.suggestion_id,
            operation="emergency-post-review",
            actor_id=grant.authorized_by,
            actor_role=str(draft.actor.get("actor_role", "")),
            purpose_code=str(draft.actor.get("purpose_code", "")),
            occurred_at=grant.expires_at,
            why_code=grant.reason_code,
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=grant.content_digest,
            consent_decision=self._consent_decision(grant.suggestion_id),
        )
        self._flush()
        return {
            "write_kind": "emergency",
            "committed": False,
            "execution_state": "post-review-required",
            "suggestion_id": suggestion.suggestion_id,
        }

    def reconcile_emergency(
        self,
        reviewer_id: str,
        grant: EmergencyGrant,
        reviewer: dict[str, object] | None = None,
    ) -> dict[str, str | bool]:
        """Close an emergency fact only through an independent reviewer."""
        tracked = self._emergencies.get(grant.suggestion_id)
        if tracked is not None and tracked.state == "ARCHIVED":
            if tracked.emergency_grant_id != grant.grant_id:
                raise ContractError("emergency-grant-mismatch")
            return {
                "write_kind": "emergency",
                "committed": False,
                "execution_state": "archived",
                "suggestion_id": tracked.suggestion_id,
            }
        suggestion = self._emergency_for(grant.suggestion_id, "POST_REVIEW_REQUIRED")
        if suggestion.emergency_grant_id != grant.grant_id:
            raise ContractError("emergency-grant-mismatch")
        self._emergency_policy(grant, "reconcile")
        actor = self._closure_actor(reviewer_id, reviewer, "independent-post-review")
        if reviewer_id in {grant.authorized_by, "system"}:
            raise ContractError("post-reviewer-not-independent")
        try:
            transition(suggestion, "RECONCILIATION_CONFIRMED", reviewer_id, reason="independent-post-review")
            transition(suggestion, "ARCHIVED", reviewer_id, reason="independent-post-review")
        except TransitionError as exc:
            raise ContractError(str(exc)) from exc
        if suggestion.submitted or suggestion.state == "WRITEBACK_COMMITTED":
            raise ContractError("emergency-cannot-enter-ordinary-commit")
        append_actor_event(
            self.log,
            suggestion_id=suggestion.suggestion_id,
            operation="emergency-archived",
            actor_id=reviewer_id,
            actor_role=str(actor.actor_role),
            purpose_code=str(actor.purpose_code),
            occurred_at=str(actor.occurred_at),
            why_code="independent-post-review",
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=grant.content_digest,
            consent_decision=self._consent_decision(grant.suggestion_id),
        )
        self._flush()
        return {
            "write_kind": "emergency",
            "committed": False,
            "execution_state": "archived",
            "suggestion_id": suggestion.suggestion_id,
        }

    def correct_emergency(
        self,
        reviewer_id: str,
        grant: EmergencyGrant,
        reason: str,
        reviewer: dict[str, object] | None = None,
    ) -> dict[str, str | bool]:
        """Record a correction without deleting the original emergency fact."""
        tracked = self._emergencies.get(grant.suggestion_id)
        if tracked is not None and tracked.correction_recorded and tracked.state == "ARCHIVED":
            if tracked.emergency_grant_id != grant.grant_id:
                raise ContractError("emergency-grant-mismatch")
            return {
                "write_kind": "emergency",
                "committed": False,
                "execution_state": "corrected-archived",
                "suggestion_id": tracked.suggestion_id,
            }
        suggestion = self._emergency_for(grant.suggestion_id, "POST_REVIEW_REQUIRED")
        if suggestion.emergency_grant_id != grant.grant_id:
            raise ContractError("emergency-grant-mismatch")
        self._emergency_policy(grant, "correct")
        actor = self._closure_actor(reviewer_id, reviewer, reason)
        if reviewer_id in {grant.authorized_by, "system"}:
            raise ContractError("correction-reviewer-not-independent")
        if not reason or reason in {"unknown", "unspecified"}:
            raise ContractError("correction-reason-missing")
        original = tuple(suggestion.history)
        try:
            transition(suggestion, "CORRECTION_REQUIRED", reviewer_id, reason=reason)
            transition(suggestion, "RECONCILIATION_CONFIRMED", reviewer_id, reason=reason)
            transition(suggestion, "ARCHIVED", reviewer_id, reason=reason)
        except TransitionError as exc:
            raise ContractError(str(exc)) from exc
        prefixes = tuple(tuple(suggestion.history[:index]) for index in range(len(suggestion.history) + 1))
        if original not in prefixes:
            raise ContractError("emergency-history-erased")
        if suggestion.submitted:
            raise ContractError("emergency-cannot-enter-ordinary-commit")
        suggestion.correction_recorded = True
        append_actor_event(
            self.log,
            suggestion_id=suggestion.suggestion_id,
            operation="emergency-corrected",
            actor_id=reviewer_id,
            actor_role=str(actor.actor_role),
            purpose_code=str(actor.purpose_code),
            occurred_at=str(actor.occurred_at),
            why_code=reason,
            tenant_id=self.config.tenant_id,
            campus_id=self.config.campus_id,
            payload_digest=grant.content_digest,
            consent_decision=self._consent_decision(grant.suggestion_id),
        )
        self._flush()
        return {
            "write_kind": "emergency",
            "committed": False,
            "execution_state": "corrected-archived",
            "suggestion_id": suggestion.suggestion_id,
        }

    def emergency(self, suggestion_id: str) -> Suggestion:
        """Return one stored emergency suggestion."""
        try:
            return self._emergencies[suggestion_id]
        except KeyError as exc:
            raise ContractError("emergency-not-found") from exc

    def mark_commit_unknown(self, proof_id: str) -> None:
        """Keep an uncertain target receipt unknown. It cannot be retried."""
        self.writes.mark_unknown(proof_id)
        try:
            self.transactions.mark_unknown(proof_id)
        except ContractError as exc:
            if str(exc) not in {"transaction-already-committed", "transaction-key-unknown"}:
                raise
        self._flush()

    def withdraw_consent(self, consent_id: str) -> None:
        """Record withdrawal before a later ordinary commit."""
        if consent_id not in self._consent_states:
            raise ContractError("consent-not-tracked")
        self._consent_states[consent_id] = "withdrawn"
        self._flush()

    def retire_rule_pack(self, pack_id: str) -> None:
        """Record rule retirement before a later ordinary commit."""
        if pack_id not in self._rule_states:
            raise ContractError("rule-pack-not-tracked")
        self._rule_states[pack_id] = "retired"
        self._flush()
    def read_saved(self, kind: str, payload: dict[str, object]) -> tuple[dict[str, str], ...]:
        readers = {"export": export_saved, "query": query_saved, "stream": observe_saved}
        reader = readers.get(kind)
        if reader is None:
            raise ContractError("review-draft-missing")
        return reader(self, payload)
    def review_saved(self, suggestion_id: str, draft: SuggestionDraft, at_time: str) -> None:
        """Revalidate one saved suggestion against the current draft."""
        saved = self._drafts.get(suggestion_id)
        if saved is None:
            raise ContractError("review-draft-missing")
        self._review_current(draft, at_time)

    def _flush(self) -> None:
        if self.store is not None:
            self.store.flush(
                self._suggestions,
                self._emergencies,
                self.writes,
                self._consent_states,
                self._rule_states,
                self._rule_digests,
                self._evidence_digests,
                self._actors,
                self._drafts,
                replay_snapshot(self.replays),
                self.transactions,
                self.transactions.watermark(),
                self.policies,
                self.evidence,
                rule_ledger=self.rules,
                consent_ledger=self.consents,
                medication_ledger=self.medications, fhir_ledger=self.resources,
                write_ledger=self.credentials, projection_ledger=self.projections,
                query_ledger=self.queries, transfer_ledger=self.transfers,
                cache_ledger=self.caches, health_ledger=self.health,
            )

    def _accept_once(self, suggestion_id: str, nonce: str) -> None:
        """Advance one replay sequence only after the nonce is accepted."""
        sequence = self._commit_sequences.get(suggestion_id, 0) + 1
        self.replays.accept(suggestion_id, sequence, nonce)
        self._commit_sequences[suggestion_id] = sequence

    def _resource_with_actor(self, resource: dict[str, object], actor: dict[str, object]) -> dict[str, object]:
        """Copy actor responsibility onto the resource checked by the FHIR gate."""
        checked = dict(resource)
        checked["actorId"] = str(actor.get("actor_id", ""))
        checked["whyCode"] = str(actor.get("why_code", ""))
        return checked

    def _check_scope(self, draft: SuggestionDraft) -> None:
        if draft.actor.get("tenant_id") != self.config.tenant_id:
            raise ContractError("tenant-mismatch")
        if draft.actor.get("campus_id") != self.config.campus_id:
            raise ContractError("campus-mismatch")

    def _check_patient(self, draft: SuggestionDraft, resource: dict[str, object]) -> None:
        referenced = patient_reference(resource)
        if referenced and referenced != draft.patient_ref:
            raise ContractError("patient-reference-mismatch")
        if str(resource.get("purposeCode", "")) != str(draft.actor.get("purpose_code", "")):
            raise ContractError("purpose-mismatch")

    def _check_resource_consent(self, draft: SuggestionDraft, resource: dict[str, object]) -> None:
        marked = str(resource.get("consentState", "active"))
        tracked = self._consent_states.get(draft.consent.consent_id, draft.consent.state)
        if marked != tracked:
            raise ContractError("consent-state-mismatch")

    def _review_current(self, draft: SuggestionDraft, at_time: str, emergency: bool = False) -> None:
        current = self._consent_states.get(draft.consent.consent_id, draft.consent.state)
        rule_state = self._rule_states.get(draft.rule_pack.pack_id, draft.rule_pack.state)
        recorded_digest = self._rule_digests.get(draft.rule_pack.pack_id, draft.rule_pack.digest)
        if recorded_digest != draft.rule_pack.digest:
            raise ContractError("rule-digest-mismatch")
        for ref in draft.evidence:
            recorded = self._evidence_digests.get(ref.evidence_id)
            if recorded is not None and recorded != ref.value_digest:
                raise ContractError("evidence-digest-mismatch")
        saved = self._drafts.get(draft.suggestion_id)
        if saved is not None:
            saved_digests = {item.evidence_id: item.value_digest for item in saved.evidence}
            current_digests = {item.evidence_id: item.value_digest for item in draft.evidence}
            if saved_digests != current_digests:
                raise ContractError("evidence-digest-mismatch")
            if (saved.rule_decision, saved.model_decision) != (draft.rule_decision, draft.model_decision):
                raise ContractError("rule-decision-mismatch")
            if saved.medication_findings != draft.medication_findings:
                raise ContractError("medication-findings-mismatch")
            if saved.medication_facts != draft.medication_facts:
                raise ContractError("medication-facts-mismatch")
        require_locatable(draft.evidence)
        reviewed = replace(
            draft,
            at_time=at_time,
            consent=replace(draft.consent, state="active" if emergency else current),
            rule_pack=replace(draft.rule_pack, state=rule_state),
        )
        ready_for_review(reviewed, self.evidence, self.rules, self.consents, self.medications)
        if emergency and current != "active":
            if not draft.consent.consent_id or current not in {"withdrawn", "expired", "undetermined"}:
                raise ContractError("emergency-consent-untracked")

    def _remember_state(self, states: dict[str, str], key: str, incoming: str) -> None:
        current = states.get(key)
        if current not in {None, "active"} and incoming == "active":
            return
        states[key] = incoming

    def _emergency_policy(self, grant: EmergencyGrant, action: str) -> None:
        draft = self._drafts.get(grant.suggestion_id)
        consent_state = "active"
        purpose_code = "treatment"
        actor_id = grant.authorized_by
        why_code = grant.reason_code
        if not why_code:
            raise ContractError("emergency-reason-missing")
        if draft is not None:
            consent_state = self._consent_states.get(draft.consent.consent_id, draft.consent.state)
            purpose_code = str(draft.actor.get("purpose_code", ""))
            actor_id = str(draft.actor.get("actor_id", actor_id))
            why_code = str(draft.actor.get("why_code", why_code))
        fields = frozenset({"emergency-reason"}) if grant.reason_code else frozenset()
        decision = self.policies.evaluate({
            "tenant_id": self.config.tenant_id,
            "campus_id": self.config.campus_id,
            "purpose_code": purpose_code,
            "policy_version": self.config.policy_version,
            "action": action,
            "resource_id": grant.suggestion_id,
            "actor_id": actor_id,
            "why_code": why_code,
            "emergency": True,
            "fields": fields,
            "consent_state": consent_state,
        })
        if not decision.allowed:
            raise ContractError(decision.reason_codes[0])

    def _consent_decision(self, suggestion_id: str) -> str:
        draft = self._drafts.get(suggestion_id)
        if draft is None:
            return "unspecified"
        return self._consent_states.get(draft.consent.consent_id, draft.consent.state)

    def _closure_actor(self, reviewer_id: str, reviewer: dict[str, object] | None, why_code: str):
        payload = {
            "actor_role": "safety-reviewer",
            "tenant_id": self.config.tenant_id,
            "campus_id": self.config.campus_id,
            "purpose_code": "treatment",
            "why_code": why_code,
            "occurred_at": "2026-09-24T00:10:00Z",
        }
        if reviewer is not None:
            payload.update(reviewer)
        payload["actor_id"] = reviewer_id
        actor = require_context(payload)
        self._actors[reviewer_id] = {"actor_role": actor.actor_role, "purpose_code": actor.purpose_code}
        return actor

    def _suggestion_for(self, suggestion_id: str) -> Suggestion:
        try:
            return self._suggestions[suggestion_id]
        except KeyError as exc:
            raise ContractError("suggestion-not-tracked") from exc

    def _emergency_for(self, suggestion_id: str, expected_state: str) -> Suggestion:
        suggestion = self.emergency(suggestion_id)
        if suggestion.state != expected_state:
            raise ContractError("emergency-state-mismatch")
        return suggestion
