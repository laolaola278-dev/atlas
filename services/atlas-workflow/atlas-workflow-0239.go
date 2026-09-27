// Package workflow provides workflow definition management with synthetic-only validation.
// This module implements fail-closed workflow definition gates.
package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"regexp"
	"strings"
	"sync"
	"time"
)

// WorkflowDefinitionRequest represents a workflow definition creation or update request.
type WorkflowDefinitionRequest struct {
	DefinitionID    string            `json:"definition_id"`
	Name            string            `json:"name"`
	Version         string            `json:"version"`
	Steps           []WorkflowStep    `json:"steps"`
	Transitions     []StateTransition `json:"transitions"`
	InitialState    string            `json:"initial_state"`
	FinalStates     []string          `json:"final_states"`
	Metadata        map[string]string `json:"metadata"`
	IdempotencyKey  string            `json:"idempotency_key"`
	Synthetic       bool              `json:"synthetic"`
}

// WorkflowStep represents a single step in the workflow.
type WorkflowStep struct {
	StepID      string            `json:"step_id"`
	StepType    string            `json:"step_type"`
	Name        string            `json:"name"`
	Description string            `json:"description"`
	Config      map[string]string `json:"config"`
}

// StateTransition defines allowed transitions between workflow states.
type StateTransition struct {
	FromState string   `json:"from_state"`
	ToState   string   `json:"to_state"`
	Event     string   `json:"event"`
	Conditions []string `json:"conditions"`
}

// WorkflowDefinitionResponse represents the response after creating/updating a workflow definition.
type WorkflowDefinitionResponse struct {
	DefinitionID string            `json:"definition_id"`
	Name         string            `json:"name"`
	Version      string            `json:"version"`
	Checksum     string            `json:"checksum"`
	CreatedAt    string            `json:"created_at"`
	Metadata     map[string]string `json:"metadata"`
}

var (
	definitionStore      = make(map[string]*WorkflowDefinitionResponse)
	definitionMutex      sync.RWMutex
	idempotencyStore     = make(map[string]string)
	idempotencyMutex     sync.RWMutex
	phiPatterns          = []*regexp.Regexp{
		regexp.MustCompile(`(?i)\bpatient[-_]?id\b`),
		regexp.MustCompile(`(?i)\bpatient[-_]?name\b`),
		regexp.MustCompile(`(?i)\bidentifier\b`),
		regexp.MustCompile(`(?i)\bphone\b`),
		regexp.MustCompile(`(?i)\baddress\b`),
		regexp.MustCompile(`(?i)\bbirth[-_]?date\b`),
	}
	validStepTypes = map[string]bool{
		"manual":    true,
		"automatic": true,
		"decision":  true,
		"parallel":  true,
		"wait":      true,
	}
)

// ValidateWorkflowDefinitionRequest validates a workflow definition request.
func ValidateWorkflowDefinitionRequest(req *WorkflowDefinitionRequest) error {
	if req == nil {
		return errors.New("workflow-definition-request-nil")
	}

	if !req.Synthetic {
		return errors.New("workflow-definition-synthetic-required")
	}

	// Validate idempotency key first
	if req.IdempotencyKey == "" {
		return errors.New("workflow-definition-idempotency-required")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("workflow-definition-idempotency-too-short")
	}

	// Validate definition ID
	if req.DefinitionID == "" {
		return errors.New("workflow-definition-id-empty")
	}
	if !strings.HasPrefix(req.DefinitionID, "wf-") {
		return errors.New("workflow-definition-id-invalid-prefix")
	}

	// Validate name
	if req.Name == "" {
		return errors.New("workflow-definition-name-empty")
	}

	// Check PHI patterns in name
	for _, pattern := range phiPatterns {
		if pattern.MatchString(req.Name) {
			return errors.New("workflow-definition-phi-pattern-detected")
		}
	}

	// Validate version
	if req.Version == "" {
		return errors.New("workflow-definition-version-empty")
	}

	// Validate steps
	if len(req.Steps) == 0 {
		return errors.New("workflow-definition-steps-empty")
	}

	// Validate each step
	stepIDs := make(map[string]bool)
	for _, step := range req.Steps {
		if step.StepID == "" {
			return errors.New("workflow-definition-step-id-empty")
		}
		if stepIDs[step.StepID] {
			return errors.New("workflow-definition-duplicate-step-id")
		}
		stepIDs[step.StepID] = true

		if step.StepType == "" {
			return errors.New("workflow-definition-step-type-empty")
		}
		if !validStepTypes[step.StepType] {
			return errors.New("workflow-definition-step-type-invalid")
		}

		if step.Name == "" {
			return errors.New("workflow-definition-step-name-empty")
		}

		// Check PHI patterns in step config
		for key := range step.Config {
			for _, pattern := range phiPatterns {
				if pattern.MatchString(key) {
					return errors.New("workflow-definition-phi-pattern-detected")
				}
			}
		}
	}

	// Validate initial state
	if req.InitialState == "" {
		return errors.New("workflow-definition-initial-state-empty")
	}

	// Validate final states
	if len(req.FinalStates) == 0 {
		return errors.New("workflow-definition-final-states-empty")
	}

	// Validate transitions
	if len(req.Transitions) == 0 {
		return errors.New("workflow-definition-transitions-empty")
	}

	for _, transition := range req.Transitions {
		if transition.FromState == "" {
			return errors.New("workflow-definition-transition-from-empty")
		}
		if transition.ToState == "" {
			return errors.New("workflow-definition-transition-to-empty")
		}
		if transition.Event == "" {
			return errors.New("workflow-definition-transition-event-empty")
		}
	}

	// Validate metadata keys
	for key := range req.Metadata {
		if !regexp.MustCompile(`^[a-z][a-z0-9_]*$`).MatchString(key) {
			return errors.New("workflow-definition-metadata-key-invalid")
		}
		for _, pattern := range phiPatterns {
			if pattern.MatchString(key) {
				return errors.New("workflow-definition-phi-pattern-detected")
			}
		}
	}

	return nil
}

// DefineWorkflow creates or updates a workflow definition.
func DefineWorkflow(req *WorkflowDefinitionRequest) (*WorkflowDefinitionResponse, error) {
	// Check idempotency first
	idempotencyMutex.RLock()
	existingID, exists := idempotencyStore[req.IdempotencyKey]
	idempotencyMutex.RUnlock()

	if exists {
		definitionMutex.RLock()
		defer definitionMutex.RUnlock()
		if def, ok := definitionStore[existingID]; ok {
			return def, nil
		}
	}

	// Validate request
	if err := ValidateWorkflowDefinitionRequest(req); err != nil {
		return nil, err
	}

	// Generate checksum
	checksum := GenerateWorkflowDefinitionChecksum(req)

	// Create response
	resp := &WorkflowDefinitionResponse{
		DefinitionID: req.DefinitionID,
		Name:         req.Name,
		Version:      req.Version,
		Checksum:     checksum,
		CreatedAt:    time.Now().UTC().Format(time.RFC3339),
		Metadata:     req.Metadata,
	}

	// Store definition
	definitionMutex.Lock()
	definitionStore[req.DefinitionID] = resp
	definitionMutex.Unlock()

	// Store idempotency mapping
	idempotencyMutex.Lock()
	idempotencyStore[req.IdempotencyKey] = req.DefinitionID
	idempotencyMutex.Unlock()

	return resp, nil
}

// GetWorkflowDefinition retrieves a workflow definition by ID.
func GetWorkflowDefinition(definitionID string) (*WorkflowDefinitionResponse, error) {
	if definitionID == "" {
		return nil, errors.New("workflow-definition-id-empty")
	}

	definitionMutex.RLock()
	defer definitionMutex.RUnlock()

	def, exists := definitionStore[definitionID]
	if !exists {
		return nil, errors.New("workflow-definition-not-found")
	}

	return def, nil
}

// ListWorkflowDefinitions retrieves all workflow definitions.
func ListWorkflowDefinitions() ([]*WorkflowDefinitionResponse, error) {
	definitionMutex.RLock()
	defer definitionMutex.RUnlock()

	results := make([]*WorkflowDefinitionResponse, 0, len(definitionStore))
	for _, def := range definitionStore {
		results = append(results, def)
	}

	return results, nil
}

// DeleteWorkflowDefinition removes a workflow definition.
func DeleteWorkflowDefinition(definitionID string) error {
	if definitionID == "" {
		return errors.New("workflow-definition-id-empty")
	}

	definitionMutex.Lock()
	defer definitionMutex.Unlock()

	if _, exists := definitionStore[definitionID]; !exists {
		return errors.New("workflow-definition-not-found")
	}

	delete(definitionStore, definitionID)
	return nil
}

// GenerateWorkflowDefinitionChecksum generates a SHA256 checksum for the workflow definition.
func GenerateWorkflowDefinitionChecksum(req *WorkflowDefinitionRequest) string {
	h := sha256.New()
	h.Write([]byte(req.DefinitionID))
	h.Write([]byte(req.Name))
	h.Write([]byte(req.Version))
	h.Write([]byte(req.InitialState))
	for _, state := range req.FinalStates {
		h.Write([]byte(state))
	}
	for _, step := range req.Steps {
		h.Write([]byte(step.StepID))
		h.Write([]byte(step.StepType))
	}
	return hex.EncodeToString(h.Sum(nil))
}

// CleanupWorkflowDefinitions removes all workflow definitions (for testing).
func CleanupWorkflowDefinitions() {
	definitionMutex.Lock()
	definitionStore = make(map[string]*WorkflowDefinitionResponse)
	definitionMutex.Unlock()

	idempotencyMutex.Lock()
	idempotencyStore = make(map[string]string)
	idempotencyMutex.Unlock()
}
