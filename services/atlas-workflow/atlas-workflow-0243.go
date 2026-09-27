package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
)

// ClinicalWriteGuardRequest represents a request to validate clinical write operations.
type ClinicalWriteGuardRequest struct {
	Synthetic       bool              `json:"synthetic"`
	IdempotencyKey  string            `json:"idempotency_key"`
	GuardID         string            `json:"guard_id"`
	WorkflowID      string            `json:"workflow_id"`
	StepID          string            `json:"step_id"`
	OperationType   string            `json:"operation_type"` // "create", "update", "delete"
	ResourceType    string            `json:"resource_type"`  // FHIR resource type
	ExecutionMode   string            `json:"execution_mode"` // "automatic", "manual"
	RequiresReview  bool              `json:"requires_review"`
	ReviewerRole    string            `json:"reviewer_role,omitempty"`
	JustificationRequired bool        `json:"justification_required"`
	Metadata        map[string]string `json:"metadata,omitempty"`
}

// ClinicalWriteGuard represents a clinical write guard configuration.
type ClinicalWriteGuard struct {
	GuardID         string            `json:"guard_id"`
	WorkflowID      string            `json:"workflow_id"`
	StepID          string            `json:"step_id"`
	OperationType   string            `json:"operation_type"`
	ResourceType    string            `json:"resource_type"`
	ExecutionMode   string            `json:"execution_mode"`
	RequiresReview  bool              `json:"requires_review"`
	ReviewerRole    string            `json:"reviewer_role"`
	JustificationRequired bool        `json:"justification_required"`
	Metadata        map[string]string `json:"metadata"`
	Checksum        string            `json:"checksum"`
}

var clinicalWriteGuardStore = make(map[string]*ClinicalWriteGuard)
var clinicalWriteGuardIdempotency = make(map[string]string)

// ValidateClinicalWriteGuardRequest validates a clinical write guard request.
func ValidateClinicalWriteGuardRequest(req *ClinicalWriteGuardRequest) error {
	// Verify request is not nil
	if req == nil {
		return fmt.Errorf("workflow-clinical-write-guard-request-nil")
	}
	// Check synthetic flag is enabled
	if !req.Synthetic {
		return fmt.Errorf("workflow-clinical-write-guard-not-synthetic")
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("workflow-clinical-write-guard-idempotency-key-empty")
	}
	if len(req.IdempotencyKey) < 16 {
		return fmt.Errorf("workflow-clinical-write-guard-idempotency-key-too-short")
	}
	if req.GuardID == "" {
		return fmt.Errorf("workflow-clinical-write-guard-id-empty")
	}
	if !strings.HasPrefix(req.GuardID, "synthetic-guard-") {
		return fmt.Errorf("workflow-clinical-write-guard-id-invalid-prefix")
	}
	if req.WorkflowID == "" {
		return fmt.Errorf("workflow-clinical-write-guard-workflow-id-empty")
	}
	if req.StepID == "" {
		return fmt.Errorf("workflow-clinical-write-guard-step-id-empty")
	}
	if req.OperationType == "" {
		return fmt.Errorf("workflow-clinical-write-guard-operation-type-empty")
	}
	validOperations := map[string]bool{"create": true, "update": true, "delete": true}
	if !validOperations[req.OperationType] {
		return fmt.Errorf("workflow-clinical-write-guard-operation-type-invalid")
	}
	if req.ResourceType == "" {
		return fmt.Errorf("workflow-clinical-write-guard-resource-type-empty")
	}
	if req.ExecutionMode == "" {
		return fmt.Errorf("workflow-clinical-write-guard-execution-mode-empty")
	}
	validModes := map[string]bool{"automatic": true, "manual": true}
	if !validModes[req.ExecutionMode] {
		return fmt.Errorf("workflow-clinical-write-guard-execution-mode-invalid")
	}
	// Automatic clinical writes are prohibited
	if req.ExecutionMode == "automatic" {
		return fmt.Errorf("workflow-clinical-write-guard-automatic-write-prohibited")
	}
	if req.RequiresReview && req.ReviewerRole == "" {
		return fmt.Errorf("workflow-clinical-write-guard-reviewer-role-required")
	}
	// PHI pattern rejection
	phiPatterns := []string{"patient-", "mrn-", "ssn-", "dob-"}
	for _, pattern := range phiPatterns {
		if strings.Contains(req.ResourceType, pattern) {
			return fmt.Errorf("workflow-clinical-write-guard-phi-pattern-in-resource-type")
		}
		if strings.Contains(req.ReviewerRole, pattern) {
			return fmt.Errorf("workflow-clinical-write-guard-phi-pattern-in-reviewer-role")
		}
		for k := range req.Metadata {
			if strings.Contains(k, pattern) {
				return fmt.Errorf("workflow-clinical-write-guard-phi-pattern-in-metadata-key")
			}
		}
	}
	return nil
}

// CreateClinicalWriteGuard creates a new clinical write guard.
func CreateClinicalWriteGuard(req *ClinicalWriteGuardRequest) (*ClinicalWriteGuard, error) {
	if err := ValidateClinicalWriteGuardRequest(req); err != nil {
		return nil, err
	}
	// Check idempotency
	if existingID, exists := clinicalWriteGuardIdempotency[req.IdempotencyKey]; exists {
		return clinicalWriteGuardStore[existingID], nil
	}
	guard := &ClinicalWriteGuard{
		GuardID:               req.GuardID,
		WorkflowID:            req.WorkflowID,
		StepID:                req.StepID,
		OperationType:         req.OperationType,
		ResourceType:          req.ResourceType,
		ExecutionMode:         req.ExecutionMode,
		RequiresReview:        req.RequiresReview,
		ReviewerRole:          req.ReviewerRole,
		JustificationRequired: req.JustificationRequired,
		Metadata:              req.Metadata,
	}
	guard.Checksum = GenerateClinicalWriteGuardChecksum(guard)
	clinicalWriteGuardStore[guard.GuardID] = guard
	clinicalWriteGuardIdempotency[req.IdempotencyKey] = guard.GuardID
	return guard, nil
}

// GetClinicalWriteGuard retrieves a clinical write guard by ID.
func GetClinicalWriteGuard(guardID string) (*ClinicalWriteGuard, error) {
	if guardID == "" {
		return nil, fmt.Errorf("workflow-clinical-write-guard-id-empty")
	}
	guard, exists := clinicalWriteGuardStore[guardID]
	if !exists {
		return nil, fmt.Errorf("workflow-clinical-write-guard-not-found")
	}
	return guard, nil
}

// UpdateClinicalWriteGuard updates an existing clinical write guard.
func UpdateClinicalWriteGuard(guardID string, req *ClinicalWriteGuardRequest) (*ClinicalWriteGuard, error) {
	if guardID == "" {
		return nil, fmt.Errorf("workflow-clinical-write-guard-id-empty")
	}
	if err := ValidateClinicalWriteGuardRequest(req); err != nil {
		return nil, err
	}
	if _, exists := clinicalWriteGuardStore[guardID]; !exists {
		return nil, fmt.Errorf("workflow-clinical-write-guard-not-found")
	}
	guard := &ClinicalWriteGuard{
		GuardID:               guardID,
		WorkflowID:            req.WorkflowID,
		StepID:                req.StepID,
		OperationType:         req.OperationType,
		ResourceType:          req.ResourceType,
		ExecutionMode:         req.ExecutionMode,
		RequiresReview:        req.RequiresReview,
		ReviewerRole:          req.ReviewerRole,
		JustificationRequired: req.JustificationRequired,
		Metadata:              req.Metadata,
	}
	guard.Checksum = GenerateClinicalWriteGuardChecksum(guard)
	clinicalWriteGuardStore[guardID] = guard
	return guard, nil
}

// ListClinicalWriteGuards returns all clinical write guards.
func ListClinicalWriteGuards() []*ClinicalWriteGuard {
	guards := make([]*ClinicalWriteGuard, 0, len(clinicalWriteGuardStore))
	for _, guard := range clinicalWriteGuardStore {
		guards = append(guards, guard)
	}
	return guards
}

// ListClinicalWriteGuardsByWorkflow returns guards for a specific workflow.
func ListClinicalWriteGuardsByWorkflow(workflowID string) []*ClinicalWriteGuard {
	guards := make([]*ClinicalWriteGuard, 0)
	for _, guard := range clinicalWriteGuardStore {
		if guard.WorkflowID == workflowID {
			guards = append(guards, guard)
		}
	}
	return guards
}

// DeleteClinicalWriteGuard removes a clinical write guard.
func DeleteClinicalWriteGuard(guardID string) error {
	if guardID == "" {
		return fmt.Errorf("workflow-clinical-write-guard-id-empty")
	}
	if _, exists := clinicalWriteGuardStore[guardID]; !exists {
		return fmt.Errorf("workflow-clinical-write-guard-not-found")
	}
	delete(clinicalWriteGuardStore, guardID)
	return nil
}

// GenerateClinicalWriteGuardChecksum generates a SHA256 checksum for a guard.
func GenerateClinicalWriteGuardChecksum(guard *ClinicalWriteGuard) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%s|%s|%t|%s|%t",
		guard.GuardID,
		guard.WorkflowID,
		guard.StepID,
		guard.OperationType,
		guard.ResourceType,
		guard.ExecutionMode,
		guard.RequiresReview,
		guard.ReviewerRole,
		guard.JustificationRequired,
	)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
