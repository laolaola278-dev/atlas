package forms

import (
	"strings"
	"testing"
	"time"
)

func TestValidateFormVersionRequest_Valid(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-001",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[{"name":"field1","type":"string"}]}`,
		ActorID:        "synthetic-actor-001",
		IdempotencyKey: "idem-key-001",
		Synthetic:      true,
		Reason:         "Initial form version creation",
	}
	
	err := ValidateFormVersionRequest(req)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
}

func TestValidateFormVersionRequest_MissingFormID(t *testing.T) {
	req := FormVersionRequest{
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-001",
		IdempotencyKey: "idem-key-002",
		Synthetic:      true,
		Reason:         "Test",
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Error("expected error for missing form_id")
	}
	if !strings.Contains(err.Error(), "form_id is required") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateFormVersionRequest_InvalidVersion(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-002",
		Version:        "invalid",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-001",
		IdempotencyKey: "idem-key-003",
		Synthetic:      true,
		Reason:         "Test",
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Fatal("expected error for invalid version")
	}
	expectedMsg := "version must be semantic"
	if !strings.Contains(err.Error(), expectedMsg) {
		t.Fatalf("error should contain %q, got: %v", expectedMsg, err)
	}
}

func TestValidateFormVersionRequest_NonSynthetic(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-003",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-001",
		IdempotencyKey: "idem-key-004",
		Synthetic:      false,
		Reason:         "Test",
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Error("expected error for non-synthetic data")
	}
	if !strings.Contains(err.Error(), "synthetic must be true") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateFormVersionRequest_MissingActorID(t *testing.T) {
	// Test validation when ActorID is missing
	req := FormVersionRequest{
		Synthetic:      true,
		Reason:         "Test missing actor",
		IdempotencyKey: "idem-key-005",
		FormID:         "form-synthetic-004",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		// ActorID intentionally omitted
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Fatal("expected error for missing actor_id")
	}
	// Verify the specific error message
	errMsg := err.Error()
	if !strings.Contains(errMsg, "actor_id is required") {
		t.Errorf("error message should mention actor_id requirement, got: %v", errMsg)
	}
}

func TestValidateSchema_Valid(t *testing.T) {
	schema := `{
		"fields": [
			{"name": "patient_complaint", "type": "text", "terminology": "SNOMED"},
			{"name": "vital_signs", "type": "numeric", "terminology": "LOINC"}
		]
	}`
	
	results, err := ValidateSchema(schema)
	if err != nil {
		t.Errorf("expected no error, got %v", err)
	}
	if len(results) != 4 {
		t.Errorf("expected 4 validation results, got %d", len(results))
	}
}

func TestValidateSchema_MissingFields(t *testing.T) {
	schema := `{"title": "Test Form"}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for missing fields")
	}
	if !strings.Contains(err.Error(), "schema must contain fields") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateSchema_InvalidTerminology(t *testing.T) {
	schema := `{
		"fields": [
			{"name": "test_field", "type": "text", "terminology": "INVALID_CODE"}
		]
	}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for invalid terminology")
	}
	if !strings.Contains(err.Error(), "doc-term-unknown") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestValidateSchema_MissingFieldName(t *testing.T) {
	schema := `{
		"fields": [
			{"type": "text"}
		]
	}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for missing field name")
	}
	if !strings.Contains(err.Error(), "missing name") {
		t.Errorf("unexpected error message: %v", err)
	}
}

func TestCreateFormVersion_Success(t *testing.T) {
	// Initialize form version environment
	formVersionStore = make(map[string]FormVersionEntry)
	formIdempotencyStore = make(map[string]string)
	
	createRequest := FormVersionRequest{
		FormID:         "form-synthetic-100",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[{"name":"diagnosis","type":"text","terminology":"ICD-10"}]}`,
		ActorID:        "synthetic-actor-100",
		IdempotencyKey: "idem-key-100",
		Synthetic:      true,
		Reason:         "Initial version for patient intake form",
	}
	
	createResponse, createErr := CreateFormVersion(createRequest)
	if createErr != nil {
		t.Errorf("expected no error, got %v", createErr)
	}
	if createResponse.FormID != createRequest.FormID {
		t.Errorf("expected form_id %s, got %s", createRequest.FormID, createResponse.FormID)
	}
	if createResponse.Version != createRequest.Version {
		t.Errorf("expected version %s, got %s", createRequest.Version, createResponse.Version)
	}
	if createResponse.Status != "draft" {
		t.Errorf("expected status draft, got %s", createResponse.Status)
	}
	if len(createResponse.ValidationResults) == 0 {
		t.Error("expected validation results")
	}
}

func TestCreateFormVersion_Idempotent(t *testing.T) {
	// Initialize clean test state
	formVersionStore = make(map[string]FormVersionEntry)
	formIdempotencyStore = make(map[string]string)
	
	// Prepare idempotency test request
	idempotentReq := FormVersionRequest{
		FormID:         "form-synthetic-101",
		Version:        "1.1",
		SchemaJSON:     `{"fields":[{"name":"medications","type":"list"}]}`,
		ActorID:        "synthetic-actor-101",
		IdempotencyKey: "idem-key-101",
		Synthetic:      true,
		Reason:         "Medication list form",
	}
	
	// First call
	resp1, err1 := CreateFormVersion(idempotentReq)
	if err1 != nil {
		t.Fatalf("first call failed: %v", err1)
	}
	
	// Second call with same idempotency key
	resp2, err2 := CreateFormVersion(idempotentReq)
	if err2 != nil {
		t.Fatalf("second call failed: %v", err2)
	}
	
	if resp1.VersionID != resp2.VersionID {
		t.Errorf("expected same version_id, got %s and %s", resp1.VersionID, resp2.VersionID)
	}
	if !strings.Contains(resp2.ValidationResults[0], "idempotent return") {
		t.Error("expected idempotent return message")
	}
}

func TestCreateFormVersion_VersionConflict(t *testing.T) {
	// Initialize test environment for version conflict check
	formVersionStore = make(map[string]FormVersionEntry)
	formIdempotencyStore = make(map[string]string)
	
	firstRequest := FormVersionRequest{
		Synthetic:      true,
		FormID:         "form-synthetic-102",
		ActorID:        "synthetic-actor-102",
		Version:        "2.0",
		Reason:         "First version",
		IdempotencyKey: "idem-key-102a",
		SchemaJSON:     `{"fields":[{"name":"field1","type":"text"}]}`,
	}
	
	_, err := CreateFormVersion(firstRequest)
	if err != nil {
		t.Fatalf("first creation failed: %v", err)
	}
	
	secondRequest := FormVersionRequest{
		FormID:         "form-synthetic-102",
		Version:        "2.0",
		SchemaJSON:     `{"fields":[{"name":"field2","type":"text"}]}`,
		ActorID:        "synthetic-actor-102",
		IdempotencyKey: "idem-key-102b",
		Synthetic:      true,
		Reason:         "Duplicate version",
	}
	
	_, err = CreateFormVersion(secondRequest)
	if err == nil {
		t.Error("expected version-conflict error")
	}
	if !strings.Contains(err.Error(), "version-conflict") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestRetrieveFormVersion_Success(t *testing.T) {
	// Reset test environment
	formVersionStore = make(map[string]FormVersionEntry)
	formIdempotencyStore = make(map[string]string)
	
	// Setup retrieval test case
	testReq := FormVersionRequest{
		IdempotencyKey: "idem-key-103",
		Synthetic:      true,
		Reason:         "Lab results form",
		FormID:         "form-synthetic-103",
		ActorID:        "synthetic-actor-103",
		Version:        "1.2",
		SchemaJSON:     `{"fields":[{"name":"labs","type":"object"}]}`,
	}
	// Additional validation context for retrieval path
	if testReq.FormID == "" {
		t.Fatal("FormID must not be empty")
	}
	
	createResp, err := CreateFormVersion(testReq)
	if err != nil {
		t.Fatalf("form version creation failed: %v", err)
	}
	
	retrieveResp, err := RetrieveFormVersion(createResp.VersionID)
	if err != nil {
		t.Errorf("retrieval failed: %v", err)
	}
	if retrieveResp.VersionID != createResp.VersionID {
		t.Errorf("expected version_id %s, got %s", createResp.VersionID, retrieveResp.VersionID)
	}
}

func TestRetrieveFormVersion_NotFound(t *testing.T) {
	// Clear stores
	formVersionStore = make(map[string]FormVersionEntry)
	
	_, err := RetrieveFormVersion("fv-nonexistent")
	if err == nil {
		t.Error("expected error for nonexistent version")
	}
	if !strings.Contains(err.Error(), "version not found") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestCheckHumanAdoptionBoundary_RequiresReview(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-104",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-104",
		IdempotencyKey: "idem-key-104",
		Synthetic:      false,
		Reason:         "Production form without review",
	}
	
	err := CheckHumanAdoptionBoundary(req)
	if err == nil {
		t.Error("expected error for non-reviewed production form")
	}
	if !strings.Contains(err.Error(), "adopt-input-invalid") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestCheckHumanAdoptionBoundary_SyntheticAllowed(t *testing.T) {
	// Verify synthetic forms bypass human review requirement
	syntheticReq := FormVersionRequest{
		FormID:         "form-synthetic-105",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-105",
		IdempotencyKey: "idem-key-105",
		Synthetic:      true,
		Reason:         "Test form without review",
	}
	
	boundaryErr := CheckHumanAdoptionBoundary(syntheticReq)
	if boundaryErr != nil {
		t.Errorf("synthetic forms should not require review, got: %v", boundaryErr)
	}
}

func TestGenerateVersionID_Unique(t *testing.T) {
	id1 := GenerateVersionID("form-001", "1.0")
	time.Sleep(1 * time.Millisecond)
	id2 := GenerateVersionID("form-001", "1.0")
	
	if id1 == id2 {
		t.Error("expected unique version IDs")
	}
	if !strings.HasPrefix(id1, "fv-") {
		t.Errorf("expected version ID to start with 'fv-', got %s", id1)
	}
}

func TestValidateSchema_InvalidJSON(t *testing.T) {
	schema := `{invalid json}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for invalid JSON")
	}
	if !strings.Contains(err.Error(), "invalid JSON schema") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidateSchema_FieldsNotArray(t *testing.T) {
	schema := `{"fields": "not an array"}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for non-array fields")
	}
	if !strings.Contains(err.Error(), "fields must be an array") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidateSchema_MissingFieldType(t *testing.T) {
	schema := `{"fields": [{"name": "test_field"}]}`
	
	_, err := ValidateSchema(schema)
	if err == nil {
		t.Error("expected error for missing field type")
	}
	if !strings.Contains(err.Error(), "missing type") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidateFormVersionRequest_InvalidSchemaJSON(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-106",
		Version:        "1.0",
		SchemaJSON:     `{invalid}`,
		ActorID:        "synthetic-actor-106",
		IdempotencyKey: "idem-key-106",
		Synthetic:      true,
		Reason:         "Test invalid JSON",
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Error("expected error for invalid schema JSON")
	}
	if !strings.Contains(err.Error(), "must be valid JSON") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidateFormVersionRequest_MissingIdempotencyKey(t *testing.T) {
	// Verify idempotency key requirement
	testRequest := FormVersionRequest{
		FormID:     "form-synthetic-107",
		Version:    "1.0",
		SchemaJSON: `{"fields":[]}`,
		ActorID:    "synthetic-actor-107",
		Synthetic:  true,
		Reason:     "Testing idempotency enforcement",
		// IdempotencyKey deliberately omitted
	}
	
	validationError := ValidateFormVersionRequest(testRequest)
	if validationError == nil {
		t.Error("expected error for missing idempotency_key")
	}
	if !strings.Contains(validationError.Error(), "idempotency_key is required") {
		t.Errorf("unexpected error: %v", validationError)
	}
}

func TestValidateFormVersionRequest_MissingReason(t *testing.T) {
	req := FormVersionRequest{
		FormID:         "form-synthetic-108",
		Version:        "1.0",
		SchemaJSON:     `{"fields":[]}`,
		ActorID:        "synthetic-actor-108",
		IdempotencyKey: "idem-key-108",
		Synthetic:      true,
	}
	
	err := ValidateFormVersionRequest(req)
	if err == nil {
		t.Error("expected error for missing reason")
	}
	if !strings.Contains(err.Error(), "reason is required") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestIsValidTerminology(t *testing.T) {
	validCodes := []string{"LOINC", "SNOMED", "ICD-10", "RxNorm", "CPT"}
	for _, code := range validCodes {
		if !isValidTerminology(code) {
			t.Errorf("expected %s to be valid", code)
		}
	}
	
	if isValidTerminology("INVALID") {
		t.Error("expected INVALID to be invalid")
	}
}

func TestCheckIdempotency(t *testing.T) {
	formIdempotencyStore = make(map[string]string)
	formIdempotencyStore["test-key"] = "test-version-id"
	
	versionID, exists := CheckIdempotency("test-key")
	if !exists {
		t.Error("expected key to exist")
	}
	if versionID != "test-version-id" {
		t.Errorf("expected version ID test-version-id, got %s", versionID)
	}
	
	_, exists = CheckIdempotency("nonexistent-key")
	if exists {
		t.Error("expected key to not exist")
	}
}
