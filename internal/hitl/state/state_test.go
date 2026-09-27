package state

import "testing"

func TestOrdinaryCommitAdvances(t *testing.T) {
	current := Suggestion{ID: "suggestion-synthetic", State: "WRITEBACK_PENDING", Version: 1}
	next, err := Move(current, "WRITEBACK_COMMITTED", false)
	if err != nil {
		t.Fatalf("commit rejected: %v", err)
	}
	if next.State != "WRITEBACK_COMMITTED" || next.Version != 2 {
		t.Fatalf("unexpected suggestion: %+v", next)
	}
	if current.State != "WRITEBACK_PENDING" {
		t.Fatal("failed transition mutated the caller value")
	}
}

func TestEmergencyCannotEnterOrdinaryCommit(t *testing.T) {
	current := Suggestion{ID: "suggestion-synthetic", State: "EMERGENCY_RECORDED", Version: 3}
	if _, err := Move(current, "WRITEBACK_COMMITTED", true); err == nil {
		t.Fatal("emergency entered the ordinary commit path")
	}
}

func TestUnknownTransitionIsRejected(t *testing.T) {
	current := Suggestion{ID: "suggestion-synthetic", State: "DRAFT", Version: 1}
	next, err := Move(current, "WRITEBACK_COMMITTED", false)
	if err == nil || next.State != current.State || next.Version != current.Version {
		t.Fatalf("unknown transition changed state: %+v %v", next, err)
	}
}
