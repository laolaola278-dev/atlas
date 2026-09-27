package workflow

import (
	"fmt"
	"testing"
)

func baseCompensationActionReq() *CompensationActionRequest {
	return &CompensationActionRequest{
		IdempotencyKey:   "compensation-action-test-base-key-0242",
		ActionID:         "action-rollback-synthetic-0242",
		WorkflowID:       "workflow-synthetic-compensation-0242",
		StepID:           "step-synthetic-payment-0242",
		TriggerCondition: "on_failure",
		CompensationType: "rollback_state",
		TargetState:      "state-synthetic-pending-0242",
		Metadata: map[string]string{
			"department": "synthetic-oncology",
			"priority":   "high",
		},
		Synthetic: true,
	}
}

func checkError0242(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected error %q, got nil", expected)
	}
	if err.Error() != expected {
		t.Fatalf("expected error %q, got %q", expected, err.Error())
	}
}

func TestValidateCompensationActionRequest_Valid(t *testing.T) {
	req := baseCompensationActionReq()
	err := ValidateCompensationActionRequest(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestValidateCompensationActionRequest_NilRequest(t *testing.T) {
	err := ValidateCompensationActionRequest(nil)
	checkError0242(t, err, "workflow-compensation-action-request-nil")
}

func TestValidateCompensationActionRequest_NotSynthetic(t *testing.T) {
	req := baseCompensationActionReq()
	req.Synthetic = false
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-not-synthetic")
}

func TestValidateCompensationActionRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseCompensationActionReq()
	// Clear idempotency key to trigger validation
	req.IdempotencyKey = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-idempotency-key-empty")
}

func TestValidateCompensationActionRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "short-key-0242"
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-idempotency-key-too-short")
}

func TestValidateCompensationActionRequest_EmptyActionID(t *testing.T) {
	req := baseCompensationActionReq()
	req.ActionID = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestValidateCompensationActionRequest_InvalidActionIDPrefix(t *testing.T) {
	req := baseCompensationActionReq()
	req.ActionID = "synthetic-invalid-0242" // Missing "action-" prefix
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-id-invalid-prefix")
}

func TestValidateCompensationActionRequest_EmptyWorkflowID(t *testing.T) {
	req := baseCompensationActionReq()
	// Clear workflow identifier to trigger validation
	req.WorkflowID = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-workflow-id-empty")
}

func TestValidateCompensationActionRequest_EmptyStepID(t *testing.T) {
	req := baseCompensationActionReq()
	// Clear step identifier to trigger validation
	req.StepID = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-step-id-empty")
}

func TestValidateCompensationActionRequest_EmptyTriggerCondition(t *testing.T) {
	req := baseCompensationActionReq()
	// Clear trigger condition to trigger validation
	req.TriggerCondition = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-trigger-condition-empty")
}

func TestValidateCompensationActionRequest_InvalidTriggerCondition(t *testing.T) {
	req := baseCompensationActionReq()
	req.TriggerCondition = "on_success"
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-trigger-condition-invalid")
}

func TestValidateCompensationActionRequest_EmptyCompensationType(t *testing.T) {
	req := baseCompensationActionReq()
	req.CompensationType = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-type-empty")
}

func TestValidateCompensationActionRequest_InvalidCompensationType(t *testing.T) {
	req := baseCompensationActionReq()
	req.CompensationType = "invalid_type"
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-type-invalid")
}

func TestValidateCompensationActionRequest_MissingTargetState(t *testing.T) {
	req := baseCompensationActionReq()
	req.CompensationType = "rollback_state"
	// Clear target state for rollback type validation
	req.TargetState = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-target-state-required")
}

func TestValidateCompensationActionRequest_MissingRollbackScript(t *testing.T) {
	req := baseCompensationActionReq()
	req.CompensationType = "execute_script"
	req.RollbackScript = ""
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-rollback-script-required")
}

func TestValidateCompensationActionRequest_PHIPatternInTargetState(t *testing.T) {
	req := baseCompensationActionReq()
	req.TargetState = "state-patient-name-pending"
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-target-state-phi-pattern")
}

func TestValidateCompensationActionRequest_PHIPatternInRollbackScript(t *testing.T) {
	req := baseCompensationActionReq()
	req.CompensationType = "execute_script"
	req.RollbackScript = "rollback-patient-email-script"
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-rollback-script-phi-pattern")
}

func TestValidateCompensationActionRequest_PHIPatternInNotifyUsers(t *testing.T) {
	req := baseCompensationActionReq()
	req.NotifyUsers = []string{"user-john-doe-name"}
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-notify-users-phi-pattern")
}

func TestValidateCompensationActionRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseCompensationActionReq()
	req.Metadata = map[string]string{"patient-name": "synthetic-value"}
	err := ValidateCompensationActionRequest(req)
	checkError0242(t, err, "workflow-compensation-action-metadata-key-phi-pattern")
}

func TestCreateCompensationAction_Success(t *testing.T) {
	req := baseCompensationActionReq()
	action, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if action.ID == "" {
		t.Fatal("expected non-empty ID")
	}
	if action.ActionID != req.ActionID {
		t.Fatalf("expected ActionID %q, got %q", req.ActionID, action.ActionID)
	}
	if action.Checksum == "" {
		t.Fatal("expected non-empty Checksum")
	}
}

func TestCreateCompensationAction_Idempotency(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "compensation-action-idempotency-test-0242"
	action1, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on first create, got %v", err)
	}
	action2, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on second create, got %v", err)
	}
	if action1.ID != action2.ID {
		t.Fatalf("expected same ID, got %q and %q", action1.ID, action2.ID)
	}
}

func TestCreateCompensationAction_ValidationFailure(t *testing.T) {
	req := baseCompensationActionReq()
	req.ActionID = ""
	_, err := CreateCompensationAction(req)
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestGetCompensationAction_Success(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "compensation-action-get-test-0242"
	created, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on create, got %v", err)
	}
	retrieved, err := GetCompensationAction(created.ID)
	if err != nil {
		t.Fatalf("expected no error on get, got %v", err)
	}
	if retrieved.ID != created.ID {
		t.Fatalf("expected ID %q, got %q", created.ID, retrieved.ID)
	}
}

func TestGetCompensationAction_EmptyID(t *testing.T) {
	_, err := GetCompensationAction("")
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestGetCompensationAction_NotFound(t *testing.T) {
	_, err := GetCompensationAction("compensation-nonexistent-0242")
	checkError0242(t, err, "workflow-compensation-action-not-found")
}

func TestUpdateCompensationAction_Success(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "compensation-action-update-test-0242"
	created, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on create, got %v", err)
	}
	req.TargetState = "state-synthetic-updated-0242"
	req.IdempotencyKey = "compensation-action-update-new-key-0242"
	updated, err := UpdateCompensationAction(created.ID, req)
	if err != nil {
		t.Fatalf("expected no error on update, got %v", err)
	}
	if updated.TargetState != req.TargetState {
		t.Fatalf("expected TargetState %q, got %q", req.TargetState, updated.TargetState)
	}
}

func TestUpdateCompensationAction_EmptyID(t *testing.T) {
	req := baseCompensationActionReq()
	_, err := UpdateCompensationAction("", req)
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestUpdateCompensationAction_ValidationFailure(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "compensation-action-update-validation-0242"
	created, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on create, got %v", err)
	}
	req.ActionID = ""
	_, err = UpdateCompensationAction(created.ID, req)
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestUpdateCompensationAction_NotFound(t *testing.T) {
	req := baseCompensationActionReq()
	_, err := UpdateCompensationAction("compensation-nonexistent-0242", req)
	checkError0242(t, err, "workflow-compensation-action-not-found")
}

func TestListCompensationActions_Success(t *testing.T) {
	req1 := baseCompensationActionReq()
	req1.IdempotencyKey = "compensation-action-list-test-1-0242"
	req1.ActionID = "action-list-synthetic-1-0242"
	_, err := CreateCompensationAction(req1)
	if err != nil {
		t.Fatalf("expected no error on create 1, got %v", err)
	}
	req2 := baseCompensationActionReq()
	req2.IdempotencyKey = "compensation-action-list-test-2-0242"
	req2.ActionID = "action-list-synthetic-2-0242"
	_, err = CreateCompensationAction(req2)
	if err != nil {
		t.Fatalf("expected no error on create 2, got %v", err)
	}
	actions := ListCompensationActions()
	if len(actions) < 2 {
		t.Fatalf("expected at least 2 actions, got %d", len(actions))
	}
}

func TestListCompensationActions_Empty(t *testing.T) {
	compensationActionStore = make(map[string]*CompensationAction)
	actions := ListCompensationActions()
	if len(actions) != 0 {
		t.Fatalf("expected 0 actions, got %d", len(actions))
	}
}

func TestListCompensationActionsByWorkflow_Success(t *testing.T) {
	compensationActionStore = make(map[string]*CompensationAction)
	compensationActionIdempotency = make(map[string]string)

	req1 := baseCompensationActionReq()
	req1.IdempotencyKey = "compensation-action-workflow-list-1-0242"
	req1.ActionID = "action-workflow-synthetic-1-0242"
	req1.WorkflowID = "workflow-synthetic-target-0242"
	_, err := CreateCompensationAction(req1)
	if err != nil {
		t.Fatalf("expected no error on create 1, got %v", err)
	}
	req2 := baseCompensationActionReq()
	req2.IdempotencyKey = "compensation-action-workflow-list-2-0242"
	req2.ActionID = "action-workflow-synthetic-2-0242"
	req2.WorkflowID = "workflow-synthetic-target-0242"
	_, err = CreateCompensationAction(req2)
	if err != nil {
		t.Fatalf("expected no error on create 2, got %v", err)
	}
	actions := ListCompensationActionsByWorkflow("workflow-synthetic-target-0242")
	if len(actions) != 2 {
		t.Fatalf("expected 2 actions, got %d", len(actions))
	}
}

func TestDeleteCompensationAction_Success(t *testing.T) {
	req := baseCompensationActionReq()
	req.IdempotencyKey = "compensation-action-delete-test-0242"
	created, err := CreateCompensationAction(req)
	if err != nil {
		t.Fatalf("expected no error on create, got %v", err)
	}
	err = DeleteCompensationAction(created.ID)
	if err != nil {
		t.Fatalf("expected no error on delete, got %v", err)
	}
	_, err = GetCompensationAction(created.ID)
	checkError0242(t, err, "workflow-compensation-action-not-found")
}

func TestDeleteCompensationAction_EmptyID(t *testing.T) {
	err := DeleteCompensationAction("")
	checkError0242(t, err, "workflow-compensation-action-id-empty")
}

func TestDeleteCompensationAction_NotFound(t *testing.T) {
	err := DeleteCompensationAction("compensation-nonexistent-0242")
	checkError0242(t, err, "workflow-compensation-action-not-found")
}

func TestGenerateCompensationActionChecksum_Deterministic(t *testing.T) {
	req := baseCompensationActionReq()
	checksum1 := GenerateCompensationActionChecksum(req)
	checksum2 := GenerateCompensationActionChecksum(req)
	if checksum1 != checksum2 {
		t.Fatalf("expected deterministic checksum, got %q and %q", checksum1, checksum2)
	}
}

func TestGenerateCompensationActionChecksum_DifferentInputs(t *testing.T) {
	req1 := baseCompensationActionReq()
	checksum1 := GenerateCompensationActionChecksum(req1)
	req2 := baseCompensationActionReq()
	req2.TargetState = "state-synthetic-different-0242"
	checksum2 := GenerateCompensationActionChecksum(req2)
	if checksum1 == checksum2 {
		t.Fatal("expected different checksums for different inputs")
	}
}

func TestCreateCompensationAction_AllCompensationTypes(t *testing.T) {
	compensationActionStore = make(map[string]*CompensationAction)
	compensationActionIdempotency = make(map[string]string)

	types := []string{"rollback_state", "execute_script", "notify_only"}
	for i, compType := range types {
		req := baseCompensationActionReq()
		req.IdempotencyKey = fmt.Sprintf("compensation-action-type-%s-test-0242", compType)
		req.ActionID = fmt.Sprintf("action-type-synthetic-%d-0242", i)
		req.CompensationType = compType
		if compType == "rollback_state" {
			req.TargetState = "state-synthetic-rollback-0242"
			req.RollbackScript = ""
		} else if compType == "execute_script" {
			req.TargetState = ""
			req.RollbackScript = "script-synthetic-rollback-0242"
		} else {
			req.TargetState = ""
			req.RollbackScript = ""
		}
		action, err := CreateCompensationAction(req)
		if err != nil {
			t.Fatalf("expected no error for type %s, got %v", compType, err)
		}
		if action.CompensationType != compType {
			t.Fatalf("expected CompensationType %q, got %q", compType, action.CompensationType)
		}
	}
}

func TestListCompensationActionsByWorkflow_MultipleMatches(t *testing.T) {
	compensationActionStore = make(map[string]*CompensationAction)
	compensationActionIdempotency = make(map[string]string)

	workflowID := "workflow-synthetic-multi-match-0242"
	for i := 0; i < 3; i++ {
		req := baseCompensationActionReq()
		req.IdempotencyKey = fmt.Sprintf("compensation-action-multi-%d-0242", i)
		req.ActionID = fmt.Sprintf("action-multi-synthetic-%d-0242", i)
		req.WorkflowID = workflowID
		_, err := CreateCompensationAction(req)
		if err != nil {
			t.Fatalf("expected no error on create %d, got %v", i, err)
		}
	}
	actions := ListCompensationActionsByWorkflow(workflowID)
	if len(actions) != 3 {
		t.Fatalf("expected 3 actions, got %d", len(actions))
	}
}
