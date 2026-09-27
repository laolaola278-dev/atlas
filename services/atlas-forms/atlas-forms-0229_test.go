package forms

import (
	"testing"
	"time"
)

func TestValidateSignatureRequest(t *testing.T) {
	validReq := SignatureRequest{
		FormID:             "F001",
		SubmissionID:       "SUB001",
		SignerID:           "synthetic-signer-789",
		SignatureHash:      "abcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
		SignatureTimestamp: "2025-01-15T10:30:00Z",
		IdempotencyKey:     "idem-key-001",
		Synthetic:          true,
		Reason:             "Test signature validation",
	}

	err := ValidateSignatureRequest(validReq)
	if err != nil {
		t.Fatalf("Expected no error for valid request, got %v", err)
	}

	invalidReqs := []struct {
		name string
		req  SignatureRequest
		want string
	}{
		{
			name: "missing form ID",
			req: SignatureRequest{
				SubmissionID:       "SUB001",
				SignerID:           "synthetic-signer-789",
				SignatureHash:      "abcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
				SignatureTimestamp: "2025-01-15T10:30:00Z",
				IdempotencyKey:     "idem-key-002",
				Synthetic:          true,
				Reason:             "Test",
			},
			want: "signature-invalid",
		},
		{
			name: "short signature hash",
			req: SignatureRequest{
				FormID:             "F001",
				SubmissionID:       "SUB001",
				SignerID:           "synthetic-signer-789",
				SignatureHash:      "short",
				SignatureTimestamp: "2025-01-15T10:30:00Z",
				IdempotencyKey:     "idem-key-003",
				Synthetic:          true,
				Reason:             "Test",
			},
			want: "signature-format-invalid",
		},
		{
			name: "invalid timestamp format",
			req: SignatureRequest{
				FormID:             "F001",
				SubmissionID:       "SUB001",
				SignerID:           "synthetic-signer-789",
				SignatureHash:      "abcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
				SignatureTimestamp: "2025-01-15 10:30:00",
				IdempotencyKey:     "idem-key-004",
				Synthetic:          true,
				Reason:             "Test",
			},
			want: "signature-timestamp-invalid",
		},
	}

	for _, tc := range invalidReqs {
		t.Run(tc.name, func(t *testing.T) {
			err := ValidateSignatureRequest(tc.req)
			if err == nil {
				t.Fatal("Expected error, got nil")
			}
			if err.Error() != tc.want {
				t.Errorf("Expected error %q, got %q", tc.want, err.Error())
			}
		})
	}
}

func TestIsHex(t *testing.T) {
	tests := []struct {
		input string
		want  bool
	}{
		{"abcdef1234567890", true},
		{"ABCDEF1234567890", true},
		{"xyz123", false},
		{"12345g", false},
		{"", true},
	}

	for _, tc := range tests {
		result := isHex(tc.input)
		if result != tc.want {
			t.Errorf("isHex(%q) = %v, want %v", tc.input, result, tc.want)
		}
	}
}

func TestValidateSignatureIntegrity(t *testing.T) {
	validHash := "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
	err := ValidateSignatureIntegrity("SUB001", "synthetic-signer-789", validHash)
	if err != nil {
		t.Errorf("Expected no error for valid integrity check, got %v", err)
	}

	shortHash := "short"
	err = ValidateSignatureIntegrity("SUB001", "synthetic-signer-789", shortHash)
	if err == nil || err.Error() != "signature-format-invalid" {
		t.Errorf("Expected signature-format-invalid for short hash, got %v", err)
	}
}

func TestCheckSignatureHumanAdoptionBoundary(t *testing.T) {
	err := CheckSignatureHumanAdoptionBoundary(true)
	if err != nil {
		t.Errorf("Expected no error for synthetic=true, got %v", err)
	}

	err = CheckSignatureHumanAdoptionBoundary(false)
	if err == nil || err.Error() != "signature-synthetic-only" {
		t.Errorf("Expected signature-synthetic-only for synthetic=false, got %v", err)
	}
}

func TestGenerateSignatureID(t *testing.T) {
	id1 := GenerateSignatureID("SUB001", "synthetic-signer-123")
	id2 := GenerateSignatureID("SUB001", "synthetic-signer-123")

	if id1 == id2 {
		t.Error("Expected unique signature IDs for different timestamps")
	}

	if len(id1) != 36 {
		t.Errorf("Expected signature ID length 36 (SIG- + 32 hex), got %d", len(id1))
	}

	if id1[:4] != "SIG-" {
		t.Errorf("Expected signature ID to start with 'SIG-', got %q", id1[:4])
	}
}

func TestCheckSignatureIdempotency(t *testing.T) {
	signatureIdempotency = make(map[string]string)

	_, exists := CheckSignatureIdempotency("key-unknown")
	if exists {
		t.Error("Expected no match for unknown key")
	}

	signatureIdempotency["key-123"] = "SIG-abc"
	id, exists := CheckSignatureIdempotency("key-123")
	if !exists || id != "SIG-abc" {
		t.Errorf("Expected SIG-abc for key-123, got %q, exists=%v", id, exists)
	}
}

func TestCreateSignature(t *testing.T) {
	signatureStore = make(map[string]SignatureEntry)
	signatureIdempotency = make(map[string]string)

	req := SignatureRequest{
		FormID:             "F001",
		SubmissionID:       "SUB001",
		SignerID:           "synthetic-signer-456",
		SignatureHash:      "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
		SignatureTimestamp: "2025-01-15T11:00:00Z",
		IdempotencyKey:     "idem-create-001",
		Synthetic:          true,
		Reason:             "Create signature test",
	}

	resp, err := CreateSignature(req)
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if resp.Status != "signed" {
		t.Errorf("Expected status 'signed', got %q", resp.Status)
	}

	if resp.SubmissionID != "SUB001" {
		t.Errorf("Expected SubmissionID 'SUB001', got %q", resp.SubmissionID)
	}

	if len(resp.SignatureID) == 0 {
		t.Error("Expected non-empty SignatureID")
	}

	resp2, err2 := CreateSignature(req)
	if err2 != nil {
		t.Fatalf("Expected no error on duplicate request, got %v", err2)
	}

	if resp2.Status != "duplicate" {
		t.Errorf("Expected status 'duplicate' on second request, got %q", resp2.Status)
	}

	if resp2.SignatureID != resp.SignatureID {
		t.Errorf("Expected same SignatureID, got %q vs %q", resp2.SignatureID, resp.SignatureID)
	}
}

func TestCreateSignature_NonSynthetic(t *testing.T) {
	signatureStore = make(map[string]SignatureEntry)
	signatureIdempotency = make(map[string]string)

	req := SignatureRequest{
		FormID:             "F001",
		SubmissionID:       "SUB001",
		SignerID:           "synthetic-signer-789",
		SignatureHash:      "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
		SignatureTimestamp: "2025-01-15T11:00:00Z",
		IdempotencyKey:     "idem-non-synth-001",
		Synthetic:          false,
		Reason:             "Non-synthetic test",
	}

	_, err := CreateSignature(req)
	if err == nil || err.Error() != "signature-synthetic-only" {
		t.Errorf("Expected signature-synthetic-only for non-synthetic request, got %v", err)
	}
}

func TestRetrieveSignature(t *testing.T) {
	signatureStore = make(map[string]SignatureEntry)

	entry := SignatureEntry{
		SignatureID:   "SIG-retrieve-001",
		SubmissionID:  "SUB001",
		SignerID:      "synthetic-signer-321",
		SignatureHash: "abcd1234567890abcdef1234567890abcdef1234567890abcdef1234567890ab",
		SignedAt:      time.Now().UTC().Format(time.RFC3339),
		Synthetic:     true,
	}
	signatureStore["SIG-retrieve-001"] = entry

	retrieved, err := RetrieveSignature("SIG-retrieve-001")
	if err != nil {
		t.Fatalf("Expected no error, got %v", err)
	}

	if retrieved.SignatureID != "SIG-retrieve-001" {
		t.Errorf("Expected SignatureID 'SIG-retrieve-001', got %q", retrieved.SignatureID)
	}

	if retrieved.SignerID != "synthetic-signer-321" {
		t.Errorf("Expected SignerID 'synthetic-signer-321', got %q", retrieved.SignerID)
	}

	_, err = RetrieveSignature("SIG-unknown")
	if err == nil || err.Error() != "signature-not-found" {
		t.Errorf("Expected signature-not-found for unknown ID, got %v", err)
	}
}

func TestValidateSignerAuthorization(t *testing.T) {
	err := ValidateSignerAuthorization("synthetic-signer-111", "SUB001")
	if err != nil {
		t.Errorf("Expected no error for valid authorization, got %v", err)
	}

	err = ValidateSignerAuthorization("", "SUB001")
	if err == nil || err.Error() != "signature-unauthorized" {
		t.Errorf("Expected signature-unauthorized for empty signerID, got %v", err)
	}

	err = ValidateSignerAuthorization("SUB001", "SUB001")
	if err == nil || err.Error() != "signature-self-sign-forbidden" {
		t.Errorf("Expected signature-self-sign-forbidden for self-signing, got %v", err)
	}
}
