package audit

import "testing"

func event(sequence string, operation string) Fields {
	if operation == "" {
		operation = "review"
	}
	return Fields{
		"event_id":       "event-" + sequence,
		"stream_id":      "stream-synthetic",
		"sequence":       sequence,
		"tenant_id":      "tenant-synthetic",
		"campus_id":      "campus-synthetic",
		"actor_id":       "reviewer-synthetic",
		"actor_role":     "attending",
		"operation":      operation,
		"resource_type":  "Suggestion",
		"resource_id":    "suggestion-synthetic",
		"purpose_code":   "treatment",
		"why_code":       "review-decision",
		"policy_version": "1.0.0",
		"occurred_at":    "2026-09-24T00:00:00Z",
		"payload_digest": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
		"clock_quality":  "synchronized",
	}
}

func newSyntheticLog(t *testing.T) *Log {
	t.Helper()
	log, err := NewLog("stream-synthetic")
	if err != nil {
		t.Fatalf("NewLog rejected synthetic stream: %v", err)
	}
	return log
}

func TestAppendLinksPreviousHashAndVerifies(t *testing.T) {
	log := newSyntheticLog(t)
	first, err := log.Append(event("1", ""))
	if err != nil {
		t.Fatalf("first append rejected: %v", err)
	}
	second, err := log.Append(event("2", "commit"))
	if err != nil {
		t.Fatalf("second append rejected: %v", err)
	}
	if first.PreviousHash != Genesis {
		t.Fatalf("first previous hash is not genesis: %s", first.PreviousHash)
	}
	if second.PreviousHash != first.EventHash {
		t.Fatalf("second event is not linked to the first")
	}
	if err := log.Verify(); err != nil {
		t.Fatalf("verify rejected a clean chain: %v", err)
	}
}

func TestMissingWhyIsRejected(t *testing.T) {
	log := newSyntheticLog(t)
	missing := event("1", "")
	missing["why_code"] = ""
	if _, err := log.Append(missing); err == nil || err.Error() != "audit-why-missing" {
		t.Fatalf("missing why accepted: %v", err)
	}
	if len(log.Events()) != 0 {
		t.Fatal("rejected event was stored")
	}
}

func TestSkippedSequenceIsRejected(t *testing.T) {
	log := newSyntheticLog(t)
	if _, err := log.Append(event("2", "")); err == nil || err.Error() != "audit-sequence-invalid" {
		t.Fatalf("skipped sequence accepted: %v", err)
	}
	if len(log.Events()) != 0 {
		t.Fatal("rejected event was stored")
	}
}

func TestChangedActorBreaksVerification(t *testing.T) {
	log := newSyntheticLog(t)
	if _, err := log.Append(event("1", "")); err != nil {
		t.Fatalf("append rejected: %v", err)
	}
	stored := log.Events()[0]
	stored.ActorID = "other-user"
	log.events[0] = stored
	if err := log.Verify(); err == nil || err.Error() != "audit-hash-mismatch" {
		t.Fatalf("tampered actor passed verification: %v", err)
	}
}

func TestReorderedEventsBreakVerification(t *testing.T) {
	log := newSyntheticLog(t)
	if _, err := log.Append(event("1", "")); err != nil {
		t.Fatalf("append 1 rejected: %v", err)
	}
	if _, err := log.Append(event("2", "commit")); err != nil {
		t.Fatalf("append 2 rejected: %v", err)
	}
	log.events[0], log.events[1] = log.events[1], log.events[0]
	if err := log.Verify(); err == nil {
		t.Fatal("reordered chain passed verification")
	}
}

func TestSkippedPolicyVersionIsRejected(t *testing.T) {
	log := newSyntheticLog(t)
	skipped := event("1", "")
	skipped["policy_version"] = "1.2"
	if _, err := log.Append(skipped); err == nil || err.Error() != "audit-version-incompatible" {
		t.Fatalf("skipped policy version accepted: %v", err)
	}
}

func TestIdentifierActorIsRejected(t *testing.T) {
	log := newSyntheticLog(t)
	named := event("1", "")
	named["actor_id"] = "subject.identifier"
	if _, err := log.Append(named); err == nil || err.Error() != "audit-identifier-forbidden" {
		t.Fatalf("identifier actor accepted: %v", err)
	}
}

func TestIdentifierStreamIsRejected(t *testing.T) {
	if _, err := NewLog("subject.identifier"); err == nil || err.Error() != "audit-identifier-forbidden" {
		t.Fatalf("identifier stream accepted: %v", err)
	}
}

func TestStreamMismatchIsRejected(t *testing.T) {
	log := newSyntheticLog(t)
	wrong := event("1", "")
	wrong["stream_id"] = "stream-other"
	if _, err := log.Append(wrong); err == nil || err.Error() != "audit-stream-mismatch" {
		t.Fatalf("cross-stream event accepted: %v", err)
	}
}

func TestEmptyStreamIsRejected(t *testing.T) {
	if _, err := NewLog(""); err == nil || err.Error() != "audit-stream-invalid" {
		t.Fatalf("empty stream accepted: %v", err)
	}
}

func TestFhirMappingKeepsCodesAndDigest(t *testing.T) {
	log := newSyntheticLog(t)
	stored, err := log.Append(event("1", ""))
	if err != nil {
		t.Fatalf("append rejected: %v", err)
	}
	mapped, err := ToFhirAuditEvent(stored)
	if err != nil {
		t.Fatalf("fhir mapping rejected synthetic event: %v", err)
	}
	if mapped["resourceType"] != "AuditEvent" || mapped["action"] != "review" {
		t.Fatalf("unexpected mapping: %+v", mapped)
	}
	if len(mapped["entityDigest"]) != 64 || len(mapped["eventHash"]) != 64 {
		t.Fatalf("digest length lost: %+v", mapped)
	}
	if _, found := mapped["actor_id"]; found {
		t.Fatal("actor identifier leaked into the fhir mapping")
	}
	if _, found := mapped["resource_id"]; found {
		t.Fatal("resource identifier leaked into the fhir mapping")
	}
}
