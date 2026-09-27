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

// SyntheticFormRequest represents a request to generate a synthetic form
type SyntheticFormRequest struct {
	FormID         string            `json:"form_id"`
	FormType       string            `json:"form_type"`
	FieldSpec      map[string]string `json:"field_spec"` // Field name to type mapping for synthetic generation
	Seed           string            `json:"seed"`
	Version        string            `json:"version"`
	IdempotencyKey string            `json:"idempotency_key"`
	Synthetic      bool              `json:"synthetic"`
}

// SyntheticFormResponse represents the generated synthetic form
type SyntheticFormResponse struct {
	FormID      string            `json:"form_id"`
	FormType    string            `json:"form_type"`
	Fields      map[string]string `json:"fields"`
	GeneratedAt time.Time         `json:"generated_at"`
	Checksum    string            `json:"checksum"`
	Version     string            `json:"version"`
	Synthetic   bool              `json:"synthetic"`
}

// SyntheticFormStore holds generated synthetic forms
type SyntheticFormStore struct {
	mu    sync.RWMutex
	forms map[string]*SyntheticFormResponse
	idem  map[string]string
}

var syntheticStore = &SyntheticFormStore{
	forms: make(map[string]*SyntheticFormResponse),
	idem:  make(map[string]string),
}

var exportPHIPatterns = []*regexp.Regexp{
	regexp.MustCompile(`(?i)\bpatient_id\b`),
	regexp.MustCompile(`(?i)\bname\b`),
	regexp.MustCompile(`(?i)\bphone\b`),
	regexp.MustCompile(`(?i)\baddress\b`),
	regexp.MustCompile(`(?i)\bbirth_date\b`),
	regexp.MustCompile(`(?i)\bidentifier\b`),
	regexp.MustCompile(`(?i)\bssn\b`),
	regexp.MustCompile(`(?i)\bemail\b`),
}

// ValidateSyntheticFormRequest validates the synthetic form generation request
func ValidateSyntheticFormRequest(req *SyntheticFormRequest) error {
	if req == nil {
		return errors.New("synthetic-form-request-nil")
	}
	if req.FormID == "" {
		return errors.New("synthetic-form-id-empty")
	}
	if req.FormType == "" {
		return errors.New("synthetic-form-type-empty")
	}
	if !req.Synthetic {
		return errors.New("synthetic-form-not-synthetic")
	}
	if req.IdempotencyKey == "" {
		return errors.New("synthetic-form-idempotency-required")
	}
	if len(req.IdempotencyKey) < 16 {
		return errors.New("synthetic-form-idempotency-too-short")
	}
	if req.Seed == "" {
		return errors.New("synthetic-form-seed-empty")
	}
	if len(req.FieldSpec) == 0 {
		return errors.New("synthetic-form-field-spec-empty")
	}
	for key := range req.FieldSpec {
		for _, pattern := range exportPHIPatterns {
			if pattern.MatchString(key) {
				return errors.New("synthetic-form-phi-pattern-detected")
			}
		}
	}
	validTypes := map[string]bool{
		"consent":    true,
		"assessment": true,
		"intake":     true,
		"discharge":  true,
		"procedure":  true,
		"medication": true,
		"lab-order":  true,
		"imaging":    true,
	}
	if !validTypes[req.FormType] {
		return errors.New("synthetic-form-type-invalid")
	}
	if req.Version == "" {
		return errors.New("synthetic-form-version-empty")
	}
	parts := strings.Split(req.Version, ".")
	if len(parts) < 2 {
		return errors.New("synthetic-form-version-invalid")
	}
	return nil
}

// GenerateSyntheticForm generates a synthetic form based on the request
func GenerateSyntheticForm(req *SyntheticFormRequest) (*SyntheticFormResponse, error) {
	if err := ValidateSyntheticFormRequest(req); err != nil {
		return nil, err
	}
	syntheticStore.mu.Lock()
	defer syntheticStore.mu.Unlock()
	if existingID, exists := syntheticStore.idem[req.IdempotencyKey]; exists {
		if form, ok := syntheticStore.forms[existingID]; ok {
			return form, nil
		}
		return nil, errors.New("synthetic-form-idempotency-mismatch")
	}
	fields := make(map[string]string)
	for key, valueType := range req.FieldSpec {
		fields[key] = generateSyntheticValue(valueType, req.Seed, key)
	}
	form := &SyntheticFormResponse{
		FormID:      req.FormID,
		FormType:    req.FormType,
		Fields:      fields,
		GeneratedAt: time.Now().UTC(),
		Version:     req.Version,
		Synthetic:   true,
	}
	checksumData := fmt.Sprintf("%s|%s|%s|%v", form.FormID, form.FormType, form.Version, form.Fields)
	hash := sha256.Sum256([]byte(checksumData))
	form.Checksum = hex.EncodeToString(hash[:])
	syntheticStore.forms[req.FormID] = form
	syntheticStore.idem[req.IdempotencyKey] = req.FormID
	return form, nil
}

// generateSyntheticValue generates a synthetic value based on type and seed
func generateSyntheticValue(valueType, seed, key string) string {
	combined := seed + "|" + key
	hash := sha256.Sum256([]byte(combined))
	hashStr := hex.EncodeToString(hash[:])
	switch valueType {
	case "string":
		return "synthetic-" + hashStr[:12]
	case "number":
		return fmt.Sprintf("%d", int(hash[0])%1000)
	case "boolean":
		return fmt.Sprintf("%t", hash[0]%2 == 0)
	case "date":
		days := int(hash[0]) % 365
		baseDate := time.Date(2024, 1, 1, 0, 0, 0, 0, time.UTC)
		return baseDate.AddDate(0, 0, days).Format("2006-01-02")
	case "code":
		return "CODE-" + hashStr[:8]
	case "text":
		return "Synthetic text value generated from seed"
	default:
		return "synthetic-" + hashStr[:16]
	}
}

// GetSyntheticForm retrieves a generated synthetic form by ID
func GetSyntheticForm(formID string) (*SyntheticFormResponse, error) {
	if formID == "" {
		return nil, errors.New("synthetic-form-id-empty")
	}
	syntheticStore.mu.RLock()
	defer syntheticStore.mu.RUnlock()
	form, exists := syntheticStore.forms[formID]
	if !exists {
		return nil, errors.New("synthetic-form-not-found")
	}
	return form, nil
}

// ListSyntheticForms returns all generated synthetic forms
func ListSyntheticForms(formType string) ([]*SyntheticFormResponse, error) {
	syntheticStore.mu.RLock()
	defer syntheticStore.mu.RUnlock()
	var results []*SyntheticFormResponse
	for _, form := range syntheticStore.forms {
		if formType == "" || form.FormType == formType {
			results = append(results, form)
		}
	}
	return results, nil
}

// ValidateSyntheticForm validates that a form is properly synthetic
func ValidateSyntheticForm(formID string) error {
	if formID == "" {
		return errors.New("synthetic-form-id-empty")
	}
	syntheticStore.mu.RLock()
	defer syntheticStore.mu.RUnlock()
	form, exists := syntheticStore.forms[formID]
	if !exists {
		return errors.New("synthetic-form-not-found")
	}
	if !form.Synthetic {
		return errors.New("synthetic-form-not-synthetic")
	}
	checksumData := fmt.Sprintf("%s|%s|%s|%v", form.FormID, form.FormType, form.Version, form.Fields)
	hash := sha256.Sum256([]byte(checksumData))
	expectedChecksum := hex.EncodeToString(hash[:])
	if form.Checksum != expectedChecksum {
		return errors.New("synthetic-form-checksum-mismatch")
	}
	return nil
}

// DeleteSyntheticForm removes a synthetic form from the store
func DeleteSyntheticForm(formID string) error {
	if formID == "" {
		return errors.New("synthetic-form-id-empty")
	}
	syntheticStore.mu.Lock()
	defer syntheticStore.mu.Unlock()
	if _, exists := syntheticStore.forms[formID]; !exists {
		return errors.New("synthetic-form-not-found")
	}
	delete(syntheticStore.forms, formID)
	for key, id := range syntheticStore.idem {
		if id == formID {
			delete(syntheticStore.idem, key)
			break
		}
	}
	return nil
}

// CleanupSyntheticForms removes all synthetic forms from the store
func CleanupSyntheticForms() error {
	syntheticStore.mu.Lock()
	defer syntheticStore.mu.Unlock()
	syntheticStore.forms = make(map[string]*SyntheticFormResponse)
	syntheticStore.idem = make(map[string]string)
	return nil
}
