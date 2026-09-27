package forms

import (
	"strings"
	"testing"
)

func TestValidateAttachmentRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     *AttachmentRequest
		wantErr bool
	}{
		{
			name: "valid request",
			req: &AttachmentRequest{
				FormID:         "form-synthetic-101",
				SubmissionID:   "sub-synthetic-202",
				AttachmentID:   "att-synthetic-303",
				Filename:       "document.pdf",
				MimeType:       "application/pdf",
				SizeBytes:      1024,
				Checksum:       "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
				ActorID:        "actor-synthetic-404",
				IdempotencyKey: "idem-synthetic-505",
				Synthetic:      true,
			},
			wantErr: false,
		},
		{
			name: "missing form_id",
			req: &AttachmentRequest{
				SubmissionID:   "sub-synthetic-202",
				AttachmentID:   "att-synthetic-303",
				Filename:       "document.pdf",
				MimeType:       "application/pdf",
				SizeBytes:      1024,
				Checksum:       "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
				ActorID:        "actor-synthetic-404",
				IdempotencyKey: "idem-synthetic-505",
			},
			wantErr: true,
		},
		{
			name: "invalid checksum length",
			req: &AttachmentRequest{
				FormID:         "form-synthetic-101",
				SubmissionID:   "sub-synthetic-202",
				AttachmentID:   "att-synthetic-303",
				Filename:       "document.pdf",
				MimeType:       "application/pdf",
				SizeBytes:      1024,
				Checksum:       "short",
				ActorID:        "actor-synthetic-404",
				IdempotencyKey: "idem-synthetic-505",
			},
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateAttachmentRequest(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateAttachmentRequest() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestValidateMimeType(t *testing.T) {
	tests := []struct {
		name     string
		mimeType string
		wantErr  bool
	}{
		{"allowed pdf", "application/pdf", false},
		{"allowed jpeg", "image/jpeg", false},
		{"allowed png", "image/png", false},
		{"allowed text", "text/plain", false},
		{"allowed json", "application/json", false},
		{"not allowed executable", "application/x-msdownload", true},
		{"not allowed script", "application/javascript", true},
	}

	testIdx := 0
	for testIdx < len(tests) {
		currentCase := tests[testIdx]
		t.Run(currentCase.name, func(t *testing.T) {
			validationResult := ValidateMimeType(currentCase.mimeType)
			shouldFail := currentCase.wantErr
			didFail := (validationResult != nil)

			if shouldFail && !didFail {
				t.Fatal("mime validation should have failed")
			}
			if !shouldFail && didFail {
				t.Fatalf("mime validation failed: %v", validationResult)
			}
		})
		testIdx++
	}
}

func TestValidateFileSize(t *testing.T) {
	tests := []struct {
		name      string
		sizeBytes int64
		wantErr   bool
	}{
		{"within limit 1KB", 1024, false},
		{"within limit 5MB", 5 * 1024 * 1024, false},
		{"at limit 10MB", 10 * 1024 * 1024, false},
		{"exceeds limit", 11 * 1024 * 1024, true},
		{"far exceeds limit", 100 * 1024 * 1024, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateFileSize(tt.sizeBytes)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateFileSize() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestValidateChecksum(t *testing.T) {
	validLower := "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
	validUpper := "A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2C3D4E5F6A1B2"
	validMixed := "aAbBcCdDeEfF00112233445566778899aAbBcCdDeEfF00112233445566778899"
	tooShort := "a1b2c3"
	nonHex := "g1h2i3j4k5l6m1n2o3p4q5r6s1t2u3v4w5x6y1z2a3b4c5d6e1f2a3b4c5d6e7f8"

	t.Run("valid lowercase hex", func(t *testing.T) {
		if ValidateChecksum(validLower) != nil {
			t.Error("lowercase hex checksum rejected")
		}
	})

	t.Run("valid uppercase hex", func(t *testing.T) {
		if ValidateChecksum(validUpper) != nil {
			t.Error("uppercase hex checksum rejected")
		}
	})

	t.Run("valid mixed case", func(t *testing.T) {
		if ValidateChecksum(validMixed) != nil {
			t.Error("mixed case hex checksum rejected")
		}
	})

	t.Run("too short", func(t *testing.T) {
		if ValidateChecksum(tooShort) == nil {
			t.Error("short checksum accepted incorrectly")
		}
	})

	t.Run("contains non-hex", func(t *testing.T) {
		if ValidateChecksum(nonHex) == nil {
			t.Error("non-hex checksum accepted incorrectly")
		}
	})
}

func TestValidateFilename(t *testing.T) {
	// Valid filenames
	validCases := map[string]string{
		"simple pdf":        "document.pdf",
		"with spaces":       "my document.pdf",
		"with subdirectory": "reports/annual.pdf",
	}

	for testName, filename := range validCases {
		t.Run(testName, func(t *testing.T) {
			if err := ValidateFilename(filename); err != nil {
				t.Errorf("valid filename %q rejected: %v", filename, err)
			}
		})
	}

	// Invalid filenames
	invalidCases := map[string]string{
		"path traversal dotdot": "../secret.pdf",
		"path traversal middle": "reports/../secret.pdf",
		"absolute unix":         "/etc/passwd",
		"absolute windows":      "\\Windows\\System32\\config",
		"executable extension":  "malware.exe",
		"batch file":            "script.bat",
		"shell script":          "install.sh",
		"powershell":            "deploy.ps1",
		"command file":          "setup.cmd",
	}

	for testName, filename := range invalidCases {
		t.Run(testName, func(t *testing.T) {
			if err := ValidateFilename(filename); err == nil {
				t.Errorf("dangerous filename %q accepted incorrectly", filename)
			}
		})
	}
}

func TestCheckValidationHumanAdoptionBoundary(t *testing.T) {
	tests := []struct {
		name      string
		synthetic bool
		wantErr   bool
	}{
		{"synthetic allowed", true, false},
		{"non-synthetic blocked", false, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := &AttachmentRequest{Synthetic: tt.synthetic}
			err := CheckValidationHumanAdoptionBoundary(req)
			if (err != nil) != tt.wantErr {
				t.Errorf("CheckValidationHumanAdoptionBoundary() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestGenerateAttachmentValidationID(t *testing.T) {
	id1 := GenerateAttachmentValidationID("att-synthetic-123")
	id2 := GenerateAttachmentValidationID("att-synthetic-456")

	if !strings.HasPrefix(id1, "VAL-") {
		t.Errorf("validation ID should start with VAL-, got %s", id1)
	}
	if id1 == id2 {
		t.Errorf("validation IDs should be unique, got %s and %s", id1, id2)
	}
	if len(id1) != 20 {
		t.Errorf("validation ID should be 20 characters, got %d", len(id1))
	}
}

func TestValidateAttachment(t *testing.T) {
	tests := []struct {
		name       string
		req        *AttachmentRequest
		wantStatus string
		wantErr    bool
	}{
		{
			name: "valid attachment",
			req: &AttachmentRequest{
				FormID:         "form-synthetic-701",
				SubmissionID:   "sub-synthetic-702",
				AttachmentID:   "att-synthetic-703",
				Filename:       "report.pdf",
				MimeType:       "application/pdf",
				SizeBytes:      2048,
				Checksum:       "def0123456789abcdef0123456789abcdef0123456789abcdef0123456789abc",
				ActorID:        "actor-synthetic-704",
				IdempotencyKey: "idem-synthetic-705",
				Synthetic:      true,
			},
			wantStatus: "valid",
			wantErr:    false,
		},
		{
			name: "invalid mime type",
			req: &AttachmentRequest{
				FormID:         "form-synthetic-801",
				SubmissionID:   "sub-synthetic-802",
				AttachmentID:   "att-synthetic-803",
				Filename:       "script.js",
				MimeType:       "application/javascript",
				SizeBytes:      512,
				Checksum:       "abc0123456789abcdef0123456789abcdef0123456789abcdef0123456789abc",
				ActorID:        "actor-synthetic-804",
				IdempotencyKey: "idem-synthetic-805",
				Synthetic:      true,
			},
			wantStatus: "invalid",
			wantErr:    false,
		},
		{
			name: "non-synthetic blocked",
			req: func() *AttachmentRequest {
				r := &AttachmentRequest{
					Synthetic: false,
				}
				r.FormID = "form-synthetic-901"
				r.SubmissionID = "sub-synthetic-902"
				r.AttachmentID = "att-synthetic-903"
				r.Filename = "data.json"
				r.MimeType = "application/json"
				r.SizeBytes = 256
				r.Checksum = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
				r.ActorID = "actor-synthetic-904"
				r.IdempotencyKey = "idem-synthetic-905"
				return r
			}(),
			wantErr: true,
		},
	}

	runTest := func(idx int) {
		testData := tests[idx]
		t.Run(testData.name, func(t *testing.T) {
			result, err := ValidateAttachment(testData.req)

			switch {
			case testData.wantErr && err == nil:
				t.Fatalf("[test %d] validation should have failed", idx)
			case testData.wantErr && err != nil:
				// Expected failure
				return
			case !testData.wantErr && err != nil:
				t.Fatalf("[test %d] validation failed: %v", idx, err)
			case !testData.wantErr && err == nil:
				// Success case - verify response
				if result.Status != testData.wantStatus {
					t.Errorf("[test %d] wrong status: got %s", idx, result.Status)
				}
			}
		})
	}

	for idx := 0; idx < len(tests); idx++ {
		runTest(idx)
	}
}

func TestValidateAttachmentIdempotency(t *testing.T) {
	req := new(AttachmentRequest)
	req.FormID = "form-synthetic-1001"
	req.SubmissionID = "sub-synthetic-1002"
	req.AttachmentID = "att-synthetic-1003"
	req.Filename = "idempotent.pdf"
	req.MimeType = "application/pdf"
	req.SizeBytes = 4096
	req.Checksum = "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
	req.ActorID = "actor-synthetic-1004"
	req.IdempotencyKey = "idem-unique-1005"
	req.Synthetic = true

	resp1, err1 := ValidateAttachment(req)
	if err1 != nil {
		t.Fatalf("first ValidateAttachment() failed: %v", err1)
	}

	resp2, err2 := ValidateAttachment(req)
	if err2 != nil {
		t.Fatalf("second ValidateAttachment() failed: %v", err2)
	}

	if resp1.ValidationID != resp2.ValidationID {
		t.Errorf("idempotent requests should return same validation ID, got %s and %s",
			resp1.ValidationID, resp2.ValidationID)
	}
}

func TestRetrieveAttachmentValidation(t *testing.T) {
	req := &AttachmentRequest{
		FormID:         "form-synthetic-1101",
		SubmissionID:   "sub-synthetic-1102",
		AttachmentID:   "att-synthetic-1103",
		Filename:       "retrieve.png",
		MimeType:       "image/png",
		SizeBytes:      8192,
		Checksum:       "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
		ActorID:        "actor-synthetic-1104",
		IdempotencyKey: "idem-synthetic-1105",
		Synthetic:      true,
	}

	created, err := ValidateAttachment(req)
	if err != nil {
		t.Fatalf("ValidateAttachment() failed: %v", err)
	}

	retrieved, err := RetrieveAttachmentValidation(created.ValidationID)
	if err != nil {
		t.Fatalf("RetrieveAttachmentValidation() failed: %v", err)
	}

	if retrieved.ValidationID != created.ValidationID {
		t.Errorf("retrieved validation ID = %v, want %v", retrieved.ValidationID, created.ValidationID)
	}
	if retrieved.AttachmentID != created.AttachmentID {
		t.Errorf("retrieved attachment ID = %v, want %v", retrieved.AttachmentID, created.AttachmentID)
	}
}

func TestRetrieveAttachmentValidationNotFound(t *testing.T) {
	_, err := RetrieveAttachmentValidation("VAL-nonexistent")
	if err == nil {
		t.Error("RetrieveAttachmentValidation() should fail for non-existent ID")
	}
	if !strings.Contains(err.Error(), "attachment-not-found") {
		t.Errorf("expected attachment-not-found error, got %v", err)
	}
}
