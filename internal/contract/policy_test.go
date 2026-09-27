package contract

import "testing"

func TestDecideAllowsScopedTreatment(t *testing.T) {
	decision := Decide(map[string]string{
		"action":         "review",
		"actor_id":       "reviewer-synthetic",
		"campus_id":      "campus-synthetic",
		"consent_state":  "active",
		"policy_version": "1.0.0",
		"purpose_code":   "treatment",
		"tenant_id":      "tenant-synthetic",
		"why_code":       "treatment-review",
	}, false, nil)
	if !decision.Allowed || decision.Reasons[0] != "allowed" {
		t.Fatalf("scoped request denied: %+v", decision)
	}
}

func TestDecideRejectsUnknownReason(t *testing.T) {
	decision := Decide(map[string]string{
		"action":         "review",
		"campus_id":      "campus-synthetic",
		"policy_version": "1.0.0",
		"purpose_code":   "treatment",
		"tenant_id":      "tenant-synthetic",
		"why_code":       "unknown",
	}, false, nil)
	if decision.Allowed || !hasReason(decision.Reasons, "actor-why-missing") {
		t.Fatalf("unknown reason accepted: %+v", decision)
	}
}

func TestDecideRejectsEmergencyWithoutReason(t *testing.T) {
	decision := Decide(map[string]string{
		"action":         "break-glass",
		"campus_id":      "campus-synthetic",
		"policy_version": "1.1.0",
		"purpose_code":   "treatment",
		"tenant_id":      "tenant-synthetic",
		"why_code":       "treatment-review",
	}, true, []string{"status"})
	if decision.Allowed || !hasReason(decision.Reasons, "emergency-reason-missing") {
		t.Fatalf("emergency without reason accepted: %+v", decision)
	}
}

func hasReason(reasons []string, wanted string) bool {
	for _, reason := range reasons {
		if reason == wanted {
			return true
		}
	}
	return false
}
