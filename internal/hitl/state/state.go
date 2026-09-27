// Package state is the ordinary and emergency write-eligibility skeleton.
//
// An emergency grant can record one emergency fact, but it can never enter
// the ordinary approved or committed path. This workspace has no Go toolchain,
// so this file has not been compiled here.
package state

import "errors"

const ordinaryCommitted = "WRITEBACK_COMMITTED"

var errForbidden = errors.New("transition-forbidden")

var emergencyBlocked = map[string]struct{}{
	"APPROVED":           {},
	"WRITEBACK_PENDING":  {},
	ordinaryCommitted:    {},
}

var allowed = map[string]map[string]struct{}{
	"DRAFT":                         set("EVIDENCE_READY", "GENERATION_FAILED"),
	"PENDING_REVIEW":                set("APPROVED_ONE", "REJECTED", "EMERGENCY_OVERRIDE"),
	"APPROVED_ONE":                  set("SECOND_REVIEW_PENDING", "APPROVED"),
	"APPROVED":                      set("WRITEBACK_PENDING", "WITHDRAWN", "ROLLED_BACK"),
	"WRITEBACK_PENDING":             set(ordinaryCommitted, "WRITE_UNKNOWN", "WRITE_FAILED"),
	"EMERGENCY_OVERRIDE":            set("EMERGENCY_PENDING_CONFIRMATION", "CORRECTION_REQUIRED"),
	"EMERGENCY_PENDING_CONFIRMATION": set("EMERGENCY_RECORDED", "EMERGENCY_UNKNOWN"),
	"EMERGENCY_RECORDED":            set("POST_REVIEW_REQUIRED"),
	"POST_REVIEW_REQUIRED":          set("RECONCILIATION_CONFIRMED", "CORRECTION_REQUIRED"),
	"RECONCILIATION_CONFIRMED":      set("ARCHIVED"),
}

// Suggestion is one fail-closed safety projection.
type Suggestion struct {
	ID      string
	State   string
	Version int
}

func set(targets ...string) map[string]struct{} {
	result := make(map[string]struct{}, len(targets))
	for _, target := range targets {
		result[target] = struct{}{}
	}
	return result
}

// Move advances one state or rejects the transition without changing it.
func Move(current Suggestion, target string, emergency bool) (Suggestion, error) {
	if current.ID == "" || current.State == "" || target == "" {
		return current, errors.New("suggestion-context-incomplete")
	}
	next, ok := allowed[current.State]
	if !ok {
		return current, errForbidden
	}
	if _, ok = next[target]; !ok {
		return current, errForbidden
	}
	if emergency {
		if _, blocked := emergencyBlocked[target]; blocked {
			return current, errors.New("emergency-cannot-enter-ordinary-commit")
		}
	}
	current.State = target
	current.Version++
	return current, nil
}
