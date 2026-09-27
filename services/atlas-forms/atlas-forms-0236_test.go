package forms

import (
	"fmt"
	"testing"
	"time"
)

func checkError0236(t *testing.T, err error, expectedCode string) {
	t.Helper()
	if err == nil {
		t.Errorf("Expected error %s, got nil", expectedCode)
		return
	}
	if err.Error() != expectedCode {
		t.Errorf("Expected %s, got %v", expectedCode, err)
	}
}

func baseFormReq() *SyntheticFormRequest {
	return &SyntheticFormRequest{
		FormID:   "form-synthetic-001",
		FormType: "consent",
		FieldSpec: map[string]string{
			"field_a": "string",
			"field_b": "number",
			"field_c": "boolean",
		},
		Seed:           "test-seed-12345",
		Version:        "1.0",
		IdempotencyKey: "idem-synthetic-form-001",
		Synthetic:      true,
	}
}

func TestValidateSyntheticFormRequest_Valid(t *testing.T) {
	req := baseFormReq()
	if err := ValidateSyntheticFormRequest(req); err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

func TestValidateSyntheticFormRequest_NilRequest(t *testing.T) {
	err := ValidateSyntheticFormRequest(nil)
	checkError0236(t, err, "synthetic-form-request-nil")
}

func TestValidateSyntheticFormRequest_EmptyFormID(t *testing.T) {
	req := baseFormReq()
	req.FormID = ""
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-id-empty")
}

func TestValidateSyntheticFormRequest_EmptyFormType(t *testing.T) {
	req := baseFormReq()
	req.FormType = ""
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-type-empty")
}

func TestValidateSyntheticFormRequest_NotSynthetic(t *testing.T) {
	req := baseFormReq()
	req.Synthetic = false
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-not-synthetic")
}

func TestValidateSyntheticFormRequest_EmptyIdempotencyKey(t *testing.T) {
	// Form generation requires idempotency key to prevent duplicate synthetic forms
	req := baseFormReq()
	req.IdempotencyKey = ""
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-idempotency-required")
}

func TestValidateSyntheticFormRequest_ShortIdempotencyKey(t *testing.T) {
	// Idempotency key must be at least 16 characters for synthetic forms
	req := baseFormReq()
	req.IdempotencyKey = "short"
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-idempotency-too-short")
}

func TestValidateSyntheticFormRequest_EmptySeed(t *testing.T) {
	req := baseFormReq()
	req.Seed = ""
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-seed-empty")
}

func TestValidateSyntheticFormRequest_EmptyFieldSpec(t *testing.T) {
	req := baseFormReq()
	req.FieldSpec = map[string]string{}
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-field-spec-empty")
}

func TestValidateSyntheticFormRequest_PHIPatternDetected(t *testing.T) {
	req := baseFormReq()
	req.FieldSpec["patient_id"] = "string"
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-phi-pattern-detected")
}

func TestValidateSyntheticFormRequest_InvalidFormType(t *testing.T) {
	req := baseFormReq()
	req.FormType = "invalid-type"
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-type-invalid")
}

func TestValidateSyntheticFormRequest_EmptyVersion(t *testing.T) {
	req := baseFormReq()
	req.Version = ""
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-version-empty")
}

func TestValidateSyntheticFormRequest_InvalidVersion(t *testing.T) {
	req := baseFormReq()
	req.Version = "1"
	err := ValidateSyntheticFormRequest(req)
	checkError0236(t, err, "synthetic-form-version-invalid")
}

func TestGenerateSyntheticForm_Success(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	form, err := GenerateSyntheticForm(req)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	// Verify generated form contains all request fields
	if form.FormID != req.FormID {
		t.Errorf("Expected FormID %s, got %s", req.FormID, form.FormID)
	}
	if form.FormType != req.FormType {
		t.Errorf("Expected FormType %s, got %s", req.FormType, form.FormType)
	}
	if !form.Synthetic {
		t.Error("Expected Synthetic to be true")
	}
	if len(form.Fields) != len(req.FieldSpec) {
		t.Errorf("Expected %d fields, got %d", len(req.FieldSpec), len(form.Fields))
	}
	if form.Checksum == "" {
		t.Error("Expected non-empty checksum")
	}
}

func TestGenerateSyntheticForm_Idempotency(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	form1, err1 := GenerateSyntheticForm(req)
	if err1 != nil {
		t.Fatalf("Expected no error on first call, got %v", err1)
	}
	form2, err2 := GenerateSyntheticForm(req)
	if err2 != nil {
		t.Fatalf("Expected no error on second call, got %v", err2)
	}
	if form1.FormID != form2.FormID {
		t.Error("Expected same FormID for idempotent calls")
	}
	if form1.Checksum != form2.Checksum {
		t.Error("Expected same Checksum for idempotent calls")
	}
}

func TestGenerateSyntheticForm_ValidationFailure(t *testing.T) {
	req := baseFormReq()
	req.FormID = ""
	_, err := GenerateSyntheticForm(req)
	if err == nil {
		t.Error("Expected validation error")
	}
}

func TestGetSyntheticForm_Success(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	generated, err := GenerateSyntheticForm(req)
	if err != nil {
		t.Fatalf("Failed to generate form: %v", err)
	}
	retrieved, err := GetSyntheticForm(generated.FormID)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if retrieved.FormID != generated.FormID {
		t.Errorf("Expected FormID %s, got %s", generated.FormID, retrieved.FormID)
	}
}

func TestGetSyntheticForm_EmptyID(t *testing.T) {
	_, err := GetSyntheticForm("")
	checkError0236(t, err, "synthetic-form-id-empty")
}

func TestGetSyntheticForm_NotFound(t *testing.T) {
	CleanupSyntheticForms()
	_, err := GetSyntheticForm("non-existent-form")
	checkError0236(t, err, "synthetic-form-not-found")
}

func TestListSyntheticForms_AllTypes(t *testing.T) {
	CleanupSyntheticForms()
	req1 := baseFormReq()
	req1.FormID = "form-001"
	req1.IdempotencyKey = "idem-001-unique-key"
	_, err1 := GenerateSyntheticForm(req1)
	if err1 != nil {
		t.Fatalf("Expected no error generating form1, got %v", err1)
	}
	req2 := baseFormReq()
	req2.FormID = "form-002"
	req2.FormType = "assessment"
	req2.IdempotencyKey = "idem-002-unique-key"
	_, err2 := GenerateSyntheticForm(req2)
	if err2 != nil {
		t.Fatalf("Expected no error generating form2, got %v", err2)
	}
	forms, err := ListSyntheticForms("")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(forms) != 2 {
		t.Errorf("Expected 2 forms, got %d", len(forms))
	}
}

func TestListSyntheticForms_FilterByType(t *testing.T) {
	CleanupSyntheticForms()
	req1 := baseFormReq()
	req1.FormID = "form-consent-001"
	req1.FormType = "consent"
	req1.IdempotencyKey = "idem-consent-001"
	GenerateSyntheticForm(req1)
	req2 := baseFormReq()
	req2.FormID = "form-assessment-001"
	req2.FormType = "assessment"
	req2.IdempotencyKey = "idem-assessment-001"
	GenerateSyntheticForm(req2)
	forms, err := ListSyntheticForms("consent")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}
	if len(forms) != 1 {
		t.Errorf("Expected 1 form, got %d", len(forms))
	}
	if forms[0].FormType != "consent" {
		t.Errorf("Expected FormType consent, got %s", forms[0].FormType)
	}
}

func TestValidateSyntheticForm_Success(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	form, _ := GenerateSyntheticForm(req)
	err := ValidateSyntheticForm(form.FormID)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
}

func TestValidateSyntheticForm_EmptyID(t *testing.T) {
	err := ValidateSyntheticForm("")
	checkError0236(t, err, "synthetic-form-id-empty")
}

func TestValidateSyntheticForm_NotFound(t *testing.T) {
	CleanupSyntheticForms()
	err := ValidateSyntheticForm("non-existent")
	checkError0236(t, err, "synthetic-form-not-found")
}

func TestDeleteSyntheticForm_Success(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	form, _ := GenerateSyntheticForm(req)
	err := DeleteSyntheticForm(form.FormID)
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	_, getErr := GetSyntheticForm(form.FormID)
	if getErr == nil {
		t.Error("Expected form to be deleted")
	}
}

func TestDeleteSyntheticForm_EmptyID(t *testing.T) {
	err := DeleteSyntheticForm("")
	checkError0236(t, err, "synthetic-form-id-empty")
}

func TestDeleteSyntheticForm_NotFound(t *testing.T) {
	CleanupSyntheticForms()
	err := DeleteSyntheticForm("non-existent")
	checkError0236(t, err, "synthetic-form-not-found")
}

func TestCleanupSyntheticForms_Success(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	GenerateSyntheticForm(req)
	err := CleanupSyntheticForms()
	if err != nil {
		t.Errorf("Expected no error, got %v", err)
	}
	forms, _ := ListSyntheticForms("")
	if len(forms) != 0 {
		t.Errorf("Expected 0 forms after cleanup, got %d", len(forms))
	}
}

func TestGenerateSyntheticValue_AllTypes(t *testing.T) {
	seed := "test-seed"
	key := "test-key"
	types := []string{"string", "number", "boolean", "date", "code", "text", "unknown"}
	for _, vType := range types {
		value := generateSyntheticValue(vType, seed, key)
		if value == "" {
			t.Errorf("Expected non-empty value for type %s", vType)
		}
	}
}

func TestGenerateSyntheticForm_DeterministicGeneration(t *testing.T) {
	CleanupSyntheticForms()
	req1 := baseFormReq()
	req1.FormID = "form-deterministic-1"
	req1.IdempotencyKey = "idem-deterministic-1"
	form1, err1 := GenerateSyntheticForm(req1)
	if err1 != nil {
		t.Fatalf("Expected no error generating form1, got %v", err1)
	}
	fieldValueA := form1.Fields["field_a"]

	// Generate second form with different IDs but same seed and field spec
	CleanupSyntheticForms()
	req2 := baseFormReq()
	req2.FormID = "form-deterministic-2"
	req2.IdempotencyKey = "idem-deterministic-2"
	req2.Seed = req1.Seed           // Explicit same seed
	req2.FieldSpec = req1.FieldSpec // Explicit same field spec
	form2, err2 := GenerateSyntheticForm(req2)
	if err2 != nil {
		t.Fatalf("Expected no error generating form2, got %v", err2)
	}
	if fieldValueA != form2.Fields["field_a"] {
		t.Error("Expected deterministic field generation with same seed and field spec")
	}
}

func TestGenerateSyntheticForm_Timestamps(t *testing.T) {
	CleanupSyntheticForms()
	req := baseFormReq()
	before := time.Now().UTC()
	form, _ := GenerateSyntheticForm(req)
	after := time.Now().UTC()
	if form.GeneratedAt.Before(before) || form.GeneratedAt.After(after) {
		t.Error("Expected GeneratedAt to be within test execution time")
	}
}

func TestValidateSyntheticFormRequest_PHIPatternVariations(t *testing.T) {
	phiFields := []string{"name", "phone", "address", "birth_date", "identifier", "ssn", "email"}
	for _, field := range phiFields {
		req := baseFormReq()
		req.FieldSpec[field] = "string"
		err := ValidateSyntheticFormRequest(req)
		if err == nil {
			t.Errorf("Expected error for PHI field: %s", field)
		}
		if err.Error() != "synthetic-form-phi-pattern-detected" {
			t.Errorf("For field %s, expected synthetic-form-phi-pattern-detected, got %v", field, err)
		}
	}
}

func TestGenerateSyntheticForm_ValidFormTypes(t *testing.T) {
	CleanupSyntheticForms()
	validTypes := []string{"consent", "assessment", "intake", "discharge", "procedure", "medication", "lab-order", "imaging"}
	for idx, formType := range validTypes {
		req := baseFormReq()
		req.FormID = "form-type-" + formType
		req.FormType = formType
		req.IdempotencyKey = fmt.Sprintf("idem-type-%s-%d", formType, idx)
		_, err := GenerateSyntheticForm(req)
		if err != nil {
			t.Errorf("Expected no error for form type %s, got %v", formType, err)
		}
	}
}
