package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"sync"
	"time"
)

// ValidationErrorRequest represents a request to record a form validation error
type ValidationErrorRequest struct {
	ErrorID        string            `json:"error_id"`
	FormID         string            `json:"form_id"`
	FieldName      string            `json:"field_name"`
	ErrorType      string            `json:"error_type"` // required/format/range/constraint
	ErrorMessage   string            `json:"error_message"`
	AttemptedValue string            `json:"attempted_value"`
	Metadata       map[string]string `json:"metadata"`
	IdempotencyKey string            `json:"idempotency_key"`
	Synthetic      bool              `json:"synthetic"`
}

// ValidationErrorResponse contains the recorded validation error
// and associated metadata for tracking form validation issues
type ValidationErrorResponse struct {
	ErrorID        string            `json:"error_id"`
	FieldName      string            `json:"field_name"`
	FormID         string            `json:"form_id"`
	ErrorType      string            `json:"error_type"`
	ErrorMessage   string            `json:"error_message"`
	AttemptedValue string            `json:"attempted_value"`
	RecordedAt     time.Time         `json:"recorded_at"`
	Metadata       map[string]string `json:"metadata"`
}

var (
	validationErrorStore        = make(map[string]*ValidationErrorResponse)
	validationErrorIdempotency  = make(map[string]string)
	validationErrorMutex        sync.RWMutex
	validErrorTypes             = map[string]bool{"required": true, "format": true, "range": true, "constraint": true}
	phiFieldPattern             = regexp.MustCompile(`(?i)(name|identifier|phone|address|birth_date|patient_id)`)
)

// ValidateValidationErrorRequest checks the validation error request for contract violations
func ValidateValidationErrorRequest(req *ValidationErrorRequest) error {
	if req == nil {
		return errors.New("validation-error-request-nil")
	}
	if !req.Synthetic {
		return errors.New("validation-error-synthetic-required")
	}
	if req.ErrorID == "" {
		return errors.New("validation-error-error-id-empty")
	}
	if !strings.HasPrefix(req.ErrorID, "err-") {
		return errors.New("validation-error-invalid-id")
	}
	if req.FormID == "" {
		return errors.New("validation-error-form-id-empty")
	}
	if req.FieldName == "" {
		return errors.New("validation-error-field-name-empty")
	}
	if phiFieldPattern.MatchString(req.FieldName) {
		return errors.New("validation-error-phi-pattern-detected")
	}
	if req.IdempotencyKey == "" {
		return errors.New("validation-error-idempotency-required")
	}
	if req.ErrorType == "" {
		return errors.New("validation-error-error-type-empty")
	}
	if !validErrorTypes[req.ErrorType] {
		return errors.New("validation-error-error-type-invalid")
	}
	if req.ErrorMessage == "" {
		return errors.New("validation-error-message-empty")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("validation-error-idempotency-too-short")
	}
	return nil
}

// RecordValidationError records a form validation error
func RecordValidationError(req *ValidationErrorRequest) (*ValidationErrorResponse, error) {
	if err := ValidateValidationErrorRequest(req); err != nil {
		return nil, err
	}

	validationErrorMutex.Lock()
	defer validationErrorMutex.Unlock()

	if existingID, found := validationErrorIdempotency[req.IdempotencyKey]; found {
		if existing, ok := validationErrorStore[existingID]; ok {
			return existing, nil
		}
	}

	resp := &ValidationErrorResponse{
		ErrorID:        req.ErrorID,
		FormID:         req.FormID,
		FieldName:      req.FieldName,
		ErrorType:      req.ErrorType,
		ErrorMessage:   req.ErrorMessage,
		AttemptedValue: req.AttemptedValue,
		Metadata:       req.Metadata,
		RecordedAt:     time.Now().UTC(),
	}

	validationErrorStore[req.ErrorID] = resp
	validationErrorIdempotency[req.IdempotencyKey] = req.ErrorID

	return resp, nil
}

// GetValidationError retrieves a recorded validation error
func GetValidationError(errorID string) (*ValidationErrorResponse, error) {
	if errorID == "" {
		return nil, errors.New("validation-error-error-id-empty")
	}

	validationErrorMutex.RLock()
	defer validationErrorMutex.RUnlock()

	if resp, found := validationErrorStore[errorID]; found {
		return resp, nil
	}

	return nil, errors.New("validation-error-not-found")
}

// ListValidationErrors lists validation errors for a form
func ListValidationErrors(formID string) ([]*ValidationErrorResponse, error) {
	if formID == "" {
		return nil, errors.New("validation-error-form-id-empty")
	}

	validationErrorMutex.RLock()
	defer validationErrorMutex.RUnlock()

	var results []*ValidationErrorResponse
	for _, resp := range validationErrorStore {
		if resp.FormID == formID {
			results = append(results, resp)
		}
	}

	return results, nil
}

// GetValidationErrorsByField retrieves validation errors for a specific field
func GetValidationErrorsByField(formID, fieldName string) ([]*ValidationErrorResponse, error) {
	if formID == "" {
		return nil, errors.New("validation-error-form-id-empty")
	}
	if fieldName == "" {
		return nil, errors.New("validation-error-field-name-empty")
	}

	validationErrorMutex.RLock()
	defer validationErrorMutex.RUnlock()

	var results []*ValidationErrorResponse
	for _, resp := range validationErrorStore {
		if resp.FormID == formID && resp.FieldName == fieldName {
			results = append(results, resp)
		}
	}

	return results, nil
}

// DeleteValidationError removes a validation error
func DeleteValidationError(errorID string) error {
	if errorID == "" {
		return errors.New("validation-error-error-id-empty")
	}

	validationErrorMutex.Lock()
	defer validationErrorMutex.Unlock()

	if _, found := validationErrorStore[errorID]; !found {
		return errors.New("validation-error-not-found")
	}

	delete(validationErrorStore, errorID)
	return nil
}

// ClearValidationErrors removes all validation errors for a form
func ClearValidationErrors(formID string) (int, error) {
	if formID == "" {
		return 0, errors.New("validation-error-form-id-empty")
	}

	validationErrorMutex.Lock()
	defer validationErrorMutex.Unlock()

	count := 0
	for errorID, resp := range validationErrorStore {
		if resp.FormID == formID {
			delete(validationErrorStore, errorID)
			count++
		}
	}

	return count, nil
}

// GenerateValidationErrorDigest creates a SHA256 hash of the validation error details
func GenerateValidationErrorDigest(formID, fieldName, errorType string) string {
	combined := fmt.Sprintf("%s:%s:%s", formID, fieldName, errorType)
	hash := sha256.Sum256([]byte(combined))
	return hex.EncodeToString(hash[:])
}

// CleanupValidationErrors removes all validation errors (for testing)
func CleanupValidationErrors() {
	validationErrorMutex.Lock()
	defer validationErrorMutex.Unlock()
	validationErrorStore = make(map[string]*ValidationErrorResponse)
	validationErrorIdempotency = make(map[string]string)
}
