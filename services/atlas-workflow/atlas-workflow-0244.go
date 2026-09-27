package workflow

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

// WorkflowEvent represents a workflow event for deduplication
type WorkflowEvent struct {
	EventID           string
	WorkflowID        string
	EventType         string
	EventPayload      string
	EventFingerprint  string
	EventTimestamp    time.Time
	DeduplicationTTL  int
	IdempotencyKey    string
	Metadata          map[string]string
}

// WorkflowEventRequest represents input for event operations
type WorkflowEventRequest struct {
	EventID          string
	WorkflowID       string
	EventType        string
	EventPayload     string
	DeduplicationTTL int
	IdempotencyKey   string
	Metadata         map[string]string
}

var (
	workflowEventStore        = make(map[string]*WorkflowEvent)
	workflowEventIdempotency  = make(map[string]string)
	workflowEventFingerprints = make(map[string]time.Time)
)

// CreateWorkflowEvent creates a new workflow event with deduplication
func CreateWorkflowEvent(req *WorkflowEventRequest) (*WorkflowEvent, error) {
	if req.IdempotencyKey != "" {
		if existingID, exists := workflowEventIdempotency[req.IdempotencyKey]; exists {
			return workflowEventStore[existingID], nil
		}
	}

	if err := ValidateWorkflowEventRequest(req); err != nil {
		return nil, err
	}

	fingerprint := GenerateEventFingerprint(req.WorkflowID, req.EventType, req.EventPayload)

	if expiry, exists := workflowEventFingerprints[fingerprint]; exists {
		if time.Now().Before(expiry) {
			return nil, errors.New("duplicate event detected within TTL window")
		}
	}

	event := &WorkflowEvent{
		EventID:          req.EventID,
		WorkflowID:       req.WorkflowID,
		EventType:        req.EventType,
		EventPayload:     req.EventPayload,
		EventFingerprint: fingerprint,
		EventTimestamp:   time.Now(),
		DeduplicationTTL: req.DeduplicationTTL,
		IdempotencyKey:   req.IdempotencyKey,
		Metadata:         req.Metadata,
	}

	workflowEventStore[event.EventID] = event
	if req.IdempotencyKey != "" {
		workflowEventIdempotency[req.IdempotencyKey] = event.EventID
	}

	ttlDuration := time.Duration(req.DeduplicationTTL) * time.Second
	workflowEventFingerprints[fingerprint] = time.Now().Add(ttlDuration)

	return event, nil
}

// GetWorkflowEvent retrieves an event by ID
func GetWorkflowEvent(eventID string) (*WorkflowEvent, error) {
	if eventID == "" {
		return nil, errors.New("event ID cannot be empty")
	}

	event, exists := workflowEventStore[eventID]
	if !exists {
		return nil, fmt.Errorf("event not found: %s", eventID)
	}

	return event, nil
}

// ListWorkflowEvents returns all events
func ListWorkflowEvents() []*WorkflowEvent {
	events := make([]*WorkflowEvent, 0, len(workflowEventStore))
	for _, event := range workflowEventStore {
		events = append(events, event)
	}
	return events
}

// ListWorkflowEventsByWorkflow returns events for a specific workflow
func ListWorkflowEventsByWorkflow(workflowID string) []*WorkflowEvent {
	events := make([]*WorkflowEvent, 0)
	for _, event := range workflowEventStore {
		if event.WorkflowID == workflowID {
			events = append(events, event)
		}
	}
	return events
}

// DeleteWorkflowEvent removes an event
func DeleteWorkflowEvent(eventID string) error {
	if eventID == "" {
		return errors.New("event ID cannot be empty")
	}

	event, exists := workflowEventStore[eventID]
	if !exists {
		return fmt.Errorf("event not found: %s", eventID)
	}

	delete(workflowEventStore, eventID)
	if event.IdempotencyKey != "" {
		delete(workflowEventIdempotency, event.IdempotencyKey)
	}

	return nil
}

// ValidateWorkflowEventRequest validates event request
func ValidateWorkflowEventRequest(req *WorkflowEventRequest) error {
	if req == nil {
		return errors.New("request cannot be nil")
	}

	if req.IdempotencyKey == "" {
		return errors.New("idempotency key is required")
	}

	if len(req.IdempotencyKey) < 16 {
		return errors.New("idempotency key must be at least 16 characters")
	}

	if req.EventID == "" {
		return errors.New("event ID is required")
	}

	if !strings.HasPrefix(req.EventID, "synthetic-event-") {
		return errors.New("event ID must start with 'synthetic-event-'")
	}

	if req.WorkflowID == "" {
		return errors.New("workflow ID is required")
	}

	if req.EventType == "" {
		return errors.New("event type is required")
	}

	validTypes := map[string]bool{
		"workflow-started":   true,
		"workflow-completed": true,
		"step-executed":      true,
		"step-failed":        true,
		"timeout-triggered":  true,
	}
	if !validTypes[req.EventType] {
		return fmt.Errorf("invalid event type: %s", req.EventType)
	}

	if req.EventPayload == "" {
		return errors.New("event payload is required")
	}

	if req.DeduplicationTTL <= 0 {
		return errors.New("deduplication TTL must be positive")
	}

	for key := range req.Metadata {
		if containsPHIPattern(key) {
			return fmt.Errorf("metadata key contains PHI pattern: %s", key)
		}
	}

	return nil
}

// GenerateEventFingerprint creates a deterministic fingerprint for deduplication
func GenerateEventFingerprint(workflowID, eventType, payload string) string {
	input := fmt.Sprintf("%s|%s|%s", workflowID, eventType, payload)
	hash := sha256.Sum256([]byte(input))
	return hex.EncodeToString(hash[:])
}

func containsPHIPattern(s string) bool {
	lowerS := strings.ToLower(s)
	phiPatterns := []string{"patient", "name", "address", "phone", "ssn", "birth"}
	for _, pattern := range phiPatterns {
		if strings.Contains(lowerS, pattern) {
			return true
		}
	}
	return false
}
