package forms

import (
	"fmt"
	"testing"
	"time"
)

func TestValidateSubmissionRequest(t *testing.T) {
	validReq := &SubmissionRequest{
		FormID:          "FORM-001",
		UserID:          "USER-001",
		FormData:        map[string]interface{}{"field1": "value1"},
		Operation:       "submit",
		ActorID:         "ACTOR-001",
		IdempotencyKey:  "key-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-001",
	}

	if err := ValidateSubmissionRequest(validReq); err != nil {
		t.Errorf("Expected valid request, got error: %v", err)
	}

	invalidReq := &SubmissionRequest{
		FormID:          "FORM-001",
		UserID:          "USER-001",
		FormData:        map[string]interface{}{"name": "John"},
		Operation:       "submit",
		ActorID:         "ACTOR-001",
		IdempotencyKey:  "key-002",
		Synthetic:       true,
		SubmissionNonce: "nonce-002",
	}

	if err := ValidateSubmissionRequest(invalidReq); err == nil {
		t.Error("Expected error for prohibited field 'name', got nil")
	}
}

func TestValidateSubmissionID(t *testing.T) {
	validID := "SUB-A1B2C3D4E5F6G7H8"
	if err := ValidateSubmissionID(validID); err != nil {
		t.Errorf("Expected valid ID, got error: %v", err)
	}

	invalidID := "INVALID-ID"
	if err := ValidateSubmissionID(invalidID); err == nil {
		t.Error("Expected error for invalid ID format, got nil")
	}
}

func TestCalculateSubmissionChecksum(t *testing.T) {
	formData := map[string]interface{}{"field1": "value1"}
	checksum1, err := CalculateSubmissionChecksum("FORM-001", "USER-001", formData, "nonce-001")
	if err != nil {
		t.Fatalf("Checksum calculation failed: %v", err)
	}

	if len(checksum1) != 64 {
		t.Errorf("Expected 64-character checksum, got %d", len(checksum1))
	}

	checksum2, _ := CalculateSubmissionChecksum("FORM-001", "USER-001", formData, "nonce-001")
	if checksum1 != checksum2 {
		t.Error("Expected identical checksums for same input")
	}

	checksum3, _ := CalculateSubmissionChecksum("FORM-001", "USER-001", formData, "nonce-002")
	if checksum1 == checksum3 {
		t.Error("Expected different checksums for different nonces")
	}
}

func TestGenerateSubmissionID(t *testing.T) {
	timestamp := time.Now()
	id := GenerateSubmissionID("FORM-001", "USER-001", timestamp)

	if err := ValidateSubmissionID(id); err != nil {
		t.Errorf("Generated ID failed validation: %v", err)
	}

	id2 := GenerateSubmissionID("FORM-001", "USER-001", timestamp)
	if id != id2 {
		t.Error("Expected identical IDs for same inputs")
	}

	id3 := GenerateSubmissionID("FORM-002", "USER-001", timestamp)
	if id == id3 {
		t.Error("Expected different IDs for different form IDs")
	}
}

func TestSubmitForm(t *testing.T) {
	req := &SubmissionRequest{
		FormID:          "FORM-TEST-001",
		UserID:          "USER-TEST-001",
		FormData:        map[string]interface{}{"question1": "answer1"},
		Operation:       "submit",
		ActorID:         "ACTOR-TEST-001",
		IdempotencyKey:  "idem-test-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-test-001",
	}

	resp, err := SubmitForm(req)
	if err != nil {
		t.Fatalf("SubmitForm failed: %v", err)
	}

	if resp.Status != "submitted" {
		t.Errorf("Expected status 'submitted', got '%s'", resp.Status)
	}

	if resp.SubmissionID == "" {
		t.Error("Expected non-empty submission ID")
	}

	resp2, err := SubmitForm(req)
	if err != nil {
		t.Fatalf("Idempotent SubmitForm failed: %v", err)
	}

	if resp2.SubmissionID != resp.SubmissionID {
		t.Error("Expected same submission ID for idempotent request")
	}
}

func TestUpdateSubmission(t *testing.T) {
	submitReq := &SubmissionRequest{
		FormID:          "FORM-UPDATE-001",
		UserID:          "USER-UPDATE-001",
		FormData:        map[string]interface{}{"field1": "original"},
		Operation:       "submit",
		ActorID:         "ACTOR-UPDATE-001",
		IdempotencyKey:  "idem-update-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-update-001",
	}

	submitResp, err := SubmitForm(submitReq)
	if err != nil {
		t.Fatalf("SubmitForm failed: %v", err)
	}

	updateReq := &SubmissionRequest{
		SubmissionID:    submitResp.SubmissionID,
		FormID:          "FORM-UPDATE-001",
		UserID:          "USER-UPDATE-001",
		FormData:        map[string]interface{}{"field1": "updated"},
		Operation:       "update",
		ActorID:         "ACTOR-UPDATE-001",
		IdempotencyKey:  "idem-update-002",
		Synthetic:       true,
		SubmissionNonce: "nonce-update-002",
	}

	updateResp, err := UpdateSubmission(updateReq)
	if err != nil {
		t.Fatalf("UpdateSubmission failed: %v", err)
	}

	if updateResp.Checksum == submitResp.Checksum {
		t.Error("Expected different checksum after update")
	}
}

func TestWithdrawSubmission(t *testing.T) {
	submitReq := &SubmissionRequest{
		FormID:          "FORM-WITHDRAW-001",
		UserID:          "USER-WITHDRAW-001",
		FormData:        map[string]interface{}{"field1": "value1"},
		Operation:       "submit",
		ActorID:         "ACTOR-WITHDRAW-001",
		IdempotencyKey:  "idem-withdraw-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-withdraw-001",
	}

	submitResp, err := SubmitForm(submitReq)
	if err != nil {
		t.Fatalf("SubmitForm failed: %v", err)
	}

	withdrawResp, err := WithdrawSubmission(submitResp.SubmissionID, "USER-WITHDRAW-001")
	if err != nil {
		t.Fatalf("WithdrawSubmission failed: %v", err)
	}

	if withdrawResp.Status != "withdrawn" {
		t.Errorf("Expected status 'withdrawn', got '%s'", withdrawResp.Status)
	}

	withdrawResp2, err := WithdrawSubmission(submitResp.SubmissionID, "USER-WITHDRAW-001")
	if err != nil {
		t.Fatalf("Second WithdrawSubmission failed: %v", err)
	}

	if withdrawResp2.Status != "withdrawn" {
		t.Error("Expected idempotent withdrawal to maintain withdrawn status")
	}
}

func TestSubmissionAccessControl(t *testing.T) {
	submitReq := &SubmissionRequest{
		FormID:          "FORM-ACCESS-001",
		UserID:          "USER-OWNER",
		FormData:        map[string]interface{}{"field1": "value1"},
		Operation:       "submit",
		ActorID:         "ACTOR-ACCESS-001",
		IdempotencyKey:  "idem-access-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-access-001",
	}

	submitResp, err := SubmitForm(submitReq)
	if err != nil {
		t.Fatalf("SubmitForm failed: %v", err)
	}

	updateReq := &SubmissionRequest{
		SubmissionID:    submitResp.SubmissionID,
		FormID:          "FORM-ACCESS-001",
		UserID:          "USER-INTRUDER",
		FormData:        map[string]interface{}{"field1": "hacked"},
		Operation:       "update",
		ActorID:         "ACTOR-ACCESS-002",
		IdempotencyKey:  "idem-access-002",
		Synthetic:       true,
		SubmissionNonce: "nonce-access-002",
	}

	_, err = UpdateSubmission(updateReq)
	if err == nil {
		t.Error("Expected error when unauthorized user tries to update submission")
	}

	_, err = WithdrawSubmission(submitResp.SubmissionID, "USER-INTRUDER")
	if err == nil {
		t.Error("Expected error when unauthorized user tries to withdraw submission")
	}
}

func TestProcessSubmission(t *testing.T) {
	submitReq := &SubmissionRequest{
		FormID:          "FORM-PROCESS-001",
		UserID:          "USER-PROCESS-001",
		FormData:        map[string]interface{}{"field1": "value1"},
		Operation:       "submit",
		ActorID:         "ACTOR-PROCESS-001",
		IdempotencyKey:  "idem-process-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-process-001",
	}

	resp, err := ProcessSubmission(submitReq)
	if err != nil {
		t.Fatalf("ProcessSubmission (submit) failed: %v", err)
	}

	if resp.Status != "submitted" {
		t.Errorf("Expected status 'submitted', got '%s'", resp.Status)
	}

	updateReq := &SubmissionRequest{
		SubmissionID:    resp.SubmissionID,
		FormID:          "FORM-PROCESS-001",
		UserID:          "USER-PROCESS-001",
		FormData:        map[string]interface{}{"field1": "updated"},
		Operation:       "update",
		ActorID:         "ACTOR-PROCESS-001",
		IdempotencyKey:  "idem-process-002",
		Synthetic:       true,
		SubmissionNonce: "nonce-process-002",
	}

	_, err = ProcessSubmission(updateReq)
	if err != nil {
		t.Fatalf("ProcessSubmission (update) failed: %v", err)
	}

	withdrawReq := &SubmissionRequest{
		SubmissionID: resp.SubmissionID,
		UserID:       "USER-PROCESS-001",
		Operation:    "withdraw",
		ActorID:      "ACTOR-PROCESS-001",
		Synthetic:    true,
	}

	withdrawResp, err := ProcessSubmission(withdrawReq)
	if err != nil {
		t.Fatalf("ProcessSubmission (withdraw) failed: %v", err)
	}

	if withdrawResp.Status != "withdrawn" {
		t.Errorf("Expected status 'withdrawn', got '%s'", withdrawResp.Status)
	}
}

func TestSubmissionFieldLimit(t *testing.T) {
	largeFormData := make(map[string]interface{})
	for i := 0; i < 201; i++ {
		key := fmt.Sprintf("field_%d", i)
		largeFormData[key] = "value"
	}

	req := &SubmissionRequest{
		FormID:          "FORM-LIMIT-001",
		UserID:          "USER-LIMIT-001",
		FormData:        largeFormData,
		Operation:       "submit",
		ActorID:         "ACTOR-LIMIT-001",
		IdempotencyKey:  "idem-limit-001",
		Synthetic:       true,
		SubmissionNonce: "nonce-limit-001",
	}

	err := ValidateSubmissionRequest(req)
	if err == nil {
		t.Error("Expected error for exceeding field limit, got nil")
	}
}
