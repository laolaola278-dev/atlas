package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// FormVersionRequest represents a request to create or retrieve a form version
type FormVersionRequest struct {
	FormID         string `json:"form_id"`
	Version        string `json:"version"`
	SchemaJSON     string `json:"schema_json"`
	ActorID        string `json:"actor_id"`
	IdempotencyKey string `json:"idempotency_key"`
	Synthetic      bool   `json:"synthetic"`
	Reason         string `json:"reason"`
}

// FormVersionResponse contains the result of a form version operation
type FormVersionResponse struct {
	VersionID         string   `json:"version_id"`
	FormID            string   `json:"form_id"`
	Version           string   `json:"version"`
	Status            string   `json:"status"`
	CreatedAt         string   `json:"created_at"`
	ValidationResults []string `json:"validation_results"`
}

// FormVersionEntry represents a stored form version
type FormVersionEntry struct {
	VersionID      string
	FormID         string
	Version        string
	SchemaJSON     string
	Status         string
	CreatedAt      string
	ActorID        string
	IdempotencyKey string
	Synthetic      bool
	Reason         string
}

var (
	formVersionStore         = make(map[string]FormVersionEntry)
	formIdempotencyStore     = make(map[string]string)
	formVersionPattern       = regexp.MustCompile(`^\d+\.\d+$`)
	validFormStatuses        = map[string]bool{"draft": true, "active": true, "deprecated": true}
)

// ValidateFormVersionRequest validates the form version request
func ValidateFormVersionRequest(req FormVersionRequest) error {
	if req.FormID == "" {
		return errors.New("form-invalid: form_id is required")
	}
	if !req.Synthetic {
		return errors.New("form-version-invalid: synthetic must be true for test data")
	}
	if req.Version == "" {
		return errors.New("form-version-invalid: version is required")
	}
	if !formVersionPattern.MatchString(req.Version) {
		return errors.New("form-version-invalid: version must be semantic (e.g., 1.0)")
	}
	if req.SchemaJSON == "" {
		return errors.New("form-version-invalid: schema_json is required")
	}
	if req.ActorID == "" {
		return errors.New("actor-context-incomplete: actor_id is required")
	}
	if req.IdempotencyKey == "" {
		return errors.New("idempotency-key-invalid: idempotency_key is required")
	}
	if req.Reason == "" {
		return errors.New("form-version-invalid: reason is required")
	}
	
	// Validate schema JSON structure
	var schema map[string]interface{}
	if err := json.Unmarshal([]byte(req.SchemaJSON), &schema); err != nil {
		return errors.New("form-version-invalid: schema_json must be valid JSON")
	}
	
	return nil
}

// ValidateSchema validates the form schema structure and terminology
func ValidateSchema(schemaJSON string) ([]string, error) {
	var schema map[string]interface{}
	if err := json.Unmarshal([]byte(schemaJSON), &schema); err != nil {
		return nil, errors.New("form-version-invalid: invalid JSON schema")
	}
	
	results := []string{}
	
	// Check required schema fields
	if _, ok := schema["fields"]; !ok {
		return nil, errors.New("form-version-invalid: schema must contain fields")
	}
	
	fields, ok := schema["fields"].([]interface{})
	if !ok {
		return nil, errors.New("form-version-invalid: fields must be an array")
	}
	
	// Validate each field
	for i, fieldInterface := range fields {
		field, ok := fieldInterface.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("form-version-invalid: field %d must be an object", i)
		}
		
		// Check field name
		fieldName, ok := field["name"].(string)
		if !ok || fieldName == "" {
			return nil, fmt.Errorf("form-version-invalid: field %d missing name", i)
		}
		
		// Check field type
		fieldType, ok := field["type"].(string)
		if !ok || fieldType == "" {
			return nil, fmt.Errorf("form-version-invalid: field %s missing type", fieldName)
		}
		
		// Validate terminology if present
		if terminology, ok := field["terminology"].(string); ok && terminology != "" {
			if !isValidTerminology(terminology) {
				return nil, fmt.Errorf("doc-term-unknown: field %s has unknown terminology %s", fieldName, terminology)
			}
			results = append(results, fmt.Sprintf("field %s: terminology %s validated", fieldName, terminology))
		}
		
		results = append(results, fmt.Sprintf("field %s: type %s validated", fieldName, fieldType))
	}
	
	return results, nil
}

// isValidTerminology checks if the terminology code is valid
func isValidTerminology(code string) bool {
	validCodes := map[string]bool{
		"LOINC":   true,
		"SNOMED":  true,
		"ICD-10":  true,
		"RxNorm":  true,
		"CPT":     true,
	}
	return validCodes[code]
}

// GenerateVersionID generates a unique version identifier
func GenerateVersionID(formID, version string) string {
	data := fmt.Sprintf("%s:%s:%d", formID, version, time.Now().UnixNano())
	hash := sha256.Sum256([]byte(data))
	return "fv-" + hex.EncodeToString(hash[:])[:16]
}

// CheckIdempotency checks if this request was already processed
func CheckIdempotency(key string) (string, bool) {
	versionID, exists := formIdempotencyStore[key]
	return versionID, exists
}

// CreateFormVersion creates a new form version
func CreateFormVersion(req FormVersionRequest) (FormVersionResponse, error) {
	// Check idempotency first
	if existingVersionID, exists := CheckIdempotency(req.IdempotencyKey); exists {
		existing := formVersionStore[existingVersionID]
		return FormVersionResponse{
			VersionID:         existing.VersionID,
			FormID:            existing.FormID,
			Version:           existing.Version,
			Status:            existing.Status,
			CreatedAt:         existing.CreatedAt,
			ValidationResults: []string{"idempotent return: already processed"},
		}, nil
	}
	
	// Validate request
	if err := ValidateFormVersionRequest(req); err != nil {
		return FormVersionResponse{}, err
	}
	
	// Validate schema and terminology
	validationResults, err := ValidateSchema(req.SchemaJSON)
	if err != nil {
		return FormVersionResponse{}, err
	}
	
	// Check for version conflicts
	for _, entry := range formVersionStore {
		if entry.FormID == req.FormID && entry.Version == req.Version {
			return FormVersionResponse{}, errors.New("version-conflict: form version already exists")
		}
	}
	
	// Generate version ID
	versionID := GenerateVersionID(req.FormID, req.Version)
	timestamp := time.Now().UTC().Format(time.RFC3339)
	
	// Store the version
	entry := FormVersionEntry{
		VersionID:      versionID,
		FormID:         req.FormID,
		Version:        req.Version,
		SchemaJSON:     req.SchemaJSON,
		Status:         "draft",
		CreatedAt:      timestamp,
		ActorID:        req.ActorID,
		IdempotencyKey: req.IdempotencyKey,
		Synthetic:      req.Synthetic,
		Reason:         req.Reason,
	}
	formVersionStore[versionID] = entry
	formIdempotencyStore[req.IdempotencyKey] = versionID
	
	return FormVersionResponse{
		VersionID:         versionID,
		FormID:            req.FormID,
		Version:           req.Version,
		Status:            "draft",
		CreatedAt:         timestamp,
		ValidationResults: validationResults,
	}, nil
}

// RetrieveFormVersion retrieves a form version by ID
func RetrieveFormVersion(versionID string) (FormVersionResponse, error) {
	entry, exists := formVersionStore[versionID]
	if !exists {
		return FormVersionResponse{}, errors.New("form-version-invalid: version not found")
	}
	
	validationResults, _ := ValidateSchema(entry.SchemaJSON)
	
	return FormVersionResponse{
		VersionID:         entry.VersionID,
		FormID:            entry.FormID,
		Version:           entry.Version,
		Status:            entry.Status,
		CreatedAt:         entry.CreatedAt,
		ValidationResults: validationResults,
	}, nil
}

// CheckHumanAdoptionBoundary validates that form creation requires human oversight
func CheckHumanAdoptionBoundary(req FormVersionRequest) error {
	// All form versions must be reviewed by humans before production use
	if !strings.Contains(req.Reason, "human-reviewed") && !req.Synthetic {
		return errors.New("adopt-input-invalid: form version requires human review before adoption")
	}
	return nil
}
