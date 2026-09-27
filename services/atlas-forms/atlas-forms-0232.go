package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
)

// SubmissionRequest represents a form submission request
type SubmissionRequest struct {
	SubmissionID    string                 `json:"submission_id"`
	FormID          string                 `json:"form_id"`
	UserID          string                 `json:"user_id"`
	FormData        map[string]interface{} `json:"form_data"`
	Operation       string                 `json:"operation"` // submit, update, withdraw
	ActorID         string                 `json:"actor_id"`
	IdempotencyKey  string                 `json:"idempotency_key"`
	Synthetic       bool                   `json:"synthetic"`
	SubmissionNonce string                 `json:"submission_nonce"`
}

// SubmissionResponse represents submission result
type SubmissionResponse struct {
	SubmissionID string    `json:"submission_id"`
	Status       string    `json:"status"` // pending, submitted, withdrawn
	Checksum     string    `json:"checksum"`
	SubmittedAt  time.Time `json:"submitted_at"`
	Message      string    `json:"message"`
}

// SubmissionEntry stores submission state
type SubmissionEntry struct {
	SubmissionID    string
	FormID          string
	UserID          string
	FormData        map[string]interface{}
	Status          string
	Checksum        string
	SubmittedAt     time.Time
	IdempotencyKey  string
	SubmissionNonce string
}

var (
	submissionStore     = make(map[string]*SubmissionEntry)
	submissionStoreLock sync.RWMutex
	idempotencyMap      = make(map[string]string)
	idempotencyMapLock  sync.RWMutex
	submissionIDPattern = regexp.MustCompile(`^SUB-[A-Z0-9]{16}$`)
)

// ValidateSubmissionRequest validates the submission request
func ValidateSubmissionRequest(req *SubmissionRequest) error {
	if !req.Synthetic {
		return errors.New("submission-synthetic-required: synthetic flag must be true for test data")
	}

	if req.FormID == "" {
		return errors.New("submission-form-id-required: form_id is required")
	}

	if req.UserID == "" {
		return errors.New("submission-user-id-required: user_id is required")
	}

	if req.FormData == nil || len(req.FormData) == 0 {
		return errors.New("submission-form-data-required: form_data must not be empty")
	}

	if len(req.FormData) > 200 {
		return errors.New("submission-form-data-too-large: form_data cannot exceed 200 fields")
	}

	for key := range req.FormData {
		lowerKey := strings.ToLower(key)
		if lowerKey == "name" || lowerKey == "identifier" || lowerKey == "phone" ||
			lowerKey == "address" || lowerKey == "birth_date" || lowerKey == "patient_id" {
			return fmt.Errorf("submission-prohibited-field: field '%s' is prohibited", key)
		}
	}

	if req.Operation != "submit" && req.Operation != "update" && req.Operation != "withdraw" {
		return fmt.Errorf("submission-invalid-operation: operation must be submit, update, or withdraw, got '%s'", req.Operation)
	}

	if req.ActorID == "" {
		return errors.New("submission-actor-required: actor_id is required")
	}

	if req.IdempotencyKey == "" {
		return errors.New("submission-idempotency-required: idempotency_key is required")
	}

	if req.SubmissionNonce == "" {
		return errors.New("submission-nonce-required: submission_nonce is required for replay prevention")
	}

	return nil
}

// ValidateSubmissionID validates submission ID format
func ValidateSubmissionID(id string) error {
	if !submissionIDPattern.MatchString(id) {
		return fmt.Errorf("submission-invalid-id: submission_id must match pattern SUB-[A-Z0-9]{16}, got '%s'", id)
	}
	return nil
}

// CalculateSubmissionChecksum computes submission data checksum
func CalculateSubmissionChecksum(formID, userID string, formData map[string]interface{}, nonce string) (string, error) {
	dataJSON, err := json.Marshal(map[string]interface{}{
		"form_id":   formID,
		"user_id":   userID,
		"form_data": formData,
		"nonce":     nonce,
	})
	if err != nil {
		return "", fmt.Errorf("submission-checksum-marshal-error: %v", err)
	}

	hash := sha256.Sum256(dataJSON)
	return hex.EncodeToString(hash[:]), nil
}

// GenerateSubmissionID generates a unique submission ID
func GenerateSubmissionID(formID, userID string, timestamp time.Time) string {
	data := fmt.Sprintf("%s:%s:%d", formID, userID, timestamp.UnixNano())
	hash := sha256.Sum256([]byte(data))
	encoded := hex.EncodeToString(hash[:8])
	return fmt.Sprintf("SUB-%s", strings.ToUpper(encoded))
}

// CheckSubmissionIdempotency checks if the idempotency key has been used
func CheckSubmissionIdempotency(key string) (string, bool) {
	idempotencyMapLock.RLock()
	defer idempotencyMapLock.RUnlock()
	submissionID, exists := idempotencyMap[key]
	return submissionID, exists
}

// SubmitForm processes form submission with idempotency
func SubmitForm(req *SubmissionRequest) (*SubmissionResponse, error) {
	if err := ValidateSubmissionRequest(req); err != nil {
		return nil, err
	}

	existingID, exists := CheckSubmissionIdempotency(req.IdempotencyKey)
	if exists {
		submissionStoreLock.RLock()
		entry, found := submissionStore[existingID]
		submissionStoreLock.RUnlock()

		if !found {
			return nil, errors.New("submission-idempotency-inconsistent: idempotency key exists but submission not found")
		}

		return &SubmissionResponse{
			SubmissionID: entry.SubmissionID,
			Status:       entry.Status,
			Checksum:     entry.Checksum,
			SubmittedAt:  entry.SubmittedAt,
			Message:      "submission-duplicate: idempotent request processed",
		}, nil
	}

	timestamp := time.Now()
	submissionID := GenerateSubmissionID(req.FormID, req.UserID, timestamp)

	checksum, err := CalculateSubmissionChecksum(req.FormID, req.UserID, req.FormData, req.SubmissionNonce)
	if err != nil {
		return nil, err
	}

	entry := &SubmissionEntry{
		SubmissionID:    submissionID,
		FormID:          req.FormID,
		UserID:          req.UserID,
		FormData:        req.FormData,
		Status:          "submitted",
		Checksum:        checksum,
		SubmittedAt:     timestamp,
		IdempotencyKey:  req.IdempotencyKey,
		SubmissionNonce: req.SubmissionNonce,
	}

	submissionStoreLock.Lock()
	submissionStore[submissionID] = entry
	submissionStoreLock.Unlock()

	idempotencyMapLock.Lock()
	idempotencyMap[req.IdempotencyKey] = submissionID
	idempotencyMapLock.Unlock()

	return &SubmissionResponse{
		SubmissionID: submissionID,
		Status:       "submitted",
		Checksum:     checksum,
		SubmittedAt:  timestamp,
		Message:      "submission-success: form submitted successfully",
	}, nil
}

// UpdateSubmission updates an existing submission
func UpdateSubmission(req *SubmissionRequest) (*SubmissionResponse, error) {
	if err := ValidateSubmissionRequest(req); err != nil {
		return nil, err
	}

	if req.SubmissionID == "" {
		return nil, errors.New("submission-id-required: submission_id is required for update")
	}

	if err := ValidateSubmissionID(req.SubmissionID); err != nil {
		return nil, err
	}

	submissionStoreLock.Lock()
	defer submissionStoreLock.Unlock()

	entry, exists := submissionStore[req.SubmissionID]
	if !exists {
		return nil, fmt.Errorf("submission-not-found: submission '%s' does not exist", req.SubmissionID)
	}

	if entry.UserID != req.UserID {
		return nil, fmt.Errorf("submission-unauthorized: user '%s' cannot update submission owned by '%s'", req.UserID, entry.UserID)
	}

	if entry.Status == "withdrawn" {
		return nil, errors.New("submission-already-withdrawn: cannot update withdrawn submission")
	}

	checksum, err := CalculateSubmissionChecksum(req.FormID, req.UserID, req.FormData, req.SubmissionNonce)
	if err != nil {
		return nil, err
	}

	entry.FormData = req.FormData
	entry.Checksum = checksum
	entry.SubmissionNonce = req.SubmissionNonce

	return &SubmissionResponse{
		SubmissionID: entry.SubmissionID,
		Status:       entry.Status,
		Checksum:     checksum,
		SubmittedAt:  entry.SubmittedAt,
		Message:      "submission-updated: submission updated successfully",
	}, nil
}

// WithdrawSubmission withdraws a submission
func WithdrawSubmission(submissionID, userID string) (*SubmissionResponse, error) {
	if submissionID == "" {
		return nil, errors.New("submission-id-required: submission_id is required")
	}

	if err := ValidateSubmissionID(submissionID); err != nil {
		return nil, err
	}

	if userID == "" {
		return nil, errors.New("submission-user-required: user_id is required")
	}

	submissionStoreLock.Lock()
	defer submissionStoreLock.Unlock()

	entry, exists := submissionStore[submissionID]
	if !exists {
		return nil, fmt.Errorf("submission-not-found: submission '%s' does not exist", submissionID)
	}

	if entry.UserID != userID {
		return nil, fmt.Errorf("submission-unauthorized: user '%s' cannot withdraw submission owned by '%s'", userID, entry.UserID)
	}

	if entry.Status == "withdrawn" {
		return &SubmissionResponse{
			SubmissionID: entry.SubmissionID,
			Status:       "withdrawn",
			Checksum:     entry.Checksum,
			SubmittedAt:  entry.SubmittedAt,
			Message:      "submission-already-withdrawn: submission was already withdrawn",
		}, nil
	}

	entry.Status = "withdrawn"

	return &SubmissionResponse{
		SubmissionID: entry.SubmissionID,
		Status:       "withdrawn",
		Checksum:     entry.Checksum,
		SubmittedAt:  entry.SubmittedAt,
		Message:      "submission-withdrawn: submission withdrawn successfully",
	}, nil
}

// ProcessSubmission is the main entry point for submission operations
func ProcessSubmission(req *SubmissionRequest) (*SubmissionResponse, error) {
	switch req.Operation {
	case "submit":
		return SubmitForm(req)
	case "update":
		return UpdateSubmission(req)
	case "withdraw":
		return WithdrawSubmission(req.SubmissionID, req.UserID)
	default:
		return nil, fmt.Errorf("submission-unknown-operation: unknown operation '%s'", req.Operation)
	}
}
