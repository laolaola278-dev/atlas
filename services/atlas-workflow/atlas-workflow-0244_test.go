package workflow

import (
	"fmt"
	"testing"
	"time"
)

func baseWorkflowEventReq() *WorkflowEventRequest {
	return &WorkflowEventRequest{
		EventID:          "synthetic-event-base-0244",
		WorkflowID:       "synthetic-workflow-0244",
		EventType:        "workflow-started",
		EventPayload:     "synthetic-payload-0244",
		DeduplicationTTL: 300,
		IdempotencyKey:   "base-workflow-event-key-0244",
		Metadata:         map[string]string{"category": "test"},
	}
}

func TestValidateWorkflowEventRequest_Valid(t *testing.T) {
	req := baseWorkflowEventReq()
	if err := ValidateWorkflowEventRequest(req); err != nil {
		t.Fatalf("expected valid request, got error: %v", err)
	}
}

func TestValidateWorkflowEventRequest_NilRequest(t *testing.T) {
	err := ValidateWorkflowEventRequest(nil)
	if err == nil || err.Error() != "request cannot be nil" {
		t.Fatalf("expected nil request error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseWorkflowEventReq()
	req.IdempotencyKey = ""
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "idempotency key is required" {
		t.Fatalf("expected idempotency key required error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseWorkflowEventReq()
	req.IdempotencyKey = "short" // Trigger length validation
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "idempotency key must be at least 16 characters" {
		t.Fatalf("expected short idempotency key error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_EmptyEventID(t *testing.T) {
	req := baseWorkflowEventReq()
	req.EventID = "" // Clear event ID to trigger validation
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "event ID is required" {
		t.Fatalf("expected event ID required error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_InvalidEventIDPrefix(t *testing.T) {
	req := baseWorkflowEventReq()
	// Missing synthetic prefix to trigger validation
	req.EventID = "event-invalid-0244"
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "event ID must start with 'synthetic-event-'" {
		t.Fatalf("expected invalid event ID prefix error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_EmptyWorkflowID(t *testing.T) {
	req := baseWorkflowEventReq()
	req.WorkflowID = "" // Clear workflow ID
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "workflow ID is required" {
		t.Fatalf("expected workflow ID required error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_EmptyEventType(t *testing.T) {
	req := baseWorkflowEventReq()
	req.EventType = ""
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "event type is required" {
		t.Fatalf("expected event type required error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_InvalidEventType(t *testing.T) {
	req := baseWorkflowEventReq()
	req.EventType = "invalid-type"
	err := ValidateWorkflowEventRequest(req)
	if err == nil {
		t.Fatalf("expected invalid event type error, got nil")
	}
}

func TestValidateWorkflowEventRequest_EmptyEventPayload(t *testing.T) {
	req := baseWorkflowEventReq()
	req.EventPayload = ""
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "event payload is required" {
		t.Fatalf("expected event payload required error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_NegativeTTL(t *testing.T) {
	req := baseWorkflowEventReq()
	req.DeduplicationTTL = -10
	err := ValidateWorkflowEventRequest(req)
	if err == nil || err.Error() != "deduplication TTL must be positive" {
		t.Fatalf("expected negative TTL error, got: %v", err)
	}
}

func TestValidateWorkflowEventRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseWorkflowEventReq()
	req.Metadata = map[string]string{"patient-data": "value"}
	err := ValidateWorkflowEventRequest(req)
	if err == nil {
		t.Fatalf("expected PHI pattern error, got nil")
	}
}

func TestCreateWorkflowEvent_Success(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	req := baseWorkflowEventReq()
	event, err := CreateWorkflowEvent(req)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if event.EventID != req.EventID {
		t.Fatalf("expected EventID %s, got %s", req.EventID, event.EventID)
	}
}

func TestCreateWorkflowEvent_Idempotency(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	req := baseWorkflowEventReq()
	event1, _ := CreateWorkflowEvent(req)
	event2, _ := CreateWorkflowEvent(req)

	if event1.EventID != event2.EventID {
		t.Fatalf("expected same event, got different IDs")
	}
}

func TestCreateWorkflowEvent_DuplicateDetection(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time) // Duplicate fingerprint tracking

	req1 := baseWorkflowEventReq()
	_, err := CreateWorkflowEvent(req1)
	if err != nil {
		t.Fatalf("first event should succeed, got: %v", err)
	}

	req2 := baseWorkflowEventReq()
	req2.EventID = "synthetic-event-duplicate-0244"
	req2.IdempotencyKey = "duplicate-workflow-event-key-0244"
	_, err = CreateWorkflowEvent(req2)
	if err == nil {
		t.Fatalf("expected duplicate event error, got nil")
	}
}

func TestCreateWorkflowEvent_ValidationFailure(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)

	req := baseWorkflowEventReq()
	// Empty workflow ID triggers validation failure
	req.WorkflowID = ""
	_, err := CreateWorkflowEvent(req)
	if err == nil {
		t.Fatalf("expected validation error, got nil")
	}
}

func TestGetWorkflowEvent_Success(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	req := baseWorkflowEventReq()
	created, _ := CreateWorkflowEvent(req)
	retrieved, err := GetWorkflowEvent(created.EventID)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}
	if retrieved.EventID != created.EventID {
		t.Fatalf("expected EventID %s, got %s", created.EventID, retrieved.EventID)
	}
}

func TestGetWorkflowEvent_EmptyID(t *testing.T) {
	_, err := GetWorkflowEvent("")
	if err == nil || err.Error() != "event ID cannot be empty" {
		t.Fatalf("expected empty ID error, got: %v", err)
	}
}

func TestGetWorkflowEvent_NotFound(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)

	_, err := GetWorkflowEvent("synthetic-event-missing-0244")
	if err == nil {
		t.Fatalf("expected not found error, got nil")
	}
}

func TestListWorkflowEvents_Success(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	for i := 0; i < 3; i++ {
		req := baseWorkflowEventReq()
		req.EventID = fmt.Sprintf("synthetic-event-list-%d-0244", i)
		req.IdempotencyKey = fmt.Sprintf("list-workflow-event-key-%d-0244", i)
		req.EventPayload = fmt.Sprintf("synthetic-payload-list-%d-0244", i)
		CreateWorkflowEvent(req)
	}

	events := ListWorkflowEvents()
	if len(events) != 3 {
		t.Fatalf("expected 3 events, got %d", len(events))
	}
}

func TestListWorkflowEvents_Empty(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)

	events := ListWorkflowEvents()
	if len(events) != 0 {
		t.Fatalf("expected 0 events, got %d", len(events))
	}
}

func TestListWorkflowEventsByWorkflow_Success(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	targetWorkflow := "synthetic-workflow-target-0244"
	for i := 0; i < 2; i++ {
		req := baseWorkflowEventReq()
		req.EventID = fmt.Sprintf("synthetic-event-target-%d-0244", i)
		req.WorkflowID = targetWorkflow
		req.IdempotencyKey = fmt.Sprintf("target-workflow-event-key-%d-0244", i)
		req.EventPayload = fmt.Sprintf("payload-%d", i)
		CreateWorkflowEvent(req)
	}

	req := baseWorkflowEventReq()
	req.EventID = "synthetic-event-other-0244"
	req.WorkflowID = "synthetic-workflow-other-0244"
	req.IdempotencyKey = "other-workflow-event-key-0244"
	CreateWorkflowEvent(req)

	events := ListWorkflowEventsByWorkflow(targetWorkflow)
	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d", len(events))
	}
}

func TestDeleteWorkflowEvent_Success(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	req := baseWorkflowEventReq()
	event, _ := CreateWorkflowEvent(req)
	err := DeleteWorkflowEvent(event.EventID)
	if err != nil {
		t.Fatalf("expected no error, got: %v", err)
	}

	_, err = GetWorkflowEvent(event.EventID)
	if err == nil {
		t.Fatalf("expected not found error after deletion, got nil")
	}
}

func TestDeleteWorkflowEvent_EmptyID(t *testing.T) {
	err := DeleteWorkflowEvent("")
	if err == nil || err.Error() != "event ID cannot be empty" {
		t.Fatalf("expected empty ID error, got: %v", err)
	}
}

func TestDeleteWorkflowEvent_NotFound(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)

	err := DeleteWorkflowEvent("synthetic-event-missing-0244")
	if err == nil {
		t.Fatalf("expected not found error, got nil")
	}
}

func TestGenerateEventFingerprint_Deterministic(t *testing.T) {
	fp1 := GenerateEventFingerprint("wf-0244", "workflow-started", "payload-0244")
	fp2 := GenerateEventFingerprint("wf-0244", "workflow-started", "payload-0244")

	if fp1 != fp2 {
		t.Fatalf("expected deterministic fingerprints, got %s and %s", fp1, fp2)
	}
}

func TestGenerateEventFingerprint_DifferentInputs(t *testing.T) {
	// First fingerprint with workflow-started type
	fp1 := GenerateEventFingerprint("wf-0244", "workflow-started", "payload-0244")
	// Second fingerprint with step-executed type to ensure different hash
	fp2 := GenerateEventFingerprint("wf-0244", "step-executed", "payload-0244")

	if fp1 == fp2 {
		t.Fatalf("expected different fingerprints for different inputs")
	}
}

func TestCreateWorkflowEvent_AllEventTypes(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	eventTypes := []string{"workflow-started", "workflow-completed", "step-executed", "step-failed", "timeout-triggered"}

	for _, eventType := range eventTypes {
		req := baseWorkflowEventReq()
		req.IdempotencyKey = "all-types-test-" + eventType + "-0244"
		req.EventID = "synthetic-event-" + eventType + "-0244"
		req.EventType = eventType
		req.EventPayload = "payload-" + eventType
		// Create event with specific type
		event, err := CreateWorkflowEvent(req)
		if err != nil {
			t.Errorf("Expected no error for type %s, got %v", eventType, err)
		}
		if event.EventType != eventType {
			t.Errorf("Expected EventType %s, got %s", eventType, event.EventType)
		}
	}
}

func TestListWorkflowEventsByWorkflow_MultipleMatches(t *testing.T) {
	workflowEventStore = make(map[string]*WorkflowEvent)
	workflowEventIdempotency = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)

	workflowID := "synthetic-workflow-multi-match-0244"
	for i := 0; i < 3; i++ {
		req := baseWorkflowEventReq()
		req.IdempotencyKey = fmt.Sprintf("multi-match-test-%d-0244", i)
		req.EventID = fmt.Sprintf("synthetic-event-multi-%d-0244", i)
		req.WorkflowID = workflowID
		req.EventPayload = fmt.Sprintf("payload-%d", i)
		CreateWorkflowEvent(req)
	}

	events := ListWorkflowEventsByWorkflow(workflowID)
	if len(events) != 3 {
		t.Fatalf("expected 3 matching events, got %d", len(events))
	}
}
