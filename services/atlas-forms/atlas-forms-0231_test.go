package forms

import (
	"testing"
)

func TestValidateDraftRecoveryRequest(t *testing.T) {
	tests := []struct {
		name    string
		req     DraftRecoveryRequest
		wantErr bool
		errMsg  string
	}{
		{
			name: "valid save request",
			req: DraftRecoveryRequest{
				FormID:         "#FORM-001",
				UserID:         "#USER-001",
				Operation:      "save",
				DraftData:      map[string]string{"#field1": "value1"},
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-001",
				Synthetic:      true,
				Reason:         "test save",
			},
			wantErr: false,
		},
		{
			name: "missing form_id",
			req: DraftRecoveryRequest{
				UserID:         "#USER-001",
				Operation:      "save",
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-002",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "draft-invalid: form_id is required",
		},
		{
			name: "non-synthetic",
			req: DraftRecoveryRequest{
				FormID:         "#FORM-001",
				UserID:         "#USER-001",
				Operation:      "save",
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-003",
				Synthetic:      false,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "draft-synthetic-only: synthetic must be true for test data",
		},
		{
			name: "invalid operation",
			req: DraftRecoveryRequest{
				FormID:         "#FORM-001",
				UserID:         "#USER-001",
				Operation:      "invalid",
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-004",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "draft-operation-invalid: operation must be save, recover, or discard",
		},
		{
			name: "save without draft_data",
			req: DraftRecoveryRequest{
				FormID:         "#FORM-001",
				UserID:         "#USER-001",
				Operation:      "save",
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-005",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "draft-invalid: draft_data is required for save operation",
		},
		{
			name: "recover without draft_id",
			req: DraftRecoveryRequest{
				FormID:         "#FORM-001",
				UserID:         "#USER-001",
				Operation:      "recover",
				ActorID:        "#ACTOR-001",
				IdempotencyKey: "key-006",
				Synthetic:      true,
				Reason:         "test",
			},
			wantErr: true,
			errMsg:  "draft-invalid: draft_id is required for recover operation",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateDraftRecoveryRequest(tt.req)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateDraftRecoveryRequest() error = %v, wantErr %v", err, tt.wantErr)
				return
			}
			if err != nil && err.Error() != tt.errMsg {
				t.Errorf("ValidateDraftRecoveryRequest() error = %v, want %v", err.Error(), tt.errMsg)
			}
		})
	}
}

func TestValidateDraftID(t *testing.T) {
	tests := []struct {
		name    string
		draftID string
		wantErr bool
		errMsg  string
	}{
		{
			name:    "valid draft_id",
			draftID: "DRAFT-1234567890ABCDEF",
			wantErr: false,
		},
		{
			name:    "empty draft_id",
			draftID: "",
			wantErr: true,
			errMsg:  "draft-invalid: draft_id is required",
		},
		{
			name:    "invalid format",
			draftID: "INVALID-ID",
			wantErr: true,
			errMsg:  "draft-id-invalid: draft_id must match pattern DRAFT-[A-Z0-9]{16}",
		},
		{
			name:    "too short",
			draftID: "DRAFT-123",
			wantErr: true,
			errMsg:  "draft-id-invalid: draft_id must match pattern DRAFT-[A-Z0-9]{16}",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			result := ValidateDraftID(tc.draftID)
			if tc.wantErr {
				if result == nil {
					t.Errorf("ValidateDraftID() expected error but got nil")
				} else if result.Error() != tc.errMsg {
					t.Errorf("ValidateDraftID() error = %v, want %v", result.Error(), tc.errMsg)
				}
			} else if result != nil {
				t.Errorf("ValidateDraftID() unexpected error = %v", result)
			}
		})
	}
}

func TestValidateDraftData(t *testing.T) {
	tests := []struct {
		name      string
		draftData map[string]string
		wantErr   bool
		errMsg    string
	}{
		{
			name:      "valid draft_data",
			draftData: map[string]string{"#field1": "value1", "#field2": "value2"},
			wantErr:   false,
		},
		{
			name:      "empty draft_data",
			draftData: map[string]string{},
			wantErr:   true,
			errMsg:    "draft-data-empty: draft_data cannot be empty",
		},
		{
			name:      "prohibited key name",
			draftData: map[string]string{"name": "value"},
			wantErr:   true,
			errMsg:    "draft-data-invalid: prohibited key 'name' found",
		},
		{
			name:      "prohibited PHI key rejection",
			draftData: map[string]string{"patient_id": "12345"},
			wantErr:   true,
			errMsg:    "draft-data-invalid: prohibited key 'patient_id' found",
		},
	}

	for i, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			validationErr := ValidateDraftData(test.draftData)
			hasError := validationErr != nil
			if hasError != test.wantErr {
				t.Errorf("Test case %d: ValidateDraftData() error = %v, wantErr %v", i, validationErr, test.wantErr)
				return
			}
			if hasError && validationErr.Error() != test.errMsg {
				t.Errorf("Test case %d: ValidateDraftData() error message = %q, want %q", i, validationErr.Error(), test.errMsg)
			}
		})
	}
}

func TestCalculateDraftChecksum(t *testing.T) {
	tests := []struct {
		name      string
		draftData map[string]string
		wantErr   bool
	}{
		{
			name:      "valid checksum calculation",
			draftData: map[string]string{"#field1": "value1"},
			wantErr:   false,
		},
		{
			name:      "empty data",
			draftData: map[string]string{},
			wantErr:   false,
		},
	}

	for idx := range tests {
		testCase := tests[idx]
		t.Run(testCase.name, func(t *testing.T) {
			checksum, err := CalculateDraftChecksum(testCase.draftData)
			if testCase.wantErr && err == nil {
				t.Errorf("CalculateDraftChecksum() expected error but got nil")
			}
			if !testCase.wantErr && err != nil {
				t.Errorf("CalculateDraftChecksum() unexpected error = %v", err)
			}
			if !testCase.wantErr && len(checksum) != 64 {
				t.Errorf("CalculateDraftChecksum() checksum length = %d, want 64", len(checksum))
			}
		})
	}
}

func TestGenerateDraftID(t *testing.T) {
	formID := "#FORM-001"
	userID := "#USER-001"
	
	id1 := GenerateDraftID(formID, userID)
	
	if len(id1) != 22 {
		t.Errorf("GenerateDraftID() length = %d, want 22", len(id1))
	}
	
	if id1[:6] != "DRAFT-" {
		t.Errorf("GenerateDraftID() prefix = %s, want DRAFT-", id1[:6])
	}
	
	// Test that different inputs produce different IDs
	id2 := GenerateDraftID("#FORM-002", userID)
	if id1 == id2 {
		t.Errorf("GenerateDraftID() generated identical IDs for different forms: %s", id1)
	}
	
	id3 := GenerateDraftID(formID, "#USER-002")
	if id1 == id3 {
		t.Errorf("GenerateDraftID() generated identical IDs for different users: %s", id1)
	}
}

func TestSaveDraft(t *testing.T) {
	draftStore = make(map[string]DraftEntry)
	draftIdempotency = make(map[string]string)
	
	req := DraftRecoveryRequest{
		FormID:         "#FORM-001",
		UserID:         "#USER-001",
		Operation:      "save",
		DraftData:      map[string]string{"#field1": "value1", "#field2": "value2"},
		ActorID:        "#ACTOR-001",
		IdempotencyKey: "save-key-001",
		Synthetic:      true,
		Reason:         "test save",
	}
	
	resp, err := SaveDraft(req)
	if err != nil {
		t.Fatalf("SaveDraft() error = %v", err)
	}
	
	if resp.FormID != req.FormID {
		t.Errorf("SaveDraft() FormID = %v, want %v", resp.FormID, req.FormID)
	}
	
	if resp.Status != "active" {
		t.Errorf("SaveDraft() Status = %v, want active", resp.Status)
	}
	
	if len(resp.DataChecksum) != 64 {
		t.Errorf("SaveDraft() checksum length = %d, want 64", len(resp.DataChecksum))
	}
	
	resp2, err := SaveDraft(req)
	if err != nil {
		t.Fatalf("SaveDraft() idempotency error = %v", err)
	}
	
	if resp2.DraftID != resp.DraftID {
		t.Errorf("SaveDraft() idempotency failed: got %v, want %v", resp2.DraftID, resp.DraftID)
	}
}

func TestRecoverDraft(t *testing.T) {
	draftStore = make(map[string]DraftEntry)
	draftIdempotency = make(map[string]string)
	
	saveReq := DraftRecoveryRequest{
		FormID:         "#FORM-002",
		UserID:         "#USER-002",
		Operation:      "save",
		DraftData:      map[string]string{"#field1": "saved value"},
		ActorID:        "#ACTOR-002",
		IdempotencyKey: "save-key-002",
		Synthetic:      true,
		Reason:         "test save for recovery",
	}
	
	saveResp, err := SaveDraft(saveReq)
	if err != nil {
		t.Fatalf("SaveDraft() error = %v", err)
	}
	
	recoverReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-002",
		UserID:         "#USER-002",
		Operation:      "recover",
		ActorID:        "#ACTOR-002",
		IdempotencyKey: "recover-key-001",
		Synthetic:      true,
		Reason:         "test recovery",
	}
	
	recoverResp, err := RecoverDraft(recoverReq)
	if err != nil {
		t.Fatalf("RecoverDraft() error = %v", err)
	}
	
	if recoverResp.DraftID != saveResp.DraftID {
		t.Errorf("RecoverDraft() DraftID = %v, want %v", recoverResp.DraftID, saveResp.DraftID)
	}
	
	if recoverResp.Status != "recovered" {
		t.Errorf("RecoverDraft() Status = %v, want recovered", recoverResp.Status)
	}
	
	if recoverResp.DraftData["#field1"] != "saved value" {
		t.Errorf("RecoverDraft() data mismatch: got %v", recoverResp.DraftData)
	}
	
	nonExistReq := DraftRecoveryRequest{
		DraftID:        "DRAFT-NONEXISTENT123",
		FormID:         "#FORM-002",
		UserID:         "#USER-002",
		Operation:      "recover",
		ActorID:        "#ACTOR-002",
		IdempotencyKey: "recover-key-002",
		Synthetic:      true,
		Reason:         "test non-existent",
	}
	
	_, err = RecoverDraft(nonExistReq)
	if err == nil {
		t.Error("RecoverDraft() expected error for non-existent draft")
	}
}

func TestDiscardDraft(t *testing.T) {
	draftStore = make(map[string]DraftEntry)
	draftIdempotency = make(map[string]string)
	
	saveReq := DraftRecoveryRequest{
		FormID:         "#FORM-003",
		UserID:         "#USER-003",
		Operation:      "save",
		DraftData:      map[string]string{"#field1": "to be discarded"},
		ActorID:        "#ACTOR-003",
		IdempotencyKey: "save-key-003",
		Synthetic:      true,
		Reason:         "test save for discard",
	}
	
	saveResp, err := SaveDraft(saveReq)
	if err != nil {
		t.Fatalf("SaveDraft() error = %v", err)
	}
	
	discardReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-003",
		UserID:         "#USER-003",
		Operation:      "discard",
		ActorID:        "#ACTOR-003",
		IdempotencyKey: "discard-key-001",
		Synthetic:      true,
		Reason:         "test discard",
	}
	
	discardResp, err := DiscardDraft(discardReq)
	if err != nil {
		t.Fatalf("DiscardDraft() error = %v", err)
	}
	
	if discardResp.Status != "discarded" {
		t.Errorf("DiscardDraft() Status = %v, want discarded", discardResp.Status)
	}
	
	recoverReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-003",
		UserID:         "#USER-003",
		Operation:      "recover",
		ActorID:        "#ACTOR-003",
		IdempotencyKey: "recover-key-003",
		Synthetic:      true,
		Reason:         "test recovery of discarded",
	}
	
	_, err = RecoverDraft(recoverReq)
	if err == nil {
		t.Error("RecoverDraft() expected error for discarded draft")
	}
	if err.Error() != "draft-discarded: draft has been discarded" {
		t.Errorf("RecoverDraft() error = %v, want draft-discarded error", err)
	}
}

func TestProcessDraftRecovery(t *testing.T) {
	draftStore = make(map[string]DraftEntry)
	draftIdempotency = make(map[string]string)
	
	saveReq := DraftRecoveryRequest{
		FormID:         "#FORM-004",
		UserID:         "#USER-004",
		Operation:      "save",
		DraftData:      map[string]string{"#field1": "value1"},
		ActorID:        "#ACTOR-004",
		IdempotencyKey: "process-save-001",
		Synthetic:      true,
		Reason:         "test process save",
	}
	
	saveResp, err := ProcessDraftRecovery(saveReq)
	if err != nil {
		t.Fatalf("ProcessDraftRecovery(save) error = %v", err)
	}
	
	if saveResp.Status != "active" {
		t.Errorf("ProcessDraftRecovery(save) Status = %v, want active", saveResp.Status)
	}
	
	recoverReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-004",
		UserID:         "#USER-004",
		Operation:      "recover",
		ActorID:        "#ACTOR-004",
		IdempotencyKey: "process-recover-001",
		Synthetic:      true,
		Reason:         "test process recover",
	}
	
	recoverResp, err := ProcessDraftRecovery(recoverReq)
	if err != nil {
		t.Fatalf("ProcessDraftRecovery(recover) error = %v", err)
	}
	
	if recoverResp.Status != "recovered" {
		t.Errorf("ProcessDraftRecovery(recover) Status = %v, want recovered", recoverResp.Status)
	}
	
	invalidReq := DraftRecoveryRequest{
		FormID:         "#FORM-004",
		UserID:         "#USER-004",
		Operation:      "invalid",
		ActorID:        "#ACTOR-004",
		IdempotencyKey: "process-invalid-001",
		Synthetic:      true,
		Reason:         "test invalid",
	}
	
	_, err = ProcessDraftRecovery(invalidReq)
	if err == nil {
		t.Error("ProcessDraftRecovery(invalid) expected error")
	}
}

func TestDraftAccessControl(t *testing.T) {
	draftStore = make(map[string]DraftEntry)
	draftIdempotency = make(map[string]string)
	
	saveReq := DraftRecoveryRequest{
		FormID:         "#FORM-005",
		UserID:         "#USER-A",
		Operation:      "save",
		DraftData:      map[string]string{"#field1": "user A data"},
		ActorID:        "#ACTOR-A",
		IdempotencyKey: "access-save-001",
		Synthetic:      true,
		Reason:         "test access control",
	}
	
	saveResp, err := SaveDraft(saveReq)
	if err != nil {
		t.Fatalf("SaveDraft() error = %v", err)
	}
	
	recoverReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-005",
		UserID:         "#USER-B",
		Operation:      "recover",
		ActorID:        "#ACTOR-B",
		IdempotencyKey: "access-recover-001",
		Synthetic:      true,
		Reason:         "test unauthorized access",
	}
	
	_, err = RecoverDraft(recoverReq)
	if err == nil {
		t.Error("RecoverDraft() expected access denied error")
	}
	if err.Error() != "draft-access-denied: user does not own this draft" {
		t.Errorf("RecoverDraft() error = %v, want access denied", err)
	}
	
	discardReq := DraftRecoveryRequest{
		DraftID:        saveResp.DraftID,
		FormID:         "#FORM-005",
		UserID:         "#USER-B",
		Operation:      "discard",
		ActorID:        "#ACTOR-B",
		IdempotencyKey: "access-discard-001",
		Synthetic:      true,
		Reason:         "test unauthorized discard",
	}
	
	_, err = DiscardDraft(discardReq)
	if err == nil {
		t.Error("DiscardDraft() expected access denied error")
	}
	if err.Error() != "draft-access-denied: user does not own this draft" {
		t.Errorf("DiscardDraft() error = %v, want access denied", err)
	}
}
