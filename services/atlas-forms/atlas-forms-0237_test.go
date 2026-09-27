package forms

import (
	"fmt"
	"strings"
	"testing"
)

func baseValidationErrorReq() *ValidationErrorRequest {
	return &ValidationErrorRequest{
		ErrorID:        "err-test-001",
		FormID:         "form-test-001",
		FieldName:      "field_a",
		ErrorType:      "required",
		ErrorMessage:   "Field is required",
		AttemptedValue: "",
		Metadata:       map[string]string{"context": "test"},
		IdempotencyKey: "idem-validation-001",
		Synthetic:      true,
	}
}

func checkError0237(t *testing.T, err error, expected string) {
	t.Helper()
	if err == nil {
		t.Fatalf("Expected error %s, got nil", expected)
	}
	if err.Error() != expected {
		t.Errorf("Expected error %s, got %v", expected, err)
	}
}

func setupValidationError(errorID, idempotencyKey string, overrides ...func(*ValidationErrorRequest)) *ValidationErrorRequest {
	req := baseValidationErrorReq()
	req.ErrorID = errorID
	req.IdempotencyKey = idempotencyKey
	for _, fn := range overrides {
		fn(req)
	}
	return req
}

// Validation tests
func TestValidateValidationErrorRequest_Valid(t *testing.T) {
	req := baseValidationErrorReq()
	err := ValidateValidationErrorRequest(req)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

func TestValidateValidationErrorRequest_NilRequest(t *testing.T) {
	err := ValidateValidationErrorRequest(nil)
	checkError0237(t, err, "validation-error-request-nil")
}

func TestValidateValidationErrorRequest_NotSynthetic(t *testing.T) {
	req := baseValidationErrorReq()
	req.Synthetic = false
	err := ValidateValidationErrorRequest(req)
	if err == nil {
		t.Fatal("expected error for non-synthetic request")
	}
	checkError0237(t, err, "validation-error-synthetic-required")
}

func TestValidateValidationErrorRequest_EmptyErrorID(t *testing.T) {
	req := baseValidationErrorReq()
	req.ErrorID = "" // ID is mandatory
	err := ValidateValidationErrorRequest(req)
	if err == nil {
		t.Fatal("expected error for empty ErrorID")
	}
	checkError0237(t, err, "validation-error-error-id-empty")
}

func TestValidateValidationErrorRequest_InvalidIDFormat(t *testing.T) {
	req := baseValidationErrorReq()
	req.ErrorID = "invalid-format"
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-invalid-id")
}

func TestValidateValidationErrorRequest_EmptyFormID(t *testing.T) {
	// Validation error tracking requires non-empty form ID
	req := baseValidationErrorReq()
	req.FormID = ""
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-form-id-empty")
}

func TestValidateValidationErrorRequest_EmptyField(t *testing.T) {
	req := baseValidationErrorReq()
	req.FieldName = ""
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-field-name-empty")
}

func TestValidateValidationErrorRequest_PHIPatternDetected(t *testing.T) {
	req := baseValidationErrorReq()
	req.FieldName = "patient_name"
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-phi-pattern-detected")
}

func TestValidateValidationErrorRequest_EmptyErrorType(t *testing.T) {
	req := baseValidationErrorReq()
	req.ErrorType = ""
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-error-type-empty")
}

func TestValidateValidationErrorRequest_InvalidErrorType(t *testing.T) {
	// Test validation error type must be one of: required, format, range, constraint
	req := baseValidationErrorReq()
	req.ErrorType = "unknown" // invalid type
	err := ValidateValidationErrorRequest(req)
	if err == nil {
		t.Fatal("expected validation failure for invalid error type")
	}
	checkError0237(t, err, "validation-error-error-type-invalid")
}

func TestValidateValidationErrorRequest_EmptyMessage(t *testing.T) {
	// Error message field is mandatory for validation error recording
	req := baseValidationErrorReq()
	req.ErrorMessage = "" // empty message not allowed
	err := ValidateValidationErrorRequest(req)
	if err == nil {
		t.Fatal("expected error when message is empty")
	}
	checkError0237(t, err, "validation-error-message-empty")
}

func TestValidateValidationErrorRequest_EmptyIdempotencyKey(t *testing.T) {
	// Idempotency key prevents duplicate error records
	req := baseValidationErrorReq()
	req.IdempotencyKey = "" // must not be empty
	err := ValidateValidationErrorRequest(req)
	if err == nil {
		t.Fatal("expected error for empty idempotency key")
	}
	checkError0237(t, err, "validation-error-idempotency-required")
}

func TestValidateValidationErrorRequest_ShortIdempotencyKey(t *testing.T) {
	req := baseValidationErrorReq()
	req.IdempotencyKey = "short"
	err := ValidateValidationErrorRequest(req)
	checkError0237(t, err, "validation-error-idempotency-too-short")
}

// RecordValidationError tests
func TestRecordValidationError_Success(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	// Record validation error with complete request
	resp, err := RecordValidationError(req)
	// Verify successful recording with no error
	if err != nil {
		t.Fatalf("RecordValidationError failed: %v", err)
	}
	if resp.ErrorID != req.ErrorID {
		t.Errorf("Expected ErrorID %s, got %s", req.ErrorID, resp.ErrorID)
	}
	// Verify validation error response fields match request
	if resp.FieldName != req.FieldName {
		t.Errorf("Expected FieldName %s, got %s", req.FieldName, resp.FieldName)
	}
	if resp.FormID != req.FormID {
		t.Errorf("FormID mismatch: expected %s, got %s", req.FormID, resp.FormID)
	}
	if resp.ErrorType != req.ErrorType {
		t.Errorf("Expected ErrorType %s, got %s", req.ErrorType, resp.ErrorType)
	}
}

func TestRecordValidationError_Idempotency(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	resp1, err1 := RecordValidationError(req)
	if err1 != nil {
		t.Fatalf("Expected no error on first call, got %v", err1)
	}
	resp2, err2 := RecordValidationError(req)
	if err2 != nil {
		t.Fatalf("Expected no error on second call, got %v", err2)
	}
	if resp1.ErrorID != resp2.ErrorID {
		t.Error("Expected idempotent responses to have same ErrorID")
	}
}

func TestRecordValidationError_ValidationFailure(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	req.ErrorID = ""
	_, err := RecordValidationError(req)
	if err == nil {
		t.Error("Expected validation error, got nil")
	}
}

// GetValidationError tests
func TestGetValidationError_Success(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	created, _ := RecordValidationError(req)
	retrieved, err := GetValidationError(created.ErrorID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if retrieved.ErrorID != created.ErrorID {
		t.Error("Expected retrieved error to match created error")
	}
}

func TestGetValidationError_EmptyID(t *testing.T) {
	_, err := GetValidationError("")
	checkError0237(t, err, "validation-error-error-id-empty")
}

func TestGetValidationError_NotFound(t *testing.T) {
	CleanupValidationErrors()
	_, err := GetValidationError("err-nonexistent")
	checkError0237(t, err, "validation-error-not-found")
}

// ListValidationErrors tests
func TestListValidationErrors_Success(t *testing.T) {
	CleanupValidationErrors()
	req1 := setupValidationError("err-list-001", "idem-list-key-001")
	_, err := RecordValidationError(req1)
	if err != nil {
		t.Fatalf("Failed to record error 1: %v", err)
	}
	req2 := setupValidationError("err-list-002", "idem-list-key-002")
	_, err = RecordValidationError(req2)
	if err != nil {
		t.Fatalf("Failed to record error 2: %v", err)
	}

	results, err := ListValidationErrors(req1.FormID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(results) != 2 {
		t.Errorf("Expected 2 errors, got %d", len(results))
	}
}

func TestListValidationErrors_EmptyFormID(t *testing.T) {
	_, err := ListValidationErrors("")
	checkError0237(t, err, "validation-error-form-id-empty")
}

func TestListValidationErrors_NoResults(t *testing.T) {
	CleanupValidationErrors()
	results, err := ListValidationErrors("form-nonexistent")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(results) != 0 {
		t.Errorf("Expected 0 errors, got %d", len(results))
	}
}

// GetValidationErrorsByField tests
func TestGetValidationErrorsByField_Success(t *testing.T) {
	CleanupValidationErrors()
	req1 := setupValidationError("err-field-001", "idem-field-key-001", func(r *ValidationErrorRequest) {
		r.FieldName = "field_x"
	})
	_, err := RecordValidationError(req1)
	if err != nil {
		t.Fatalf("Failed to record error 1: %v", err)
	}

	req2 := baseValidationErrorReq()
	req2.ErrorID = "err-field-002"
	req2.FieldName = "field_y"
	req2.IdempotencyKey = "idem-field-key-002"
	_, err = RecordValidationError(req2)
	if err != nil {
		t.Fatalf("Failed to record error 2: %v", err)
	}

	results, err := GetValidationErrorsByField(req1.FormID, "field_x")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(results) != 1 {
		t.Errorf("Expected 1 error, got %d", len(results))
	}
	if len(results) > 0 && results[0].FieldName != "field_x" {
		t.Error("Expected error for field_x")
	}
}

func TestGetValidationErrorsByField_EmptyFormID(t *testing.T) {
	_, err := GetValidationErrorsByField("", "field_a")
	checkError0237(t, err, "validation-error-form-id-empty")
}

func TestGetValidationErrorsByField_EmptyField(t *testing.T) {
	_, err := GetValidationErrorsByField("form-test", "")
	checkError0237(t, err, "validation-error-field-name-empty")
}

// DeleteValidationError tests
func TestDeleteValidationError_Success(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	created, _ := RecordValidationError(req)
	err := DeleteValidationError(created.ErrorID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	_, getErr := GetValidationError(created.ErrorID)
	if getErr == nil {
		t.Error("Expected error after deletion")
	}
}

func TestDeleteValidationError_EmptyID(t *testing.T) {
	err := DeleteValidationError("")
	checkError0237(t, err, "validation-error-error-id-empty")
}

func TestDeleteValidationError_NotFound(t *testing.T) {
	CleanupValidationErrors()
	err := DeleteValidationError("err-nonexistent")
	checkError0237(t, err, "validation-error-not-found")
}

// ClearValidationErrors tests
func TestClearValidationErrors_Success(t *testing.T) {
	CleanupValidationErrors()
	req1 := baseValidationErrorReq()
	req1.ErrorID = "err-clear-001"
	req1.IdempotencyKey = "idem-clear-key-001"
	RecordValidationError(req1)

	req2 := baseValidationErrorReq()
	req2.ErrorID = "err-clear-002"
	req2.IdempotencyKey = "idem-clear-key-002"
	RecordValidationError(req2)

	count, err := ClearValidationErrors(req1.FormID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if count != 2 {
		t.Errorf("Expected 2 cleared, got %d", count)
	}
}

func TestClearValidationErrors_EmptyFormID(t *testing.T) {
	_, err := ClearValidationErrors("")
	checkError0237(t, err, "validation-error-form-id-empty")
}

// GenerateValidationErrorDigest tests
func TestGenerateValidationErrorDigest_Deterministic(t *testing.T) {
	digest1 := GenerateValidationErrorDigest("form-001", "field_a", "required")
	digest2 := GenerateValidationErrorDigest("form-001", "field_a", "required")
	if digest1 != digest2 {
		t.Error("Expected deterministic digest generation")
	}
	if len(digest1) != 64 {
		t.Errorf("Expected 64-character digest, got %d", len(digest1))
	}
}

func TestGenerateValidationErrorDigest_DifferentInputs(t *testing.T) {
	digest1 := GenerateValidationErrorDigest("form-001", "field_a", "required")
	digest2 := GenerateValidationErrorDigest("form-001", "field_b", "required")
	if digest1 == digest2 {
		t.Error("Expected different digests for different inputs")
	}
}

// Error type validation tests
func TestRecordValidationError_AllErrorTypes(t *testing.T) {
	CleanupValidationErrors()
	errorTypes := []string{"required", "format", "range", "constraint"}
	for i, errorType := range errorTypes {
		req := baseValidationErrorReq()
		req.ErrorID = fmt.Sprintf("err-type-%03d", i)
		req.ErrorType = errorType
		req.IdempotencyKey = fmt.Sprintf("idem-type-key-%03d", i)
		resp, err := RecordValidationError(req)
		if err != nil {
			t.Errorf("Test %d: Expected no error for type %s, got %v", i, errorType, err)
			continue
		}
		if resp.ErrorType != errorType {
			t.Errorf("Test %d: Expected type %s, got %s", i, errorType, resp.ErrorType)
		}
	}
}

// PHI pattern tests
func TestValidateValidationErrorRequest_PHIPatterns(t *testing.T) {
	phiFields := []string{"patient_name", "user_identifier", "phone_number", "home_address", "birth_date", "patient_id"}
	for _, field := range phiFields {
		req := baseValidationErrorReq()
		req.FieldName = field
		err := ValidateValidationErrorRequest(req)
		if err == nil {
			t.Errorf("Expected PHI pattern error for field %s", field)
		}
		if !strings.Contains(err.Error(), "phi-pattern-detected") {
			t.Errorf("Expected phi-pattern-detected error for field %s, got %v", field, err)
		}
	}
}

// Metadata preservation tests
func TestRecordValidationError_MetadataPreserved(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	req.Metadata = map[string]string{
		"context":   "test-context",
		"validator": "test-validator",
		"rule":      "test-rule",
	}
	resp, err := RecordValidationError(req)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(resp.Metadata) != 3 {
		t.Errorf("Expected 3 metadata entries, got %d", len(resp.Metadata))
	}
	if resp.Metadata["context"] != "test-context" {
		t.Error("Expected metadata to be preserved")
	}
}

// AttemptedValue tests
func TestRecordValidationError_AttemptedValueRecorded(t *testing.T) {
	CleanupValidationErrors()
	req := baseValidationErrorReq()
	req.AttemptedValue = "invalid-value-123"
	resp, err := RecordValidationError(req)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if resp.AttemptedValue != "invalid-value-123" {
		t.Errorf("Expected attempted value to be preserved, got %s", resp.AttemptedValue)
	}
}
