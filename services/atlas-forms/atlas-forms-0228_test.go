package forms

import (
	"testing"
	"time"
)

func TestValidateRequiredFieldRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     RequiredFieldRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid request",
			req: RequiredFieldRequest{
				FormID:         "form-001",
				SubmissionID:   "sub-001",
				FieldValues:    map[string]string{"field1": "value1"},
				SchemaJSON:     `{"fields":[{"name":"field1","type":"string","required":true}]}`,
				ActorID:        "actor-synthetic-001",
				IdempotencyKey: "idem-001",
				Synthetic:      true,
				Reason:         "test validation",
			},
			wantErr: false,
		},
		{
			name: "missing form_id",
			req: RequiredFieldRequest{
				SubmissionID:   "sub-001",
				SchemaJSON:     `{"fields":[]}`,
				ActorID:        "actor-002",
				IdempotencyKey: "idem-002",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "field-invalid: form_id is required",
		},
		{
			name: "missing submission_id",
			req: RequiredFieldRequest{
				FormID:         "form-003",
				SchemaJSON:     `{"fields":[]}`,
				ActorID:        "actor-003",
				IdempotencyKey: "idem-003",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "field-invalid: submission_id is required",
		},
		{
			name: "non-synthetic request",
			req: RequiredFieldRequest{
				FormID:         "form-004",
				SubmissionID:   "sub-004",
				SchemaJSON:     `{"fields":[]}`,
				ActorID:        "actor-004",
				IdempotencyKey: "idem-004",
				Synthetic:      false,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "field-synthetic-only: only synthetic validation requests are allowed",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRequiredFieldRequest(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateRequiredFieldRequest() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil && tt.errMsg != "" && err.Error() != tt.errMsg {
				t.Errorf("ValidateRequiredFieldRequest() error = %v, want %v", err.Error(), tt.errMsg)
			}
		})
	}
}

func TestParseSchema(t *testing.T) {
	tests := []struct {
		name       string
		schemaJSON string
		wantErr    bool
		errMsg     string
	}{
		{
			name:       "valid schema",
			schemaJSON: `{"fields":[{"name":"patient_name","type":"string","required":true}]}`,
			wantErr:    false,
		},
		{
			name:       "empty fields",
			schemaJSON: `{"fields":[]}`,
			wantErr:    true,
			errMsg:     "field-schema-invalid: schema must contain at least one field",
		},
		{
			name:       "invalid json",
			schemaJSON: `{"fields":`,
			wantErr:    true,
			errMsg:     "field-schema-invalid",
		},
		{
			name:       "duplicate field names",
			schemaJSON: `{"fields":[{"name":"age","type":"number","required":true},{"name":"age","type":"string","required":false}]}`,
			wantErr:    true,
			errMsg:     "field-schema-invalid: duplicate field name: age",
		},
		{
			name:       "valid conditional",
			schemaJSON: `{"fields":[{"name":"has_allergy","type":"boolean","required":true},{"name":"allergy_details","type":"string","conditional":{"depends_on":"has_allergy","value":"true","operator":"eq"}}]}`,
			wantErr:    false,
		},
		{
			name:       "invalid conditional operator",
			schemaJSON: `{"fields":[{"name":"field_a","type":"string","required":true},{"name":"field_b","type":"string","conditional":{"depends_on":"field_a","value":"yes","operator":"invalid_op"}}]}`,
			wantErr:    true,
			errMsg:     "field-conditional-invalid: invalid operator: invalid_op",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			schema, err := ParseSchema(tt.schemaJSON)
			if (err != nil) != tt.wantErr {
				t.Errorf("ParseSchema() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err == nil && schema == nil {
				t.Error("ParseSchema() returned nil schema without error")
			}
		})
	}
}

func TestValidateRequiredFields(t *testing.T) {
	schema := &FormSchema{
		Fields: []SchemaField{
			{Name: "record_key", Type: "string", Required: true},
			{Name: "visit_date", Type: "string", Required: true},
			{Name: "notes", Type: "string", Required: false},
		},
	}

	tests := []struct {
		name        string
		fieldValues map[string]string
		wantMissing int
	}{
		{
			name: "all required present",
			fieldValues: map[string]string{
				"record_key": "synthetic-patient-123",
				"visit_date": "2024-01-15",
				"notes":      "routine checkup",
			},
			wantMissing: 0,
		},
		{
			name: "missing one required",
			fieldValues: map[string]string{
				"record_key": "synthetic-patient-456",
				"notes":      "follow-up",
			},
			wantMissing: 1,
		},
		{
			name: "missing all required",
			fieldValues: map[string]string{
				"notes": "emergency visit",
			},
			wantMissing: 2,
		},
		{
			name: "empty value treated as missing",
			fieldValues: map[string]string{
				"record_key": "",
				"visit_date": "2024-01-16",
			},
			wantMissing: 1,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			missing := ValidateRequiredFields(schema, tt.fieldValues)
			if len(missing) != tt.wantMissing {
				t.Errorf("ValidateRequiredFields() got %d missing, want %d", len(missing), tt.wantMissing)
			}
		})
	}
}

func TestEvaluateConditional(t *testing.T) {
	tests := []struct {
		name        string
		rule        *ConditionalRule
		fieldValues map[string]string
		want        bool
	}{
		{
			name: "eq operator true",
			rule: &ConditionalRule{
				DependsOn: "has_symptoms",
				Value:     "yes",
				Operator:  "eq",
			},
			fieldValues: map[string]string{"has_symptoms": "yes"},
			want:        true,
		},
		{
			name: "eq operator false",
			rule: &ConditionalRule{
				DependsOn: "has_symptoms",
				Value:     "yes",
				Operator:  "eq",
			},
			fieldValues: map[string]string{"has_symptoms": "no"},
			want:        false,
		},
		{
			name: "ne operator true",
			rule: &ConditionalRule{
				DependsOn: "status",
				Value:     "inactive",
				Operator:  "ne",
			},
			fieldValues: map[string]string{"status": "active"},
			want:        true,
		},
		{
			name: "contains operator true",
			rule: &ConditionalRule{
				DependsOn: "diagnosis",
				Value:     "hypertension",
				Operator:  "contains",
			},
			fieldValues: map[string]string{"diagnosis": "primary hypertension stage 2"},
			want:        true,
		},
		{
			name: "missing dependent field",
			rule: &ConditionalRule{
				DependsOn: "field_x",
				Value:     "value",
				Operator:  "eq",
			},
			fieldValues: map[string]string{"field_y": "other"},
			want:        false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := EvaluateConditional(tt.rule, tt.fieldValues)
			if got != tt.want {
				t.Errorf("EvaluateConditional() = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestValidateConditionalFields(t *testing.T) {
	schema := &FormSchema{
		Fields: []SchemaField{
			{Name: "has_allergy", Type: "boolean", Required: true},
			{
				Name: "allergy_type",
				Type: "string",
				Conditional: &ConditionalRule{
					DependsOn: "has_allergy",
					Value:     "true",
					Operator:  "eq",
				},
			},
			{Name: "age", Type: "number", Required: true},
			{
				Name: "guardian_name",
				Type: "string",
				Conditional: &ConditionalRule{
					DependsOn: "age",
					Value:     "18",
					Operator:  "lt",
				},
			},
		},
	}

	tests := []struct {
		name       string
		fieldValues map[string]string
		wantErrors int
	}{
		{
			name: "all conditionals satisfied",
			fieldValues: map[string]string{
				"has_allergy":  "true",
				"allergy_type": "medication",
				"age":          "16",
				"guardian_name": "synthetic-parent-789",
			},
			wantErrors: 0,
		},
		{
			name: "missing conditional field",
			fieldValues: map[string]string{
				"has_allergy": "true",
				"age":         "25",
			},
			wantErrors: 1,
		},
		{
			name: "conditional not triggered",
			fieldValues: map[string]string{
				"has_allergy": "false",
				"age":         "30",
			},
			wantErrors: 0,
		},
		{
			name: "multiple conditionals missing",
			fieldValues: map[string]string{
				"has_allergy": "true",
				"age":         "12",
			},
			wantErrors: 2,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			errors := ValidateConditionalFields(schema, tt.fieldValues)
			if len(errors) != tt.wantErrors {
				t.Errorf("ValidateConditionalFields() got %d errors, want %d", len(errors), tt.wantErrors)
			}
		})
	}
}

func TestValidateRequiredFieldSubmission(t *testing.T) {
	// Clear stores before tests
	validationStore = make(map[string]ValidationEntry)
	validationIdempotency = make(map[string]string)

	schemaJSON := `{
		"fields": [
			{"name": "chief_complaint", "type": "string", "required": true},
			{"name": "has_fever", "type": "boolean", "required": true},
			{
				"name": "temperature",
				"type": "number",
				"conditional": {
					"depends_on": "has_fever",
					"value": "true",
					"operator": "eq"
				}
			}
		]
	}`

	tests := []struct {
		name       string
		req        RequiredFieldRequest
		wantStatus string
		wantErr    bool
	}{
		{
			name: "valid submission",
			req: RequiredFieldRequest{
				FormID:       "form-test-101",
				SubmissionID: "sub-test-101",
				FieldValues: map[string]string{
					"chief_complaint": "headache",
					"has_fever":       "true",
					"temperature":     "38.5",
				},
				SchemaJSON:     schemaJSON,
				ActorID:        "actor-test-101",
				IdempotencyKey: "idem-test-101",
				Synthetic:      true,
				Reason:         "test complete validation",
			},
			wantStatus: "valid",
			wantErr:    false,
		},
		{
			name: "missing required field",
			req: RequiredFieldRequest{
				FormID:       "form-test-102",
				SubmissionID: "sub-test-102",
				FieldValues: map[string]string{
					"has_fever": "false",
				},
				SchemaJSON:     schemaJSON,
				ActorID:        "actor-test-102",
				IdempotencyKey: "idem-test-102",
				Synthetic:      true,
				Reason:         "test missing required",
			},
			wantStatus: "invalid",
			wantErr:    false,
		},
		{
			name: "missing conditional field",
			req: RequiredFieldRequest{
				FormID:       "form-test-103",
				SubmissionID: "sub-test-103",
				FieldValues: map[string]string{
					"chief_complaint": "fever",
					"has_fever":       "true",
				},
				SchemaJSON:     schemaJSON,
				ActorID:        "actor-test-103",
				IdempotencyKey: "idem-test-103",
				Synthetic:      true,
				Reason:         "test missing conditional",
			},
			wantStatus: "invalid",
			wantErr:    false,
		},
		{
			name: "idempotent request",
			req: RequiredFieldRequest{
				FormID:       "form-test-101",
				SubmissionID: "sub-test-101",
				FieldValues: map[string]string{
					"chief_complaint": "headache",
					"has_fever":       "true",
					"temperature":     "38.5",
				},
				SchemaJSON:     schemaJSON,
				ActorID:        "actor-test-101",
				IdempotencyKey: "idem-test-101",
				Synthetic:      true,
				Reason:         "duplicate request",
			},
			wantStatus: "valid",
			wantErr:    false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := ValidateRequiredFieldSubmission(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateRequiredFieldSubmission() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err == nil {
				if resp.Status != tt.wantStatus {
					t.Errorf("ValidateRequiredFieldSubmission() status = %v, want %v", resp.Status, tt.wantStatus)
				}
				if resp.ValidationID == "" {
					t.Error("ValidateRequiredFieldSubmission() returned empty validation_id")
				}
				if resp.SubmissionID != tt.req.SubmissionID {
					t.Errorf("ValidateRequiredFieldSubmission() submission_id = %v, want %v", resp.SubmissionID, tt.req.SubmissionID)
				}
			}
		})
	}
}

func TestRetrieveValidation(t *testing.T) {
	// Clear and populate store
	validationStore = make(map[string]ValidationEntry)
	
	entry := ValidationEntry{
		ValidationID:      "val-retrieve-001",
		SubmissionID:      "sub-retrieve-001",
		FormID:            "form-retrieve-001",
		Status:            "valid",
		MissingFields:     []string{},
		ConditionalErrors: []string{},
		ValidatedAt:       "2024-01-15T10:00:00Z",
		ActorID:           "actor-retrieve-001",
		Synthetic:         true,
	}
	validationStore[entry.ValidationID] = entry

	tests := []struct {
		name         string
		validationID string
		wantErr      bool
		errMsg       string
	}{
		{
			name:         "existing validation",
			validationID: "val-retrieve-001",
			wantErr:      false,
		},
		{
			name:         "non-existent validation",
			validationID: "val-nonexistent",
			wantErr:      true,
			errMsg:       "field-not-found: validation not found",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := RetrieveValidation(tt.validationID)
			if (err != nil) != tt.wantErr {
				t.Errorf("RetrieveValidation() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err == nil && resp.ValidationID != tt.validationID {
				t.Errorf("RetrieveValidation() validation_id = %v, want %v", resp.ValidationID, tt.validationID)
			}
		})
	}
}

func TestGenerateValidationID(t *testing.T) {
	formID := "form-gen-001"
	submissionID := "sub-gen-001"
	actorID := "actor-gen-001"
	timestamp := timeNow()

	id1 := GenerateValidationID(formID, submissionID, actorID, timestamp)
	id2 := GenerateValidationID(formID, submissionID, actorID, timestamp)

	if id1 != id2 {
		t.Error("GenerateValidationID() should be deterministic")
	}
	if id1 == "" {
		t.Error("GenerateValidationID() returned empty string")
	}
	if len(id1) != 20 { // "val-" + 16 hex chars
		t.Errorf("GenerateValidationID() length = %d, want 20", len(id1))
	}
}

func timeNow() time.Time {
	return time.Date(2024, 1, 15, 12, 0, 0, 0, time.UTC)
}
