package contract

import "testing"

func TestCommitAdvancesWatermark(t *testing.T) {
	stream := NewWatermark()
	digest := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	begun, err := stream.Begin("write-synthetic", digest, "reviewer-synthetic", "treatment-review")
	if err != nil {
		t.Fatalf("begin failed: %v", err)
	}
	committed, err := stream.Commit(begun.Key)
	if err != nil || committed.State != "committed" || stream.Committed() != begun.Sequence {
		t.Fatalf("watermark did not advance: %+v %v", committed, err)
	}
}

func TestUnknownResultDoesNotAdvance(t *testing.T) {
	stream := NewWatermark()
	digest := "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
	begun, err := stream.Begin("write-unknown", digest, "reviewer-synthetic", "treatment-review")
	if err != nil {
		t.Fatalf("begin failed: %v", err)
	}
	if _, err = stream.Freeze(begun.Key); err != nil {
		t.Fatalf("freeze failed: %v", err)
	}
	if _, err = stream.Commit(begun.Key); err == nil || err.Error() != "transaction-result-unknown" {
		t.Fatalf("unknown result committed: %v", err)
	}
	if stream.Committed() != 0 {
		t.Fatalf("unknown result moved watermark to %d", stream.Committed())
	}
}

func TestChangedDigestConflicts(t *testing.T) {
	stream := NewWatermark()
	first := "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
	if _, err := stream.Begin("write-conflict", first, "reviewer-synthetic", "treatment-review"); err != nil {
		t.Fatalf("begin failed: %v", err)
	}
	second := "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
	_, err := stream.Begin("write-conflict", second, "reviewer-synthetic", "treatment-review")
	if err == nil || err.Error() != "transaction-conflict" {
		t.Fatalf("changed digest accepted: %v", err)
	}
}
