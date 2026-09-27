package workflow

import (
	"strings"
	"testing"
)

func baseWorkflowDefReq() *WorkflowDefinitionRequest {
	return &WorkflowDefinitionRequest{
		DefinitionID: "wf-synth-001",
		Name:         "synthetic-workflow",
		Version:      "1.0.0",
		Steps: []WorkflowStep{
			{
				StepID:      "step-1",
				StepType:    "manual",
				Name:        "initial-step",
				Description: "first step",
				Config:      map[string]string{"key": "value"},
			},
		},
		Transitions: []StateTransition{
			{
				FromState:  "start",
				ToState:    "pending",
				Event:      "initiated",
				Conditions: []string{"valid"},
			},
		},
		InitialState:   "start",
		FinalStates:    []string{"completed"},
		Metadata:       map[string]string{"category": "test"},
		IdempotencyKey: "test-idempotency-key-0239",
		Synthetic:      true,
	}
}

func checkError(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Fatalf("expected error containing %q, got nil", expected)
	}
	if !strings.Contains(err.Error(), expected) {
		t.Fatalf("expected error containing %q, got %q", expected, err.Error())
	}
}

// Validation Tests

func TestValidateWorkflowDefinitionRequest_Valid(t *testing.T) {
	req := baseWorkflowDefReq()
	err := ValidateWorkflowDefinitionRequest(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
}

func TestValidateWorkflowDefinitionRequest_NilRequest(t *testing.T) {
	err := ValidateWorkflowDefinitionRequest(nil)
	checkError(t, err, "workflow-definition-request-nil")
}

func TestValidateWorkflowDefinitionRequest_NotSynthetic(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Synthetic = false
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-synthetic-required")
}

func TestValidateWorkflowDefinitionRequest_EmptyIdempotencyKey(t *testing.T) {
	req := baseWorkflowDefReq()
	req.IdempotencyKey = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-idempotency-required")
}

func TestValidateWorkflowDefinitionRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseWorkflowDefReq()
	req.IdempotencyKey = "short"
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-idempotency-too-short")
}

func TestValidateWorkflowDefinitionRequest_EmptyDefinitionID(t *testing.T) {
	req := baseWorkflowDefReq()
	req.DefinitionID = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-id-empty")
}

func TestValidateWorkflowDefinitionRequest_InvalidDefinitionIDPrefix(t *testing.T) {
	req := baseWorkflowDefReq()
	req.DefinitionID = "invalid-001"
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-id-invalid-prefix")
}

func TestValidateWorkflowDefinitionRequest_BlankWorkflowTitle(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Name = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-name-empty")
}

func TestValidateWorkflowDefinitionRequest_PHIPatternInWorkflowTitle(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Name = "workflow-with-patient_id"
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-phi-pattern-detected")
}

func TestValidateWorkflowDefinitionRequest_EmptyVersion(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Version = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-version-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptySteps(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Steps = []WorkflowStep{}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-steps-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyStepID(t *testing.T) {
	req := baseWorkflowDefReq()
	// Clear the step ID field
	req.Steps[0].StepID = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-step-id-empty")
}

func TestValidateWorkflowDefinitionRequest_DuplicateStepID(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Steps = append(req.Steps, WorkflowStep{
		StepID:   "step-1",
		StepType: "automatic",
		Name:     "duplicate",
	})
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-duplicate-step-id")
}

func TestValidateWorkflowDefinitionRequest_EmptyStepType(t *testing.T) {
	req := baseWorkflowDefReq()
	// Clear step type to trigger validation
	req.Steps[0].StepType = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-step-type-empty")
}

func TestValidateWorkflowDefinitionRequest_InvalidStepType(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Steps[0].StepType = "invalid-type"
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-step-type-invalid")
}

func TestValidateWorkflowDefinitionRequest_BlankStepTitle(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Steps[0].Name = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-step-name-empty")
}

func TestValidateWorkflowDefinitionRequest_PHIPatternInStepConfig(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Steps[0].Config = map[string]string{"patient_id": "value"}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-phi-pattern-detected")
}

func TestValidateWorkflowDefinitionRequest_EmptyInitialState(t *testing.T) {
	req := baseWorkflowDefReq()
	req.InitialState = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-initial-state-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyFinalStates(t *testing.T) {
	req := baseWorkflowDefReq()
	req.FinalStates = []string{}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-final-states-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyTransitions(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Transitions = []StateTransition{}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-transitions-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyTransitionFrom(t *testing.T) {
	req := baseWorkflowDefReq()
	// Clear FromState to trigger validation
	req.Transitions[0].FromState = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-transition-from-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyTransitionTo(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Transitions[0].ToState = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-transition-to-empty")
}

func TestValidateWorkflowDefinitionRequest_EmptyTransitionEvent(t *testing.T) {
	req := baseWorkflowDefReq()
	// Empty event to test validation
	req.Transitions[0].Event = ""
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-transition-event-empty")
}

func TestValidateWorkflowDefinitionRequest_InvalidMetadataKey(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Metadata = map[string]string{"Invalid-Key": "value"}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-metadata-key-invalid")
}

func TestValidateWorkflowDefinitionRequest_PHIPatternInMetadataKey(t *testing.T) {
	req := baseWorkflowDefReq()
	req.Metadata = map[string]string{"patient_name": "value"}
	err := ValidateWorkflowDefinitionRequest(req)
	checkError(t, err, "workflow-definition-phi-pattern-detected")
}

// Operation Tests

func TestDefineWorkflow_Success(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	resp, err := DefineWorkflow(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if resp.DefinitionID != req.DefinitionID {
		t.Errorf("expected DefinitionID %q, got %q", req.DefinitionID, resp.DefinitionID)
	}
	if resp.Name != req.Name {
		t.Errorf("expected Name %q, got %q", req.Name, resp.Name)
	}
	if resp.Checksum == "" {
		t.Error("expected non-empty Checksum")
	}
}

func TestDefineWorkflow_Idempotency(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	resp1, err := DefineWorkflow(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	resp2, err := DefineWorkflow(req)
	if err != nil {
		t.Fatalf("expected no error on second call, got %v", err)
	}
	if resp1.DefinitionID != resp2.DefinitionID {
		t.Errorf("expected same DefinitionID, got %q and %q", resp1.DefinitionID, resp2.DefinitionID)
	}
	if resp1.Checksum != resp2.Checksum {
		t.Errorf("expected same Checksum, got %q and %q", resp1.Checksum, resp2.Checksum)
	}
}

func TestDefineWorkflow_ValidationFailure(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	req.Synthetic = false
	_, err := DefineWorkflow(req)
	checkError(t, err, "workflow-definition-synthetic-required")
}

func TestGetWorkflowDefinition_Success(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	created, _ := DefineWorkflow(req)
	retrieved, err := GetWorkflowDefinition(created.DefinitionID)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if retrieved.DefinitionID != created.DefinitionID {
		t.Errorf("expected DefinitionID %q, got %q", created.DefinitionID, retrieved.DefinitionID)
	}
}

func TestGetWorkflowDefinition_EmptyID(t *testing.T) {
	_, err := GetWorkflowDefinition("")
	checkError(t, err, "workflow-definition-id-empty")
}

func TestGetWorkflowDefinition_NotFound(t *testing.T) {
	CleanupWorkflowDefinitions()
	_, err := GetWorkflowDefinition("wf-nonexistent")
	checkError(t, err, "workflow-definition-not-found")
}

func TestListWorkflowDefinitions_Success(t *testing.T) {
	CleanupWorkflowDefinitions()
	req1 := baseWorkflowDefReq()
	DefineWorkflow(req1)
	req2 := baseWorkflowDefReq()
	req2.DefinitionID = "wf-synth-002"
	req2.IdempotencyKey = "another-key-0239"
	DefineWorkflow(req2)

	list, err := ListWorkflowDefinitions()
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if len(list) != 2 {
		t.Errorf("expected 2 definitions, got %d", len(list))
	}
}

func TestListWorkflowDefinitions_Empty(t *testing.T) {
	CleanupWorkflowDefinitions()
	list, err := ListWorkflowDefinitions()
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if len(list) != 0 {
		t.Errorf("expected 0 definitions, got %d", len(list))
	}
}

func TestDeleteWorkflowDefinition_Success(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	created, _ := DefineWorkflow(req)
	err := DeleteWorkflowDefinition(created.DefinitionID)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	_, err = GetWorkflowDefinition(created.DefinitionID)
	checkError(t, err, "workflow-definition-not-found")
}

func TestDeleteWorkflowDefinition_EmptyID(t *testing.T) {
	err := DeleteWorkflowDefinition("")
	checkError(t, err, "workflow-definition-id-empty")
}

func TestDeleteWorkflowDefinition_NotFound(t *testing.T) {
	CleanupWorkflowDefinitions()
	err := DeleteWorkflowDefinition("wf-nonexistent")
	checkError(t, err, "workflow-definition-not-found")
}

func TestGenerateWorkflowDefinitionChecksum_Deterministic(t *testing.T) {
	req := baseWorkflowDefReq()
	checksum1 := GenerateWorkflowDefinitionChecksum(req)
	checksum2 := GenerateWorkflowDefinitionChecksum(req)
	if checksum1 != checksum2 {
		t.Errorf("expected deterministic checksum, got %q and %q", checksum1, checksum2)
	}
}

func TestGenerateWorkflowDefinitionChecksum_DifferentInputs(t *testing.T) {
	req1 := baseWorkflowDefReq()
	req2 := baseWorkflowDefReq()
	req2.Name = "different-workflow"
	checksum1 := GenerateWorkflowDefinitionChecksum(req1)
	checksum2 := GenerateWorkflowDefinitionChecksum(req2)
	if checksum1 == checksum2 {
		t.Error("expected different checksums for different inputs")
	}
}

func TestDefineWorkflow_AllStepTypes(t *testing.T) {
	CleanupWorkflowDefinitions()
	stepTypes := []string{"manual", "automatic", "decision", "parallel", "wait"}
	for i, stepType := range stepTypes {
		req := baseWorkflowDefReq()
		req.DefinitionID = "wf-synth-" + stepType
		req.IdempotencyKey = "workflow-step-type-" + stepType + "-test-0239"
		req.Steps[0].StepType = stepType
		req.Steps[0].StepID = "step-" + stepType
		_, err := DefineWorkflow(req)
		if err != nil {
			t.Errorf("step type %d (%s): expected no error, got %v", i, stepType, err)
		}
	}
}

func TestDefineWorkflow_MultipleSteps(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	req.Steps = append(req.Steps, WorkflowStep{
		StepID:   "step-2",
		StepType: "automatic",
		Name:     "second-step",
	})
	req.Steps = append(req.Steps, WorkflowStep{
		StepID:   "step-3",
		StepType: "decision",
		Name:     "third-step",
	})
	resp, err := DefineWorkflow(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if resp.DefinitionID != req.DefinitionID {
		t.Errorf("expected DefinitionID %q, got %q", req.DefinitionID, resp.DefinitionID)
	}
}

func TestDefineWorkflow_ComplexTransitions(t *testing.T) {
	CleanupWorkflowDefinitions()
	req := baseWorkflowDefReq()
	req.Transitions = append(req.Transitions, StateTransition{
		FromState:  "pending",
		ToState:    "processing",
		Event:      "started",
		Conditions: []string{"authorized"},
	})
	req.Transitions = append(req.Transitions, StateTransition{
		FromState:  "processing",
		ToState:    "completed",
		Event:      "finished",
		Conditions: []string{"validated"},
	})
	resp, err := DefineWorkflow(req)
	if err != nil {
		t.Fatalf("expected no error, got %v", err)
	}
	if resp.DefinitionID != req.DefinitionID {
		t.Errorf("expected DefinitionID %q, got %q", req.DefinitionID, resp.DefinitionID)
	}
}
