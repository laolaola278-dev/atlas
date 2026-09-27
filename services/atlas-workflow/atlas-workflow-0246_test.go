package workflow

import (
	"fmt"
	"strings"
	"testing"
)

// Failure isolation tests validate request fields and CRUD operations

func baseFailureIsolationReq() *WorkflowFailureIsolationRequest {
	return &WorkflowFailureIsolationRequest{
		IdempotencyKey:  "test-isolation-key-12345",
		IsolationID:     "isolation-test-001",
		WorkflowID:      "workflow-test-001",
		IsolationScope:  "step-level",
		IsolationMode:   "continue",
		FailurePatterns: []string{"timeout", "network-error"},
		RetryStrategy:   "exponential-backoff",
		Metadata:        map[string]string{"region": "us-east-1"},
	}
}

// Validation tests
func TestValidateWorkflowFailureIsolationRequest_Valid(t *testing.T) {
	req := baseFailureIsolationReq()
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err != nil {
		t.Fatalf("expected valid request, got error: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_NilRequest(t *testing.T) {
	err := ValidateWorkflowFailureIsolationRequest(nil)
	if err == nil || err.Error() != "request cannot be nil" {
		t.Fatalf("expected nil request error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IdempotencyKey = ""
	// Idempotency key is mandatory for all failure isolation requests
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "idempotency key is required" {
		t.Fatalf("expected idempotency key required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IdempotencyKey = "short" // Key length validation
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "idempotency key must be at least 16 characters" {
		t.Fatalf("expected idempotency key length error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyIsolationID(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationID = "" // Clear isolation ID
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation ID is required" {
		t.Fatalf("expected isolation ID required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_InvalidIsolationIDPrefix(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationID = "invalid-001" // Missing 'isolation-' prefix
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation ID must start with 'isolation-'" {
		t.Fatalf("expected isolation ID prefix error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyWorkflowID(t *testing.T) {
	req := baseFailureIsolationReq()
	req.WorkflowID = "" // Workflow ID validation required
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "workflow ID is required" {
		t.Fatalf("expected workflow ID required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyIsolationScope(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationScope = "" // Empty scope field
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation scope is required" {
		t.Fatalf("expected isolation scope required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_InvalidIsolationScope(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationScope = "invalid-scope" // Invalid scope value
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation scope must be one of: step-level, workflow-level, tenant-level" {
		t.Fatalf("expected invalid isolation scope error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyIsolationMode(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationMode = ""
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation mode is required" {
		t.Fatalf("expected isolation mode required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_InvalidIsolationMode(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationMode = "unknown" // Invalid mode value
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "isolation mode must be one of: continue, abort, rollback" {
		t.Fatalf("expected invalid isolation mode error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyFailurePatterns(t *testing.T) {
	req := baseFailureIsolationReq()
	req.FailurePatterns = []string{}
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || err.Error() != "at least one failure pattern is required" {
		t.Fatalf("expected failure patterns required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_EmptyRetryStrategy(t *testing.T) {
	req := baseFailureIsolationReq()
	req.RetryStrategy = ""
	// Retry strategy defines how failures should be handled
	err := ValidateWorkflowFailureIsolationRequest(req)
	// Validation must reject empty retry strategy
	if err == nil || err.Error() != "retry strategy is required" {
		t.Fatalf("expected retry strategy required error, got: %v", err)
	}
}

func TestValidateWorkflowFailureIsolationRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseFailureIsolationReq()
	req.Metadata = map[string]string{"patient_id": "synthetic-001"}
	err := ValidateWorkflowFailureIsolationRequest(req)
	if err == nil || !strings.Contains(err.Error(), "prohibited PHI pattern") {
		t.Fatalf("expected PHI pattern error, got: %v", err)
	}
}

// CRUD operation tests
func TestCreateWorkflowFailureIsolation_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	isolation, err := CreateWorkflowFailureIsolation(req)
	if err != nil {
		t.Fatalf("expected successful creation, got error: %v", err)
	}

	if isolation.IsolationID != req.IsolationID {
		t.Errorf("expected isolation ID %s, got %s", req.IsolationID, isolation.IsolationID)
	}
	if isolation.Checksum == "" {
		t.Error("expected non-empty checksum")
	}
}

func TestCreateWorkflowFailureIsolation_Idempotency(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	isolation1, err := CreateWorkflowFailureIsolation(req)
	if err != nil {
		t.Fatalf("first creation failed: %v", err)
	}

	isolation2, err := CreateWorkflowFailureIsolation(req)
	if err != nil {
		t.Fatalf("second creation failed: %v", err)
	}

	if isolation1.IsolationID != isolation2.IsolationID {
		t.Error("idempotency failed: different isolations returned")
	}
}

func TestCreateWorkflowFailureIsolation_DuplicateIsolationID(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req1 := baseFailureIsolationReq()
	_, err := CreateWorkflowFailureIsolation(req1)
	if err != nil {
		t.Fatalf("first creation failed: %v", err)
	}

	req2 := baseFailureIsolationReq()
	req2.IdempotencyKey = "different-key-67890"
	_, err = CreateWorkflowFailureIsolation(req2)
	if err == nil || !strings.Contains(err.Error(), "already exists") {
		t.Fatalf("expected duplicate isolation ID error, got: %v", err)
	}
}

func TestCreateWorkflowFailureIsolation_ValidationFailure(t *testing.T) {
	req := baseFailureIsolationReq()
	req.IsolationScope = ""
	_, err := CreateWorkflowFailureIsolation(req)
	if err == nil {
		t.Fatal("expected validation error")
	}
}

func TestGetWorkflowFailureIsolation_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	created, _ := CreateWorkflowFailureIsolation(req)

	retrieved, err := GetWorkflowFailureIsolation(created.IsolationID)
	if err != nil {
		t.Fatalf("expected successful retrieval, got error: %v", err)
	}

	if retrieved.IsolationID != created.IsolationID {
		t.Error("retrieved isolation does not match created")
	}
}

func TestGetWorkflowFailureIsolation_EmptyID(t *testing.T) {
	// Get operation should reject empty ID
	_, err := GetWorkflowFailureIsolation("")
	if err == nil || err.Error() != "isolation ID is required" {
		t.Fatalf("expected empty ID error, got: %v", err)
	}
}

func TestGetWorkflowFailureIsolation_NotFound(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	_, err := GetWorkflowFailureIsolation("isolation-nonexistent")
	if err == nil || !strings.Contains(err.Error(), "not found") {
		t.Fatalf("expected not found error, got: %v", err)
	}
}

func TestUpdateWorkflowFailureIsolation_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	created, _ := CreateWorkflowFailureIsolation(req)
	originalChecksum := created.Checksum

	req.IsolationMode = "abort"
	updated, err := UpdateWorkflowFailureIsolation(req)
	if err != nil {
		t.Fatalf("expected successful update, got error: %v", err)
	}

	if updated.IsolationMode != "abort" {
		t.Errorf("expected mode 'abort', got %s", updated.IsolationMode)
	}
	if updated.Checksum == originalChecksum {
		t.Error("checksum should change after update")
	}
}

func TestUpdateWorkflowFailureIsolation_NotFound(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	req.IsolationID = "isolation-nonexistent"
	// Update should fail when target isolation does not exist
	_, err := UpdateWorkflowFailureIsolation(req)
	if err == nil || !strings.Contains(err.Error(), "not found") {
		t.Fatalf("expected not found error, got: %v", err)
	}
}

func TestDeleteWorkflowFailureIsolation_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req := baseFailureIsolationReq()
	created, _ := CreateWorkflowFailureIsolation(req)

	err := DeleteWorkflowFailureIsolation(created.IsolationID)
	if err != nil {
		t.Fatalf("expected successful deletion, got error: %v", err)
	}

	_, err = GetWorkflowFailureIsolation(created.IsolationID)
	if err == nil {
		t.Fatal("expected not found error after deletion")
	}
}

func TestDeleteWorkflowFailureIsolation_EmptyID(t *testing.T) {
	err := DeleteWorkflowFailureIsolation("")
	if err == nil || err.Error() != "isolation ID is required" {
		t.Fatalf("expected empty ID error, got: %v", err)
	}
}

func TestDeleteWorkflowFailureIsolation_NotFound(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	// Delete operation must reject nonexistent isolation
	err := DeleteWorkflowFailureIsolation("isolation-nonexistent")
	if err == nil || !strings.Contains(err.Error(), "not found") {
		t.Fatalf("expected not found error, got: %v", err)
	}
}

func TestListWorkflowFailureIsolations_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req1 := baseFailureIsolationReq()
	CreateWorkflowFailureIsolation(req1)

	req2 := baseFailureIsolationReq()
	req2.IdempotencyKey = "another-key-67890"
	req2.IsolationID = "isolation-test-002"
	CreateWorkflowFailureIsolation(req2)

	isolations := ListWorkflowFailureIsolations()
	if len(isolations) != 2 {
		t.Errorf("expected 2 isolations, got %d", len(isolations))
	}
}

func TestListWorkflowFailureIsolations_Empty(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	isolations := ListWorkflowFailureIsolations()
	if len(isolations) != 0 {
		t.Errorf("expected 0 isolations, got %d", len(isolations))
	}
}

func TestListWorkflowFailureIsolationsByWorkflow_Success(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	req1 := baseFailureIsolationReq()
	req1.WorkflowID = "workflow-alpha"
	CreateWorkflowFailureIsolation(req1)

	req2 := baseFailureIsolationReq()
	req2.IdempotencyKey = "another-key-67890"
	req2.IsolationID = "isolation-test-002"
	req2.WorkflowID = "workflow-beta"
	CreateWorkflowFailureIsolation(req2)

	isolations := ListWorkflowFailureIsolationsByWorkflow("workflow-alpha")
	if len(isolations) != 1 {
		t.Errorf("expected 1 isolation, got %d", len(isolations))
	}
	if isolations[0].WorkflowID != "workflow-alpha" {
		t.Error("workflow ID mismatch")
	}
}

func TestGenerateIsolationChecksum_Deterministic(t *testing.T) {
	isolation := &WorkflowFailureIsolation{
		IsolationID:     "isolation-test-001",
		WorkflowID:      "workflow-test-001",
		IsolationScope:  "step-level",
		IsolationMode:   "continue",
		FailurePatterns: []string{"timeout", "network-error"},
		RetryStrategy:   "exponential-backoff",
	}

	checksum1 := GenerateIsolationChecksum(isolation)
	checksum2 := GenerateIsolationChecksum(isolation)

	if checksum1 != checksum2 {
		t.Error("checksum should be deterministic")
	}
}

func TestGenerateIsolationChecksum_DifferentInputs(t *testing.T) {
	isolation1 := &WorkflowFailureIsolation{
		IsolationID:     "isolation-test-001",
		WorkflowID:      "workflow-test-001",
		IsolationScope:  "step-level",
		IsolationMode:   "continue",
		FailurePatterns: []string{"timeout"},
		RetryStrategy:   "exponential-backoff",
	}

	isolation2 := &WorkflowFailureIsolation{
		IsolationID:     "isolation-test-002",
		WorkflowID:      "workflow-test-001",
		IsolationScope:  "workflow-level",
		IsolationMode:   "abort",
		FailurePatterns: []string{"network-error"},
		RetryStrategy:   "linear-backoff",
	}

	checksum1 := GenerateIsolationChecksum(isolation1)
	checksum2 := GenerateIsolationChecksum(isolation2)

	if checksum1 == checksum2 {
		t.Error("different isolations should have different checksums")
	}
}

func TestCreateWorkflowFailureIsolation_AllIsolationScopes(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	scopes := []string{"step-level", "workflow-level", "tenant-level"}
	for i, scope := range scopes {
		req := baseFailureIsolationReq()
		req.IdempotencyKey = fmt.Sprintf("key-%d-1234567890", i)
		req.IsolationID = fmt.Sprintf("isolation-scope-%d", i)
		req.IsolationScope = scope // Different scope for each isolation

		_, err := CreateWorkflowFailureIsolation(req)
		if err != nil {
			t.Errorf("failed to create isolation with scope %s: %v", scope, err)
		}
	}
}

func TestCreateWorkflowFailureIsolation_AllIsolationModes(t *testing.T) {
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	modes := []string{"continue", "abort", "rollback"}
	for i, mode := range modes {
		req := baseFailureIsolationReq()
		req.IdempotencyKey = fmt.Sprintf("key-%d-9876543210", i)
		req.IsolationID = fmt.Sprintf("isolation-mode-%d", i)
		req.IsolationMode = mode // Different mode for each isolation

		_, err := CreateWorkflowFailureIsolation(req)
		if err != nil {
			t.Errorf("failed to create isolation with mode %s: %v", mode, err)
		}
	}
}

func TestListWorkflowFailureIsolationsByWorkflow_MultipleMatches(t *testing.T) {
	isolationStore = make(map[string]*WorkflowFailureIsolation)
	isolationKeys = make(map[string]string)
	defer func() {
		isolationStore = make(map[string]*WorkflowFailureIsolation)
		isolationKeys = make(map[string]string)
	}()

	for i := 0; i < 3; i++ {
		req := baseFailureIsolationReq()
		req.IdempotencyKey = fmt.Sprintf("multi-key-%d-abcdefgh", i)
		req.IsolationID = fmt.Sprintf("isolation-multi-%d", i)
		req.WorkflowID = "workflow-shared"
		created, err := CreateWorkflowFailureIsolation(req)
		if err != nil {
			t.Fatalf("failed to create isolation %d: %v", i, err)
		}
		if created == nil {
			t.Fatalf("created isolation %d is nil", i)
		}
	}

	isolations := ListWorkflowFailureIsolationsByWorkflow("workflow-shared")
	if len(isolations) != 3 {
		t.Errorf("expected 3 isolations, got %d", len(isolations))
		t.Logf("store has %d items", len(isolationStore))
	}
}
