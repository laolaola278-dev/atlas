// Package hitl checks review credentials before a write can be committed.
//
// An emergency grant is never an approval proof. This workspace has no Go
// toolchain, so this file has not been compiled here.
package hitl

import "errors"

type reviewCommand struct {
	SuggestionID string
	Decision     string
	ReviewerID   string
}

func (command reviewCommand) validate() error {
	if command.SuggestionID == "" || command.Decision == "" {
		return errors.New("review-draft-missing")
	}
	if command.ReviewerID == "" || command.ReviewerID == "system" {
		return errors.New("approval-missing")
	}
	return nil
}

type approvalProof struct {
	ProofID    string
	ReviewerID string
	Digest     string
}

func (proof approvalProof) validate() error {
	if proof.ProofID == "" || proof.ReviewerID == "" {
		return errors.New("approval-missing")
	}
	if len(proof.Digest) != 64 {
		return errors.New("write-digest-invalid")
	}
	return nil
}

type emergencyGrant struct {
	GrantID string
}

func (grant emergencyGrant) asApproval() error {
	if grant.GrantID == "" {
		return errors.New("approval-missing")
	}
	return errors.New("emergency-grant-not-approval")
}
