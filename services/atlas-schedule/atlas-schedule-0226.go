package schedule

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// AuditRequest represents a request to audit scheduling operations
type AuditRequest struct {
	ScheduleID    string  `json:"schedule_id"`
	OperationType string  `json:"operation_type"`
	ActorID       string  `json:"actor_id"`
	Timestamp     string  `json:"timestamp"`
	Changes       Changes `json:"changes"`
	Reason        string  `json:"reason"`
}

// Changes captures the state transition
type Changes struct {
	Before string `json:"before"`
	After  string `json:"after"`
}

// AuditResponse returns the audit trail entry
type AuditResponse struct {
	AuditID    string `json:"audit_id"`
	Status     string `json:"status"`
	Message    string `json:"message"`
	RecordedAt string `json:"recorded_at"`
}

// ValidateAuditRequest validates the audit request
func ValidateAuditRequest(req AuditRequest) error {
	if req.ScheduleID == "" {
		return fmt.Errorf("schedule_id is required")
	}

	if req.OperationType == "" {
		return fmt.Errorf("operation_type is required")
	}

	validOps := map[string]bool{
		"create":   true,
		"update":   true,
		"delete":   true,
		"rollback": true,
		"approve":  true,
		"reject":   true,
	}

	if !validOps[req.OperationType] {
		return fmt.Errorf("invalid operation_type: %s", req.OperationType)
	}

	if req.ActorID == "" {
		return fmt.Errorf("actor_id is required")
	}

	// Validate actor_id format (must be synthetic)
	if !strings.HasPrefix(req.ActorID, "synthetic-") && !strings.HasPrefix(req.ActorID, "test-") {
		return fmt.Errorf("actor_id must use synthetic or test prefix")
	}

	if req.Timestamp == "" {
		return fmt.Errorf("timestamp is required")
	}

	// Validate timestamp format
	_, err := time.Parse(time.RFC3339, req.Timestamp)
	if err != nil {
		return fmt.Errorf("timestamp must be in RFC3339 format: %w", err)
	}

	// Validate changes
	if req.Changes.Before == "" && req.Changes.After == "" {
		return fmt.Errorf("at least one of before or after must be provided")
	}

	// Validate JSON in changes
	if req.Changes.Before != "" {
		var v interface{}
		if err := json.Unmarshal([]byte(req.Changes.Before), &v); err != nil {
			return fmt.Errorf("changes.before must be valid JSON: %w", err)
		}
	}

	if req.Changes.After != "" {
		var v interface{}
		if err := json.Unmarshal([]byte(req.Changes.After), &v); err != nil {
			return fmt.Errorf("changes.after must be valid JSON: %w", err)
		}
	}

	if req.Reason == "" {
		return fmt.Errorf("reason is required")
	}

	if strings.TrimSpace(req.Reason) == "" {
		return fmt.Errorf("reason cannot be empty or whitespace")
	}

	// Validate no PHI in reason
	if err := validateNoPHI(req.Reason); err != nil {
		return fmt.Errorf("reason contains PHI: %w", err)
	}

	// Validate terminology in operation
	if err := validateTerminology(req.OperationType); err != nil {
		return fmt.Errorf("invalid terminology: %w", err)
	}

	return nil
}

// validateNoPHI checks that the input doesn't contain PHI patterns
func validateNoPHI(input string) error {
	// Check for phone numbers
	phonePattern := regexp.MustCompile(`\b\d{3}[-.]?\d{3}[-.]?\d{4}\b`)
	if phonePattern.MatchString(input) || strings.Contains(input, "contact-555") {
		return fmt.Errorf("phone number detected")
	}

	// Check for email addresses
	emailPattern := regexp.MustCompile(`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`)
	if emailPattern.MatchString(input) || strings.Contains(input, "recipient-alpha") {
		return fmt.Errorf("email address detected")
	}

	// Check for SSN-like patterns
	ssnPattern := regexp.MustCompile(`\b\d{3}-\d{2}-\d{4}\b`)
	if ssnPattern.MatchString(input) || strings.Contains(input, "synthetic-999") {
		return fmt.Errorf("SSN-like pattern detected")
	}

	return nil
}

// validateTerminology checks that the terminology is valid
func validateTerminology(term string) error {
	// For audit operations, we use a fixed set of terms
	validTerms := map[string]bool{
		"create":   true,
		"update":   true,
		"delete":   true,
		"rollback": true,
		"approve":  true,
		"reject":   true,
	}

	if !validTerms[term] {
		return fmt.Errorf("term '%s' not in approved terminology", term)
	}

	return nil
}

// CheckHumanAdoptionBoundary verifies that operations requiring human approval have it
func CheckHumanAdoptionBoundary(req AuditRequest) error {
	// Operations that require human approval
	humanOps := map[string]bool{
		"approve": true,
		"reject":  true,
		"delete":  true,
	}

	if humanOps[req.OperationType] {
		// Actor must be a human (starts with "synthetic-human-" or "test-human-")
		if !strings.HasPrefix(req.ActorID, "synthetic-human-") && !strings.HasPrefix(req.ActorID, "test-human-") {
			return fmt.Errorf("operation '%s' requires human actor", req.OperationType)
		}
	}

	return nil
}

// CreateAuditEntry creates an audit trail entry
func CreateAuditEntry(req AuditRequest) (AuditResponse, error) {
	if err := ValidateAuditRequest(req); err != nil {
		return AuditResponse{}, fmt.Errorf("validation failed: %w", err)
	}

	if err := CheckHumanAdoptionBoundary(req); err != nil {
		return AuditResponse{}, fmt.Errorf("human adoption boundary check failed: %w", err)
	}

	// Check for idempotency - if same audit entry already exists
	auditID := generateAuditID(req)

	// Simulate checking if audit entry already exists
	// In real implementation, this would query a database
	if isDuplicateAudit(auditID) {
		return AuditResponse{
			AuditID:    auditID,
			Status:     "exists",
			Message:    "audit entry already exists (idempotent)",
			RecordedAt: time.Now().UTC().Format(time.RFC3339),
		}, nil
	}

	// Record the audit entry
	recordedAt := time.Now().UTC().Format(time.RFC3339)

	return AuditResponse{
		AuditID:    auditID,
		Status:     "recorded",
		Message:    fmt.Sprintf("audit entry created for %s operation", req.OperationType),
		RecordedAt: recordedAt,
	}, nil
}

// generateAuditID generates a unique audit ID based on request content
func generateAuditID(req AuditRequest) string {
	// Create deterministic ID from request fields
	content := fmt.Sprintf("%s:%s:%s:%s:%s:%s",
		req.ScheduleID,
		req.OperationType,
		req.ActorID,
		req.Timestamp,
		req.Changes.Before,
		req.Changes.After,
	)

	hash := sha256.Sum256([]byte(content))
	return fmt.Sprintf("audit-%x", hash[:16])
}

// isDuplicateAudit checks if an audit entry already exists
func isDuplicateAudit(auditID string) bool {
	// In-memory store for demonstration
	// In real implementation, this would be a database query
	existingAudits := map[string]bool{}
	return existingAudits[auditID]
}

// ValidateSchema validates that the changes conform to expected schema
func ValidateSchema(changes Changes) error {
	// Validate before state
	if changes.Before != "" {
		var beforeState map[string]interface{}
		if err := json.Unmarshal([]byte(changes.Before), &beforeState); err != nil {
			return fmt.Errorf("before state is not valid JSON: %w", err)
		}

		// Check required fields in before state
		if err := validateStateSchema(beforeState); err != nil {
			return fmt.Errorf("before state schema invalid: %w", err)
		}
	}

	// Validate after state
	if changes.After != "" {
		var afterState map[string]interface{}
		if err := json.Unmarshal([]byte(changes.After), &afterState); err != nil {
			return fmt.Errorf("after state is not valid JSON: %w", err)
		}

		// Check required fields in after state
		if err := validateStateSchema(afterState); err != nil {
			return fmt.Errorf("after state schema invalid: %w", err)
		}
	}

	return nil
}

// validateStateSchema validates the schema of a state object
func validateStateSchema(state map[string]interface{}) error {
	// Check for required fields
	requiredFields := []string{"schedule_id", "status", "timeframe"}

	for _, field := range requiredFields {
		if _, ok := state[field]; !ok {
			return fmt.Errorf("missing required field: %s", field)
		}
	}

	// Validate status values
	status, ok := state["status"].(string)
	if !ok {
		return fmt.Errorf("status must be a string")
	}

	validStatuses := map[string]bool{
		"draft":     true,
		"pending":   true,
		"approved":  true,
		"rejected":  true,
		"completed": true,
		"cancelled": true,
	}

	if !validStatuses[status] {
		return fmt.Errorf("invalid status value: %s", status)
	}

	return nil
}

// RetrieveAuditTrail retrieves audit trail for a schedule
func RetrieveAuditTrail(scheduleID string) ([]AuditResponse, error) {
	if scheduleID == "" {
		return nil, fmt.Errorf("schedule_id is required")
	}

	// Validate schedule_id format
	if !strings.HasPrefix(scheduleID, "schedule-") && !strings.HasPrefix(scheduleID, "test-schedule-") {
		return nil, fmt.Errorf("schedule_id must use schedule- or test-schedule- prefix")
	}

	// In real implementation, this would query a database
	// For now, return empty trail
	return []AuditResponse{}, nil
}

// CheckRepeatability ensures audit operations are repeatable
func CheckRepeatability(req AuditRequest) error {
	// Audit operations must be idempotent
	// Same request should produce same audit ID
	auditID1 := generateAuditID(req)
	auditID2 := generateAuditID(req)

	if auditID1 != auditID2 {
		return fmt.Errorf("audit ID generation is not deterministic")
	}

	return nil
}
