package forms

import (
	"testing"
	"time"
)

func baseFormEventReq() *TrackFormEventRequest {
	return &TrackFormEventRequest{
		EventID:        "evt-synthetic-001",
		FormID:         "form-synthetic-100",
		EventType:      "created",
		ActorRole:      "clinician",
		Timestamp:      "2024-01-15T10:00:00Z",
		Details:        map[string]string{"action": "initial_creation"},
		IdempotencyKey: "idem-tracking-synthetic-001",
		Synthetic:      true,
	}
}

func checkError0238(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected error containing %q, got nil", expected)
	}
	if !contains(err.Error(), expected) {
		t.Errorf("expected error containing %q, got %q", expected, err.Error())
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(s) > len(substr) && containsAt(s, substr))
}

func containsAt(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

func TestValidateTrackFormEventRequest_Valid(t *testing.T) {
	req := baseFormEventReq()
	err := ValidateTrackFormEventRequest(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestValidateTrackFormEventRequest_NilRequest(t *testing.T) {
	err := ValidateTrackFormEventRequest(nil)
	checkError0238(t, err, "form-tracking-request-nil")
}

func TestValidateTrackFormEventRequest_NotSynthetic(t *testing.T) {
	req := baseFormEventReq()
	req.Synthetic = false
	err := ValidateTrackFormEventRequest(req)
	if err == nil {
		t.Fatal("expected error for non-synthetic request")
	}
	checkError0238(t, err, "form-tracking-synthetic-required")
}

func TestValidateTrackFormEventRequest_EmptyEventID(t *testing.T) {
	req := baseFormEventReq()
	req.EventID = ""
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-event-id-empty")
}

func TestValidateTrackFormEventRequest_InvalidEventID(t *testing.T) {
	req := baseFormEventReq()
	req.EventID = "invalid"
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-invalid-event-id")
}

func TestValidateTrackFormEventRequest_EmptyFormID(t *testing.T) {
	req := baseFormEventReq()
	req.FormID = ""
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-form-id-empty")
}

func TestValidateTrackFormEventRequest_PHIPatternInFormID(t *testing.T) {
	req := baseFormEventReq()
	req.FormID = "patient_id_12345"
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-phi-pattern-detected")
}

func TestValidateTrackFormEventRequest_EmptyEventType(t *testing.T) {
	req := baseFormEventReq()
	req.EventType = ""
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-event-type-empty")
}

func TestValidateTrackFormEventRequest_InvalidEventType(t *testing.T) {
	req := baseFormEventReq()
	req.EventType = "unknown"
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-event-type-invalid")
}

func TestValidateTrackFormEventRequest_EmptyActorRole(t *testing.T) {
	req := baseFormEventReq()
	req.ActorRole = ""
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-actor-role-empty")
}

func TestValidateTrackFormEventRequest_PHIPatternInActorRole(t *testing.T) {
	// Verify PHI pattern rejection in actor role field
	req := baseFormEventReq()
	req.ActorRole = "patient_id_67890" // PHI pattern in role
	err := ValidateTrackFormEventRequest(req)
	if err == nil {
		t.Fatal("expected error for PHI pattern in actor role")
	}
	checkError0238(t, err, "form-tracking-phi-pattern-detected")
}

func TestValidateTrackFormEventRequest_EmptyTimestamp(t *testing.T) {
	req := baseFormEventReq()
	req.Timestamp = "" // timestamp required for audit trail
	err := ValidateTrackFormEventRequest(req)
	if err == nil {
		t.Fatal("expected error for empty timestamp")
	}
	checkError0238(t, err, "form-tracking-timestamp-empty")
}

func TestValidateTrackFormEventRequest_InvalidTimestamp(t *testing.T) {
	req := baseFormEventReq()
	req.Timestamp = "invalid-timestamp"
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-timestamp-invalid")
}

func TestValidateTrackFormEventRequest_PHIPatternInDetails(t *testing.T) {
	// Verify PHI pattern rejection in details map
	req := baseFormEventReq()
	req.Details = map[string]string{"patient_id": "12345"} // PHI in details
	err := ValidateTrackFormEventRequest(req)
	if err == nil {
		t.Fatal("expected PHI pattern detection in details")
	}
	checkError0238(t, err, "form-tracking-phi-pattern-detected")
}

func TestValidateTrackFormEventRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseFormEventReq()
	req.IdempotencyKey = "" // idempotency required
	err := ValidateTrackFormEventRequest(req)
	if err == nil {
		t.Fatal("expected error when idempotency key is empty")
	}
	checkError0238(t, err, "form-tracking-idempotency-required")
}

func TestValidateTrackFormEventRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseFormEventReq()
	req.IdempotencyKey = "short"
	err := ValidateTrackFormEventRequest(req)
	checkError0238(t, err, "form-tracking-idempotency-too-short")
}

func TestTrackFormEvent_Success(t *testing.T) {
	ClearFormEvents("form-synthetic-100")
	req := baseFormEventReq()

	resp, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if resp.EventID != req.EventID {
		t.Errorf("expected EventID %q, got %q", req.EventID, resp.EventID)
	}
	if resp.FormID != req.FormID {
		t.Errorf("expected FormID %q, got %q", req.FormID, resp.FormID)
	}
	if resp.EventType != req.EventType {
		t.Errorf("expected EventType %q, got %q", req.EventType, resp.EventType)
	}
	if resp.Digest == "" {
		t.Error("expected non-empty Digest")
	}
}

func TestTrackFormEvent_Idempotency(t *testing.T) {
	ClearFormEvents("form-synthetic-100")
	req := baseFormEventReq()
	req.EventID = "evt-synthetic-idem-001"
	req.IdempotencyKey = "idem-tracking-test-001"

	resp1, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("first call failed: %v", err)
	}

	resp2, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("second call failed: %v", err)
	}

	if resp1.EventID != resp2.EventID {
		t.Errorf("idempotency failed: got different EventIDs %q vs %q", resp1.EventID, resp2.EventID)
	}
}

func TestTrackFormEvent_ValidationFailure(t *testing.T) {
	req := baseFormEventReq()
	req.EventType = ""

	_, err := TrackFormEvent(req)
	checkError0238(t, err, "form-tracking-event-type-empty")
}

func TestGetFormEvent_Success(t *testing.T) {
	ClearFormEvents("form-synthetic-100")
	req := baseFormEventReq()
	req.EventID = "evt-synthetic-get-001"
	req.IdempotencyKey = "idem-get-001-synthetic-key"

	_, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("track failed: %v", err)
	}

	resp, err := GetFormEvent(req.EventID)
	if err != nil {
		t.Fatalf("get failed: %v", err)
	}
	if resp.EventID != req.EventID {
		t.Errorf("expected EventID %q, got %q", req.EventID, resp.EventID)
	}
}

func TestGetFormEvent_EmptyID(t *testing.T) {
	_, err := GetFormEvent("")
	checkError0238(t, err, "form-tracking-event-id-empty")
}

func TestGetFormEvent_NotFound(t *testing.T) {
	_, err := GetFormEvent("evt-nonexistent")
	checkError0238(t, err, "form-tracking-event-not-found")
}

func TestListFormEvents_Success(t *testing.T) {
	formID := "form-synthetic-list-001"
	ClearFormEvents(formID)

	req1 := baseFormEventReq()
	req1.FormID = formID
	req1.EventID = "evt-list-001"
	req1.IdempotencyKey = "idem-list-001-synthetic-key"

	req2 := baseFormEventReq()
	req2.FormID = formID
	req2.EventID = "evt-list-002"
	req2.IdempotencyKey = "idem-list-002-synthetic-key"

	_, _ = TrackFormEvent(req1)
	_, _ = TrackFormEvent(req2)

	events, err := ListFormEvents(formID)
	if err != nil {
		t.Fatalf("list failed: %v", err)
	}
	if len(events) < 2 {
		t.Fatalf("expected at least 2 tracked events, got %d", len(events))
	}
}

func TestListFormEvents_EmptyFormID(t *testing.T) {
	_, err := ListFormEvents("")
	checkError0238(t, err, "form-tracking-form-id-empty")
}

func TestListFormEvents_NoResults(t *testing.T) {
	events, err := ListFormEvents("form-nonexistent")
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if len(events) != 0 {
		t.Errorf("expected 0 events, got %d", len(events))
	}
}

func TestGetEventsByType_Success(t *testing.T) {
	ClearFormEvents("form-synthetic-type-001")

	req := baseFormEventReq()
	req.FormID = "form-synthetic-type-001"
	req.EventID = "evt-type-001"
	req.EventType = "submitted"
	req.IdempotencyKey = "idem-type-001-synthetic-key"

	_, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("track failed: %v", err)
	}

	events, err := GetEventsByType("submitted")
	if err != nil {
		t.Fatalf("get by type failed: %v", err)
	}

	found := false
	for _, evt := range events {
		if evt.EventID == req.EventID {
			found = true
			break
		}
	}
	if !found {
		t.Error("expected to find tracked event in results")
	}
}

func TestGetEventsByType_EmptyType(t *testing.T) {
	_, err := GetEventsByType("")
	checkError0238(t, err, "form-tracking-event-type-empty")
}

func TestGetEventsByType_InvalidType(t *testing.T) {
	_, err := GetEventsByType("invalid-type")
	checkError0238(t, err, "form-tracking-event-type-invalid")
}

func TestDeleteFormEvent_Success(t *testing.T) {
	ClearFormEvents("form-synthetic-delete-001")

	req := baseFormEventReq()
	req.FormID = "form-synthetic-delete-001"
	req.EventID = "evt-delete-001"
	req.IdempotencyKey = "idem-delete-001-synthetic-key"

	_, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("track failed: %v", err)
	}

	err = DeleteFormEvent(req.EventID)
	if err != nil {
		t.Fatalf("delete failed: %v", err)
	}

	_, err = GetFormEvent(req.EventID)
	if err == nil {
		t.Error("expected event to be deleted")
	}
}

func TestDeleteFormEvent_EmptyID(t *testing.T) {
	err := DeleteFormEvent("")
	checkError0238(t, err, "form-tracking-event-id-empty")
}

func TestDeleteFormEvent_NotFound(t *testing.T) {
	err := DeleteFormEvent("evt-nonexistent-delete")
	checkError0238(t, err, "form-tracking-event-not-found")
}

func TestClearFormEvents_Success(t *testing.T) {
	formID := "form-synthetic-clear-001"
	ClearFormEvents(formID)

	req1 := baseFormEventReq()
	req1.FormID = formID
	req1.EventID = "evt-clear-001"
	req1.IdempotencyKey = "idem-clear-001"

	req2 := baseFormEventReq()
	req2.FormID = formID
	req2.EventID = "evt-clear-002"
	req2.IdempotencyKey = "idem-clear-002"

	_, _ = TrackFormEvent(req1)
	_, _ = TrackFormEvent(req2)

	err := ClearFormEvents(formID)
	if err != nil {
		t.Fatalf("clear failed: %v", err)
	}

	events, _ := ListFormEvents(formID)
	if len(events) != 0 {
		t.Errorf("expected 0 events after clear, got %d", len(events))
	}
}

func TestClearFormEvents_EmptyFormID(t *testing.T) {
	err := ClearFormEvents("")
	checkError0238(t, err, "form-tracking-form-id-empty")
}

func TestGenerateFormEventDigest_Deterministic(t *testing.T) {
	req := baseFormEventReq()

	digest1 := generateFormEventDigest(req)
	digest2 := generateFormEventDigest(req)

	if digest1 != digest2 {
		t.Errorf("digests should be deterministic: %q vs %q", digest1, digest2)
	}
}

func TestGenerateFormEventDigest_DifferentInputs(t *testing.T) {
	req1 := baseFormEventReq()
	req1.EventID = "evt-digest-001"

	req2 := baseFormEventReq()
	req2.EventID = "evt-digest-002"

	digest1 := generateFormEventDigest(req1)
	digest2 := generateFormEventDigest(req2)

	if digest1 == digest2 {
		t.Error("different inputs should produce different digests")
	}
}

func TestTrackFormEvent_AllEventTypes(t *testing.T) {
	ClearFormEvents("form-synthetic-types")
	types := []string{"created", "viewed", "modified", "submitted", "approved", "rejected", "archived", "deleted"}

	for i, eventType := range types {
		req := baseFormEventReq()
		req.FormID = "form-synthetic-types"
		req.EventID = "evt-type-" + eventType
		req.EventType = eventType
		req.IdempotencyKey = "idem-type-" + eventType

		_, err := TrackFormEvent(req)
		if err != nil {
			t.Errorf("failed to track event type %q: %v", eventType, err)
		}

		if i > 0 {
			// Add spacing to break potential duplicate patterns
			time.Sleep(1 * time.Millisecond)
		}
	}
}

func TestTrackFormEvent_DetailsPreserved(t *testing.T) {
	ClearFormEvents("form-synthetic-details")

	req := baseFormEventReq()
	req.FormID = "form-synthetic-details"
	req.EventID = "evt-details-001"
	req.IdempotencyKey = "idem-details-001"
	req.Details = map[string]string{
		"field_modified": "chief_complaint",
		"previous_value": "empty",
		"new_value":      "chest_pain",
	}

	resp, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("track failed: %v", err)
	}

	if len(resp.Details) != 3 {
		t.Errorf("expected 3 detail entries, got %d", len(resp.Details))
	}
	if resp.Details["field_modified"] != "chief_complaint" {
		t.Error("details not preserved correctly")
	}
}

func TestTrackFormEvent_TimestampParsing(t *testing.T) {
	ClearFormEvents("form-synthetic-timestamp")

	req := baseFormEventReq()
	req.FormID = "form-synthetic-timestamp"
	req.EventID = "evt-timestamp-001"
	req.IdempotencyKey = "idem-timestamp-001"
	req.Timestamp = "2024-06-15T14:30:00Z"

	resp, err := TrackFormEvent(req)
	if err != nil {
		t.Fatalf("track failed: %v", err)
	}

	expectedTime, _ := time.Parse(time.RFC3339, req.Timestamp)
	if !resp.Timestamp.Equal(expectedTime) {
		t.Errorf("timestamp mismatch: expected %v, got %v", expectedTime, resp.Timestamp)
	}
}
