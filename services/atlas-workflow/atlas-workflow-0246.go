package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"sync"
	"time"
)

// WorkflowFailureIsolation represents a failure isolation policy
type WorkflowFailureIsolation struct {
	IsolationID     string
	IdempotencyKey  string
	WorkflowID      string
	IsolationScope  string // step-level, workflow-level, tenant-level
	IsolationMode   string // continue, abort, rollback
	FailurePatterns []string
	RetryStrategy   string
	Metadata        map[string]string
	Checksum        string
	CreatedAt       time.Time
	UpdatedAt       time.Time
}

// WorkflowFailureIsolationRequest represents the request to create/update isolation
type WorkflowFailureIsolationRequest struct {
	IdempotencyKey  string
	IsolationID     string
	WorkflowID      string
	IsolationScope  string
	IsolationMode   string
	FailurePatterns []string
	RetryStrategy   string
	Metadata        map[string]string
}

var (
	isolationStore = make(map[string]*WorkflowFailureIsolation)
	isolationMutex sync.RWMutex
	isolationKeys  = make(map[string]string)
)

// ValidateWorkflowFailureIsolationRequest validates the isolation request
func ValidateWorkflowFailureIsolationRequest(req *WorkflowFailureIsolationRequest) error {
	if req == nil {
		return errors.New("request cannot be nil")
	}

	if req.IdempotencyKey == "" {
		return errors.New("idempotency key is required")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("idempotency key must be at least 16 characters")
	}

	if req.IsolationID == "" {
		return errors.New("isolation ID is required")
	}
	if !strings.HasPrefix(req.IsolationID, "isolation-") {
		return errors.New("isolation ID must start with 'isolation-'")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow ID is required")
	}

	if req.IsolationScope == "" {
		return errors.New("isolation scope is required")
	}
	validScopes := map[string]bool{
		"step-level":     true,
		"workflow-level": true,
		"tenant-level":   true,
	}
	if !validScopes[req.IsolationScope] {
		return errors.New("isolation scope must be one of: step-level, workflow-level, tenant-level")
	}

	if req.IsolationMode == "" {
		return errors.New("isolation mode is required")
	}
	validModes := map[string]bool{
		"continue": true,
		"abort":    true,
		"rollback": true,
	}
	if !validModes[req.IsolationMode] {
		return errors.New("isolation mode must be one of: continue, abort, rollback")
	}

	if len(req.FailurePatterns) == 0 {
		return errors.New("at least one failure pattern is required")
	}

	if req.RetryStrategy == "" {
		return errors.New("retry strategy is required")
	}

	// Reject direct PHI patterns in metadata keys
	for key := range req.Metadata {
		lowerKey := strings.ToLower(key)
		if strings.Contains(lowerKey, "patient_id") || strings.Contains(lowerKey, "birth_date") ||
			strings.Contains(lowerKey, "identifier") {
			return fmt.Errorf("metadata key '%s' contains prohibited PHI pattern", key)
		}
	}

	return nil
}

// CreateWorkflowFailureIsolation creates a new failure isolation
func CreateWorkflowFailureIsolation(req *WorkflowFailureIsolationRequest) (*WorkflowFailureIsolation, error) {
	if err := ValidateWorkflowFailureIsolationRequest(req); err != nil {
		return nil, err
	}

	isolationMutex.Lock()
	defer isolationMutex.Unlock()

	// Check idempotency
	if existingID, exists := isolationKeys[req.IdempotencyKey]; exists {
		return isolationStore[existingID], nil
	}

	// Check for duplicate isolation ID
	if _, exists := isolationStore[req.IsolationID]; exists {
		return nil, fmt.Errorf("isolation ID '%s' already exists", req.IsolationID)
	}

	now := time.Now()
	isolation := &WorkflowFailureIsolation{
		IsolationID:     req.IsolationID,
		IdempotencyKey:  req.IdempotencyKey,
		WorkflowID:      req.WorkflowID,
		IsolationScope:  req.IsolationScope,
		IsolationMode:   req.IsolationMode,
		FailurePatterns: req.FailurePatterns,
		RetryStrategy:   req.RetryStrategy,
		Metadata:        req.Metadata,
		CreatedAt:       now,
		UpdatedAt:       now,
	}

	isolation.Checksum = GenerateIsolationChecksum(isolation)
	isolationStore[isolation.IsolationID] = isolation
	isolationKeys[req.IdempotencyKey] = isolation.IsolationID

	return isolation, nil
}

// GetWorkflowFailureIsolation retrieves an isolation by ID
func GetWorkflowFailureIsolation(isolationID string) (*WorkflowFailureIsolation, error) {
	if isolationID == "" {
		return nil, errors.New("isolation ID is required")
	}

	isolationMutex.RLock()
	defer isolationMutex.RUnlock()

	isolation, exists := isolationStore[isolationID]
	if !exists {
		return nil, fmt.Errorf("isolation '%s' not found", isolationID)
	}

	return isolation, nil
}

// UpdateWorkflowFailureIsolation updates an existing isolation
func UpdateWorkflowFailureIsolation(req *WorkflowFailureIsolationRequest) (*WorkflowFailureIsolation, error) {
	if err := ValidateWorkflowFailureIsolationRequest(req); err != nil {
		return nil, err
	}

	isolationMutex.Lock()
	defer isolationMutex.Unlock()

	isolation, exists := isolationStore[req.IsolationID]
	if !exists {
		return nil, fmt.Errorf("isolation '%s' not found", req.IsolationID)
	}

	// Update fields
	isolation.IsolationScope = req.IsolationScope
	isolation.IsolationMode = req.IsolationMode
	isolation.FailurePatterns = req.FailurePatterns
	isolation.RetryStrategy = req.RetryStrategy
	isolation.Metadata = req.Metadata
	isolation.UpdatedAt = time.Now()
	isolation.Checksum = GenerateIsolationChecksum(isolation)

	return isolation, nil
}

// DeleteWorkflowFailureIsolation deletes an isolation
func DeleteWorkflowFailureIsolation(isolationID string) error {
	if isolationID == "" {
		return errors.New("isolation ID is required")
	}

	isolationMutex.Lock()
	defer isolationMutex.Unlock()

	isolation, exists := isolationStore[isolationID]
	if !exists {
		return fmt.Errorf("isolation '%s' not found", isolationID)
	}

	delete(isolationKeys, isolation.IdempotencyKey)
	delete(isolationStore, isolationID)

	return nil
}

// ListWorkflowFailureIsolations lists all isolations
func ListWorkflowFailureIsolations() []*WorkflowFailureIsolation {
	isolationMutex.RLock()
	defer isolationMutex.RUnlock()

	isolations := make([]*WorkflowFailureIsolation, 0, len(isolationStore))
	for _, isolation := range isolationStore {
		isolations = append(isolations, isolation)
	}

	return isolations
}

// ListWorkflowFailureIsolationsByWorkflow lists isolations for a workflow
func ListWorkflowFailureIsolationsByWorkflow(workflowID string) []*WorkflowFailureIsolation {
	isolationMutex.RLock()
	defer isolationMutex.RUnlock()

	isolations := make([]*WorkflowFailureIsolation, 0)
	for _, isolation := range isolationStore {
		if isolation.WorkflowID == workflowID {
			isolations = append(isolations, isolation)
		}
	}

	return isolations
}

// GenerateIsolationChecksum generates a SHA256 checksum for the isolation
func GenerateIsolationChecksum(isolation *WorkflowFailureIsolation) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%v|%s",
		isolation.IsolationID,
		isolation.WorkflowID,
		isolation.IsolationScope,
		isolation.IsolationMode,
		isolation.FailurePatterns,
		isolation.RetryStrategy,
	)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
