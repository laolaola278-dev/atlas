package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

// CompensationActionRequest represents a request to define a compensation action for workflow rollback.
type CompensationActionRequest struct {
	IdempotencyKey   string            `json:"idempotency_key"`
	ActionID         string            `json:"action_id"`
	WorkflowID       string            `json:"workflow_id"`
	StepID           string            `json:"step_id"`
	TriggerCondition string            `json:"trigger_condition"`
	CompensationType string            `json:"compensation_type"`
	TargetState      string            `json:"target_state,omitempty"`
	RollbackScript   string            `json:"rollback_script,omitempty"`
	NotifyUsers      []string          `json:"notify_users,omitempty"`
	Metadata         map[string]string `json:"metadata,omitempty"`
	Synthetic        bool              `json:"synthetic"`
}

// CompensationAction represents a stored compensation action.
type CompensationAction struct {
	ID               string            `json:"id"`
	ActionID         string            `json:"action_id"`
	WorkflowID       string            `json:"workflow_id"`
	StepID           string            `json:"step_id"`
	TriggerCondition string            `json:"trigger_condition"`
	CompensationType string            `json:"compensation_type"`
	TargetState      string            `json:"target_state,omitempty"`
	RollbackScript   string            `json:"rollback_script,omitempty"`
	NotifyUsers      []string          `json:"notify_users,omitempty"`
	Metadata         map[string]string `json:"metadata,omitempty"`
	Checksum         string            `json:"checksum"`
}

var compensationActionStore = make(map[string]*CompensationAction)
var compensationActionIdempotency = make(map[string]string)

// ValidateCompensationActionRequest validates a compensation action request.
func ValidateCompensationActionRequest(req *CompensationActionRequest) error {
	// Check for nil request pointer
	if req == nil {
		return fmt.Errorf("workflow-compensation-action-request-nil")
	}
	// Verify synthetic flag is set
	if !req.Synthetic {
		return fmt.Errorf("workflow-compensation-action-not-synthetic")
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("workflow-compensation-action-idempotency-key-empty")
	}
	if len(req.IdempotencyKey) < 16 {
		return fmt.Errorf("workflow-compensation-action-idempotency-key-too-short")
	}
	if req.ActionID == "" {
		return fmt.Errorf("workflow-compensation-action-id-empty")
	}
	if !strings.HasPrefix(req.ActionID, "action-") {
		return fmt.Errorf("workflow-compensation-action-id-invalid-prefix")
	}
	if req.WorkflowID == "" {
		return fmt.Errorf("workflow-compensation-action-workflow-id-empty")
	}
	if req.StepID == "" {
		return fmt.Errorf("workflow-compensation-action-step-id-empty")
	}
	if req.TriggerCondition == "" {
		return fmt.Errorf("workflow-compensation-action-trigger-condition-empty")
	}
	validTriggers := map[string]bool{
		"on_failure": true, "on_timeout": true, "on_cancel": true, "manual": true,
	}
	if !validTriggers[req.TriggerCondition] {
		return fmt.Errorf("workflow-compensation-action-trigger-condition-invalid")
	}
	if req.CompensationType == "" {
		return fmt.Errorf("workflow-compensation-action-type-empty")
	}
	validTypes := map[string]bool{
		"rollback_state": true, "execute_script": true, "notify_only": true,
	}
	if !validTypes[req.CompensationType] {
		return fmt.Errorf("workflow-compensation-action-type-invalid")
	}
	if req.CompensationType == "rollback_state" && req.TargetState == "" {
		return fmt.Errorf("workflow-compensation-action-target-state-required")
	}
	if req.CompensationType == "execute_script" && req.RollbackScript == "" {
		return fmt.Errorf("workflow-compensation-action-rollback-script-required")
	}

	phiPatterns := []string{"name", "phone", "address", "ssn", "mrn", "dob", "email"}
	for _, pattern := range phiPatterns {
		if strings.Contains(strings.ToLower(req.TargetState), pattern) {
			return fmt.Errorf("workflow-compensation-action-target-state-phi-pattern")
		}
		if strings.Contains(strings.ToLower(req.RollbackScript), pattern) {
			return fmt.Errorf("workflow-compensation-action-rollback-script-phi-pattern")
		}
		for _, user := range req.NotifyUsers {
			if strings.Contains(strings.ToLower(user), pattern) {
				return fmt.Errorf("workflow-compensation-action-notify-users-phi-pattern")
			}
		}
		for key := range req.Metadata {
			if strings.Contains(strings.ToLower(key), pattern) {
				return fmt.Errorf("workflow-compensation-action-metadata-key-phi-pattern")
			}
		}
	}

	return nil
}

// CreateCompensationAction creates a new compensation action.
func CreateCompensationAction(req *CompensationActionRequest) (*CompensationAction, error) {
	if err := ValidateCompensationActionRequest(req); err != nil {
		return nil, err
	}

	if existingID, found := compensationActionIdempotency[req.IdempotencyKey]; found {
		return compensationActionStore[existingID], nil
	}

	id := generateCompensationActionID(req)
	checksum := GenerateCompensationActionChecksum(req)

	action := &CompensationAction{
		ID:               id,
		ActionID:         req.ActionID,
		WorkflowID:       req.WorkflowID,
		StepID:           req.StepID,
		TriggerCondition: req.TriggerCondition,
		CompensationType: req.CompensationType,
		TargetState:      req.TargetState,
		RollbackScript:   req.RollbackScript,
		NotifyUsers:      req.NotifyUsers,
		Metadata:         req.Metadata,
		Checksum:         checksum,
	}

	compensationActionStore[id] = action
	compensationActionIdempotency[req.IdempotencyKey] = id

	return action, nil
}

// GetCompensationAction retrieves a compensation action by ID.
func GetCompensationAction(id string) (*CompensationAction, error) {
	if id == "" {
		return nil, fmt.Errorf("workflow-compensation-action-id-empty")
	}
	action, found := compensationActionStore[id]
	if !found {
		return nil, fmt.Errorf("workflow-compensation-action-not-found")
	}
	return action, nil
}

// UpdateCompensationAction updates an existing compensation action.
func UpdateCompensationAction(id string, req *CompensationActionRequest) (*CompensationAction, error) {
	if id == "" {
		return nil, fmt.Errorf("workflow-compensation-action-id-empty")
	}
	if err := ValidateCompensationActionRequest(req); err != nil {
		return nil, err
	}

	if _, found := compensationActionStore[id]; !found {
		return nil, fmt.Errorf("workflow-compensation-action-not-found")
	}

	checksum := GenerateCompensationActionChecksum(req)

	action := &CompensationAction{
		ID:               id,
		ActionID:         req.ActionID,
		WorkflowID:       req.WorkflowID,
		StepID:           req.StepID,
		TriggerCondition: req.TriggerCondition,
		CompensationType: req.CompensationType,
		TargetState:      req.TargetState,
		RollbackScript:   req.RollbackScript,
		NotifyUsers:      req.NotifyUsers,
		Metadata:         req.Metadata,
		Checksum:         checksum,
	}

	compensationActionStore[id] = action

	return action, nil
}

// ListCompensationActions lists all compensation actions.
func ListCompensationActions() []*CompensationAction {
	actions := make([]*CompensationAction, 0, len(compensationActionStore))
	for _, action := range compensationActionStore {
		actions = append(actions, action)
	}
	return actions
}

// ListCompensationActionsByWorkflow lists compensation actions for a specific workflow.
func ListCompensationActionsByWorkflow(workflowID string) []*CompensationAction {
	actions := make([]*CompensationAction, 0)
	for _, action := range compensationActionStore {
		if action.WorkflowID == workflowID {
			actions = append(actions, action)
		}
	}
	return actions
}

// DeleteCompensationAction deletes a compensation action by ID.
func DeleteCompensationAction(id string) error {
	if id == "" {
		return fmt.Errorf("workflow-compensation-action-id-empty")
	}
	if _, found := compensationActionStore[id]; !found {
		return fmt.Errorf("workflow-compensation-action-not-found")
	}
	delete(compensationActionStore, id)
	return nil
}

// GenerateCompensationActionChecksum generates a SHA256 checksum for a compensation action request.
func GenerateCompensationActionChecksum(req *CompensationActionRequest) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%s",
		req.ActionID, req.WorkflowID, req.StepID,
		req.TriggerCondition, req.CompensationType,
		req.TargetState, req.RollbackScript)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

func generateCompensationActionID(req *CompensationActionRequest) string {
	data := fmt.Sprintf("%s-%s-%s", req.WorkflowID, req.StepID, req.ActionID)
	hash := sha256.Sum256([]byte(data))
	return fmt.Sprintf("compensation-%s", hex.EncodeToString(hash[:16]))
}
