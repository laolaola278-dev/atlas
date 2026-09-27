package workflow // Workflow trace module

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

// WorkflowTrace represents a trace record for visualization
type WorkflowTrace struct {
	TraceID          string
	WorkflowID       string
	StepID           string
	StepTitle        string
	StepStatus       string
	StepStartTime    time.Time
	StepEndTime      time.Time
	StepDuration     int
	TraceChecksum    string
	IdempotencyKey   string
	Metadata         map[string]string
}

// WorkflowTraceRequest represents input for trace operations
type WorkflowTraceRequest struct {
	TraceID        string
	WorkflowID     string
	StepID         string
	StepTitle      string
	StepStatus     string
	StepStartTime  time.Time
	StepEndTime    time.Time
	StepDuration   int
	IdempotencyKey string
	Metadata       map[string]string
}

var (
	workflowTraceStore       = make(map[string]*WorkflowTrace)
	workflowTraceIdempotency = make(map[string]string)
)

// ValidateWorkflowTraceRequest validates trace request with PHI pattern rejection
func ValidateWorkflowTraceRequest(req *WorkflowTraceRequest) error {
	if req == nil {
		return errors.New("trace request is required")
	}

	if req.IdempotencyKey == "" {
		return errors.New("idempotency key is required")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("idempotency key must be at least 16 characters")
	}

	if req.TraceID == "" {
		return errors.New("trace ID is required")
	}
	if !strings.HasPrefix(req.TraceID, "synthetic-trace-") {
		return errors.New("trace ID must start with 'synthetic-trace-'")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow ID is required")
	}

	if req.StepID == "" {
		return errors.New("step ID is required")
	}

	if strings.TrimSpace(req.StepTitle) == "" {
		return errors.New("step title cannot be blank")
	}

	if req.StepStatus == "" {
		return errors.New("step status is required")
	}
	validStatuses := map[string]bool{
		"pending":    true,
		"running":    true,
		"completed":  true,
		"failed":     true,
		"skipped":    true,
	}
	if !validStatuses[req.StepStatus] {
		return errors.New("step status must be one of: pending, running, completed, failed, skipped")
	}

	if req.StepDuration < 0 {
		return errors.New("step duration cannot be negative")
	}

	phiPatterns := []string{"name", "identifier", "phone", "address", "birth_date", "patient_id"}
	for key := range req.Metadata {
		keyLower := strings.ToLower(key)
		for _, pattern := range phiPatterns {
			if strings.Contains(keyLower, pattern) {
				return fmt.Errorf("metadata key '%s' contains PHI pattern '%s'", key, pattern)
			}
		}
	}

	return nil
}

// CreateWorkflowTrace creates a new workflow trace with idempotency
func CreateWorkflowTrace(req *WorkflowTraceRequest) (*WorkflowTrace, error) {
	if err := ValidateWorkflowTraceRequest(req); err != nil {
		return nil, err
	}

	if existingID, found := workflowTraceIdempotency[req.IdempotencyKey]; found {
		return workflowTraceStore[existingID], nil
	}

	if _, exists := workflowTraceStore[req.TraceID]; exists {
		return nil, errors.New("trace ID already exists")
	}

	checksum := GenerateTraceChecksum(req)

	trace := &WorkflowTrace{
		TraceID:        req.TraceID,
		WorkflowID:     req.WorkflowID,
		StepID:         req.StepID,
		StepTitle:      req.StepTitle,
		StepStatus:     req.StepStatus,
		StepStartTime:  req.StepStartTime,
		StepEndTime:    req.StepEndTime,
		StepDuration:   req.StepDuration,
		TraceChecksum:  checksum,
		IdempotencyKey: req.IdempotencyKey,
		Metadata:       req.Metadata,
	}

	workflowTraceStore[trace.TraceID] = trace
	workflowTraceIdempotency[req.IdempotencyKey] = trace.TraceID

	return trace, nil
}

// GetWorkflowTrace retrieves a trace by ID
func GetWorkflowTrace(traceID string) (*WorkflowTrace, error) {
	if traceID == "" {
		return nil, errors.New("trace ID is required")
	}

	trace, found := workflowTraceStore[traceID]
	if !found {
		return nil, errors.New("trace not found")
	}

	return trace, nil
}

// UpdateWorkflowTrace updates an existing trace
func UpdateWorkflowTrace(req *WorkflowTraceRequest) (*WorkflowTrace, error) {
	if err := ValidateWorkflowTraceRequest(req); err != nil {
		return nil, err
	}

	trace, found := workflowTraceStore[req.TraceID]
	if !found {
		return nil, errors.New("trace not found")
	}

	trace.StepStatus = req.StepStatus
	trace.StepEndTime = req.StepEndTime
	trace.StepDuration = req.StepDuration
	trace.Metadata = req.Metadata
	trace.TraceChecksum = GenerateTraceChecksum(req)

	return trace, nil
}

// DeleteWorkflowTrace removes a trace by ID
func DeleteWorkflowTrace(traceID string) error {
	if traceID == "" {
		return errors.New("trace ID is required")
	}

	trace, found := workflowTraceStore[traceID]
	if !found {
		return errors.New("trace not found")
	}

	delete(workflowTraceIdempotency, trace.IdempotencyKey)
	delete(workflowTraceStore, traceID)

	return nil
}

// ListWorkflowTraces returns all traces
func ListWorkflowTraces() []*WorkflowTrace {
	traces := make([]*WorkflowTrace, 0, len(workflowTraceStore))
	for _, trace := range workflowTraceStore {
		traces = append(traces, trace)
	}
	return traces
}

// ListWorkflowTracesByWorkflow returns traces for a specific workflow
func ListWorkflowTracesByWorkflow(workflowID string) []*WorkflowTrace {
	traces := make([]*WorkflowTrace, 0)
	for _, trace := range workflowTraceStore {
		if trace.WorkflowID == workflowID {
			traces = append(traces, trace)
		}
	}
	return traces
}

// GenerateTraceChecksum generates SHA256 checksum for a trace
func GenerateTraceChecksum(req *WorkflowTraceRequest) string {
	data := fmt.Sprintf("%s|%s|%s|%s|%s|%d|%s",
		req.TraceID,
		req.WorkflowID,
		req.StepID,
		req.StepTitle,
		req.StepStatus,
		req.StepDuration,
		req.StepEndTime.Format(time.RFC3339),
	)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}
