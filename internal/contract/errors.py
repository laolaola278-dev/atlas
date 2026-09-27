"""Stable contract errors.

Codes are safe for logs. They never include a patient identifier, free-text
clinical content, or a secret.
"""
from __future__ import annotations

from dataclasses import dataclass


class ContractError(Exception):
    """Base class for fail-closed contract violations."""

    code = "contract-invalid"


@dataclass(frozen=True)
class ErrorCode:
    code: str
    retryable: bool
    http_status: int

    def __post_init__(self) -> None:
        if not self.code or " " in self.code:
            raise ContractError("error-code-invalid")
        if self.http_status < 400 or self.http_status > 599:
            raise ContractError("error-status-invalid")


CODES = {
    "context-incomplete": ErrorCode("context-incomplete", False, 400),
    "tenant-missing": ErrorCode("tenant-missing", False, 403),
    "campus-missing": ErrorCode("campus-missing", False, 403),
    "purpose-missing": ErrorCode("purpose-missing", False, 403),
    "version-conflict": ErrorCode("version-conflict", False, 409),
    "idempotency-conflict": ErrorCode("idempotency-conflict", False, 409),
    "approval-missing": ErrorCode("approval-missing", False, 403),
    "emergency-grant-not-approval": ErrorCode("emergency-grant-not-approval", False, 403),
    "result-unknown": ErrorCode("result-unknown", True, 503),
    "dependency-unavailable": ErrorCode("dependency-unavailable", True, 503),
    "identifier-forbidden": ErrorCode("identifier-forbidden", False, 403),
    "actor-identifier-forbidden": ErrorCode("actor-identifier-forbidden", False, 403),
    "audit-identifier-forbidden": ErrorCode("audit-identifier-forbidden", False, 403),
    "batch-identifier-forbidden": ErrorCode("batch-identifier-forbidden", False, 403),
    "cache-identifier-forbidden": ErrorCode("cache-identifier-forbidden", False, 403),
    "config-identifier-forbidden": ErrorCode("config-identifier-forbidden", False, 403),
    "consent-identifier-forbidden": ErrorCode("consent-identifier-forbidden", False, 403),
    "evidence-identifier-forbidden": ErrorCode("evidence-identifier-forbidden", False, 403),
    "idempotency-identifier-forbidden": ErrorCode("idempotency-identifier-forbidden", False, 403),
    "medication-identifier-forbidden": ErrorCode("medication-identifier-forbidden", False, 403),
    "policy-identifier-forbidden": ErrorCode("policy-identifier-forbidden", False, 403),
    "query-identifier-forbidden": ErrorCode("query-identifier-forbidden", False, 403),
    "replay-identifier-forbidden": ErrorCode("replay-identifier-forbidden", False, 403),
    "rule-identifier-forbidden": ErrorCode("rule-identifier-forbidden", False, 403),
    "stream-identifier-forbidden": ErrorCode("stream-identifier-forbidden", False, 403),
    "suggestion-identifier-forbidden": ErrorCode("suggestion-identifier-forbidden", False, 403),
    "trace-identifier-forbidden": ErrorCode("trace-identifier-forbidden", False, 403),
    "transaction-identifier-forbidden": ErrorCode("transaction-identifier-forbidden", False, 403),
    "write-identifier-forbidden": ErrorCode("write-identifier-forbidden", False, 403),
}


def _register(code: str, retryable: bool, http_status: int) -> None:
    CODES.setdefault(code, ErrorCode(code, retryable, http_status))


def _register_raised_codes() -> None:
    """Register every stable code the services already raise."""
    unavailable = {
        "ack-result-unknown",
        "dependency-unavailable",
        "validator-engine-timeout",
        "validator-engine-unavailable",
        "validator-output-corrupt",
        "validator-output-missing",
        "doc-retry-unknown",
        "import-result-unknown",
        "pharmacy-result-unknown",
        "receipt-result-unknown",
        "result-unknown",
        "schedule-result-unknown",
        "transaction-result-unknown",
        "validator-result-unknown",
    }
    conflicts = {"version-conflict", "idempotency-conflict", "schedule-idempotency-conflict", "transaction-conflict"}
    for code in _RAISED:
        if code in unavailable:
            _register(code, True, 503)
        elif code in conflicts:
            _register(code, False, 409)
        elif code.endswith("-forbidden") or code.endswith("-mismatch") or "secret" in code:
            _register(code, False, 403)
        else:
            _register(code, False, 400)


_RAISED = (
    "actor-context-incomplete actor-why-missing adopt-actor-forbidden adopt-input-invalid adopt-state-invalid ack-message-invalid ack-outcome-invalid ack-result-unknown alarm-count-invalid alarm-debounced alarm-point-unknown api-content-type-rejected api-input-invalid api-method-forbidden api-route-forbidden api-route-unknown allergy-severity-invalid allergy-severity-missing approval-mismatch approval-not-emergency-grant "
    "approval-reviewer-not-recorded approval-role-mismatch audit-chain-broken audit-context-incomplete "
    "audit-file-corrupt audit-file-tampered audit-fhir-digest-invalid audit-fhir-identifier-forbidden audit-hash-mismatch audit-sequence-invalid audit-stream-invalid audit-link-digest-invalid audit-link-mismatch audit-link-operation-invalid "
    "audit-stream-mismatch audit-version-incompatible audit-why-missing arrival-gap arrival-input-invalid arrival-late arrival-reordered doc-arrival-below doc-arrival-invalid doc-rollback-invalid doc-rollback-sealed doc-load-exceeded doc-load-invalid doc-load-not-synthetic doc-retry-exhausted doc-retry-forbidden doc-retry-invalid doc-retry-unknown doc-term-unknown doc-term-unregistered draft-isolated draft-lane-invalid accepted-isolated batch-backpressure batch-cancelled batch-capacity-invalid batch-consent-not-active batch-item-invalid batch-responsibility-mismatch batch-why-missing block-findings-invalid block-hard-mismatch bundle-empty bundle-entry-duplicate bundle-entry-invalid bundle-too-large bundle-type-invalid bundle-type-rejected buffer-input-invalid buffer-online-forbidden buffer-overflow break-glass-authorizer-forbidden break-glass-reason-invalid bypass-catalog-forbidden bypass-catalog-invalid bypass-catalog-unknown bypass-forbidden bypass-path-invalid "
    "cache-consent-invalid cache-field-invalid "
    "cache-fields-missing cache-phi-forbidden cache-responsibility-mismatch cache-scope-incomplete cache-why-missing canary-digest-invalid canary-percent-invalid canary-gate-open canary-slice-invalid capability-software-invalid capability-status-invalid capability-type-rejected capability-version-incompatible capability-version-missing chapter-identifier-forbidden chapter-required-missing capacity-exceeded capacity-input-invalid case-digest-invalid case-identifier-forbidden case-not-synthetic citation-duplicate citation-set-invalid citation-unregistered channel-critical-isolated channel-input-invalid channel-ordinary-isolated clock-epoch-invalid clock-skew-isolated commit-kind-invalid emergency-commit-forbidden coding-dirty coding-field-invalid coding-registry-invalid campus-mismatch code-digest-invalid code-registry-invalid code-unknown commit-state-invalid "
    "config-incomplete config-secret-inline config-secret-ref-invalid config-signature-invalid config-signature-same config-version-incompatible condition-status-invalid condition-status-missing consent-incomplete consumer-conflict-retry consumer-digest-invalid consumer-forbidden-retry consumer-purpose-rejected consumer-trace-invalid consumer-version-rejected contact-identifier-forbidden diff-set-invalid diff-unchanged defect-defer-forbidden defect-grade-invalid device-certificate-expired device-digest-invalid device-id-forbidden dicom-digest-invalid dicom-digest-reused dicom-fields-missing dicom-pixel-forbidden display-digest-invalid display-language-invalid dose-input-invalid dose-limit-exceeded dose-unit-unknown dual-scope-invalid contact-suppressed contraindication-digest-invalid contraindication-registry-invalid contraindication-unknown "
    "consent-not-active consent-not-tracked consent-outside-window consent-purpose-mismatch consent-responsibility-mismatch consent-state-mismatch "
    "consent-version-incompatible consent-why-missing constraint-check-failed constraint-duplicate constraint-identifier-forbidden constraint-kind-invalid constraint-required-missing contract-version-incompatible counterfactual-action-invalid counterfactual-execute-forbidden counterfactual-mode-invalid correction-reason-missing correction-reviewer-not-independent correction-state-invalid critical-range-invalid critical-value document-hash-invalid document-hash-missing duplicate-digest-invalid duplicate-order duplicate-set-invalid edge-clock-invalid edge-clock-rejected "
    "emergency-action-forbidden emergency-authorizer-forbidden emergency-authorizer-mismatch emergency-cannot-enter-ordinary-commit emergency-consent-untracked "
    "emergency-context-incomplete emergency-grant-mismatch emergency-intent-conflict emergency-intent-forbidden emergency-history-erased emergency-mismatch emergency-reason-missing "
    "emergency-not-found emergency-receipt-invalid emergency-state-mismatch emergency-version-mismatch encounter-period-inverted encounter-period-missing encounter-status-invalid encounter-status-missing episode-digest-invalid evidence-citation-missing evidence-decision-invalid episode-duplicate episode-reference-forbidden episode-set-invalid evidence-cycle "
    "evidence-dangling evidence-digest-mismatch evidence-duplicate evidence-incomplete evidence-missing evidence-responsibility-mismatch evidence-unlocatable evidence-version-incompatible evidence-why-missing explain-digest-invalid extension-digest-invalid extension-duplicate extension-id-forbidden extension-not-synthetic false-positive-incomplete false-positive-invalid fault-device-forbidden fault-healthy-isolated fault-input-invalid fault-not-isolated fixture-digest-invalid fixture-not-synthetic fixture-pixel-forbidden explain-input-invalid explain-decision-invalid explain-digest-invalid explain-rule-forbidden explain-audit-action-invalid explain-audit-digest-invalid explain-audit-mismatch explain-version-invalid explain-version-mismatch fhir-responsibility-mismatch health-actor-missing age-bound-invalid weight-bound-invalid health-responsibility-mismatch health-why-missing evidence-index-corrupt evidence-index-why-missing evidence-output-missing evidence-plan-corrupt evidence-test-missing "
    "idempotency-key-invalid idempotency-key-unknown idempotency-receipt-pending repeat-conflict repeat-digest-invalid repeat-state-invalid idempotency-responsibility-mismatch import-item-unknown import-result-unknown import-state-invalid ingest-audit-forbidden ingest-audit-invalid index-partition-mismatch journey-kind-invalid journey-not-synthetic journey-path-invalid guide-entry-unknown guide-not-synthetic grouper-isolated grouper-lane-invalid code-version-mismatch code-version-unknown hit-path-invalid hit-step-repeated hit-step-unknown knowledge-digest-invalid lab-time-invalid lab-time-inverted local-code-mismatch local-code-unknown group-reason-mismatch group-reason-unknown billing-review-forbidden billing-review-invalid charge-line-invalid charge-line-mismatch denial-reason-unknown denial-year-unknown batch-total-invalid batch-total-mismatch batch-unknown rule-replay-mismatch rule-replay-unknown export-forbidden export-lane-invalid statement-invalid statement-mismatch statement-not-synthetic billing-audit-circular billing-audit-invalid batch-cap-exceeded batch-cap-invalid billing-window-expired billing-window-invalid billing-checksum-invalid billing-checksum-mismatch billing-amount-invalid billing-amount-out-of-range billing-lock-invalid billing-lock-violation billing-adjustment-invalid notification-invalid notification-content-mismatch capacity-invalid capacity-headroom-insufficient fairness-report-invalid fairness-threshold-invalid fairness-variance-exceeded rollback-invalid rollback-forbidden submission-invalid submission-content-mismatch submission-actor-required submission-already-withdrawn submission-checksum-marshal-error submission-form-data-required submission-form-data-too-large submission-form-id-required submission-id-required submission-idempotency-inconsistent submission-idempotency-required submission-invalid-id submission-invalid-operation submission-nonce-required submission-not-found submission-prohibited-field submission-synthetic-required submission-unauthorized submission-unknown-operation submission-user-id-required submission-user-required revocation-actor-required revocation-already-revoked revocation-failed revocation-id-invalid revocation-idempotency-required revocation-not-found revocation-reason-too-long revocation-reason-too-short revocation-request-nil revocation-revoked-by-empty revocation-status-invalid revocation-submission-not-found revocation-synthetic-required revocation-timestamp-invalid revocation-validation-failed form-version-invalid form-version-unsupported field-invalid field-synthetic-only field-schema-invalid field-conditional-invalid field-not-found attachment-mime-not-whitelisted attachment-size-exceeded attachment-checksum-invalid attachment-filename-invalid attachment-synthetic-only attachment-not-found signature-format-invalid signature-timestamp-invalid signature-weak signature-synthetic-only signature-not-found draft-recovery-nil-request draft-recovery-synthetic-only draft-recovery-invalid-form-id draft-recovery-invalid-submission-id draft-recovery-invalid-draft-id draft-recovery-invalid-actor-id draft-recovery-missing-idempotency-key draft-recovery-draft-not-found draft-recovery-invalid-status draft-recovery-empty-data draft-recovery-empty-field-name draft-recovery-empty-field-value draft-recovery-non-synthetic-field draft-recovery-form-mismatch draft-recovery-submission-mismatch draft-recovery-invalid-recovery-id draft-recovery-recovery-not-found draft-save-synthetic-only draft-save-invalid-draft-id signature-unauthorized signature-self-sign-forbidden revocation-invalid revocation-reason-invalid revocation-unauthorized fields-invalid fields-required-missing schedule-invalid schedule-capacity-exceeded schedule-synthetic-required schedule-overlap schedule-department-invalid schedule-slot-invalid schedule-idempotency-conflict schedule-result-unknown review-status-invalid signature-invalid signature-format-invalid attachment-invalid attachment-type-forbidden attachment-size-exceeded draft-invalid draft-not-found draft-action-invalid draft-id-invalid draft-data-empty draft-data-invalid draft-data-too-large draft-synthetic-only draft-operation-invalid draft-checksum-failed draft-discarded draft-access-denied synthetic-form-id-empty synthetic-form-id-invalid synthetic-form-type-empty synthetic-form-type-invalid synthetic-form-field-spec-empty synthetic-form-seed-invalid synthetic-form-version-invalid synthetic-form-version-unsupported synthetic-form-idempotency-key-empty synthetic-form-idempotency-conflict synthetic-form-not-found synthetic-form-checksum-invalid synthetic-form-fields-invalid synthetic-form-synthetic-required form-tracking-request-nil form-tracking-synthetic-required form-tracking-event-id-empty form-tracking-invalid-event-id form-tracking-form-id-empty form-tracking-phi-pattern-detected form-tracking-event-type-empty form-tracking-event-type-invalid form-tracking-actor-role-empty form-tracking-timestamp-empty form-tracking-timestamp-invalid form-tracking-idempotency-required form-tracking-idempotency-too-short form-tracking-event-not-found lab-time-missing knowledge-signer-forbidden knowledge-signers-invalid interaction-digest-invalid interaction-pair-invalid interaction-unknown index-reference-forbidden intent-kind-invalid intent-not-ordinary inventory-device-forbidden inventory-mismatch inventory-set-invalid "
    "idempotency-state-invalid idempotency-why-missing image-access-digest-invalid image-access-invalid icd-digest-invalid icd-family-rejected icd-package-forbidden icd-release-invalid reproductive-restricted reproductive-state-invalid medication-dose-invalid medication-facts-incomplete medication-facts-mismatch medication-findings-invalid "
    "medication-findings-mismatch medication-responsibility-mismatch medication-rule-mismatch match-below-threshold match-digest-invalid match-digest-mismatch match-score-invalid medcode-digest-invalid medcode-not-synthetic medcode-same-digest merge-same-reviewer merge-signature-missing medication-why-missing migration-action-unknown migration-destructive-forbidden migration-identifier-forbidden migration-input-invalid migration-not-synthetic migration-unreviewed message-conflict message-key-invalid loinc-digest-invalid loinc-not-synthetic loinc-unit-unknown limit-backpressure limit-invalid limit-source-forbidden merge-automatic-forbidden merge-blocked-zero-tolerance model-boundary-invalid model-cannot-override-rule model-digest-invalid model-vote-invalid model-pixel-forbidden mqtt-client-forbidden mqtt-session-dirty mqtt-topic-forbidden newborn-identifier-forbidden newborn-input-invalid newborn-review-missing newborn-same-reviewer newborn-score-low newborn-window-closed observation-quantity-invalid observation-range-invalid observation-range-inverted nonce-invalid nonce-reused order-digest-invalid order-emergency-isolated order-lane-invalid order-ordinary-isolated order-not-synthetic order-reference-forbidden order-proof-absent order-proof-digest-invalid order-proof-missing order-proof-rejected order-audit-action-invalid order-audit-digest-invalid order-audit-mismatch order-state-invalid order-subject-forbidden order-subject-mismatch order-subject-missing object-body-forbidden object-digest-invalid object-digest-mismatch object-cross-campus-forbidden order-cancel-too-late order-change-invalid order-correct-too-early object-size-invalid pack-digest-invalid allergy-digest-invalid allergy-group-invalid allergy-no-cross allergy-unknown pack-signature-same pack-version-invalid offline-cache-cache-id-empty offline-cache-cache-key-empty offline-cache-data-hash-empty offline-cache-data-hash-invalid offline-cache-encrypted-data-empty offline-cache-expired offline-cache-form-id-empty offline-cache-hash-mismatch offline-cache-idempotency-required offline-cache-invalid-id offline-cache-not-found offline-cache-phi-pattern-detected offline-cache-synthetic-required offline-cache-ttl-invalid synthetic-form-checksum-invalid synthetic-form-field-spec-empty synthetic-form-form-id-empty synthetic-form-form-type-empty synthetic-form-form-type-invalid synthetic-form-idempotency-required synthetic-form-invalid-id synthetic-form-not-found synthetic-form-phi-pattern-detected synthetic-form-seed-empty synthetic-form-synthetic-required synthetic-form-version-empty synthetic-form-version-invalid offline-cache-form-id-empty offline-cache-hash-mismatch offline-cache-idempotency-required offline-cache-invalid-id offline-cache-not-found offline-cache-phi-pattern-detected offline-cache-synthetic-required offline-cache-ttl-invalid offline-digest-invalid offline-signature-same offline-signer-forbidden outcome-empty outcome-identifier-forbidden patient-identifier-forbidden patient-reference-mismatch partition-forbidden partition-missing partition-split pharmacy-receipt-invalid pharmacy-result-unknown pharmacy-state-invalid pid-digest-invalid pid-missing permission-campus-denied permission-grant-invalid permission-purpose-denied permission-tenant-denied point-not-synthetic point-unit-mismatch point-unknown "
    "policy-payload-invalid postreview-duplicate postreview-key-forbidden postreview-kind-invalid policy-responsibility-mismatch proof-digest-invalid proof-expired proof-expiry-incomplete proof-expiry-invalid proof-binding-incomplete proof-binding-mismatch proof-patient-forbidden proof-signers-invalid post-reviewer-not-independent privacy-consent-not-active privilege-account-forbidden privilege-action-invalid privilege-identifier-forbidden privilege-input-invalid procedure-status-invalid procedure-status-missing procedure-time-inverted procedure-time-missing provenance-agent-missing provenance-recorded-missing provenance-target-missing privacy-field-forbidden priority-finding-invalid probe-input-invalid probe-value-forbidden probe-value-invalid probe-value-missing "
    "privacy-projection-empty privacy-responsibility-mismatch privacy-scope-missing privacy-why-missing profile-actor-missing profile-catalog-corrupt projection-state-unknown profile-differential-missing profile-fixture-corrupt profile-forbidden-present profile-required-missing "
    "profile-fixture-not-synthetic profile-not-declared profile-responsibility-mismatch profile-why-missing publish-digest-invalid publish-same-approver publish-signature-missing publish-signer-forbidden purpose-mismatch query-consent-not-active query-field-forbidden "
    "query-fields-invalid query-page-invalid query-responsibility-mismatch query-scope-incomplete query-tenant-isolated query-why-missing queue-candidate-missing queue-decision-invalid queue-digest-invalid queue-duplicate queue-identifier-forbidden queue-merge-forbidden replay-context-incomplete replay-digest-invalid replay-digest-mismatch replay-nonce-reused replay-responsibility-mismatch replay-version-incompatible resume-already-committed resume-gap resume-input-invalid "
    "replay-sequence-invalid replay-decision-invalid replay-digest-invalid replay-mismatch replay-why-missing regmark-authority-unknown regmark-digest-invalid regmark-subset-forbidden rebuild-duplicate rebuild-empty rebuild-too-large receipt-mismatch receipt-result-unknown receipt-state-invalid readability-identifier-forbidden readability-sections-invalid readability-text-forbidden redact-field-forbidden redact-identifier-forbidden redact-output-invalid recall-below-threshold recall-incomplete recall-invalid reconcile-digest-invalid reconcile-extra reconcile-missing reconcile-set-invalid reference-duplicate reference-set-invalid report-status-invalid report-status-missing request-priority-invalid request-priority-missing resource-version-invalid resource-version-missing review-audit-missing review-audit-partial review-digest-mismatch review-draft-missing "
    "review-state-invalid review-policy-invalid review-policy-mismatch review-pack-digest-invalid review-pack-incomplete review-pack-not-synthetic review-store-corrupt review-store-scope-invalid review-store-scope-mismatch "
    "review-store-tampered review-suggestion-mismatch rule-decision-invalid rule-decision-mismatch rule-digest-invalid "
    "rule-digest-mismatch rule-outside-window rule-pack-incomplete rule-pack-not-tracked rule-responsibility-mismatch rule-state-rejected rule-uncertain-denied rule-certainty-invalid "
    "rule-version-incompatible rule-why-missing route-source-invalid route-tenant-shared route-tenant-unknown rollback-order-invalid rollback-still-active rollback-window-incomplete same-name-different-person same-name-input-invalid same-name-not-shared safety-digest-invalid safety-signer-forbidden safety-signers-invalid sample-critical-forbidden sample-digest-invalid sample-factor-invalid sample-input-invalid sample-mismatch sample-set-invalid seal-body-forbidden seal-digest-invalid scale-count-invalid scale-not-synthetic scale-seed-forbidden search-parameter-forbidden search-parameter-missing second-backpressure second-epoch-invalid second-limit-invalid second-review-state-invalid segment-header-missing segment-identifier-forbidden segment-set-invalid segment-unknown segment-p95-exceeded segment-time-invalid shard-count-invalid shard-hot-key service-direct-write-forbidden service-grant-rejected service-input-invalid service-proof-expired service-subject-mismatch service-unsigned signoff-actor-forbidden signoff-state-invalid shard-key-forbidden second-reviewer-not-independent second-denial-invalid second-denial-state-invalid skip-switch-absent skip-switch-invalid snomed-member-duplicate snomed-member-invalid snomed-name-forbidden snomed-not-synthetic snomed-subset-invalid stream-consent-not-active "
    "stream-event-invalid stream-gap stream-invalid storage-input-invalid storage-watermark-corrupt storage-watermark-full stream-responsibility-mismatch stream-why-missing switch-input-invalid rule-disabled study-accession-forbidden study-token-invalid split-reason-missing subscription-digest-invalid subscription-identifier-forbidden subscription-incomplete subscription-tenant-mismatch subscription-type-mismatch suggestion-digest-invalid suggestion-incomplete suggestion-not-tracked "
    "system-cannot-review syntax-not-allowed target-version-missing target-version-conflict target-version-incomplete template-fields-invalid template-identifier-forbidden template-text-forbidden template-version-invalid tenant-mismatch termcache-digest-invalid termcache-expired timeout-input-invalid termcache-window-incomplete terminology-manifest-corrupt token-campus-same token-digest-invalid token-tenant-mismatch terminology-release-expired "
    "terminology-release-incomplete terminology-release-unknown terminology-responsibility-mismatch terminology-why-missing transaction-already-committed transaction-conflict "
    "transaction-key-invalid transaction-key-unknown transaction-result-unknown transaction-responsibility-mismatch transaction-state-invalid "
    "transaction-stream-invalid transaction-why-missing transfer-consent-not-active transfer-direction-invalid transfer-field-forbidden transfer-field-missing "
    "transfer-fields-missing transfer-identifier-forbidden transfer-scope-incomplete transfer-responsibility-mismatch transfer-why-missing validator-digest-invalid validator-digest-mismatch validator-engine-timeout validator-engine-unavailable validator-input-invalid validator-jar-digest-mismatch validator-not-official validator-outcome-failed validator-outcome-invalid validator-output-corrupt validator-output-missing validator-result-unknown upgrade-not-needed upgrade-rollback-forbidden upgrade-version-invalid version-invalid write-credential-incomplete write-digest-invalid write-responsibility-mismatch write-version-incompatible "
    "write-window-closed write-why-missing write-window-incomplete withdraw-input-invalid withdraw-too-late "
    "workflow-definition-duplicate-step-id workflow-definition-final-states-empty workflow-definition-id-empty workflow-definition-id-invalid-prefix workflow-definition-idempotency-required workflow-definition-idempotency-too-short workflow-definition-initial-state-empty workflow-definition-metadata-key-invalid workflow-definition-name-empty workflow-definition-not-found workflow-definition-phi-pattern-detected workflow-definition-request-nil workflow-definition-step-id-empty workflow-definition-step-name-empty workflow-definition-step-type-empty workflow-definition-step-type-invalid workflow-definition-steps-empty workflow-definition-synthetic-required workflow-definition-transition-event-empty workflow-definition-transition-from-empty workflow-definition-transition-to-empty workflow-definition-transitions-empty workflow-definition-version-empty "
    "workflow-human-task-assigned-to-empty workflow-human-task-delete-id-empty workflow-human-task-get-id-empty workflow-human-task-idempotency-key-empty workflow-human-task-idempotency-key-short workflow-human-task-metadata-key-phi-pattern workflow-human-task-not-found workflow-human-task-not-synthetic workflow-human-task-priority-invalid workflow-human-task-request-nil workflow-human-task-status-empty workflow-human-task-status-invalid workflow-human-task-step-id-empty workflow-human-task-task-id-empty workflow-human-task-task-id-invalid-prefix workflow-human-task-title-blank workflow-human-task-title-phi-pattern workflow-human-task-update-id-empty workflow-human-task-workflow-id-empty "
    "workflow-audit-event-missing workflow-audit-event-mismatch workflow-audit-event-unknown workflow-slice-stage-missing workflow-task-state-invalid workflow-task-unknown"
).split()


_register_raised_codes()


_TRACE_FORBIDDEN = frozenset({
    "name",
    "identifier",
    "phone",
    "address",
    "birth_date",
    "patient_id",
})


def _trace_has_identifier(value: str) -> bool:
    parts = value.replace("[", ".").replace("]", "").split(".")
    return any(part in _TRACE_FORBIDDEN for part in parts)


def lookup(code: str) -> ErrorCode:
    """Return a known code or fail closed for an unknown one."""
    try:
        return CODES[code]
    except KeyError as exc:
        raise ContractError("error-code-unknown") from exc


def public_body(code: str, trace_id: str) -> dict[str, str | bool | int]:
    """Build a client-visible error without echoing caller-supplied text."""
    if not trace_id or any(char.isspace() for char in trace_id):
        raise ContractError("trace-id-invalid")
    if _trace_has_identifier(trace_id):
        raise ContractError("trace-identifier-forbidden")
    item = lookup(code)
    return {
        "code": item.code,
        "retryable": item.retryable,
        "status": item.http_status,
        "trace_id": trace_id,
    }
