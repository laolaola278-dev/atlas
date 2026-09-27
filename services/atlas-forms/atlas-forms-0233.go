// Package forms implements ATLAS form lifecycle operations.
// This module handles form revocation with idempotency and audit requirements.
package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// RevocationRequest represents a request to revoke a form submission.
type RevocationRequest struct {
	SubmissionID   string                 `json:"submission_id"`
	FormID         string                 `json:"form_id"`
	RevokedBy      string                 `json:"revoked_by"`
	Reason         string                 `json:"reason"`
	RevokedAt      time.Time              `json:"revoked_at"`
	ActorID        string                 `json:"actor_id"`
	IdempotencyKey string                 `json:"idempotency_key"`
	Synthetic      bool                   `json:"synthetic"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

// RevocationResponse represents the result of a revocation operation.
type RevocationResponse struct {
	RevocationID   string    `json:"revocation_id"`
	SubmissionID   string    `json:"submission_id"`
	Status         string    `json:"status"`
	RevokedAt      time.Time `json:"revoked_at"`
	PreviousStatus string    `json:"previous_status"`
}

// RevocationEntry stores revocation metadata.
type RevocationEntry struct {
	RevocationID   string                 `json:"revocation_id"`
	SubmissionID   string                 `json:"submission_id"`
	Status         string                 `json:"status"`
	PreviousStatus string                 `json:"previous_status"`
	FormID         string                 `json:"form_id"`
	RevokedBy      string                 `json:"revoked_by"`
	Reason         string                 `json:"reason"`
	RevokedAt      time.Time              `json:"revoked_at"`
	ActorID        string                 `json:"actor_id"`
	IdempotencyKey string                 `json:"idempotency_key"`
	Metadata       map[string]interface{} `json:"metadata,omitempty"`
}

var (
	revocationIDPattern          = regexp.MustCompile(`^REV-[A-Z0-9]{16}$`)
	revocableSubmissionIDPattern = regexp.MustCompile(`^SUB-[A-Z0-9]{16}$`)
	formIDPattern                = regexp.MustCompile(`^FORM-[A-Z0-9]{16}$`)
	reasonMinLength              = 10
	reasonMaxLength              = 500

	// In-memory stores
	revocationStore          = make(map[string]*RevocationEntry)
	revocationIdempKeys      = make(map[string]string)
	revocableSubmissionStore = make(map[string]*RevocableSubmissionEntry)
)

// RevocableSubmissionEntry represents a form submission (minimal for revocation dependency)
type RevocableSubmissionEntry struct {
	SubmissionID string
	FormID       string
	Status       string
	SubmittedAt  time.Time
}

// ValidateRevocableSubmissionID validates submission ID format
func ValidateRevocableSubmissionID(submissionID string) error {
	if submissionID == "" {
		return errors.New("revocation-submission-id-required")
	}
	if !revocableSubmissionIDPattern.MatchString(submissionID) {
		return fmt.Errorf("revocation-submission-id-invalid: must match SUB-[A-Z0-9]{16}, got '%s'", submissionID)
	}
	return nil
}

// ValidateFormID validates form ID format
func ValidateFormID(formID string) error {
	if formID == "" {
		return errors.New("revocation-form-id-required")
	}
	if !formIDPattern.MatchString(formID) {
		return fmt.Errorf("revocation-form-id-invalid: must match FORM-[A-Z0-9]{16}, got '%s'", formID)
	}
	return nil
}

// ValidateNoProhibitedKeys validates that metadata contains no PHI keys
func ValidateNoProhibitedKeys(metadata map[string]interface{}) error {
	prohibitedKeys := []string{"name", "identifier", "phone", "address", "birth_date", "patient_id"}
	for key := range metadata {
		lowerKey := strings.ToLower(key)
		for _, prohibited := range prohibitedKeys {
			if lowerKey == prohibited {
				return fmt.Errorf("revocation-prohibited-field: field '%s' is prohibited", key)
			}
		}
	}
	return nil
}

// ValidateRevocationRequest validates all fields of a revocation request.
func ValidateRevocationRequest(req *RevocationRequest) error {
	if req == nil {
		return errors.New("revocation-request-nil")
	}

	if !req.Synthetic {
		return errors.New("revocation-synthetic-required")
	}

	if err := ValidateRevocableSubmissionID(req.SubmissionID); err != nil {
		return err
	}

	if err := ValidateFormID(req.FormID); err != nil {
		return err
	}

	if strings.TrimSpace(req.RevokedBy) == "" {
		return errors.New("revocation-revoked-by-empty")
	}

	if err := ValidateRevocationReason(req.Reason); err != nil {
		return err
	}

	if req.RevokedAt.IsZero() {
		return errors.New("revocation-timestamp-invalid")
	}

	if strings.TrimSpace(req.ActorID) == "" {
		return errors.New("revocation-actor-required")
	}

	if strings.TrimSpace(req.IdempotencyKey) == "" {
		return errors.New("revocation-idempotency-required")
	}

	if req.Metadata != nil {
		if err := ValidateNoProhibitedKeys(req.Metadata); err != nil {
			return err
		}
	}

	return nil
}

// ValidateRevocationReason validates the revocation reason string.
func ValidateRevocationReason(reason string) error {
	reason = strings.TrimSpace(reason)
	if len(reason) < reasonMinLength {
		return fmt.Errorf("revocation-reason-too-short")
	}
	if len(reason) > reasonMaxLength {
		return fmt.Errorf("revocation-reason-too-long")
	}
	return nil
}

// ValidateRevocationID validates the format of a revocation ID.
func ValidateRevocationID(id string) error {
	if !revocationIDPattern.MatchString(id) {
		return errors.New("revocation-id-invalid")
	}
	return nil
}

// GenerateRevocationID creates a unique revocation identifier.
func GenerateRevocationID(submissionID string, revokedAt time.Time) string {
	data := fmt.Sprintf("%s:%d", submissionID, revokedAt.UnixNano())
	hash := sha256.Sum256([]byte(data))
	hashStr := hex.EncodeToString(hash[:])
	return fmt.Sprintf("REV-%s", strings.ToUpper(hashStr[:16]))
}

// CheckRevocationIdempotency checks if this request was already processed.
func CheckRevocationIdempotency(key string) (string, bool) {
	revocationID, exists := revocationIdempKeys[key]
	return revocationID, exists
}

// RevokeSubmission revokes a form submission.
func RevokeSubmission(req *RevocationRequest) (*RevocationResponse, error) {
	if err := ValidateRevocationRequest(req); err != nil {
		return nil, err
	}

	if existingID, exists := CheckRevocationIdempotency(req.IdempotencyKey); exists {
		entry := revocationStore[existingID]
		return &RevocationResponse{
			RevocationID:   entry.RevocationID,
			SubmissionID:   entry.SubmissionID,
			Status:         entry.Status,
			RevokedAt:      entry.RevokedAt,
			PreviousStatus: entry.PreviousStatus,
		}, nil
	}

	submission, exists := revocableSubmissionStore[req.SubmissionID]
	if !exists {
		return nil, errors.New("revocation-submission-not-found")
	}

	if submission.Status == "revoked" {
		return nil, errors.New("revocation-already-revoked")
	}

	if submission.Status != "submitted" && submission.Status != "processed" {
		return nil, errors.New("revocation-status-invalid")
	}

	revocationID := GenerateRevocationID(req.SubmissionID, req.RevokedAt)
	previousStatus := submission.Status

	entry := &RevocationEntry{
		RevocationID:   revocationID,
		SubmissionID:   req.SubmissionID,
		FormID:         req.FormID,
		RevokedBy:      req.RevokedBy,
		Reason:         req.Reason,
		RevokedAt:      req.RevokedAt,
		ActorID:        req.ActorID,
		IdempotencyKey: req.IdempotencyKey,
		Status:         "revoked",
		PreviousStatus: previousStatus,
		Metadata:       req.Metadata,
	}

	revocationStore[revocationID] = entry
	revocationIdempKeys[req.IdempotencyKey] = revocationID

	submission.Status = "revoked"

	return &RevocationResponse{
		RevocationID:   revocationID,
		SubmissionID:   req.SubmissionID,
		Status:         "revoked",
		RevokedAt:      req.RevokedAt,
		PreviousStatus: previousStatus,
	}, nil
}

// GetRevocation retrieves a revocation entry by ID.
func GetRevocation(revocationID string) (*RevocationEntry, error) {
	if err := ValidateRevocationID(revocationID); err != nil {
		return nil, err
	}

	entry, exists := revocationStore[revocationID]
	if !exists {
		return nil, errors.New("revocation-not-found")
	}

	return entry, nil
}

// ProcessRevocation orchestrates the complete revocation workflow.
func ProcessRevocation(req *RevocationRequest) (*RevocationResponse, error) {
	if err := ValidateRevocationRequest(req); err != nil {
		return nil, fmt.Errorf("revocation-validation-failed: %w", err)
	}

	resp, err := RevokeSubmission(req)
	if err != nil {
		return nil, fmt.Errorf("revocation-failed: %w", err)
	}

	return resp, nil
}
