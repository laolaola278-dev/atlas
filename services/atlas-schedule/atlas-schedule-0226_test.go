package schedule

import (
	"encoding/json"
	"strings"
	"testing"
	"time"
)

func TestValidateAuditRequest_Success(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "draft",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	beforeJSON, _ := json.Marshal(beforeState)
	
	afterState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "pending",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	afterJSON, _ := json.Marshal(afterState)
	
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: string(beforeJSON),
			After:  string(afterJSON),
		},
		Reason: "Status transition from draft to pending",
	}
	
	err := ValidateAuditRequest(req)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestValidateAuditRequest_MissingScheduleID(t *testing.T) {
	timestamp := time.Now().UTC().Format(time.RFC3339)
	// Test case: ScheduleID field is omitted
	req := AuditRequest{
		OperationType: "update",
		ActorID:       "synthetic-user-456",
		Timestamp:     timestamp,
		Changes: Changes{
			Before: `{"schedule_id":"sched-A","status":"draft"}`,
			After:  `{"schedule_id":"sched-A","status":"active"}`,
		},
		Reason: "Update schedule status",
	}
	
	err := ValidateAuditRequest(req)
	if err == nil {
		t.Error("expected error for missing schedule_id")
		return
	}
	if !strings.Contains(err.Error(), "schedule_id is required") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_InvalidOperationType(t *testing.T) {
	// Build request with unsupported operation type
	invalidReq := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "invalid-op",
		ActorID:       "synthetic-user-789",
		Timestamp:     time.Now().UTC().Add(time.Hour).Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"sched-B","capacity":100}`,
			After:  `{"schedule_id":"sched-B","capacity":150}`,
		},
		Reason: "Capacity adjustment",
	}
	
	err := ValidateAuditRequest(invalidReq)
	if err == nil {
		t.Error("expected error for invalid operation_type")
	}
	if !strings.Contains(err.Error(), "invalid operation_type") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_NonSyntheticActorID(t *testing.T) {
	// Actor ID without synthetic/test prefix should be rejected
	oneHourAgo := time.Now().UTC().Add(-time.Hour).Format(time.RFC3339)
	badActorReq := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "real-user-123",
		Timestamp:     oneHourAgo,
		Changes: Changes{
			Before: `{"schedule_id":"sched-C","window":"morning"}`,
			After:  `{"schedule_id":"sched-C","window":"afternoon"}`,
		},
		Reason: "Window shift",
	}
	
	err := ValidateAuditRequest(badActorReq)
	if err == nil {
		t.Error("expected error for non-synthetic actor_id")
	}
	if !strings.Contains(err.Error(), "actor_id must use synthetic or test prefix") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_InvalidTimestamp(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     "invalid-timestamp",
		Changes: Changes{
			Before: `{"schedule_id":"sched-E","amount":500}`,
			After:  `{"schedule_id":"sched-E","amount":750}`,
		},
		Reason: "Amount update",
	}
	
	err := ValidateAuditRequest(req)
	if err == nil {
		t.Error("expected error for invalid timestamp")
	}
	if !strings.Contains(err.Error(), "timestamp must be in RFC3339 format") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_MissingChanges(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes:       Changes{},
		Reason:        "Test reason",
	}
	
	err := ValidateAuditRequest(req)
	if err == nil {
		t.Error("expected error for missing changes")
	}
	if !strings.Contains(err.Error(), "at least one of before or after must be provided") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_InvalidJSON(t *testing.T) {
	// Changes.Before contains malformed JSON
	malformedReq := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-999",
		Timestamp:     time.Now().UTC().Add(2 * time.Hour).Format(time.RFC3339),
		Changes: Changes{
			Before: "not-json",
			After:  `{"schedule_id":"sched-D","priority":"high"}`,
		},
		Reason: "Priority change",
	}
	
	err := ValidateAuditRequest(malformedReq)
	if err == nil {
		t.Error("expected error for invalid JSON in before")
	}
	if !strings.Contains(err.Error(), "changes.before must be valid JSON") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateAuditRequest_EmptyReason(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"test-schedule-001","status":"draft","timeframe":"2024-01-01T00:00:00Z"}`,
			After:  `{"schedule_id":"test-schedule-001","status":"pending","timeframe":"2024-01-01T00:00:00Z"}`,
		},
		Reason: "   ",
	}
	
	err := ValidateAuditRequest(req)
	if err == nil {
		t.Error("expected error for empty reason")
	}
	if !strings.Contains(err.Error(), "reason cannot be empty or whitespace") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateNoPHI_ContactPattern(t *testing.T) {
	err := validateNoPHI("Call me at contact-555")
	if err == nil {
		t.Error("expected error for phone number in input")
	}
	if !strings.Contains(err.Error(), "phone number detected") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateNoPHI_RecipientPattern(t *testing.T) {
	err := validateNoPHI("Contact recipient-alpha for details")
	if err == nil {
		t.Error("expected error for email in input")
	}
	if !strings.Contains(err.Error(), "email address detected") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateNoPHI_IdentifierPattern(t *testing.T) {
	err := validateNoPHI("ID is synthetic-999")
	if err == nil {
		t.Error("expected error for SSN in input")
	}
	if !strings.Contains(err.Error(), "SSN-like pattern detected") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateNoPHI_Clean(t *testing.T) {
	err := validateNoPHI("Schedule updated per protocol")
	if err != nil {
		t.Errorf("expected no error for clean input, got %v", err)
	}
}

func TestCheckHumanAdoptionBoundary_ApproveRequiresHuman(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "approve",
		ActorID:       "synthetic-system-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"test-schedule-001","status":"pending","timeframe":"2024-01-01T00:00:00Z"}`,
			After:  `{"schedule_id":"test-schedule-001","status":"approved","timeframe":"2024-01-01T00:00:00Z"}`,
		},
		Reason: "Approval required",
	}
	
	err := CheckHumanAdoptionBoundary(req)
	if err == nil {
		t.Error("expected error for approve operation without human actor")
	}
	if !strings.Contains(err.Error(), "operation 'approve' requires human actor") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestCheckHumanAdoptionBoundary_ApproveWithHuman(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "approve",
		ActorID:       "synthetic-human-clinician-001",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"test-schedule-001","status":"pending","timeframe":"2024-01-01T00:00:00Z"}`,
			After:  `{"schedule_id":"test-schedule-001","status":"approved","timeframe":"2024-01-01T00:00:00Z"}`,
		},
		Reason: "Clinical review completed",
	}
	
	err := CheckHumanAdoptionBoundary(req)
	if err != nil {
		t.Errorf("expected no error for approve with human actor, got %v", err)
	}
}

func TestCheckHumanAdoptionBoundary_UpdateNoHumanRequired(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-system-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"test-schedule-001","status":"draft","timeframe":"2024-01-01T00:00:00Z"}`,
			After:  `{"schedule_id":"test-schedule-001","status":"pending","timeframe":"2024-01-01T00:00:00Z"}`,
		},
		Reason: "Automated status update",
	}
	
	err := CheckHumanAdoptionBoundary(req)
	if err != nil {
		t.Errorf("expected no error for update operation, got %v", err)
	}
}

func TestCreateAuditEntry_Success(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "draft",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	beforeJSON, _ := json.Marshal(beforeState)
	
	afterState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "pending",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	afterJSON, _ := json.Marshal(afterState)
	
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: string(beforeJSON),
			After:  string(afterJSON),
		},
		Reason: "Status transition from draft to pending",
	}
	
	resp, err := CreateAuditEntry(req)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	
	if resp.AuditID == "" {
		t.Error("expected audit_id to be set")
	}
	
	if resp.Status != "recorded" && resp.Status != "exists" {
		t.Errorf("unexpected status: %s", resp.Status)
	}
	
	if resp.RecordedAt == "" {
		t.Error("expected recorded_at to be set")
	}
}

func TestCreateAuditEntry_ValidationFailure(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     time.Now().UTC().Format(time.RFC3339),
		Changes: Changes{
			Before: `{"schedule_id":"test-schedule-001","status":"draft","timeframe":"2024-01-01T00:00:00Z"}`,
			After:  `{"schedule_id":"test-schedule-001","status":"pending","timeframe":"2024-01-01T00:00:00Z"}`,
		},
		Reason: "Test",
	}
	
	_, err := CreateAuditEntry(req)
	if err == nil {
		t.Error("expected error for invalid request")
	}
	if !strings.Contains(err.Error(), "validation failed") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestGenerateAuditID_Deterministic(t *testing.T) {
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     "2024-01-01T00:00:00Z",
		Changes: Changes{
			Before: `{"status":"draft"}`,
			After:  `{"status":"pending"}`,
		},
	}
	
	id1 := generateAuditID(req)
	id2 := generateAuditID(req)
	
	if id1 != id2 {
		t.Errorf("audit IDs should be deterministic, got %s and %s", id1, id2)
	}
	
	if !strings.HasPrefix(id1, "audit-") {
		t.Errorf("audit ID should have 'audit-' prefix, got %s", id1)
	}
}

func TestValidateSchema_Success(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "draft",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	beforeJSON, _ := json.Marshal(beforeState)
	
	afterState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "pending",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	afterJSON, _ := json.Marshal(afterState)
	
	changes := Changes{
		Before: string(beforeJSON),
		After:  string(afterJSON),
	}
	
	err := ValidateSchema(changes)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestValidateSchema_MissingRequiredField(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "draft",
		// missing timeframe
	}
	beforeJSON, _ := json.Marshal(beforeState)
	
	changes := Changes{
		Before: string(beforeJSON),
		After:  "",
	}
	
	err := ValidateSchema(changes)
	if err == nil {
		t.Error("expected error for missing required field")
	}
	if !strings.Contains(err.Error(), "missing required field") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateSchema_InvalidStatus(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "invalid-status",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	beforeJSON, _ := json.Marshal(beforeState)
	afterState := map[string]interface{}{}
	afterJSON, _ := json.Marshal(afterState)
	
	changes := Changes{
		Before: string(beforeJSON),
		After:  string(afterJSON),
	}
	
	err := ValidateSchema(changes)
	if err == nil {
		t.Error("expected error for invalid status")
	}
	if !strings.Contains(err.Error(), "invalid status value") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestRetrieveAuditTrail_Success(t *testing.T) {
	trail, err := RetrieveAuditTrail("test-schedule-001")
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	
	if trail == nil {
		t.Error("expected non-nil trail")
	}
}

func TestRetrieveAuditTrail_MissingScheduleID(t *testing.T) {
	_, err := RetrieveAuditTrail("")
	if err == nil {
		t.Error("expected error for missing schedule_id")
	}
	if !strings.Contains(err.Error(), "schedule_id is required") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestRetrieveAuditTrail_InvalidScheduleID(t *testing.T) {
	_, err := RetrieveAuditTrail("invalid-id")
	if err == nil {
		t.Error("expected error for invalid schedule_id")
	}
	if !strings.Contains(err.Error(), "schedule_id must use schedule- or test-schedule- prefix") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestCheckRepeatability_Success(t *testing.T) {
	beforeState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "draft",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	beforeJSON, _ := json.Marshal(beforeState)
	
	afterState := map[string]interface{}{
		"schedule_id": "test-schedule-001",
		"status":      "pending",
		"timeframe":   "2024-01-01T00:00:00Z",
	}
	afterJSON, _ := json.Marshal(afterState)
	
	req := AuditRequest{
		ScheduleID:    "test-schedule-001",
		OperationType: "update",
		ActorID:       "synthetic-user-123",
		Timestamp:     "2024-01-01T00:00:00Z",
		Changes: Changes{
			Before: string(beforeJSON),
			After:  string(afterJSON),
		},
		Reason: "Test",
	}
	
	err := CheckRepeatability(req)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestValidateTerminology_ValidTerms(t *testing.T) {
	validTerms := []string{"create", "update", "delete", "rollback", "approve", "reject"}
	
	for _, term := range validTerms {
		err := validateTerminology(term)
		if err != nil {
			t.Errorf("expected no error for term '%s', got %v", term, err)
		}
	}
}

func TestValidateTerminology_InvalidTerm(t *testing.T) {
	err := validateTerminology("invalid-term")
	if err == nil {
		t.Error("expected error for invalid term")
	}
	if !strings.Contains(err.Error(), "not in approved terminology") {
		t.Errorf("unexpected error message: %v", err)
	}
}
