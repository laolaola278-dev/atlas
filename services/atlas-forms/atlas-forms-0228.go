package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
	"time"
)

// RequiredFieldRequest represents a request to validate required fields
type RequiredFieldRequest struct {
	FormID         string            `json:"form_id"`
	SubmissionID   string            `json:"submission_id"`
	FieldValues    map[string]string `json:"field_values"`
	SchemaJSON     string            `json:"schema_json"`
	ActorID        string            `json:"actor_id"`
	IdempotencyKey string            `json:"idempotency_key"`
	Synthetic      bool              `json:"synthetic"`
	Reason         string            `json:"reason"`
}

// RequiredFieldResponse contains the validation result
type RequiredFieldResponse struct {
	ValidationID      string   `json:"validation_id"`
	SubmissionID      string   `json:"submission_id"`
	Status            string   `json:"status"`
	MissingFields     []string `json:"missing_fields"`
	ConditionalErrors []string `json:"conditional_errors"`
	ValidatedAt       string   `json:"validated_at"`
}

// ValidationEntry represents a stored validation result
type ValidationEntry struct {
	ValidationID      string
	SubmissionID      string
	FormID            string
	Status            string
	MissingFields     []string
	ConditionalErrors []string
	ValidatedAt       string
	ActorID           string
	IdempotencyKey    string
	Synthetic         bool
}

// SchemaField represents a field definition in the schema
type SchemaField struct {
	Name        string                 `json:"name"`
	Type        string                 `json:"type"`
	Required    bool                   `json:"required"`
	Conditional *ConditionalRule       `json:"conditional,omitempty"`
	Properties  map[string]interface{} `json:"properties,omitempty"`
}

// ConditionalRule defines when a field is required based on other fields
type ConditionalRule struct {
	DependsOn string `json:"depends_on"`
	Value     string `json:"value"`
	Operator  string `json:"operator"` // eq, ne, gt, lt, contains
}

// FormSchema represents the complete form schema
type FormSchema struct {
	Fields []SchemaField `json:"fields"`
}

var (
	validationStore         = make(map[string]ValidationEntry)
	validationIdempotency   = make(map[string]string)
	validConditionalOps     = map[string]bool{"eq": true, "ne": true, "gt": true, "lt": true, "contains": true}
)

// ValidateRequiredFieldRequest validates the request structure
func ValidateRequiredFieldRequest(req RequiredFieldRequest) error {
	if req.FormID == "" {
		return errors.New("field-invalid: form_id is required")
	}
	if req.SubmissionID == "" {
		return errors.New("field-invalid: submission_id is required")
	}
	if req.SchemaJSON == "" {
		return errors.New("field-invalid: schema_json is required")
	}
	if req.ActorID == "" {
		return errors.New("field-invalid: actor_id is required")
	}
	if req.IdempotencyKey == "" {
		return errors.New("field-invalid: idempotency_key is required")
	}
	if !req.Synthetic {
		return errors.New("field-synthetic-only: only synthetic validation requests are allowed")
	}
	if req.Reason == "" {
		return errors.New("field-invalid: reason is required for synthetic requests")
	}
	return nil
}

// ParseSchema parses and validates the JSON schema
func ParseSchema(schemaJSON string) (*FormSchema, error) {
	var schema FormSchema
	if err := json.Unmarshal([]byte(schemaJSON), &schema); err != nil {
		return nil, fmt.Errorf("field-schema-invalid: %w", err)
	}
	if len(schema.Fields) == 0 {
		return nil, errors.New("field-schema-invalid: schema must contain at least one field")
	}
	
	// Validate field definitions
	fieldNames := make(map[string]bool)
	for _, field := range schema.Fields {
		if field.Name == "" {
			return nil, errors.New("field-schema-invalid: field name is required")
		}
		if fieldNames[field.Name] {
			return nil, fmt.Errorf("field-schema-invalid: duplicate field name: %s", field.Name)
		}
		fieldNames[field.Name] = true
		
		if field.Type == "" {
			return nil, fmt.Errorf("field-schema-invalid: field type is required for field: %s", field.Name)
		}
		
		// Validate conditional rules
		if field.Conditional != nil {
			if field.Conditional.DependsOn == "" {
				return nil, fmt.Errorf("field-conditional-invalid: depends_on is required for field: %s", field.Name)
			}
			if !fieldNames[field.Conditional.DependsOn] && field.Conditional.DependsOn != field.Name {
				return nil, fmt.Errorf("field-conditional-invalid: depends_on field not found: %s", field.Conditional.DependsOn)
			}
			if field.Conditional.Operator == "" {
				field.Conditional.Operator = "eq"
			}
			if !validConditionalOps[field.Conditional.Operator] {
				return nil, fmt.Errorf("field-conditional-invalid: invalid operator: %s", field.Conditional.Operator)
			}
		}
	}
	
	return &schema, nil
}

// ValidateRequiredFields checks for missing required fields
func ValidateRequiredFields(schema *FormSchema, fieldValues map[string]string) []string {
	var missing []string
	for _, field := range schema.Fields {
		if field.Required {
			value, exists := fieldValues[field.Name]
			if !exists || strings.TrimSpace(value) == "" {
				missing = append(missing, field.Name)
			}
		}
	}
	return missing
}

// EvaluateConditional checks if a conditional rule is satisfied
func EvaluateConditional(rule *ConditionalRule, fieldValues map[string]string) bool {
	dependentValue, exists := fieldValues[rule.DependsOn]
	if !exists {
		return false
	}
	
	switch rule.Operator {
	case "eq":
		return dependentValue == rule.Value
	case "ne":
		return dependentValue != rule.Value
	case "gt":
		return dependentValue > rule.Value
	case "lt":
		return dependentValue < rule.Value
	case "contains":
		return strings.Contains(dependentValue, rule.Value)
	default:
		return false
	}
}

// ValidateConditionalFields checks conditional field requirements
func ValidateConditionalFields(schema *FormSchema, fieldValues map[string]string) []string {
	var errors []string
	for _, field := range schema.Fields {
		if field.Conditional != nil {
			if EvaluateConditional(field.Conditional, fieldValues) {
				value, exists := fieldValues[field.Name]
				if !exists || strings.TrimSpace(value) == "" {
					errors = append(errors, fmt.Sprintf("field %s is required when %s %s %s",
						field.Name, field.Conditional.DependsOn, field.Conditional.Operator, field.Conditional.Value))
				}
			}
		}
	}
	return errors
}

// GenerateValidationID creates a deterministic validation identifier
func GenerateValidationID(formID, submissionID, actorID string, timestamp time.Time) string {
	data := fmt.Sprintf("%s:%s:%s:%d", formID, submissionID, actorID, timestamp.Unix())
	hash := sha256.Sum256([]byte(data))
	return fmt.Sprintf("val-%s", hex.EncodeToString(hash[:])[:16])
}

// CheckValidationIdempotency checks if this validation has been processed
func CheckValidationIdempotency(idempotencyKey string) (string, bool) {
	validationID, exists := validationIdempotency[idempotencyKey]
	return validationID, exists
}

// ValidateRequiredFieldSubmission performs the complete validation
func ValidateRequiredFieldSubmission(req RequiredFieldRequest) (*RequiredFieldResponse, error) {
	if err := ValidateRequiredFieldRequest(req); err != nil {
		return nil, err
	}
	
	// Check idempotency
	if validationID, exists := CheckValidationIdempotency(req.IdempotencyKey); exists {
		entry := validationStore[validationID]
		return &RequiredFieldResponse{
			ValidationID:      entry.ValidationID,
			SubmissionID:      entry.SubmissionID,
			Status:            entry.Status,
			MissingFields:     entry.MissingFields,
			ConditionalErrors: entry.ConditionalErrors,
			ValidatedAt:       entry.ValidatedAt,
		}, nil
	}
	
	// Parse schema
	schema, err := ParseSchema(req.SchemaJSON)
	if err != nil {
		return nil, err
	}
	
	// Validate required fields
	missingFields := ValidateRequiredFields(schema, req.FieldValues)
	
	// Validate conditional fields
	conditionalErrors := ValidateConditionalFields(schema, req.FieldValues)
	
	// Determine status
	status := "valid"
	if len(missingFields) > 0 || len(conditionalErrors) > 0 {
		status = "invalid"
	}
	
	// Generate validation ID
	now := time.Now().UTC()
	validationID := GenerateValidationID(req.FormID, req.SubmissionID, req.ActorID, now)
	
	// Store validation result
	entry := ValidationEntry{
		ValidationID:      validationID,
		SubmissionID:      req.SubmissionID,
		FormID:            req.FormID,
		Status:            status,
		MissingFields:     missingFields,
		ConditionalErrors: conditionalErrors,
		ValidatedAt:       now.Format(time.RFC3339),
		ActorID:           req.ActorID,
		IdempotencyKey:    req.IdempotencyKey,
		Synthetic:         req.Synthetic,
	}
	
	validationStore[validationID] = entry
	validationIdempotency[req.IdempotencyKey] = validationID
	
	return &RequiredFieldResponse{
		ValidationID:      validationID,
		SubmissionID:      req.SubmissionID,
		Status:            status,
		MissingFields:     missingFields,
		ConditionalErrors: conditionalErrors,
		ValidatedAt:       entry.ValidatedAt,
	}, nil
}

// RetrieveValidation retrieves a validation result by ID
func RetrieveValidation(validationID string) (*RequiredFieldResponse, error) {
	entry, exists := validationStore[validationID]
	if !exists {
		return nil, errors.New("field-not-found: validation not found")
	}
	
	return &RequiredFieldResponse{
		ValidationID:      entry.ValidationID,
		SubmissionID:      entry.SubmissionID,
		Status:            entry.Status,
		MissingFields:     entry.MissingFields,
		ConditionalErrors: entry.ConditionalErrors,
		ValidatedAt:       entry.ValidatedAt,
	}, nil
}
