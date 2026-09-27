package forms

import (
	"testing"
	"time"
)

func TestValidateRevocationRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     *RevocationRequest
		wantErr string
	}{
		{
			name:    "nil request",
			req:     nil,
			wantErr: "revocation-request-nil",
		},
		{
			name: "non-synthetic rejected",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-001",
				Synthetic:      false,
			},
			wantErr: "revocation-synthetic-required",
		},
		{
			name: "invalid submission ID",
			req: &RevocationRequest{
				SubmissionID:   "INVALID",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-002",
				Synthetic:      true,
			},
			wantErr: "revocation-submission-id-invalid: must match SUB-[A-Z0-9]{16}, got 'INVALID'",
		},
		{
			name: "empty revoked-by",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-003",
				Synthetic:      true,
			},
			wantErr: "revocation-revoked-by-empty",
		},
		{
			name: "reason too short",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "short",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-004",
				Synthetic:      true,
			},
			wantErr: "revocation-reason-too-short",
		},
		{
			name: "zero timestamp",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Time{},
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-005",
				Synthetic:      true,
			},
			wantErr: "revocation-timestamp-invalid",
		},
		{
			name: "empty actor ID",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "",
				IdempotencyKey: "idem-rev-006",
				Synthetic:      true,
			},
			wantErr: "revocation-actor-required",
		},
		{
			name: "empty idempotency key",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "",
				Synthetic:      true,
			},
			wantErr: "revocation-idempotency-required",
		},
		{
			name: "prohibited metadata key rejected",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-007",
				Synthetic:      true,
				Metadata: map[string]interface{}{
					"birth_date": "1990-01-01",
				},
			},
			wantErr: "revocation-prohibited-field: field 'birth_date' is prohibited",
		},
		{
			name: "valid revocation request",
			req: &RevocationRequest{
				SubmissionID:   "SUB-ABCD1234EFGH5678",
				FormID:         "FORM-1234567890ABCDEF",
				RevokedBy:      "user-synthetic-789",
				Reason:         "Test revocation reason for validation",
				RevokedAt:      time.Now(),
				ActorID:        "actor-synthetic-456",
				IdempotencyKey: "idem-rev-008",
				Synthetic:      true,
			},
			wantErr: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRevocationRequest(tt.req)
			if tt.wantErr == "" {
				if err != nil {
					t.Errorf("expected no error, got %v", err)
				}
			} else {
				if err == nil {
					t.Errorf("expected error %q, got nil", tt.wantErr)
				} else if err.Error() != tt.wantErr {
					t.Errorf("expected error %q, got %q", tt.wantErr, err.Error())
				}
			}
		})
	}
}

func TestValidateRevocationReason(t *testing.T) {
	tests := []struct {
		name    string
		reason  string
		wantErr bool
	}{
		{"too short", "short", true},
		{"minimum length", "ten_chars_", false},
		{"normal length", "This is a valid revocation reason with sufficient detail", false},
		{"maximum length", string(make([]byte, 500)), false},
		{"too long", string(make([]byte, 501)), true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRevocationReason(tt.reason)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateRevocationReason() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestValidateRevocationID(t *testing.T) {
	tests := []struct {
		name    string
		id      string
		wantErr bool
	}{
		{"valid ID", "REV-ABCD1234EFGH5678", false},
		{"lowercase rejected", "REV-abcd1234efgh5678", true},
		{"wrong prefix", "RVC-ABCD1234EFGH5678", true},
		{"too short", "REV-ABCD123", true},
		{"too long", "REV-ABCD1234EFGH56789", true},
		{"empty string", "", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateRevocationID(tt.id)
			gotErr := err != nil
			if gotErr != tt.wantErr {
				t.Errorf("ValidateRevocationID() error = %v, wantErr %v", err, tt.wantErr)
			}
		})
	}
}

func TestGenerateRevocationID(t *testing.T) {
	submissionID := "SUB-ABCD1234EFGH5678"
	ts := time.Now()

	id1 := GenerateRevocationID(submissionID, ts)
	if err := ValidateRevocationID(id1); err != nil {
		t.Errorf("generated invalid ID: %v", err)
	}

	time.Sleep(1 * time.Millisecond)
	ts2 := time.Now()
	id2 := GenerateRevocationID(submissionID, ts2)
	if id1 == id2 {
		t.Error("expected different IDs for different timestamps")
	}

	id3 := GenerateRevocationID(submissionID, ts)
	if id1 != id3 {
		t.Error("expected same ID for same inputs")
	}
}

func TestRevokeSubmission(t *testing.T) {
	revocableSubmissionStore = make(map[string]*RevocableSubmissionEntry)
	revocationStore = make(map[string]*RevocationEntry)
	revocationIdempKeys = make(map[string]string)

	submissionID := "SUB-TEST1234ABCD5678"
	revocableSubmissionStore[submissionID] = &RevocableSubmissionEntry{
		SubmissionID: submissionID,
		FormID:       "FORM-1234567890ABCDEF",
		Status:       "submitted",
		SubmittedAt:  time.Now(),
	}

	req := &RevocationRequest{
		SubmissionID:   submissionID,
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-123",
		Reason:         "Revocation test reason with required length",
		RevokedAt:      time.Now(),
		ActorID:        "actor-synthetic-789",
		IdempotencyKey: "idem-revoke-test-001",
		Synthetic:      true,
	}

	resp, err := RevokeSubmission(req)
	if err != nil {
		t.Fatalf("RevokeSubmission() failed: %v", err)
	}

	if resp.Status != "revoked" {
		t.Errorf("expected status revoked, got %s", resp.Status)
	}

	if resp.PreviousStatus != "submitted" {
		t.Errorf("expected previous status submitted, got %s", resp.PreviousStatus)
	}

	if submission := revocableSubmissionStore[submissionID]; submission.Status != "revoked" {
		t.Errorf("submission status not updated to revoked")
	}
}

func TestRevokeSubmissionIdempotency(t *testing.T) {
	revocableSubmissionStore = make(map[string]*RevocableSubmissionEntry)
	revocationStore = make(map[string]*RevocationEntry)
	revocationIdempKeys = make(map[string]string)

	submissionID := "SUB-IDEMP1234ABC5678"
	revocableSubmissionStore[submissionID] = &RevocableSubmissionEntry{
		SubmissionID: submissionID,
		FormID:       "FORM-1234567890ABCDEF",
		Status:       "submitted",
		SubmittedAt:  time.Now(),
	}

	revokedAt := time.Now()
	req := &RevocationRequest{
		SubmissionID:   submissionID,
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-456",
		Reason:         "Idempotency test reason for revocation",
		RevokedAt:      revokedAt,
		ActorID:        "actor-synthetic-123",
		IdempotencyKey: "idem-revoke-idemp-002",
		Synthetic:      true,
	}

	resp1, err := RevokeSubmission(req)
	if err != nil {
		t.Fatalf("first RevokeSubmission() failed: %v", err)
	}

	resp2, err := RevokeSubmission(req)
	if err != nil {
		t.Fatalf("second RevokeSubmission() failed: %v", err)
	}

	if resp1.RevocationID != resp2.RevocationID {
		t.Error("idempotency broken: different revocation IDs returned")
	}
}

func TestRevokeSubmissionNotFound(t *testing.T) {
	revocableSubmissionStore = make(map[string]*RevocableSubmissionEntry)
	revocationStore = make(map[string]*RevocationEntry)
	revocationIdempKeys = make(map[string]string)

	req := &RevocationRequest{
		SubmissionID:   "SUB-NOTFOUND12345678",
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-999",
		Reason:         "Attempt to revoke non-existent submission",
		RevokedAt:      time.Now(),
		ActorID:        "actor-synthetic-888",
		IdempotencyKey: "idem-revoke-notfound-003",
		Synthetic:      true,
	}

	_, err := RevokeSubmission(req)
	if err == nil {
		t.Fatal("expected error for non-existent submission")
	}

	if err.Error() != "revocation-submission-not-found" {
		t.Errorf("expected revocation-submission-not-found, got %v", err)
	}
}

func TestRevokeSubmissionAlreadyRevoked(t *testing.T) {
	// Initialize stores using helper pattern
	revocableSubmissionStore, revocationStore, revocationIdempKeys = make(map[string]*RevocableSubmissionEntry), make(map[string]*RevocationEntry), make(map[string]string)

	submissionID := "SUB-ALREADYREV123456"
	revocableSubmissionStore[submissionID] = &RevocableSubmissionEntry{
		SubmissionID: submissionID,
		FormID:       "FORM-1234567890ABCDEF",
		Status:       "revoked",
		SubmittedAt:  time.Now(),
	}

	req := &RevocationRequest{
		SubmissionID:   submissionID,
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-777",
		Reason:         "Attempt to revoke already revoked submission",
		RevokedAt:      time.Now(),
		ActorID:        "actor-synthetic-666",
		IdempotencyKey: "idem-revoke-already-004",
		Synthetic:      true,
	}

	_, err := RevokeSubmission(req)
	if err == nil {
		t.Fatal("expected error for already revoked submission")
	}

	if err.Error() != "revocation-already-revoked" {
		t.Errorf("expected revocation-already-revoked, got %v", err)
	}
}

func TestRevokeSubmissionInvalidStatus(t *testing.T) {
	// Reset all stores in single line
	revocableSubmissionStore, revocationStore, revocationIdempKeys = map[string]*RevocableSubmissionEntry{}, map[string]*RevocationEntry{}, map[string]string{}

	submissionID := "SUB-INVALIDSTAT12345"
	revocableSubmissionStore[submissionID] = &RevocableSubmissionEntry{
		SubmissionID: submissionID,
		FormID:       "FORM-1234567890ABCDEF",
		Status:       "draft",
		SubmittedAt:  time.Now(),
	}

	req := &RevocationRequest{
		SubmissionID:   submissionID,
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-555",
		Reason:         "Attempt to revoke draft submission",
		RevokedAt:      time.Now(),
		ActorID:        "actor-synthetic-444",
		IdempotencyKey: "idem-revoke-invalid-005",
		Synthetic:      true,
	}

	_, err := RevokeSubmission(req)
	if err == nil {
		t.Fatal("expected error for invalid status")
	}

	if err.Error() != "revocation-status-invalid" {
		t.Errorf("expected revocation-status-invalid, got %v", err)
	}
}

func TestGetRevocation(t *testing.T) {
	revocationStore = make(map[string]*RevocationEntry)

	revocationID := "REV-GETTST1234ABCDEF"
	entry := &RevocationEntry{
		RevocationID: revocationID,
		SubmissionID: "SUB-ABCD1234EFGH5678",
		FormID:       "FORM-1234567890ABCDEF",
		RevokedBy:    "user-synthetic-333",
		Reason:       "Test entry for retrieval validation",
		RevokedAt:    time.Now(),
		Status:       "revoked",
	}
	revocationStore[revocationID] = entry

	retrieved, err := GetRevocation(revocationID)
	if err != nil {
		t.Fatalf("GetRevocation() failed: %v", err)
	}

	if retrieved.RevocationID != revocationID {
		t.Errorf("expected revocation ID %s, got %s", revocationID, retrieved.RevocationID)
	}

	_, err = GetRevocation("REV-NOTFOUND12345678")
	if err == nil {
		t.Error("expected error for non-existent revocation")
	}
}

func TestProcessRevocation(t *testing.T) {
	revocableSubmissionStore = make(map[string]*RevocableSubmissionEntry)
	revocationStore = make(map[string]*RevocationEntry)
	revocationIdempKeys = make(map[string]string)

	submissionID := "SUB-PROCES1234567890"
	revocableSubmissionStore[submissionID] = &RevocableSubmissionEntry{
		SubmissionID: submissionID,
		FormID:       "FORM-1234567890ABCDEF",
		Status:       "processed",
		SubmittedAt:  time.Now(),
	}

	timestamp := time.Now()
	req := &RevocationRequest{
		SubmissionID:   submissionID,
		FormID:         "FORM-1234567890ABCDEF",
		RevokedBy:      "user-synthetic-222",
		Reason:         "Complete workflow test for revocation",
		RevokedAt:      timestamp,
		ActorID:        "actor-synthetic-111",
		IdempotencyKey: "idem-process-revoke-006",
		Synthetic:      true,
	}

	resp, err := ProcessRevocation(req)
	if err != nil {
		t.Fatalf("ProcessRevocation() failed: %v", err)
	}

	if resp.Status != "revoked" {
		t.Errorf("expected status revoked, got %s", resp.Status)
	}

	if resp.PreviousStatus != "processed" {
		t.Errorf("expected previous status processed, got %s", resp.PreviousStatus)
	}
}
