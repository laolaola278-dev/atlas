package workflow

import (
	"testing"
	"time"
)

func baseWorkflowTraceReq() *WorkflowTraceRequest {
	return &WorkflowTraceRequest{
		TraceID:        "synthetic-trace-test-0245",
		WorkflowID:     "synthetic-workflow-trace-0245",
		StepID:         "step-start-0245",
		StepTitle:      "Initial Step",
		StepStatus:     "completed",
		StepStartTime:  time.Now().Add(-5 * time.Minute),
		StepEndTime:    time.Now(),
		StepDuration:   300,
		IdempotencyKey: "workflow-trace-idempotency-key-0245",
		Metadata:       map[string]string{"step_type": "initialization"},
	}
}

func TestValidateWorkflowTraceRequest_Valid(t *testing.T) {
	req := baseWorkflowTraceReq()
	err := ValidateWorkflowTraceRequest(req)
	if err != nil {
		t.Fatalf("expected valid request, got error: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_NilRequest(t *testing.T) {
	err := ValidateWorkflowTraceRequest(nil)
	if err == nil || err.Error() != "trace request is required" {
		t.Fatalf("expected nil request error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.IdempotencyKey = "" // Clear key
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "idempotency key is required" {
		t.Fatalf("expected idempotency key required error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.IdempotencyKey = "short" // Trigger minimum length check
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "idempotency key must be at least 16 characters" {
		t.Fatalf("expected short idempotency key error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_EmptyTraceID(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.TraceID = "" // Clear trace ID
	err := ValidateWorkflowTraceRequest(req)
	// Expect trace ID validation error for empty field
	if err == nil || err.Error() != "trace ID is required" {
		t.Fatalf("expected trace ID required error, got: %v", err)
		t.Fatalf("expected trace ID required error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_InvalidTraceIDPrefix(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.TraceID = "trace-invalid-0245" // Missing synthetic prefix
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "trace ID must start with 'synthetic-trace-'" {
		t.Fatalf("expected invalid trace ID prefix error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_EmptyWorkflowID(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.WorkflowID = "" // Clear workflow ID
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "workflow ID is required" {
		t.Fatalf("expected workflow ID required error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_EmptyStepID(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.StepID = "" // Clear step ID field
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "step ID is required" {
		t.Fatalf("expected step ID required error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_BlankStepTitle(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.StepTitle = "   " // Whitespace only
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "step title cannot be blank" {
		t.Fatalf("expected blank step title error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_EmptyStepStatus(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.StepStatus = "" // Empty status field
	// Step status validation should catch empty value
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "step status is required" {
		t.Fatalf("expected step status required error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_InvalidStepStatus(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.StepStatus = "unknown" // Invalid status value
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "step status must be one of: pending, running, completed, failed, skipped" {
		t.Fatalf("expected invalid step status error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_NegativeDuration(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.StepDuration = -100
	err := ValidateWorkflowTraceRequest(req)
	if err == nil || err.Error() != "step duration cannot be negative" {
		t.Fatalf("expected negative duration error, got: %v", err)
	}
}

func TestValidateWorkflowTraceRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseWorkflowTraceReq()
	req.Metadata = map[string]string{"patient_identifier": "synthetic-value"}
	err := ValidateWorkflowTraceRequest(req)
	if err == nil {
		t.Fatalf("expected PHI pattern in metadata key error, got nil")
	}
}

func TestCreateWorkflowTrace_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	req := baseWorkflowTraceReq()
	trace, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("expected successful trace creation, got error: %v", err)
	}

	if trace.TraceID != req.TraceID {
		t.Fatalf("expected trace ID %s, got %s", req.TraceID, trace.TraceID)
	}
	if trace.TraceChecksum == "" {
		t.Fatalf("expected non-empty trace checksum")
	}
}

func TestCreateWorkflowTrace_Idempotency(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)
	// Test idempotency behavior

	req := baseWorkflowTraceReq()
	trace1, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("first trace creation should succeed, got: %v", err)
	}

	trace2, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("idempotent trace creation should succeed, got: %v", err)
	}

	// Both traces should have matching IDs from idempotency
	if trace1.TraceID != trace2.TraceID {
		t.Fatalf("expected same trace, got different IDs")
	}
}

func TestCreateWorkflowTrace_DuplicateTraceID(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	req1 := baseWorkflowTraceReq()
	_, err := CreateWorkflowTrace(req1)
	if err != nil {
		t.Fatalf("first trace should succeed, got: %v", err)
	}

	req2 := baseWorkflowTraceReq()
	req2.IdempotencyKey = "different-idempotency-key-0245" // Change idempotency key
	_, err = CreateWorkflowTrace(req2)
	if err == nil {
		t.Fatalf("expected duplicate trace ID error, got nil")
	}
}

func TestCreateWorkflowTrace_ValidationFailure(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	req := baseWorkflowTraceReq()
	req.WorkflowID = "" // Trigger validation error
	_, err := CreateWorkflowTrace(req)
	if err == nil {
		t.Fatalf("expected validation error, got nil")
	}
}

func TestGetWorkflowTrace_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)
	// Retrieve existing trace

	req := baseWorkflowTraceReq()
	created, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("trace creation should succeed, got: %v", err)
	}

	retrieved, err := GetWorkflowTrace(created.TraceID)
	if err != nil {
		t.Fatalf("expected successful retrieval, got error: %v", err)
	}

	if retrieved.TraceID != created.TraceID {
		t.Fatalf("expected trace ID %s, got %s", created.TraceID, retrieved.TraceID)
	}
}

func TestGetWorkflowTrace_EmptyID(t *testing.T) {
	_, err := GetWorkflowTrace("")
	// Get operation should reject empty ID
	if err == nil || err.Error() != "trace ID is required" {
		t.Fatalf("expected trace ID required error, got: %v", err)
	}
}

func TestGetWorkflowTrace_NotFound(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)

	_, err := GetWorkflowTrace("synthetic-trace-nonexistent-0245")
	if err == nil || err.Error() != "trace not found" {
		t.Fatalf("expected trace not found error, got: %v", err)
	}
}

func TestUpdateWorkflowTrace_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)
	// Modify trace attributes

	req := baseWorkflowTraceReq()
	created, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("trace creation should succeed, got: %v", err)
	}
	originalChecksum := created.TraceChecksum

	req.StepStatus = "failed"
	req.StepDuration = 600
	req.StepEndTime = time.Now().Add(1 * time.Hour)
	updated, err := UpdateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("expected successful update, got error: %v", err)
	}

	if updated.StepStatus != "failed" {
		t.Fatalf("expected status 'failed', got %s", updated.StepStatus)
	}
	if updated.StepDuration != 600 {
		t.Fatalf("expected duration 600, got %d", updated.StepDuration)
	}
	if updated.TraceChecksum == originalChecksum {
		t.Fatalf("expected checksum to change after update, original=%s updated=%s", originalChecksum, updated.TraceChecksum)
	}
}

func TestUpdateWorkflowTrace_NotFound(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)

	req := baseWorkflowTraceReq()
	req.TraceID = "synthetic-trace-missing-0245"
	_, err := UpdateWorkflowTrace(req)
	if err == nil || err.Error() != "trace not found" {
		t.Fatalf("expected trace not found error, got: %v", err)
	}
}

func TestDeleteWorkflowTrace_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)
	// Remove trace from store

	req := baseWorkflowTraceReq()
	created, err := CreateWorkflowTrace(req)
	if err != nil {
		t.Fatalf("trace creation should succeed, got: %v", err)
	}

	err = DeleteWorkflowTrace(created.TraceID)
	if err != nil {
		t.Fatalf("expected successful deletion, got error: %v", err)
	}

	_, err = GetWorkflowTrace(created.TraceID)
	if err == nil {
		t.Fatalf("expected trace not found after deletion")
	}
}

func TestDeleteWorkflowTrace_EmptyID(t *testing.T) {
	err := DeleteWorkflowTrace("")
	if err == nil || err.Error() != "trace ID is required" {
		t.Fatalf("expected trace ID required error, got: %v", err)
	}
}

func TestDeleteWorkflowTrace_NotFound(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)

	err := DeleteWorkflowTrace("synthetic-trace-nonexistent-0245")
	if err == nil || err.Error() != "trace not found" {
		t.Fatalf("expected trace not found error, got: %v", err)
	}
}

func TestListWorkflowTraces_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	req1 := baseWorkflowTraceReq()
	req1.TraceID = "synthetic-trace-list-1-0245"
	req1.IdempotencyKey = "list-trace-key-1-0245"
	_, err := CreateWorkflowTrace(req1)
	if err != nil {
		t.Fatalf("first trace creation should succeed, got: %v", err)
	}

	req2 := baseWorkflowTraceReq()
	req2.TraceID = "synthetic-trace-list-2-0245"
	req2.IdempotencyKey = "list-trace-key-2-0245"
	_, err = CreateWorkflowTrace(req2)
	if err != nil {
		t.Fatalf("second trace creation should succeed, got: %v", err)
	}

	traces := ListWorkflowTraces()
	if len(traces) != 2 {
		t.Fatalf("expected 2 traces, got %d", len(traces))
	}
}

func TestListWorkflowTraces_Empty(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)

	traces := ListWorkflowTraces()
	if len(traces) != 0 {
		t.Fatalf("expected 0 traces, got %d", len(traces))
	}
}

func TestListWorkflowTracesByWorkflow_Success(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	// Create first trace with workflow A
	req1 := baseWorkflowTraceReq()
	req1.TraceID = "synthetic-trace-workflow-1-0245"
	req1.IdempotencyKey = "workflow-trace-key-1-0245"
	req1.WorkflowID = "synthetic-workflow-A-0245"
	_, err := CreateWorkflowTrace(req1)
	if err != nil {
		t.Fatalf("first trace creation should succeed, got: %v", err)
	}

	req2 := baseWorkflowTraceReq()
	req2.TraceID = "synthetic-trace-workflow-2-0245"
	req2.IdempotencyKey = "workflow-trace-key-2-0245"
	req2.WorkflowID = "synthetic-workflow-B-0245"
	_, err = CreateWorkflowTrace(req2)
	if err != nil {
		t.Fatalf("second trace creation should succeed, got: %v", err)
	}

	traces := ListWorkflowTracesByWorkflow("synthetic-workflow-A-0245")
	if len(traces) != 1 {
		t.Fatalf("expected 1 trace for workflow A, got %d", len(traces))
	}
	if traces[0].WorkflowID != "synthetic-workflow-A-0245" {
		t.Fatalf("expected workflow ID 'synthetic-workflow-A-0245', got %s", traces[0].WorkflowID)
	}
}

func TestGenerateTraceChecksum_Deterministic(t *testing.T) {
	req := baseWorkflowTraceReq()

	checksum1 := GenerateTraceChecksum(req)
	checksum2 := GenerateTraceChecksum(req)

	if checksum1 != checksum2 {
		t.Fatalf("expected deterministic checksums, got different values")
	}
}

func TestGenerateTraceChecksum_DifferentInputs(t *testing.T) {
	req1 := baseWorkflowTraceReq()
	req1.StepStatus = "completed"

	req2 := baseWorkflowTraceReq()
	req2.StepStatus = "failed"

	checksum1 := GenerateTraceChecksum(req1)
	checksum2 := GenerateTraceChecksum(req2)

	if checksum1 == checksum2 {
		t.Fatalf("expected different checksums for different inputs")
	}
}

func TestCreateWorkflowTrace_AllStepStatuses(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	// Test all five step statuses
	statuses := []string{"pending", "running", "completed", "failed", "skipped"}

	for _, status := range statuses {
		req := baseWorkflowTraceReq()
		req.TraceID = "synthetic-trace-status-" + status + "-0245"
		req.IdempotencyKey = "trace-status-key-" + status + "-0245"
		req.StepStatus = status

		trace, err := CreateWorkflowTrace(req)
		if err != nil {
			t.Fatalf("trace creation for status '%s' should succeed, got: %v", status, err)
		}

		if trace.StepStatus != status {
			t.Fatalf("expected status '%s', got '%s'", status, trace.StepStatus)
		}
	}
}

func TestListWorkflowTracesByWorkflow_MultipleMatches(t *testing.T) {
	workflowTraceStore = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)

	workflowID := "synthetic-workflow-multi-0245"

	for i := 1; i <= 3; i++ {
		req := baseWorkflowTraceReq()
		req.TraceID = "synthetic-trace-multi-" + string(rune('0'+i)) + "-0245"
		req.IdempotencyKey = "multi-trace-key-" + string(rune('0'+i)) + "-0245"
		req.WorkflowID = workflowID

		_, err := CreateWorkflowTrace(req)
		if err != nil {
			t.Fatalf("trace %d creation should succeed, got: %v", i, err)
		}
	}

	traces := ListWorkflowTracesByWorkflow(workflowID)
	if len(traces) != 3 {
		t.Fatalf("expected 3 traces for workflow, got %d", len(traces))
	}
}
