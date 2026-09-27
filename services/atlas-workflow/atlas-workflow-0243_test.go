package workflow

import (
	"fmt"
	"strings"
	"testing"
)

func baseClinicalWriteGuardReq() *ClinicalWriteGuardRequest {
	return &ClinicalWriteGuardRequest{
		Synthetic:             true,
		IdempotencyKey:        "clinical-write-guard-test-idempotency-key-0243",
		GuardID:               "synthetic-guard-0243",
		WorkflowID:            "synthetic-workflow-0243",
		StepID:                "synthetic-step-0243",
		OperationType:         "create",
		ResourceType:          "MedicationRequest",
		ExecutionMode:         "manual",
		RequiresReview:        true,
		ReviewerRole:          "attending-physician",
		JustificationRequired: true,
		Metadata:              map[string]string{"priority": "high"},
	}
}

func checkError0243(t *testing.T, err error, expected string) {
	if err == nil {
		t.Fatalf("expected error containing %q, got nil", expected)
	}
	if !strings.Contains(err.Error(), expected) {
		t.Fatalf("expected error containing %q, got %q", expected, err.Error())
	}
}

func TestValidateClinicalWriteGuardRequest_Valid(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	err := ValidateClinicalWriteGuardRequest(req)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

func TestValidateClinicalWriteGuardRequest_NilRequest(t *testing.T) {
	err := ValidateClinicalWriteGuardRequest(nil)
	checkError0243(t, err, "workflow-clinical-write-guard-request-nil")
}

func TestValidateClinicalWriteGuardRequest_NotSynthetic(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.Synthetic = false
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-not-synthetic")
}

func TestValidateClinicalWriteGuardRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	// Clear idempotency key for validation
	req.IdempotencyKey = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-idempotency-key-empty")
}

func TestValidateClinicalWriteGuardRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "short-key-0243"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-idempotency-key-too-short")
}

func TestValidateClinicalWriteGuardRequest_EmptyGuardID(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	// Clear guard identifier for validation
	req.GuardID = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-id-empty")
}

func TestValidateClinicalWriteGuardRequest_InvalidGuardIDPrefix(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.GuardID = "synthetic-invalid-0243"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-id-invalid-prefix")
}

func TestValidateClinicalWriteGuardRequest_EmptyWorkflowID(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	// Clear workflow identifier for validation
	req.WorkflowID = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-workflow-id-empty")
}

func TestValidateClinicalWriteGuardRequest_EmptyStepID(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	// Clear step identifier for validation
	req.StepID = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-step-id-empty")
}

func TestValidateClinicalWriteGuardRequest_EmptyOperationType(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.OperationType = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-operation-type-empty")
}

func TestValidateClinicalWriteGuardRequest_InvalidOperationType(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.OperationType = "invalid_operation"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-operation-type-invalid")
}

func TestValidateClinicalWriteGuardRequest_EmptyResourceType(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ResourceType = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-resource-type-empty")
}

func TestValidateClinicalWriteGuardRequest_EmptyExecutionMode(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ExecutionMode = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-execution-mode-empty")
}

func TestValidateClinicalWriteGuardRequest_InvalidExecutionMode(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ExecutionMode = "semi_automatic"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-execution-mode-invalid")
}

func TestValidateClinicalWriteGuardRequest_AutomaticWriteProhibited(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ExecutionMode = "automatic"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-automatic-write-prohibited")
}

func TestValidateClinicalWriteGuardRequest_ReviewerRoleRequired(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.RequiresReview = true
	req.ReviewerRole = ""
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-reviewer-role-required")
}

func TestValidateClinicalWriteGuardRequest_PHIPatternInResourceType(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ResourceType = "patient-Demographics"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-phi-pattern-in-resource-type")
}

func TestValidateClinicalWriteGuardRequest_PHIPatternInReviewerRole(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ReviewerRole = "mrn-validator"
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-phi-pattern-in-reviewer-role")
}

func TestValidateClinicalWriteGuardRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.Metadata = map[string]string{"patient-id": "synthetic-value"}
	err := ValidateClinicalWriteGuardRequest(req)
	checkError0243(t, err, "workflow-clinical-write-guard-phi-pattern-in-metadata-key")
}

func TestCreateClinicalWriteGuard_Success(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "create-guard-success-test-0243"
	guard, err := CreateClinicalWriteGuard(req)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if guard.GuardID != req.GuardID {
		t.Errorf("Expected GuardID %s, got %s", req.GuardID, guard.GuardID)
	}
	if guard.Checksum == "" {
		t.Errorf("Expected non-empty checksum")
	}
}

func TestCreateClinicalWriteGuard_Idempotency(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "create-guard-idempotency-test-0243"
	guard1, err := CreateClinicalWriteGuard(req)
	if err != nil {
		t.Fatalf("Expected no error on first call, got %v", err)
	}
	guard2, err := CreateClinicalWriteGuard(req)
	if err != nil {
		t.Fatalf("Expected no error on second call, got %v", err)
	}
	if guard1.GuardID != guard2.GuardID {
		t.Errorf("Expected same GuardID, got %s and %s", guard1.GuardID, guard2.GuardID)
	}
}

func TestCreateClinicalWriteGuard_ValidationFailure(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.ExecutionMode = "automatic" // Should fail validation
	_, err := CreateClinicalWriteGuard(req)
	if err == nil {
		t.Errorf("Expected validation error, got nil")
	}
}

func TestGetClinicalWriteGuard_Success(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "get-guard-success-test-0243"
	req.GuardID = "synthetic-guard-get-0243"
	created, _ := CreateClinicalWriteGuard(req)
	retrieved, err := GetClinicalWriteGuard(created.GuardID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if retrieved.GuardID != created.GuardID {
		t.Errorf("Expected GuardID %s, got %s", created.GuardID, retrieved.GuardID)
	}
}

func TestGetClinicalWriteGuard_EmptyID(t *testing.T) {
	_, err := GetClinicalWriteGuard("")
	checkError0243(t, err, "workflow-clinical-write-guard-id-empty")
}

func TestGetClinicalWriteGuard_NotFound(t *testing.T) {
	_, err := GetClinicalWriteGuard("synthetic-guard-nonexistent-0243")
	checkError0243(t, err, "workflow-clinical-write-guard-not-found")
}

func TestUpdateClinicalWriteGuard_Success(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "update-guard-success-test-0243"
	req.GuardID = "synthetic-guard-update-0243"
	created, _ := CreateClinicalWriteGuard(req)
	updateReq := baseClinicalWriteGuardReq()
	updateReq.IdempotencyKey = "update-guard-success-test-0243-updated"
	updateReq.OperationType = "update"
	updated, err := UpdateClinicalWriteGuard(created.GuardID, updateReq)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if updated.OperationType != "update" {
		t.Errorf("Expected OperationType 'update', got %s", updated.OperationType)
	}
}

func TestUpdateClinicalWriteGuard_EmptyID(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	_, err := UpdateClinicalWriteGuard("", req)
	checkError0243(t, err, "workflow-clinical-write-guard-id-empty")
}

func TestUpdateClinicalWriteGuard_ValidationFailure(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "update-guard-validation-test-0243"
	req.GuardID = "synthetic-guard-update-val-0243"
	created, _ := CreateClinicalWriteGuard(req)
	updateReq := baseClinicalWriteGuardReq()
	updateReq.ExecutionMode = "automatic" // Should fail
	_, err := UpdateClinicalWriteGuard(created.GuardID, updateReq)
	if err == nil {
		t.Errorf("Expected validation error, got nil")
	}
}

func TestUpdateClinicalWriteGuard_NotFound(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	_, err := UpdateClinicalWriteGuard("synthetic-guard-nonexistent-update-0243", req)
	checkError0243(t, err, "workflow-clinical-write-guard-not-found")
}

func TestListClinicalWriteGuards_Success(t *testing.T) {
	req1 := baseClinicalWriteGuardReq()
	req1.IdempotencyKey = "list-guards-test-1-0243"
	req1.GuardID = "synthetic-guard-list-1-0243"
	CreateClinicalWriteGuard(req1)
	req2 := baseClinicalWriteGuardReq()
	req2.IdempotencyKey = "list-guards-test-2-0243"
	req2.GuardID = "synthetic-guard-list-2-0243"
	CreateClinicalWriteGuard(req2)
	guards := ListClinicalWriteGuards()
	if len(guards) < 2 {
		t.Errorf("Expected at least 2 guards, got %d", len(guards))
	}
}

func TestListClinicalWriteGuards_Empty(t *testing.T) {
	// Clear store for this test
	clinicalWriteGuardStore = make(map[string]*ClinicalWriteGuard)
	guards := ListClinicalWriteGuards()
	if len(guards) != 0 {
		t.Errorf("Expected 0 guards, got %d", len(guards))
	}
}

func TestListClinicalWriteGuardsByWorkflow_Success(t *testing.T) {
	req1 := baseClinicalWriteGuardReq()
	req1.IdempotencyKey = "list-by-workflow-test-1-0243"
	req1.GuardID = "synthetic-guard-workflow-1-0243"
	req1.WorkflowID = "synthetic-workflow-list-0243"
	CreateClinicalWriteGuard(req1)
	req2 := baseClinicalWriteGuardReq()
	req2.IdempotencyKey = "list-by-workflow-test-2-0243"
	req2.GuardID = "synthetic-guard-workflow-2-0243"
	req2.WorkflowID = "synthetic-workflow-list-0243"
	CreateClinicalWriteGuard(req2)
	guards := ListClinicalWriteGuardsByWorkflow("synthetic-workflow-list-0243")
	if len(guards) < 2 {
		t.Errorf("Expected at least 2 guards, got %d", len(guards))
	}
}

func TestDeleteClinicalWriteGuard_Success(t *testing.T) {
	req := baseClinicalWriteGuardReq()
	req.IdempotencyKey = "delete-guard-success-test-0243"
	req.GuardID = "synthetic-guard-delete-0243"
	created, _ := CreateClinicalWriteGuard(req)
	err := DeleteClinicalWriteGuard(created.GuardID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	_, err = GetClinicalWriteGuard(created.GuardID)
	if err == nil {
		t.Errorf("Expected error after deletion, got nil")
	}
}

func TestDeleteClinicalWriteGuard_EmptyID(t *testing.T) {
	err := DeleteClinicalWriteGuard("")
	checkError0243(t, err, "workflow-clinical-write-guard-id-empty")
}

func TestDeleteClinicalWriteGuard_NotFound(t *testing.T) {
	err := DeleteClinicalWriteGuard("synthetic-guard-nonexistent-delete-0243")
	checkError0243(t, err, "workflow-clinical-write-guard-not-found")
}

func TestGenerateClinicalWriteGuardChecksum_Deterministic(t *testing.T) {
	guard := &ClinicalWriteGuard{
		GuardID:               "synthetic-guard-checksum-0243",
		WorkflowID:            "synthetic-workflow-0243",
		StepID:                "synthetic-step-0243",
		OperationType:         "create",
		ResourceType:          "MedicationRequest",
		ExecutionMode:         "manual",
		RequiresReview:        true,
		ReviewerRole:          "attending-physician",
		JustificationRequired: true,
	}
	checksum1 := GenerateClinicalWriteGuardChecksum(guard)
	checksum2 := GenerateClinicalWriteGuardChecksum(guard)
	if checksum1 != checksum2 {
		t.Errorf("Expected deterministic checksum, got %s and %s", checksum1, checksum2)
	}
}

func TestGenerateClinicalWriteGuardChecksum_DifferentInputs(t *testing.T) {
	// First guard uses create operation
	guard1 := &ClinicalWriteGuard{
		GuardID:               "synthetic-guard-checksum-1-0243",
		WorkflowID:            "synthetic-workflow-0243",
		StepID:                "synthetic-step-0243",
		OperationType:         "create",
		ResourceType:          "MedicationRequest",
		ExecutionMode:         "manual",
		RequiresReview:        true,
		ReviewerRole:          "attending-physician",
		JustificationRequired: true,
	}
	// Second guard uses update operation to generate different checksum
	guard2 := &ClinicalWriteGuard{
		GuardID:               "synthetic-guard-checksum-2-0243",
		WorkflowID:            "synthetic-workflow-0243",
		StepID:                "synthetic-step-0243",
		OperationType:         "update",
		ResourceType:          "MedicationRequest",
		ExecutionMode:         "manual",
		RequiresReview:        true,
		ReviewerRole:          "attending-physician",
		JustificationRequired: true,
	}
	checksum1 := GenerateClinicalWriteGuardChecksum(guard1)
	checksum2 := GenerateClinicalWriteGuardChecksum(guard2)
	if checksum1 == checksum2 {
		t.Errorf("Expected different checksums for different inputs")
	}
}

func TestCreateClinicalWriteGuard_AllOperationTypes(t *testing.T) {
	operations := []string{"create", "update", "delete"}
	for _, op := range operations {
		req := baseClinicalWriteGuardReq()
		req.IdempotencyKey = "all-operations-test-" + op + "-0243"
		req.GuardID = "synthetic-guard-" + op + "-0243"
		req.OperationType = op
		// Create guard with current operation type
		guard, err := CreateClinicalWriteGuard(req)
		if err != nil {
			t.Errorf("Expected no error for operation %s, got %v", op, err)
		}
		if guard.OperationType != op {
			t.Errorf("Expected OperationType %s, got %s", op, guard.OperationType)
		}
	}
}

func TestListClinicalWriteGuardsByWorkflow_MultipleMatches(t *testing.T) {
	workflowID := "synthetic-workflow-multi-match-0243"
	for i := 0; i < 3; i++ {
		req := baseClinicalWriteGuardReq()
		req.IdempotencyKey = fmt.Sprintf("multi-match-test-%d-0243", i)
		req.GuardID = fmt.Sprintf("synthetic-guard-multi-%d-0243", i)
		req.WorkflowID = workflowID
		CreateClinicalWriteGuard(req)
	}
	guards := ListClinicalWriteGuardsByWorkflow(workflowID)
	if len(guards) < 3 {
		t.Errorf("Expected at least 3 guards, got %d", len(guards))
	}
}
