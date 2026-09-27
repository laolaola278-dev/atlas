package contract

import "testing"

func TestReadyAcceptsSyntheticDraft(t *testing.T) {
	draft := Draft{
		SuggestionID:    "suggestion-synthetic",
		PatientRef:      "Patient/synthetic",
		Action:          "review-order",
		ContentDigest:   strings64(),
		ContractVersion: "1.0",
	}
	if err := Ready(draft); err != nil {
		t.Fatalf("synthetic draft rejected: %v", err)
	}
}

func TestReadyRejectsShortDigest(t *testing.T) {
	draft := Draft{
		SuggestionID:    "suggestion-synthetic",
		PatientRef:      "Patient/synthetic",
		Action:          "review-order",
		ContentDigest:   "short",
		ContractVersion: "1.0",
	}
	if err := Ready(draft); err == nil || err.Error() != "suggestion-digest-invalid" {
		t.Fatalf("short digest accepted: %v", err)
	}
}

func TestReadyRejectsIdentifierPath(t *testing.T) {
	draft := Draft{
		SuggestionID:    "suggestion-synthetic",
		PatientRef:      "subject.identifier",
		Action:          "review-order",
		ContentDigest:   strings64(),
		ContractVersion: "1.1",
	}
	if err := Ready(draft); err == nil || err.Error() != "suggestion-identifier-forbidden" {
		t.Fatalf("identifier path accepted: %v", err)
	}
}

func strings64() string {
	return "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
}
