"""Reloadable register for review state and write results.

The file stores identifiers, states, and digests. It does not store clinical
text. A corrupt file fails closed instead of rebuilding a partial register.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from internal.contract.consent import Consent, ConsentLedger
from internal.contract.cache import CacheLedger
from internal.contract.domain import SuggestionDraft
from internal.contract.errors import ContractError
from internal.contract.evidence import EvidenceLedger, EvidenceRef
from internal.contract.fhir_gate import FhirLedger
from internal.contract.health import HealthLedger
from internal.contract.idempotency import IdempotencyLog
from internal.contract.medication import MedicationLedger
from internal.contract.policy import PolicyLedger
from internal.contract.privacy import ProjectionLedger
from internal.contract.query import QueryLedger
from internal.contract.transfer import TransferLedger
from internal.contract.rules import RuleLedger, RulePack
from internal.contract.stream import EventStream
from internal.contract.transaction import TransactionWatermark
from internal.contract.write_intent import WriteLedger
from internal.hitl.state.machine import Suggestion, TransitionError


def store_records(store: ReviewStore | None) -> dict[str, dict]:
    """Return the persisted maps, or empty maps for a memory-only service."""
    if store is None:
        return {
            "actors": {},
            "consents": {},
            "evidence_digests": {},
            "rule_digests": {},
            "rules": {},
        }
    return {
        "actors": store.actors,
        "consents": store.consents,
        "evidence_digests": store.evidence_digests,
        "rule_digests": store.rule_digests,
        "rules": store.rules,
    }


def restore_replays(guard, replays: dict[str, dict[str, object]], sequences: dict[str, int]) -> None:
    """Copy stored replay rows back into one guard."""
    for suggestion_id, replay in replays.items():
        guard._next[suggestion_id] = int(replay["next_sequence"])
        guard._nonces[suggestion_id] = set(replay["nonces"])
        sequences[suggestion_id] = int(replay["next_sequence"]) - 1
        for row in replay.get("responsibilities", []):
            guard._actors[(suggestion_id, int(row["sequence"]))] = (
                str(row["actor_id"]),
                str(row["why_code"]),
            )


def optional_lists(payload: dict[str, object], names: tuple[str, ...]) -> tuple[list, ...]:
    """Return optional stored lists, using an empty list when a name is absent."""
    loaded = []
    for name in names:
        value = payload.get(name, [])
        loaded.append([] if value is None else value)
    return tuple(loaded)


def ledger_rows(ledger) -> tuple:
    """Return stored ledger rows, or none when the caller has no ledger."""
    if ledger is None:
        return ()
    return ledger.records()


def query_saved(service, payload: dict[str, object]) -> tuple[dict[str, str], ...]:
    """Return saved suggestion states after the query ledger accepts the actor."""
    query = service.queries.prepare(payload)
    if query.tenant_id != service.config.tenant_id or query.campus_id != service.config.campus_id:
        raise ContractError("query-scope-incomplete")
    rows = []
    for suggestion in sorted(service._suggestions.values(), key=lambda item: item.suggestion_id):
        selected = {
            "action": suggestion.action,
            "state": suggestion.state,
            "suggestion_id": suggestion.suggestion_id,
        }
        visible = {field: selected[field] for field in sorted(query.requested_fields) if field in selected}
        rows.append(visible)
    service.caches.key(
        query.tenant_id,
        query.campus_id,
        query.resource_type,
        service.config.policy_version,
        tuple(sorted(query.requested_fields)),
        "active",
        query.actor_id,
        query.why_code,
    )
    service._flush()
    return tuple(rows)


def export_saved(service, payload: dict[str, object]) -> tuple[dict[str, str], ...]:
    """Export saved suggestion states after the transfer ledger accepts the actor."""
    requested = payload.get("fields", ())
    fields = set(requested) if isinstance(requested, (list, tuple, set, frozenset)) else set()
    accepted = service.transfers.check(
        str(payload.get("direction", "")),
        fields,
        str(payload.get("consent_state", "active")),
        service.config.tenant_id,
        service.config.campus_id,
        str(payload.get("purpose_code", "")),
        str(payload.get("actor_id", "")),
        str(payload.get("why_code", "")),
    )
    rows = []
    for suggestion in sorted(service._suggestions.values(), key=lambda item: item.suggestion_id):
        available = {"status": suggestion.state}
        rows.append({field: available[field] for field in sorted(accepted) if field in available})
    service._flush()
    return tuple(rows)


def project_commit(service, draft: SuggestionDraft, reviewer_id: str, why_code: str) -> None:
    """Project one committed suggestion without returning direct identifiers."""
    record = {
        "action": draft.action,
        "content_digest": draft.content_digest,
        "suggestion_id": draft.suggestion_id,
    }
    service.projections.project(
        record,
        frozenset(record),
        service._consent_states.get(draft.consent.consent_id, draft.consent.state),
        reviewer_id,
        why_code,
    )


def observe_saved(service, payload: dict[str, object]) -> tuple[dict[str, str], ...]:
    """Observe one saved event after the stream ledger accepts the actor."""
    try:
        sequence = int(payload.get("sequence", 0))
    except (TypeError, ValueError) as exc:
        raise ContractError("stream-event-invalid") from exc
    event = service.stream.observe(
        sequence,
        str(payload.get("event_id", "")),
        service.transactions.watermark(),
        str(payload.get("consent_state", "active")),
        str(payload.get("actor_id", "")),
        str(payload.get("why_code", "")),
    )
    service._flush()
    return ({"event_id": event.event_id, "late": str(event.late).lower(), "sequence": str(event.sequence)},)


def probe_startup(service, payload: dict[str, object]) -> None:
    """Probe startup after stored health responsibility has been restored."""
    checked = dict(payload)
    checked.setdefault("actor_id", "actor-synthetic")
    checked.setdefault("why_code", "startup-check")
    service.health.probe(checked)
    service._flush()


def bind_review_ledgers(service, store) -> None:
    """Attach fresh ledgers, then replace them from a store when one exists."""
    service.health = HealthLedger()
    service.policies = review_policy()
    service.evidence = EvidenceLedger()
    service.rules, service.consents, service.medications = RuleLedger(), ConsentLedger(), MedicationLedger()
    service.resources, service.credentials = FhirLedger(), WriteLedger()
    service.projections = ProjectionLedger()
    service.queries = QueryLedger()
    service.transfers = TransferLedger()
    service.caches = CacheLedger()
    service.stream = EventStream(service.config.audit_stream)
    if store is None:
        return
    service.transactions = store.transactions
    service.policies = store.policies
    service.evidence = store.evidence
    service.rules = store.rules_ledger
    service.consents = store.consent_ledger
    service.medications, service.resources = store.medication_ledger, store.fhir_ledger
    service.credentials = store.write_ledger
    service.projections = store.projection_ledger
    service.queries = store.query_ledger
    service.transfers = store.transfer_ledger
    service.caches = store.cache_ledger
    service.health = store.health_ledger
    service.stream = store.event_stream
    service.transactions._committed = max(service.transactions.watermark(), store.transaction_watermark)


def review_policy() -> PolicyLedger:
    """Return one policy ledger for a review service."""
    return PolicyLedger()


def replay_snapshot(guard) -> dict[str, dict[str, object]]:
    """Copy replay state without exposing the guard's internal layout."""
    return {
        suggestion_id: {
            "next_sequence": sequence,
            "nonces": set(guard._nonces.get(suggestion_id, set())),
            "responsibilities": [
                {"actor_id": actor, "sequence": item, "why_code": reason}
                for (stream_id, item), (actor, reason) in sorted(guard._actors.items())
                if stream_id == suggestion_id
            ],
        }
        for suggestion_id, sequence in guard._next.items()
    }


class ReviewStore:
    """One JSON register. Callers flush only after a successful transition."""

    def __init__(self, path: Path, tenant_id: str, campus_id: str, stream_id: str = "review-store") -> None:
        if not tenant_id or not campus_id:
            raise ContractError("review-store-scope-invalid")
        self.path = path
        self.tenant_id = tenant_id
        self.campus_id = campus_id
        self.suggestions: dict[str, Suggestion] = {}
        self.emergencies: dict[str, Suggestion] = {}
        self.writes = IdempotencyLog()
        self.consents: dict[str, str] = {}
        self.rules: dict[str, str] = {}
        self.rule_digests: dict[str, str] = {}
        self.evidence_digests: dict[str, str] = {}
        self.actors: dict[str, dict[str, str]] = {}
        self.drafts: dict[str, SuggestionDraft] = {}
        self.replays: dict[str, dict[str, object]] = {}
        self.transactions = TransactionWatermark("review-store")
        self.policies = review_policy()
        self.evidence = EvidenceLedger()
        self.rules_ledger = RuleLedger()
        self.consent_ledger = ConsentLedger()
        self.medication_ledger = MedicationLedger()
        self.fhir_ledger = FhirLedger()
        self.write_ledger = WriteLedger()
        self.projection_ledger = ProjectionLedger()
        self.query_ledger = QueryLedger()
        self.transfer_ledger = TransferLedger()
        self.cache_ledger = CacheLedger()
        self.health_ledger = HealthLedger()
        self.event_stream = EventStream(stream_id)
        self.transaction_watermark = 0
        self.load()

    def flush(
        self,
        suggestions: dict[str, Suggestion],
        emergencies: dict[str, Suggestion],
        writes: IdempotencyLog,
        consents: dict[str, str],
        rules: dict[str, str],
        rule_digests: dict[str, str],
        evidence_digests: dict[str, str],
        actors: dict[str, dict[str, str]],
        drafts: dict[str, SuggestionDraft],
        replays: dict[str, dict[str, object]],
        transactions: TransactionWatermark | None = None,
        transaction_watermark: int = 0,
        policies: PolicyLedger | None = None,
        evidence: EvidenceLedger | None = None,
        rule_ledger: RuleLedger | None = None,
        consent_ledger: ConsentLedger | None = None,
        medication_ledger: MedicationLedger | None = None,
        fhir_ledger: FhirLedger | None = None,
        write_ledger: WriteLedger | None = None,
        projection_ledger: ProjectionLedger | None = None,
        query_ledger: QueryLedger | None = None,
        transfer_ledger: TransferLedger | None = None,
        cache_ledger: CacheLedger | None = None,
        health_ledger: HealthLedger | None = None,
    ) -> None:
        transaction_rows = ledger_rows(transactions)
        policy_rows = ledger_rows(policies)
        evidence_rows = ledger_rows(evidence)
        rule_rows = ledger_rows(rule_ledger)
        consent_rows = ledger_rows(consent_ledger)
        medication_rows = ledger_rows(medication_ledger)
        fhir_rows = ledger_rows(fhir_ledger)
        release_rows = ledger_rows(None if fhir_ledger is None else fhir_ledger.releases)
        profile_rows = ledger_rows(None if fhir_ledger is None else fhir_ledger.profiles)
        credential_rows = ledger_rows(write_ledger)
        projection_rows = ledger_rows(projection_ledger)
        query_rows = ledger_rows(query_ledger)
        transfer_rows = ledger_rows(transfer_ledger)
        cache_rows = ledger_rows(cache_ledger)
        health_rows = ledger_rows(health_ledger)
        stream_rows = self.event_stream.records()
        payload = {
            "campus_id": self.campus_id,
            "actors": [
                {"actor_id": key, "actor_role": value["actor_role"], "purpose_code": value["purpose_code"]}
                for key, value in sorted(actors.items())
            ],
            "consent_authorizations": [
                {"actor_id": value[0], "consent_id": key, "why_code": value[1]}
                for key, value in consent_rows
            ],
            "consents": [{"consent_id": key, "state": value} for key, value in sorted(consents.items())],
            "drafts": [self._dump_draft(item) for item in drafts.values()],
            "emergencies": [self._dump(item) for item in emergencies.values()],
            "rules": [{"pack_id": key, "state": value} for key, value in sorted(rules.items())],
            "replays": [
                {
                    "next_sequence": value["next_sequence"],
                    "nonces": sorted(value["nonces"]),
                    "responsibilities": value.get("responsibilities", []),
                    "suggestion_id": key,
                }
                for key, value in sorted(replays.items())
            ],
            "evidence_graphs": [
                {
                    "actor_id": value[0],
                    "evidence_ids": list(key),
                    "why_code": value[1],
                }
                for key, value in evidence_rows
            ],
            "evidence_digests": [{"digest": value, "evidence_id": key} for key, value in sorted(evidence_digests.items())],
            "fhir_resources": [
                {"actor_id": value[0], "resource_id": key, "why_code": value[1]}
                for key, value in fhir_rows
            ],
            "profile_declarations": [
                {
                    "actor_id": value[0],
                    "declared": key,
                    "why_code": value[1],
                }
                for key, value in profile_rows
            ],
            "terminology_releases": [
                {"active": True, "actor_id": value[0], "system_url": key, "why_code": value[1]}
                for key, value in release_rows
            ],
            "write_credentials": [
                {"proof_id": key, "reviewer_id": value[0], "why_code": value[1]}
                for key, value in credential_rows
            ],
            "projections": [
                {"actor_id": value[0], "field_count": len(key), "fields": list(key), "why_code": value[1]}
                for key, value in projection_rows
            ],
            "queries": [
                {
                    "actor_id": value[0],
                    "campus_id": key[1],
                    "purpose_code": key[2],
                    "resource_type": key[3],
                    "tenant_id": key[0],
                    "why_code": value[1],
                }
                for key, value in query_rows
            ],
            "transfers": [
                {
                    "actor_id": value[0],
                    "campus_id": key[2],
                    "direction": key[0],
                    "purpose_code": key[3],
                    "tenant_id": key[1],
                    "why_code": value[1],
                }
                for key, value in transfer_rows
            ],
            "caches": [
                {
                    "actor_id": value[0],
                    "campus_id": key[1],
                    "policy_version": key[3],
                    "resource_type": key[2],
                    "tenant_id": key[0],
                    "why_code": value[1],
                }
                for key, value in cache_rows
            ],
            "health_checks": [
                {
                    "actor_id": value[0],
                    "campus_id": key[1],
                    "tenant_id": key[0],
                    "why_code": value[1],
                }
                for key, value in health_rows
            ],
            "stream_events": [
                {
                    "actor_id": row[3],
                    "event_id": row[1],
                    "late": row[2],
                    "sequence": row[0],
                    "why_code": row[4],
                }
                for row in stream_rows
            ],
            "medication_decisions": [
                {
                    "actor_id": value[0],
                    "findings": [{"name": name, "present": present} for name, present in key],
                    "why_code": value[1],
                }
                for key, value in medication_rows
            ],
            "rule_admissions": [
                {
                    "actor_id": value[0],
                    "pack_id": key,
                    "why_code": value[1],
                }
                for key, value in rule_rows
            ],
            "rule_digests": [
                {"digest": value, "pack_id": key}
                for key, value in sorted(rule_digests.items(), key=lambda item: item[0])
            ],
            "suggestions": [self._dump(item) for item in suggestions.values()],
            "tenant_id": self.tenant_id,
            "policies": [
                {
                    "action": key[3],
                    "actor_id": value[0],
                    "campus_id": key[1],
                    "purpose_code": key[2],
                    "resource_id": key[4],
                    "tenant_id": key[0],
                    "why_code": value[1],
                }
                for key, value in policy_rows
            ],
            "transaction_watermark": transaction_watermark,
            "transactions": [
                {
                    "actor_id": item.actor_id,
                    "key": item.key,
                    "payload_digest": item.payload_digest,
                    "sequence": item.sequence,
                    "state": item.state,
                    "why_code": item.why_code,
                }
                for item in transaction_rows
            ],
            "writes": [
                {
                    "actor_id": item.actor_id,
                    "key": item.key,
                    "payload_digest": item.payload_digest,
                    "state": item.state,
                    "target_version": item.target_version,
                    "why_code": item.why_code,
                }
                for item in writes._records.values()
            ],
        }
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        stored = {"body": body, "digest": hashlib.sha256(body.encode("utf-8")).hexdigest()}
        self.path.write_text(json.dumps(stored, sort_keys=True), encoding="utf-8")

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
            body = stored["body"]
            digest = stored["digest"]
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != digest:
                raise ContractError("review-store-tampered")
            payload = json.loads(body)
            if payload["tenant_id"] != self.tenant_id or payload["campus_id"] != self.campus_id:
                raise ContractError("review-store-scope-mismatch")
            suggestions = payload["suggestions"]
            emergencies = payload["emergencies"]
            writes = payload["writes"]
            consents = payload["consents"]
            rules = payload["rules"]
            rule_digests = payload["rule_digests"]
            evidence_digests = payload["evidence_digests"]
            actors = payload["actors"]
            drafts = payload["drafts"]
            (
                replays, transactions, policies, evidence_graphs, rule_admissions,
                consent_authorizations, medication_decisions, fhir_resources,
                profile_declarations, terminology_releases, write_credentials,
                projections, queries, transfers, caches, health_checks, stream_events,
            ) = optional_lists(payload, (
                "replays", "transactions", "policies", "evidence_graphs", "rule_admissions",
                "consent_authorizations", "medication_decisions", "fhir_resources",
                "profile_declarations", "terminology_releases", "write_credentials",
                "projections", "queries", "transfers", "caches", "health_checks", "stream_events",
            ))
            watermark = int(payload.get("transaction_watermark", 0))
        except ContractError:
            raise
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ContractError("review-store-corrupt") from exc
        self.suggestions = {item["suggestion_id"]: self._restore(item) for item in suggestions}
        self.emergencies = {item["suggestion_id"]: self._restore(item) for item in emergencies}
        for item in writes:
            self.writes.restore(
                str(item["key"]),
                str(item["payload_digest"]),
                str(item["state"]),
                str(item.get("target_version", "")),
                str(item.get("actor_id", "actor-synthetic")),
                str(item.get("why_code", "treatment-review")),
            )
        self.consents = {str(item["consent_id"]): str(item["state"]) for item in consents}
        self.rules = {str(item["pack_id"]): str(item["state"]) for item in rules}
        self.rule_digests = {str(item["pack_id"]): str(item["digest"]) for item in rule_digests}
        self.evidence_digests = {str(item["evidence_id"]): str(item["digest"]) for item in evidence_digests}
        self.actors = {
            str(item["actor_id"]): {
                "actor_role": str(item["actor_role"]),
                "purpose_code": str(item["purpose_code"]),
            }
            for item in actors
        }
        self.drafts = {item.suggestion_id: item for item in (self._restore_draft(item) for item in drafts)}
        self.replays = {
            str(item["suggestion_id"]): {
                "next_sequence": int(item["next_sequence"]),
                "nonces": {str(nonce) for nonce in item["nonces"]},
                "responsibilities": [
                    {
                        "actor_id": str(row.get("actor_id", "actor-synthetic")),
                        "sequence": int(row["sequence"]),
                        "why_code": str(row.get("why_code", "treatment-review")),
                    }
                    for row in item.get("responsibilities", [])
                ],
            }
            for item in replays
        }
        for item in transactions:
            self.transactions.restore(
                str(item["key"]),
                str(item["payload_digest"]),
                str(item["state"]),
                int(item["sequence"]),
                str(item.get("actor_id", "actor-synthetic")),
                str(item.get("why_code", "treatment-review")),
            )
        for item in policies:
            self.policies.restore(
                (
                    str(item["tenant_id"]),
                    str(item["campus_id"]),
                    str(item["purpose_code"]),
                    str(item["action"]),
                    str(item["resource_id"]),
                ),
                str(item["actor_id"]),
                str(item["why_code"]),
            )
        for item in evidence_graphs:
            self.evidence.restore(
                tuple(str(value) for value in item["evidence_ids"]),
                str(item["actor_id"]),
                str(item["why_code"]),
            )
        for item in rule_admissions:
            self.rules_ledger.restore(str(item["pack_id"]), str(item["actor_id"]), str(item["why_code"]))
        for item in consent_authorizations:
            self.consent_ledger.restore(str(item["consent_id"]), str(item["actor_id"]), str(item["why_code"]))
        for item in medication_decisions:
            findings = tuple((str(row["name"]), bool(row["present"])) for row in item["findings"])
            self.medication_ledger.restore(findings, str(item["actor_id"]), str(item["why_code"]))
        for item in fhir_resources:
            self.fhir_ledger.restore(str(item["resource_id"]), str(item["actor_id"]), str(item["why_code"]))
        for item in profile_declarations:
            self.fhir_ledger.profiles.restore(str(item["declared"]), str(item["actor_id"]), str(item["why_code"]))
        for item in terminology_releases:
            self.fhir_ledger.releases.restore(str(item["system_url"]), str(item["actor_id"]), str(item["why_code"]))
        for item in write_credentials:
            self.write_ledger.restore(str(item["proof_id"]), str(item["reviewer_id"]), str(item["why_code"]))
        for item in projections:
            fields = tuple(str(field) for field in item["fields"])
            self.projection_ledger.restore(fields, str(item["actor_id"]), str(item["why_code"]))
        for item in queries:
            scope = (
                str(item["tenant_id"]),
                str(item["campus_id"]),
                str(item["purpose_code"]),
                str(item["resource_type"]),
            )
            self.query_ledger.restore(scope, str(item["actor_id"]), str(item["why_code"]))
        for item in transfers:
            scope = (
                str(item["direction"]),
                str(item["tenant_id"]),
                str(item["campus_id"]),
                str(item["purpose_code"]),
            )
            self.transfer_ledger.restore(scope, str(item["actor_id"]), str(item["why_code"]))
        for item in caches:
            scope = (
                str(item["tenant_id"]),
                str(item["campus_id"]),
                str(item["resource_type"]),
                str(item["policy_version"]),
            )
            self.cache_ledger.restore(scope, str(item["actor_id"]), str(item["why_code"]))
        for item in health_checks:
            self.health_ledger.restore(
                str(item["tenant_id"]),
                str(item["campus_id"]),
                str(item["actor_id"]),
                str(item["why_code"]),
            )
        for item in stream_events:
            self.event_stream.restore(int(item["sequence"]), str(item["event_id"]), bool(item["late"]), str(item["actor_id"]), str(item["why_code"]))
        if watermark < 0:
            raise ContractError("review-store-corrupt")
        self.transaction_watermark = watermark

    def _dump(self, suggestion: Suggestion) -> dict[str, object]:
        return {
            "action": suggestion.action,
            "content_digest": suggestion.content_digest,
            "correction_recorded": suggestion.correction_recorded,
            "emergency_grant_id": suggestion.emergency_grant_id,
            "emergency_nonce": suggestion.emergency_nonce,
            "history": [list(step) for step in suggestion.history],
            "patient_ref": suggestion.patient_ref,
            "reviewers": sorted(suggestion.reviewers),
            "reviewer_roles": [
                {"actor_id": key, "actor_role": value}
                for key, value in sorted(suggestion.reviewer_roles.items())
            ],
            "state": suggestion.state,
            "submitted": suggestion.submitted,
            "suggestion_id": suggestion.suggestion_id,
            "version": suggestion.version,
            "write_intent_id": suggestion.write_intent_id,
        }

    def _dump_draft(self, draft: SuggestionDraft) -> dict[str, object]:
        consent = draft.consent
        pack = draft.rule_pack
        return {
            "action": draft.action,
            "actor": {str(key): str(value) for key, value in draft.actor.items()},
            "at_time": draft.at_time,
            "consent": {
                "consent_id": consent.consent_id,
                "effective_from": consent.effective_from,
                "effective_to": consent.effective_to,
                "purpose_code": consent.purpose_code,
                "state": consent.state,
                "version": consent.version,
            },
            "content_digest": draft.content_digest,
            "contract_version": draft.contract_version,
            "evidence": [
                {
                    "depends_on": list(item.depends_on),
                    "evidence_id": item.evidence_id,
                    "locator": item.locator,
                    "source_id": item.source_id,
                    "source_kind": item.source_kind,
                    "source_version": item.source_version,
                    "value_digest": item.value_digest,
                }
                for item in draft.evidence
            ],
            "patient_ref": draft.patient_ref,
            "medication_findings": None if draft.medication_findings is None else [
                {"finding": key, "present": value}
                for key, value in sorted(draft.medication_findings.items())
            ],
            "medication_facts": self._dump_facts(draft.medication_facts),
            "model_decision": draft.model_decision,
            "rule_decision": draft.rule_decision,
            "rule_pack": {
                "digest": pack.digest,
                "effective_from": pack.effective_from,
                "effective_to": pack.effective_to,
                "pack_id": pack.pack_id,
                "state": pack.state,
                "version": pack.version,
            },
            "suggestion_id": draft.suggestion_id,
        }

    def _restore_draft(self, item: dict[str, object]) -> SuggestionDraft:
        try:
            consent = item["consent"]
            pack = item["rule_pack"]
            evidence = item["evidence"]
            actor = item["actor"]
            return SuggestionDraft(
                str(item["suggestion_id"]),
                str(item["patient_ref"]),
                str(item["action"]),
                str(item["content_digest"]),
                tuple(
                    EvidenceRef(
                        str(ref["evidence_id"]),
                        str(ref["source_id"]),
                        str(ref["locator"]),
                        str(ref["source_version"]),
                        str(ref["value_digest"]),
                        tuple(str(dependency) for dependency in ref["depends_on"]),
                        str(ref.get("source_kind", "observation")),
                    )
                    for ref in evidence
                ),
                RulePack(
                    str(pack["pack_id"]),
                    str(pack["version"]),
                    str(pack["digest"]),
                    str(pack["state"]),
                    str(pack["effective_from"]),
                    str(pack["effective_to"]),
                ),
                Consent(
                    str(consent["consent_id"]),
                    str(consent["version"]),
                    str(consent["state"]),
                    str(consent["purpose_code"]),
                    str(consent["effective_from"]),
                    str(consent["effective_to"]),
                ),
                {str(key): str(value) for key, value in actor.items()},
                str(item["at_time"]),
                str(item.get("rule_decision", "allow")),
                str(item.get("model_decision", "allow")),
                self._restore_findings(item.get("medication_findings")),
                self._restore_facts(item.get("medication_facts")),
                str(item.get("contract_version", "1.0")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("review-store-corrupt") from exc

    def _restore_findings(self, raw: object) -> dict[str, bool] | None:
        if raw is None:
            return None
        if not isinstance(raw, list):
            raise ContractError("review-store-corrupt")
        return {str(item["finding"]): bool(item["present"]) for item in raw}

    def _dump_facts(self, facts: dict[str, object] | None) -> dict[str, object] | None:
        if facts is None:
            return None
        dumped: dict[str, object] = {}
        for key, value in sorted(facts.items()):
            dumped[key] = list(value) if isinstance(value, tuple) else value
        return dumped

    def _restore_facts(self, raw: object) -> dict[str, object] | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise ContractError("review-store-corrupt")
        restored: dict[str, object] = {}
        for key, value in raw.items():
            restored[str(key)] = tuple(str(item) for item in value) if isinstance(value, list) else value
        return restored

    def _restore(self, item: dict[str, object]) -> Suggestion:
        try:
            history = item["history"]
            return Suggestion(
                str(item["suggestion_id"]),
                str(item["patient_ref"]),
                str(item["action"]),
                state=str(item["state"]),
                version=int(item["version"]),
                write_intent_id=None if item["write_intent_id"] is None else str(item["write_intent_id"]),
                submitted=bool(item["submitted"]),
                reviewers={str(actor) for actor in item["reviewers"]},
                reviewer_roles={
                    str(role["actor_id"]): str(role["actor_role"])
                    for role in item.get("reviewer_roles", [])
                },
                emergency_nonce=None if item["emergency_nonce"] is None else str(item["emergency_nonce"]),
                content_digest=str(item["content_digest"]),
                correction_recorded=bool(item.get("correction_recorded", False)),
                emergency_grant_id=str(item["emergency_grant_id"]),
                history=[(str(step[0]), str(step[1]), str(step[2])) for step in history],
            )
        except (KeyError, TypeError, ValueError, TransitionError) as exc:
            raise ContractError("review-store-corrupt") from exc
