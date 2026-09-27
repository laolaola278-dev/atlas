package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
)

// TrackFormEventRequest represents a request to track a form event
type TrackFormEventRequest struct {
	EventID        string            `json:"event_id"`
	FormID         string            `json:"form_id"`
	EventType      string            `json:"event_type"`
	ActorRole      string            `json:"actor_role"`
	Timestamp      string            `json:"timestamp"`
	Details        map[string]string `json:"details"`
	IdempotencyKey string            `json:"idempotency_key"`
	Synthetic      bool              `json:"synthetic"`
}

// FormEventResponse contains the tracked form event
// with audit trail information
type FormEventResponse struct {
	EventID   string            `json:"event_id"`
	FormID    string            `json:"form_id"`
	EventType string            `json:"event_type"`
	ActorRole string            `json:"actor_role"`
	Timestamp time.Time         `json:"timestamp"`
	Details   map[string]string `json:"details"`
	Digest    string            `json:"digest"`
}

var (
	formEventStore       = make(map[string]*FormEventResponse)
	formEventIdempotency = make(map[string]string)
	formEventMutex       sync.RWMutex
	phiPattern           = regexp.MustCompile(`(?i)(name|identifier|phone|address|birth_date|patient_id)`)
	
	validEventTypes = map[string]bool{
		"created":   true,
		"viewed":    true,
		"modified":  true,
		"submitted": true,
		"approved":  true,
		"rejected":  true,
		"archived":  true,
		"deleted":   true,
	}
)

// ValidateTrackFormEventRequest validates the tracking request
func ValidateTrackFormEventRequest(req *TrackFormEventRequest) error {
	if req == nil {
		return fmt.Errorf("form-tracking-request-nil")
	}
	if !req.Synthetic {
		return fmt.Errorf("form-tracking-synthetic-required")
	}
	if req.EventID == "" {
		return fmt.Errorf("form-tracking-event-id-empty")
	}
	if !strings.HasPrefix(req.EventID, "evt-") || len(req.EventID) < 8 {
		return fmt.Errorf("form-tracking-invalid-event-id")
	}
	if req.FormID == "" {
		return fmt.Errorf("form-tracking-form-id-empty")
	}
	if phiPattern.MatchString(req.FormID) {
		return fmt.Errorf("form-tracking-phi-pattern-detected")
	}
	if req.EventType == "" {
		return fmt.Errorf("form-tracking-event-type-empty")
	}
	if !validEventTypes[req.EventType] {
		return fmt.Errorf("form-tracking-event-type-invalid")
	}
	if req.ActorRole == "" {
		return fmt.Errorf("form-tracking-actor-role-empty")
	}
	if phiPattern.MatchString(req.ActorRole) {
		return fmt.Errorf("form-tracking-phi-pattern-detected")
	}
	if req.Timestamp == "" {
		return fmt.Errorf("form-tracking-timestamp-empty")
	}
	if _, err := time.Parse(time.RFC3339, req.Timestamp); err != nil {
		return fmt.Errorf("form-tracking-timestamp-invalid")
	}
	for k, v := range req.Details {
		if phiPattern.MatchString(k) || phiPattern.MatchString(v) {
			return fmt.Errorf("form-tracking-phi-pattern-detected")
		}
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("form-tracking-idempotency-required")
	}
	if len(req.IdempotencyKey) < 16 {
		return fmt.Errorf("form-tracking-idempotency-too-short")
	}
	return nil
}

// TrackFormEvent records a form lifecycle event
func TrackFormEvent(req *TrackFormEventRequest) (*FormEventResponse, error) {
	if err := ValidateTrackFormEventRequest(req); err != nil {
		return nil, err
	}
	
	formEventMutex.Lock()
	defer formEventMutex.Unlock()
	
	if existingID, exists := formEventIdempotency[req.IdempotencyKey]; exists {
		return formEventStore[existingID], nil
	}
	
	ts, _ := time.Parse(time.RFC3339, req.Timestamp)
	
	resp := &FormEventResponse{
		EventID:   req.EventID,
		FormID:    req.FormID,
		EventType: req.EventType,
		ActorRole: req.ActorRole,
		Timestamp: ts,
		Details:   req.Details,
		Digest:    generateFormEventDigest(req),
	}
	
	formEventStore[req.EventID] = resp
	formEventIdempotency[req.IdempotencyKey] = req.EventID
	
	return resp, nil
}

// GetFormEvent retrieves a tracked event by ID
func GetFormEvent(eventID string) (*FormEventResponse, error) {
	if eventID == "" {
		return nil, fmt.Errorf("form-tracking-event-id-empty")
	}
	
	formEventMutex.RLock()
	defer formEventMutex.RUnlock()
	
	event, exists := formEventStore[eventID]
	if !exists {
		return nil, fmt.Errorf("form-tracking-event-not-found")
	}
	
	return event, nil
}

// ListFormEvents returns all events for a specific form
func ListFormEvents(formID string) ([]*FormEventResponse, error) {
	if formID == "" {
		return nil, fmt.Errorf("form-tracking-form-id-empty")
	}
	
	formEventMutex.RLock()
	defer formEventMutex.RUnlock()
	
	var events []*FormEventResponse
	for _, event := range formEventStore {
		if event.FormID == formID {
			events = append(events, event)
		}
	}
	
	return events, nil
}

// GetEventsByType returns all events of a specific type
func GetEventsByType(eventType string) ([]*FormEventResponse, error) {
	if eventType == "" {
		return nil, fmt.Errorf("form-tracking-event-type-empty")
	}
	if !validEventTypes[eventType] {
		return nil, fmt.Errorf("form-tracking-event-type-invalid")
	}
	
	formEventMutex.RLock()
	defer formEventMutex.RUnlock()
	
	var events []*FormEventResponse
	for _, event := range formEventStore {
		if event.EventType == eventType {
			events = append(events, event)
		}
	}
	
	return events, nil
}

// DeleteFormEvent removes a tracked event
func DeleteFormEvent(eventID string) error {
	if eventID == "" {
		return fmt.Errorf("form-tracking-event-id-empty")
	}
	
	formEventMutex.Lock()
	defer formEventMutex.Unlock()
	
	if _, exists := formEventStore[eventID]; !exists {
		return fmt.Errorf("form-tracking-event-not-found")
	}
	
	delete(formEventStore, eventID)
	return nil
}

// ClearFormEvents removes all events for a specific form
func ClearFormEvents(formID string) error {
	if formID == "" {
		return fmt.Errorf("form-tracking-form-id-empty")
	}
	
	formEventMutex.Lock()
	defer formEventMutex.Unlock()
	
	for eventID, event := range formEventStore {
		if event.FormID == formID {
			delete(formEventStore, eventID)
		}
	}
	
	return nil
}

// generateFormEventDigest creates a deterministic hash of the event
func generateFormEventDigest(req *TrackFormEventRequest) string {
	h := sha256.New()
	h.Write([]byte(req.EventID))
	h.Write([]byte(req.FormID))
	h.Write([]byte(req.EventType))
	h.Write([]byte(req.ActorRole))
	h.Write([]byte(req.Timestamp))
	return hex.EncodeToString(h.Sum(nil))
}
