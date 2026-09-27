// Package forms provides draft recovery functionality.
package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"

	"errors"
	"fmt"
	"time"
	"regexp"
	"strings"
)

// DraftRecoveryRequest represents a request to save or recover a draft
type DraftRecoveryRequest struct {
	DraftID        string            `json:"draft_id"`
	FormID         string            `json:"form_id"`
	UserID         string            `json:"user_id"`
	DraftData      map[string]string `json:"draft_data"`
	Operation      string            `json:"operation"` // save, recover, discard
	ActorID        string            `json:"actor_id"`
	IdempotencyKey string            `json:"idempotency_key"`
	Synthetic      bool              `json:"synthetic"`
	Reason         string            `json:"reason"`
}

// DraftRecoveryResponse contains the result of a draft operation
type DraftRecoveryResponse struct {
	DraftID      string            `json:"draft_id"`
	FormID       string            `json:"form_id"`
	Status       string            `json:"status"`
	DraftData    map[string]string `json:"draft_data,omitempty"`
	SavedAt      string            `json:"saved_at"`
	RecoveredAt  string            `json:"recovered_at,omitempty"`
	DataChecksum string            `json:"data_checksum"`
}

// DraftEntry represents a stored draft
type DraftEntry struct {
	DraftID        string
	FormID         string
	UserID         string
	DraftData      map[string]string
	DataChecksum   string
	SavedAt        string
	RecoveredAt    string
	Status         string
	ActorID        string
	IdempotencyKey string
	Synthetic      bool
	Reason         string
}

var (
	draftStore           = make(map[string]DraftEntry)
	draftIdempotency     = make(map[string]string)
	draftIDPattern       = regexp.MustCompile(`^DRAFT-[A-Z0-9]{16}$`)
	validDraftOperations = map[string]bool{"save": true, "recover": true, "discard": true}
	validDraftStatuses   = map[string]bool{"active": true, "recovered": true, "discarded": true}
)

// ValidateDraftRecoveryRequest validates the draft recovery request
func ValidateDraftRecoveryRequest(req DraftRecoveryRequest) error {
	if req.FormID == "" {
		return errors.New("draft-invalid: form_id is required")
	}
	if !req.Synthetic {
		return errors.New("draft-synthetic-only: synthetic must be true for test data")
	}
	if req.UserID == "" {
		return errors.New("draft-invalid: user_id is required")
	}
	if req.Operation == "" {
		return errors.New("draft-invalid: operation is required")
	}
	if !validDraftOperations[req.Operation] {
		return errors.New("draft-operation-invalid: operation must be save, recover, or discard")
	}
	if req.Operation == "save" && len(req.DraftData) == 0 {
		return errors.New("draft-invalid: draft_data is required for save operation")
	}
	if req.Operation == "recover" && req.DraftID == "" {
		return errors.New("draft-invalid: draft_id is required for recover operation")
	}
	
	// Validate common fields
	if req.ActorID == "" {
		return errors.New("actor-context-incomplete: actor_id is required")
	}
	if req.Reason == "" {
		return errors.New("draft-invalid: reason is required")
	}
	if req.IdempotencyKey == "" {
		return errors.New("idempotency-key-invalid: idempotency_key is required")
	}
	
	return nil
}

// ValidateDraftID validates the draft ID format
func ValidateDraftID(draftID string) error {
	if draftID == "" {
		return errors.New("draft-invalid: draft_id is required")
	}
	if !draftIDPattern.MatchString(draftID) {
		return errors.New("draft-id-invalid: draft_id must match pattern DRAFT-[A-Z0-9]{16}")
	}
	return nil
}

// ValidateDraftData validates the draft data structure
func ValidateDraftData(draftData map[string]string) error {
	if len(draftData) == 0 {
		return errors.New("draft-data-empty: draft_data cannot be empty")
	}
	
	// Check for direct identifiers in keys
	prohibitedKeys := []string{"name", "identifier", "phone", "address", "birth_date", "patient_id"}
	for key := range draftData {
		for _, prohibited := range prohibitedKeys {
			if key == prohibited {
				return fmt.Errorf("draft-data-invalid: prohibited key '%s' found", prohibited)
			}
		}
	}
	
	// Validate data size (max 100 fields)
	if len(draftData) > 100 {
		return errors.New("draft-data-too-large: maximum 100 fields allowed")
	}
	
	return nil
}

// CalculateDraftChecksum computes a checksum for the draft data
func CalculateDraftChecksum(draftData map[string]string) (string, error) {
	jsonData, err := json.Marshal(draftData)
	if err != nil {
		return "", errors.New("draft-checksum-failed: failed to serialize draft data")
	}
	
	hash := sha256.Sum256(jsonData)
	return hex.EncodeToString(hash[:]), nil
}

// GenerateDraftID generates a unique draft ID
func GenerateDraftID(formID, userID string) string {
	data := fmt.Sprintf("%s:%s:%d", formID, userID, time.Now().UnixNano())
	hash := sha256.Sum256([]byte(data))
	return fmt.Sprintf("DRAFT-%s", strings.ToUpper(hex.EncodeToString(hash[:8])))
}

// CheckDraftIdempotency checks if the request has already been processed
func CheckDraftIdempotency(idempotencyKey string) (string, bool) {
	draftID, exists := draftIdempotency[idempotencyKey]
	return draftID, exists
}

// SaveDraft saves a draft to the store
func SaveDraft(req DraftRecoveryRequest) (DraftRecoveryResponse, error) {
	err := ValidateDraftRecoveryRequest(req)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	err = ValidateDraftData(req.DraftData)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	// Check idempotency
	if existingDraftID, exists := CheckDraftIdempotency(req.IdempotencyKey); exists {
		existing := draftStore[existingDraftID]
		return DraftRecoveryResponse{
			DraftID:      existing.DraftID,
			FormID:       existing.FormID,
			Status:       existing.Status,
			DraftData:    existing.DraftData,
			SavedAt:      existing.SavedAt,
			DataChecksum: existing.DataChecksum,
		}, nil
	}
	
	// Generate draft ID if not provided
	draftID := req.DraftID
	if draftID == "" {
		draftID = GenerateDraftID(req.FormID, req.UserID)
	} else {
		err = ValidateDraftID(draftID)
		if err != nil {
			return DraftRecoveryResponse{}, err
		}
	}
	
	// Calculate checksum
	checksum, err := CalculateDraftChecksum(req.DraftData)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	savedAt := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	
	entry := DraftEntry{
		DraftID:        draftID,
		FormID:         req.FormID,
		UserID:         req.UserID,
		DraftData:      req.DraftData,
		DataChecksum:   checksum,
		SavedAt:        savedAt,
		Status:         "active",
		ActorID:        req.ActorID,
		IdempotencyKey: req.IdempotencyKey,
		Synthetic:      req.Synthetic,
		Reason:         req.Reason,
	}
	
	draftStore[draftID] = entry
	draftIdempotency[req.IdempotencyKey] = draftID
	
	return DraftRecoveryResponse{
		DraftID:      draftID,
		FormID:       req.FormID,
		Status:       "active",
		DraftData:    req.DraftData,
		SavedAt:      savedAt,
		DataChecksum: checksum,
	}, nil
}

// RecoverDraft recovers a previously saved draft
func RecoverDraft(req DraftRecoveryRequest) (DraftRecoveryResponse, error) {
	err := ValidateDraftRecoveryRequest(req)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	err = ValidateDraftID(req.DraftID)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	// Check idempotency
	if existingDraftID, exists := CheckDraftIdempotency(req.IdempotencyKey); exists {
		existing := draftStore[existingDraftID]
		return DraftRecoveryResponse{
			DraftID:      existing.DraftID,
			FormID:       existing.FormID,
			Status:       existing.Status,
			DraftData:    existing.DraftData,
			SavedAt:      existing.SavedAt,
			RecoveredAt:  existing.RecoveredAt,
			DataChecksum: existing.DataChecksum,
		}, nil
	}
	
	// Retrieve draft
	entry, exists := draftStore[req.DraftID]
	if !exists {
		return DraftRecoveryResponse{}, errors.New("draft-not-found: draft does not exist")
	}
	
	if entry.Status == "discarded" {
		return DraftRecoveryResponse{}, errors.New("draft-discarded: draft has been discarded")
	}
	
	// Verify user ownership
	if entry.UserID != req.UserID {
		return DraftRecoveryResponse{}, errors.New("draft-access-denied: user does not own this draft")
	}
	
	recoveredAt := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	entry.RecoveredAt = recoveredAt
	entry.Status = "recovered"
	draftStore[req.DraftID] = entry
	draftIdempotency[req.IdempotencyKey] = req.DraftID
	
	return DraftRecoveryResponse{
		DraftID:      entry.DraftID,
		FormID:       entry.FormID,
		Status:       "recovered",
		DraftData:    entry.DraftData,
		SavedAt:      entry.SavedAt,
		RecoveredAt:  recoveredAt,
		DataChecksum: entry.DataChecksum,
	}, nil
}

// DiscardDraft marks a draft as discarded
func DiscardDraft(req DraftRecoveryRequest) (DraftRecoveryResponse, error) {
	err := ValidateDraftRecoveryRequest(req)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	err = ValidateDraftID(req.DraftID)
	if err != nil {
		return DraftRecoveryResponse{}, err
	}
	
	// Check idempotency
	if existingDraftID, exists := CheckDraftIdempotency(req.IdempotencyKey); exists {
		existing := draftStore[existingDraftID]
		return DraftRecoveryResponse{
			DraftID:  existing.DraftID,
			FormID:   existing.FormID,
			Status:   existing.Status,
			SavedAt:  existing.SavedAt,
		}, nil
	}
	
	// Retrieve draft
	entry, exists := draftStore[req.DraftID]
	if !exists {
		return DraftRecoveryResponse{}, errors.New("draft-not-found: draft does not exist")
	}
	
	// Verify user ownership
	if entry.UserID != req.UserID {
		return DraftRecoveryResponse{}, errors.New("draft-access-denied: user does not own this draft")
	}
	
	entry.Status = "discarded"
	draftStore[req.DraftID] = entry
	draftIdempotency[req.IdempotencyKey] = req.DraftID
	
	return DraftRecoveryResponse{
		DraftID: entry.DraftID,
		FormID:  entry.FormID,
		Status:  "discarded",
		SavedAt: entry.SavedAt,
	}, nil
}

// ProcessDraftRecovery is the main entry point for draft operations
func ProcessDraftRecovery(req DraftRecoveryRequest) (DraftRecoveryResponse, error) {
	switch req.Operation {
	case "save":
		return SaveDraft(req)
	case "recover":
		return RecoverDraft(req)
	case "discard":
		return DiscardDraft(req)
	default:
		return DraftRecoveryResponse{}, errors.New("draft-operation-invalid: invalid operation")
	}
}
