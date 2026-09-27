package workflow

import (
	"fmt"
	"strings"
	"testing"
)

func baseTimeoutEscalationReq() *TimeoutEscalationRequest {
	return &TimeoutEscalationRequest{
		RuleID:           "synthetic-rule-001",
		WorkflowID:       "synthetic-workflow-001",
		StepID:           "synthetic-step-001",
		TimeoutDuration:  3600,
		EscalationAction: "notify",
		EscalationTarget: "synthetic-manager-001",
		NotifyUsers:      []string{"synthetic-user-001", "synthetic-user-002"},
		Metadata: map[string]string{
			"severity": "high",
			"category": "clinical-review",
		},
		IdempotencyKey: "test-idempotency-key-001",
	}
}

func checkError0241(t *testing.T, err error, expected string) {
	if err == nil {
		t.Errorf("Expected error containing '%s', got nil", expected)
		return
	}
	if !strings.Contains(err.Error(), expected) {
		t.Errorf("Expected error containing '%s', got: %v", expected, err)
	}
}

func TestValidateTimeoutEscalationRequest_Valid(t *testing.T) {
	req := baseTimeoutEscalationReq()
	err := ValidateTimeoutEscalationRequest(req)
	if err != nil {
		t.Errorf("Expected no error for valid request, got: %v", err)
	}
}

func TestValidateTimeoutEscalationRequest_NilRequest(t *testing.T) {
	err := ValidateTimeoutEscalationRequest(nil)
	checkError0241(t, err, "workflow-timeout-escalation-request-nil")
}

func TestValidateTimeoutEscalationRequest_NotSynthetic(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.RuleID = "real-rule-001"
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-rule-id-not-synthetic")
}

func TestValidateTimeoutEscalationRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.IdempotencyKey = ""
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-idempotency-key-empty")
}

func TestValidateTimeoutEscalationRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.IdempotencyKey = "short"
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-idempotency-key-short")
}

func TestValidateTimeoutEscalationRequest_EmptyRuleID(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.RuleID = ""
	err := ValidateTimeoutEscalationRequest(req)
	if err == nil || !strings.Contains(err.Error(), "workflow-timeout-escalation-rule-id") {
		t.Errorf("Expected rule ID error, got: %v", err)
	}
}

func TestValidateTimeoutEscalationRequest_InvalidRuleIDPrefix(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.RuleID = "synthetic-invalid-001" // Missing "rule-" prefix
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-rule-id-invalid-prefix")
}

func TestValidateTimeoutEscalationRequest_EmptyWorkflowID(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.WorkflowID = "" // Clear workflow ID to trigger validation
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-workflow-id-empty")
}

func TestValidateTimeoutEscalationRequest_EmptyStepID(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.StepID = ""
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-step-id-empty")
}

func TestValidateTimeoutEscalationRequest_InvalidDuration(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.TimeoutDuration = 0
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-duration-invalid")
}

func TestValidateTimeoutEscalationRequest_NegativeDuration(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.TimeoutDuration = -100
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-duration-invalid")
}

func TestValidateTimeoutEscalationRequest_EmptyAction(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.EscalationAction = ""
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-action-empty")
}

func TestValidateTimeoutEscalationRequest_InvalidAction(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.EscalationAction = "invalid-action"
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-action-invalid")
}

func TestValidateTimeoutEscalationRequest_MissingTargetForReassign(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.EscalationAction = "reassign"
	req.EscalationTarget = ""
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-target-required")
}

func TestValidateTimeoutEscalationRequest_MissingTargetForEscalate(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.EscalationAction = "escalate"
	req.EscalationTarget = ""
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-target-required")
}

func TestValidateTimeoutEscalationRequest_PHIPatternInTarget(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.EscalationTarget = "user-patient_id-123"
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-target-phi-pattern")
}

func TestValidateTimeoutEscalationRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseTimeoutEscalationReq()
	req.Metadata = map[string]string{
		"patient_name": "value",
	}
	err := ValidateTimeoutEscalationRequest(req)
	checkError0241(t, err, "workflow-timeout-escalation-metadata-key-phi-pattern")
}

func TestCreateTimeoutEscalation_Success(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	rule, err := CreateTimeoutEscalation(req)
	if err != nil {
		t.Fatalf("CreateTimeoutEscalation failed: %v", err)
	}

	if rule.RuleID != req.RuleID {
		t.Errorf("Expected RuleID %s, got %s", req.RuleID, rule.RuleID)
	}

	if rule.WorkflowID != req.WorkflowID {
		t.Errorf("Expected WorkflowID %s, got %s", req.WorkflowID, rule.WorkflowID)
	}

	if rule.Checksum == "" {
		t.Error("Expected non-empty checksum")
	}
}

func TestCreateTimeoutEscalation_Idempotency(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	rule1, err1 := CreateTimeoutEscalation(req)
	if err1 != nil {
		t.Fatalf("First CreateTimeoutEscalation failed: %v", err1)
	}

	rule2, err2 := CreateTimeoutEscalation(req)
	if err2 != nil {
		t.Fatalf("Second CreateTimeoutEscalation failed: %v", err2)
	}

	if rule1.RuleID != rule2.RuleID {
		t.Errorf("Idempotency failed: different rule IDs %s vs %s", rule1.RuleID, rule2.RuleID)
	}
}

func TestCreateTimeoutEscalation_ValidationFailure(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()
	req.RuleID = ""

	_, err := CreateTimeoutEscalation(req)
	if err == nil {
		t.Error("Expected validation error for empty RuleID")
	}
}

func TestGetTimeoutEscalation_Success(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	created, _ := CreateTimeoutEscalation(req)

	retrieved, err := GetTimeoutEscalation(req.RuleID)
	if err != nil {
		t.Fatalf("GetTimeoutEscalation failed: %v", err)
	}

	if retrieved.RuleID != created.RuleID {
		t.Errorf("Expected RuleID %s, got %s", created.RuleID, retrieved.RuleID)
	}
}

func TestGetTimeoutEscalation_EmptyID(t *testing.T) {
	_, err := GetTimeoutEscalation("")
	checkError0241(t, err, "workflow-timeout-escalation-rule-id-empty")
}

func TestGetTimeoutEscalation_NotFound(t *testing.T) {
	ClearTimeoutEscalations()

	_, err := GetTimeoutEscalation("synthetic-rule-nonexistent")
	checkError0241(t, err, "workflow-timeout-escalation-rule-not-found")
}

func TestUpdateTimeoutEscalation_Success(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	CreateTimeoutEscalation(req)

	req.TimeoutDuration = 7200
	req.EscalationAction = "escalate"

	updated, err := UpdateTimeoutEscalation(req.RuleID, req)
	if err != nil {
		t.Fatalf("UpdateTimeoutEscalation failed: %v", err)
	}

	if updated.TimeoutDuration != 7200 {
		t.Errorf("Expected TimeoutDuration 7200, got %d", updated.TimeoutDuration)
	}

	if updated.EscalationAction != "escalate" {
		t.Errorf("Expected EscalationAction 'escalate', got %s", updated.EscalationAction)
	}
}

func TestUpdateTimeoutEscalation_EmptyID(t *testing.T) {
	req := baseTimeoutEscalationReq()

	_, err := UpdateTimeoutEscalation("", req)
	checkError0241(t, err, "workflow-timeout-escalation-rule-id-empty")
}

func TestUpdateTimeoutEscalation_ValidationFailure(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	CreateTimeoutEscalation(req)

	req.TimeoutDuration = -100

	_, err := UpdateTimeoutEscalation(req.RuleID, req)
	if err == nil {
		t.Error("Expected validation error for negative duration")
	}
}

func TestUpdateTimeoutEscalation_NotFound(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	_, err := UpdateTimeoutEscalation("synthetic-rule-nonexistent", req)
	checkError0241(t, err, "workflow-timeout-escalation-rule-not-found")
}

func TestListTimeoutEscalations_Success(t *testing.T) {
	ClearTimeoutEscalations()

	req1 := baseTimeoutEscalationReq()
	req2 := baseTimeoutEscalationReq()
	req2.RuleID = "synthetic-rule-002"
	req2.IdempotencyKey = "test-idempotency-key-002"

	CreateTimeoutEscalation(req1)
	CreateTimeoutEscalation(req2)

	rules := ListTimeoutEscalations()
	if len(rules) != 2 {
		t.Errorf("Expected 2 rules, got %d", len(rules))
	}
}

func TestListTimeoutEscalations_Empty(t *testing.T) {
	ClearTimeoutEscalations()

	rules := ListTimeoutEscalations()
	if len(rules) != 0 {
		t.Errorf("Expected 0 rules, got %d", len(rules))
	}
}

func TestListTimeoutEscalationsByWorkflow_Success(t *testing.T) {
	ClearTimeoutEscalations()

	req1 := baseTimeoutEscalationReq()
	req1.WorkflowID = "synthetic-workflow-001"

	req2 := baseTimeoutEscalationReq()
	req2.RuleID = "synthetic-rule-002"
	req2.WorkflowID = "synthetic-workflow-002"
	req2.IdempotencyKey = "test-idempotency-key-002"

	CreateTimeoutEscalation(req1)
	CreateTimeoutEscalation(req2)

	rules := ListTimeoutEscalationsByWorkflow("synthetic-workflow-001")
	if len(rules) != 1 {
		t.Errorf("Expected 1 rule for workflow-001, got %d", len(rules))
	}

	if rules[0].WorkflowID != "synthetic-workflow-001" {
		t.Errorf("Expected WorkflowID synthetic-workflow-001, got %s", rules[0].WorkflowID)
	}
}

func TestDeleteTimeoutEscalation_Success(t *testing.T) {
	ClearTimeoutEscalations()
	req := baseTimeoutEscalationReq()

	CreateTimeoutEscalation(req)

	err := DeleteTimeoutEscalation(req.RuleID)
	if err != nil {
		t.Fatalf("DeleteTimeoutEscalation failed: %v", err)
	}

	_, getErr := GetTimeoutEscalation(req.RuleID)
	if getErr == nil {
		t.Error("Expected error when getting deleted rule")
	}
}

func TestDeleteTimeoutEscalation_EmptyID(t *testing.T) {
	err := DeleteTimeoutEscalation("")
	checkError0241(t, err, "workflow-timeout-escalation-rule-id-empty")
}

func TestDeleteTimeoutEscalation_NotFound(t *testing.T) {
	ClearTimeoutEscalations()

	err := DeleteTimeoutEscalation("synthetic-rule-nonexistent")
	checkError0241(t, err, "workflow-timeout-escalation-rule-not-found")
}

func TestGenerateTimeoutEscalationChecksum_Deterministic(t *testing.T) {
	req := baseTimeoutEscalationReq()

	checksum1 := GenerateTimeoutEscalationChecksum(req)
	checksum2 := GenerateTimeoutEscalationChecksum(req)

	if checksum1 != checksum2 {
		t.Error("Same input should produce same checksum")
	}
}

func TestGenerateTimeoutEscalationChecksum_DifferentInputs(t *testing.T) {
	req1 := baseTimeoutEscalationReq()
	req2 := baseTimeoutEscalationReq()
	req2.TimeoutDuration = 7200

	checksum1 := GenerateTimeoutEscalationChecksum(req1)
	checksum2 := GenerateTimeoutEscalationChecksum(req2)

	if checksum1 == checksum2 {
		t.Errorf("Different durations should yield different checksums, got: %s", checksum1)
	}
}

func TestCreateTimeoutEscalation_AllActions(t *testing.T) {
	ClearTimeoutEscalations()

	actions := []string{"notify", "reassign", "escalate", "cancel", "auto-complete"}

	for i, action := range actions {
		req := baseTimeoutEscalationReq()
		req.RuleID = fmt.Sprintf("synthetic-rule-%03d", i+1)
		req.IdempotencyKey = fmt.Sprintf("test-idempotency-key-%03d", i+1)
		req.EscalationAction = action

		if action == "reassign" || action == "escalate" {
			req.EscalationTarget = "synthetic-manager-001"
		} else {
			req.EscalationTarget = ""
		}

		_, err := CreateTimeoutEscalation(req)
		if err != nil {
			t.Errorf("Failed to create rule with action %s: %v", action, err)
		}
	}

	rules := ListTimeoutEscalations()
	if len(rules) != len(actions) {
		t.Errorf("Expected %d rules, got %d", len(actions), len(rules))
	}
}

func TestListTimeoutEscalationsByWorkflow_MultipleMatches(t *testing.T) {
	ClearTimeoutEscalations()

	for i := 0; i < 3; i++ {
		req := baseTimeoutEscalationReq()
		req.RuleID = fmt.Sprintf("synthetic-rule-%03d", i+1)
		req.IdempotencyKey = fmt.Sprintf("test-idempotency-key-%03d", i+1)
		req.WorkflowID = "synthetic-workflow-shared"

		CreateTimeoutEscalation(req)
	}

	rules := ListTimeoutEscalationsByWorkflow("synthetic-workflow-shared")
	if len(rules) != 3 {
		t.Errorf("Expected 3 rules for shared workflow, got %d", len(rules))
	}
}
