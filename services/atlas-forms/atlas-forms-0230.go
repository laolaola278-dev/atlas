package forms

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"
	"time"
)

type AttachmentRequest struct {
	FormID         string
	SubmissionID   string
	AttachmentID   string
	Filename       string
	MimeType       string
	SizeBytes      int64
	Checksum       string
	ActorID        string
	IdempotencyKey string
	Synthetic      bool
}

type AttachmentResponse struct {
	ValidationID     string
	AttachmentID     string
	Status           string
	ValidationErrors []string
	ValidatedAt      string
}

type AttachmentValidation struct {
	ValidationID string
	AttachmentID string
	FormID       string
	Status       string
	Errors       []string
	ValidatedAt  time.Time
}

var (
	attachmentStore       = make(map[string]*AttachmentValidation)
	attachmentIdempotency = make(map[string]string)
	allowedMimeTypes      = map[string]bool{
		"application/pdf":  true,
		"image/jpeg":       true,
		"image/png":        true,
		"text/plain":       true,
		"application/json": true,
	}
	maxFileSizeBytes int64 = 10 * 1024 * 1024 // 10MB
)

func ValidateAttachmentRequest(req *AttachmentRequest) error {
	if req.FormID == "" {
		return fmt.Errorf("form_id required")
	}
	if req.SubmissionID == "" {
		return fmt.Errorf("submission_id required")
	}
	if req.AttachmentID == "" {
		return fmt.Errorf("attachment_id required")
	}
	if req.Filename == "" {
		return fmt.Errorf("filename required")
	}
	if req.MimeType == "" {
		return fmt.Errorf("mime_type required")
	}
	if req.SizeBytes <= 0 {
		return fmt.Errorf("size_bytes must be positive")
	}
	if req.Checksum == "" {
		return fmt.Errorf("checksum required")
	}
	if len(req.Checksum) != 64 {
		return fmt.Errorf("checksum must be 64 hex characters")
	}
	if req.ActorID == "" {
		return fmt.Errorf("actor_id required")
	}
	if req.IdempotencyKey == "" {
		return fmt.Errorf("idempotency_key required")
	}
	return nil
}

func ValidateMimeType(mimeType string) error {
	if !allowedMimeTypes[mimeType] {
		return fmt.Errorf("mime_type not in whitelist")
	}
	return nil
}

func ValidateFileSize(sizeBytes int64) error {
	if sizeBytes > maxFileSizeBytes {
		return fmt.Errorf("file size exceeds maximum")
	}
	return nil
}

func ValidateChecksum(checksum string) error {
	if len(checksum) != 64 {
		return fmt.Errorf("invalid checksum length")
	}
	for _, c := range checksum {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')) {
			return fmt.Errorf("checksum must be hexadecimal")
		}
	}
	return nil
}

func ValidateFilename(filename string) error {
	if strings.Contains(filename, "..") {
		return fmt.Errorf("filename contains path traversal")
	}
	if strings.HasPrefix(filename, "/") || strings.HasPrefix(filename, "\\") {
		return fmt.Errorf("filename must be relative")
	}
	dangerousExtensions := []string{".exe", ".bat", ".sh", ".ps1", ".cmd"}
	lowerFilename := strings.ToLower(filename)
	for _, ext := range dangerousExtensions {
		if strings.HasSuffix(lowerFilename, ext) {
			return fmt.Errorf("dangerous file extension")
		}
	}
	return nil
}

func CheckValidationHumanAdoptionBoundary(req *AttachmentRequest) error {
	if !req.Synthetic {
		return fmt.Errorf("attachment-synthetic-only")
	}
	return nil
}

func GenerateAttachmentValidationID(attachmentID string) string {
	hash := sha256.Sum256([]byte(fmt.Sprintf("validation-%s-%d", attachmentID, time.Now().UnixNano())))
	return "VAL-" + hex.EncodeToString(hash[:])[:16]
}

func CheckAttachmentIdempotency(key string) (string, bool) {
	validationID, exists := attachmentIdempotency[key]
	return validationID, exists
}

func ValidateAttachment(req *AttachmentRequest) (*AttachmentResponse, error) {
	if err := CheckValidationHumanAdoptionBoundary(req); err != nil {
		return nil, err
	}

	if validationID, exists := CheckAttachmentIdempotency(req.IdempotencyKey); exists {
		if validation, ok := attachmentStore[validationID]; ok {
			return &AttachmentResponse{
				ValidationID:     validation.ValidationID,
				AttachmentID:     validation.AttachmentID,
				Status:           validation.Status,
				ValidationErrors: validation.Errors,
				ValidatedAt:      validation.ValidatedAt.Format(time.RFC3339),
			}, nil
		}
	}

	if err := ValidateAttachmentRequest(req); err != nil {
		return nil, err
	}

	var validationErrors []string

	if err := ValidateMimeType(req.MimeType); err != nil {
		validationErrors = append(validationErrors, err.Error())
	}

	if err := ValidateFileSize(req.SizeBytes); err != nil {
		validationErrors = append(validationErrors, err.Error())
	}

	if err := ValidateChecksum(req.Checksum); err != nil {
		validationErrors = append(validationErrors, err.Error())
	}

	if err := ValidateFilename(req.Filename); err != nil {
		validationErrors = append(validationErrors, err.Error())
	}

	status := "valid"
	if len(validationErrors) > 0 {
		status = "invalid"
	}

	validationID := GenerateAttachmentValidationID(req.AttachmentID)
	now := time.Now()

	validation := &AttachmentValidation{
		ValidationID: validationID,
		AttachmentID: req.AttachmentID,
		FormID:       req.FormID,
		Status:       status,
		Errors:       validationErrors,
		ValidatedAt:  now,
	}

	attachmentStore[validationID] = validation
	attachmentIdempotency[req.IdempotencyKey] = validationID

	return &AttachmentResponse{
		ValidationID:     validationID,
		AttachmentID:     req.AttachmentID,
		Status:           status,
		ValidationErrors: validationErrors,
		ValidatedAt:      now.Format(time.RFC3339),
	}, nil
}

func RetrieveAttachmentValidation(validationID string) (*AttachmentResponse, error) {
	validation, exists := attachmentStore[validationID]
	if !exists {
		return nil, fmt.Errorf("attachment-not-found")
	}

	return &AttachmentResponse{
		ValidationID:     validation.ValidationID,
		AttachmentID:     validation.AttachmentID,
		Status:           validation.Status,
		ValidationErrors: validation.Errors,
		ValidatedAt:      validation.ValidatedAt.Format(time.RFC3339),
	}, nil
}
