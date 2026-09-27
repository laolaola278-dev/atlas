package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
	"time"
)

// PrintRenderRequest represents a request to render a form for printing
type PrintRenderRequest struct {
	RenderID       string                 `json:"render_id"`
	FormID         string                 `json:"form_id"`
	SubmissionID   string                 `json:"submission_id"`
	Template       string                 `json:"template"`
	Format         string                 `json:"format"`
	Options        map[string]interface{} `json:"options"`
	RenderedBy     string                 `json:"rendered_by"`
	RenderedAt     time.Time              `json:"rendered_at"`
	ActorID        string                 `json:"actor_id"`
	IdempotencyKey string                 `json:"idempotency_key"`
	Synthetic      bool                   `json:"synthetic"`
}

// PrintRenderResponse represents the response to a print render request
type PrintRenderResponse struct {
	RenderID     string                 `json:"render_id"`
	Status       string                 `json:"status"`
	OutputURL    string                 `json:"output_url"`
	Format       string                 `json:"format"`
	Size         int64                  `json:"size"`
	RenderedAt   time.Time              `json:"rendered_at"`
	ExpiresAt    time.Time              `json:"expires_at"`
	Metadata     map[string]interface{} `json:"metadata"`
	ErrorMessage string                 `json:"error_message,omitempty"`
}

// RenderEntry represents a stored render record
type RenderEntry struct {
	RenderID       string
	FormID         string
	SubmissionID   string
	Template       string
	Format         string
	Options        map[string]interface{}
	Status         string
	OutputURL      string
	Size           int64
	RenderedBy     string
	RenderedAt     time.Time
	ExpiresAt      time.Time
	ActorID        string
	IdempotencyKey string
	Checksum       string
	Metadata       map[string]interface{}
}

var (
	renderStore      = make(map[string]*RenderEntry)
	idempotencyStore = make(map[string]string)
	validFormats     = map[string]bool{"pdf": true, "html": true, "docx": true}
)

// ValidatePrintRenderRequest validates a print render request
func ValidatePrintRenderRequest(req *PrintRenderRequest) error {
	if req == nil {
		return errors.New("print-render-request-nil")
	}
	if !req.Synthetic {
		return errors.New("print-render-synthetic-required")
	}
	if req.FormID == "" {
		return errors.New("print-render-form-id-empty")
	}
	if req.SubmissionID == "" {
		return errors.New("print-render-submission-id-empty")
	}
	if req.Template == "" {
		return errors.New("print-render-template-empty")
	}
	if req.Format == "" {
		return errors.New("print-render-format-empty")
	}
	if err := ValidateRenderFormat(req.Format); err != nil {
		return err
	}
	if req.RenderedBy == "" {
		return errors.New("print-render-rendered-by-empty")
	}
	if req.ActorID == "" {
		return errors.New("print-render-actor-required")
	}
	if req.IdempotencyKey == "" {
		return errors.New("print-render-idempotency-required")
	}
	if req.Options != nil {
		if err := ValidateRenderOptions(req.Options); err != nil {
			return err
		}
	}
	return nil
}

// ValidateRenderFormat validates the render format
func ValidateRenderFormat(format string) error {
	if format == "" {
		return errors.New("print-render-format-empty")
	}
	format = strings.ToLower(format)
	if !validFormats[format] {
		return errors.New("print-render-format-invalid")
	}
	return nil
}

// ValidateRenderOptions validates render options for prohibited keys
func ValidateRenderOptions(options map[string]interface{}) error {
	if options == nil {
		return nil
	}
	prohibitedKeys := []string{
		"name", "identifier", "phone", "address",
		"birth_date", "patient_id", "ssn", "mrn",
	}
	for _, key := range prohibitedKeys {
		if _, exists := options[key]; exists {
			return fmt.Errorf("print-render-prohibited-key: %s", key)
		}
	}
	return nil
}

// ValidateRenderID validates a render ID format
func ValidateRenderID(renderID string) error {
	if renderID == "" {
		return errors.New("print-render-id-empty")
	}
	if !strings.HasPrefix(renderID, "RND-") {
		return errors.New("print-render-id-invalid-prefix")
	}
	if len(renderID) != 20 {
		return errors.New("print-render-id-invalid-length")
	}
	return nil
}

// CalculateRenderChecksum calculates a checksum for render data
func CalculateRenderChecksum(formID, submissionID, template, format string) string {
	data := fmt.Sprintf("%s:%s:%s:%s", formID, submissionID, template, format)
	hash := sha256.Sum256([]byte(data))
	return hex.EncodeToString(hash[:])
}

// GenerateRenderID generates a unique render ID
func GenerateRenderID(formID, submissionID string) string {
	timestamp := time.Now().UnixNano()
	data := fmt.Sprintf("%s:%s:%d", formID, submissionID, timestamp)
	hash := sha256.Sum256([]byte(data))
	encoded := strings.ToUpper(hex.EncodeToString(hash[:8]))
	return fmt.Sprintf("RND-%s", encoded)
}

// CheckRenderIdempotency checks if a render request is idempotent
func CheckRenderIdempotency(idempotencyKey string) (string, bool) {
	renderID, exists := idempotencyStore[idempotencyKey]
	return renderID, exists
}

// RenderForm renders a form for printing
func RenderForm(req *PrintRenderRequest) (*PrintRenderResponse, error) {
	if err := ValidatePrintRenderRequest(req); err != nil {
		return nil, err
	}
	if existingRenderID, exists := CheckRenderIdempotency(req.IdempotencyKey); exists {
		entry := renderStore[existingRenderID]
		return &PrintRenderResponse{
			RenderID:   entry.RenderID,
			Status:     entry.Status,
			OutputURL:  entry.OutputURL,
			Format:     entry.Format,
			Size:       entry.Size,
			RenderedAt: entry.RenderedAt,
			ExpiresAt:  entry.ExpiresAt,
			Metadata:   entry.Metadata,
		}, nil
	}
	renderID := GenerateRenderID(req.FormID, req.SubmissionID)
	if req.RenderID != "" {
		if err := ValidateRenderID(req.RenderID); err != nil {
			return nil, err
		}
		renderID = req.RenderID
	}
	checksum := CalculateRenderChecksum(req.FormID, req.SubmissionID, req.Template, req.Format)
	outputURL := fmt.Sprintf("https://example.invalid/renders/%s.%s", renderID, strings.ToLower(req.Format))
	expiresAt := time.Now().Add(24 * time.Hour)
	entry := &RenderEntry{
		RenderID:       renderID,
		FormID:         req.FormID,
		SubmissionID:   req.SubmissionID,
		Template:       req.Template,
		Format:         req.Format,
		Options:        req.Options,
		Status:         "rendered",
		OutputURL:      outputURL,
		Size:           1024,
		RenderedBy:     req.RenderedBy,
		RenderedAt:     time.Now(),
		ExpiresAt:      expiresAt,
		ActorID:        req.ActorID,
		IdempotencyKey: req.IdempotencyKey,
		Checksum:       checksum,
		Metadata:       make(map[string]interface{}),
	}
	renderStore[renderID] = entry
	idempotencyStore[req.IdempotencyKey] = renderID
	return &PrintRenderResponse{
		RenderID:   renderID,
		Status:     "rendered",
		OutputURL:  outputURL,
		Format:     req.Format,
		Size:       entry.Size,
		RenderedAt: entry.RenderedAt,
		ExpiresAt:  expiresAt,
		Metadata:   entry.Metadata,
	}, nil
}

// GetRender retrieves a render by ID
func GetRender(renderID string) (*PrintRenderResponse, error) {
	if err := ValidateRenderID(renderID); err != nil {
		return nil, err
	}
	entry, exists := renderStore[renderID]
	if !exists {
		return nil, errors.New("print-render-not-found")
	}
	return &PrintRenderResponse{
		RenderID:   entry.RenderID,
		Status:     entry.Status,
		OutputURL:  entry.OutputURL,
		Format:     entry.Format,
		Size:       entry.Size,
		RenderedAt: entry.RenderedAt,
		ExpiresAt:  entry.ExpiresAt,
		Metadata:   entry.Metadata,
	}, nil
}

// DeleteRender deletes a render
func DeleteRender(renderID, actorID string) error {
	if err := ValidateRenderID(renderID); err != nil {
		return err
	}
	entry, exists := renderStore[renderID]
	if !exists {
		return errors.New("print-render-not-found")
	}
	if entry.ActorID != actorID {
		return errors.New("print-render-unauthorized")
	}
	delete(renderStore, renderID)
	if entry.IdempotencyKey != "" {
		delete(idempotencyStore, entry.IdempotencyKey)
	}
	return nil
}

// ProcessPrintRender processes a print render request with full validation
func ProcessPrintRender(req *PrintRenderRequest) (*PrintRenderResponse, error) {
	if err := ValidatePrintRenderRequest(req); err != nil {
		return nil, fmt.Errorf("print-render-validation-failed: %w", err)
	}
	resp, err := RenderForm(req)
	if err != nil {
		return nil, fmt.Errorf("print-render-failed: %w", err)
	}
	return resp, nil
}
