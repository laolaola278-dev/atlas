// Package contract evaluates one access request and fails closed.
//
// Missing scope, an unknown reason, or a direct identifier denies the
// request. Emergency access still needs its own reason. This workspace has
// no Go toolchain, so this file has not been compiled here.
package contract

// Decision is the fail-closed result of one access request.
type Decision struct {
	Allowed bool
	Reasons []string
}

var policyVersions = map[string]struct{}{
	"1.0":   {},
	"1.0.0": {},
	"1.1":   {},
	"1.1.0": {},
}

// Decide denies any request that is incomplete or identifies a patient.
func Decide(fields map[string]string, emergency bool, granted []string) Decision {
	reasons := make([]string, 0, 4)
	if fields["tenant_id"] == "" || fields["campus_id"] == "" {
		reasons = append(reasons, "scope-missing")
	}
	if fields["purpose_code"] == "" || fields["action"] == "" {
		reasons = append(reasons, "purpose-missing")
	}
	if _, known := policyVersions[fields["policy_version"]]; !known {
		reasons = append(reasons, "policy-version-incompatible")
	}
	if fields["why_code"] == "" || fields["why_code"] == "unknown" || fields["why_code"] == "unspecified" {
		reasons = append(reasons, "actor-why-missing")
	}
	scoped := []string{
		fields["tenant_id"], fields["campus_id"], fields["purpose_code"],
		fields["action"], fields["actor_id"], fields["why_code"],
	}
	for _, value := range scoped {
		if hasDirectIdentifier(value) {
			reasons = append(reasons, "policy-identifier-forbidden")
			break
		}
	}
	if emergency && !contains(granted, "emergency-reason") {
		reasons = append(reasons, "emergency-reason-missing")
	}
	if fields["consent_state"] != "" && fields["consent_state"] != "active" && !emergency {
		reasons = append(reasons, "consent-not-active")
	}
	if len(reasons) > 0 {
		return Decision{Allowed: false, Reasons: reasons}
	}
	return Decision{Allowed: true, Reasons: []string{"allowed"}}
}

func contains(values []string, wanted string) bool {
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}
