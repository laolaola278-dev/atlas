package hitl

import "testing"

func TestReviewCommandRequiresReviewer(t *testing.T) {
	command := reviewCommand{SuggestionID: "suggestion-synthetic", Decision: "approve"}
	if err := command.validate(); err == nil || err.Error() != "approval-missing" {
		t.Fatalf("missing reviewer accepted: %v", err)
	}
}

func TestApprovalProofRequiresDigest(t *testing.T) {
	proof := approvalProof{ProofID: "proof-synthetic", ReviewerID: "reviewer-synthetic", Digest: "short"}
	if err := proof.validate(); err == nil || err.Error() != "write-digest-invalid" {
		t.Fatalf("short proof digest accepted: %v", err)
	}
}

func TestEmergencyGrantIsNotApproval(t *testing.T) {
	grant := emergencyGrant{GrantID: "grant-synthetic"}
	if err := grant.asApproval(); err == nil || err.Error() != "emergency-grant-not-approval" {
		t.Fatalf("grant accepted as approval: %v", err)
	}
}
